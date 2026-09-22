"""Tests for the mock ERP (services/mock_erp/).

Every endpoint, every error path, the one-write rule, the API key, the
seed data (deterministic, committed, consistent with the ticket
corpus, synthetic), and a real server started in the background the way
a Colab cell starts it - including a restart that proves the state is
reset and the data identical.

    python -m pytest tests/test_mock_erp.py -q
"""

import json
import re
import socket
import subprocess
import sys
import threading
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from services.mock_erp import launch, seed  # noqa: E402
from services.mock_erp import main as erp_main  # noqa: E402
from services.mock_erp.main import create_app  # noqa: E402
from services.mock_erp.models import WorkOrderCreate  # noqa: E402

import check_tickets  # noqa: E402
import ticket_phrases  # noqa: E402

DATA_DIR = REPO_ROOT / "services" / "mock_erp" / "data"
TICKETS = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"
TAG = re.compile(r"\b(?:HX|FV|P|K|V|C|E|T)-\d{4}[AB]?\b")

GOOD_BODY = {
    "equipment_tag": "P-1201A",
    "work_type": "corrective",
    "priority": 2,
    "title": "P-1201A abnormal noise, suspect seal",
    "description": "Control room reports P-1201A screen red and the pump sounds wrong.",
    "requested_by": "Control room operator, MRB",
    "approved_by": "Salim (maintenance planner, MRB)",
    "source_ticket": "INC-004412",
}


@pytest.fixture
def client():
    """A fresh ERP per test, no API key whatever the local .env says."""
    return TestClient(create_app(api_key=""))


def load(name):
    return json.loads((DATA_DIR / f"{name}.json").read_text(encoding="ascii"))


def assert_error_shape(reply, status, error):
    assert reply.status_code == status, reply.text
    body = reply.json()
    assert body["error"] == error
    assert isinstance(body["message"], str) and len(body["message"]) > 20
    return body


# ---------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["service"] == "mock-erp"
    assert body["auth"] == "off"
    assert body["counts"] == {"equipment": 86, "work_orders": 295, "maintenance_history": 258}
    assert body["work_orders_raised_since_start"] == 0
    assert re.fullmatch(r"[0-9a-f]{12}", body["data_fingerprint"])
    assert body["started"].endswith("+04:00")


def test_root_redirects_to_docs(client):
    reply = client.get("/", follow_redirects=False)
    assert reply.status_code == 307
    assert reply.headers["location"] == "/docs"
    assert client.get("/docs").status_code == 200


# ---------------------------------------------------------------------
# Equipment master
# ---------------------------------------------------------------------


def test_list_equipment_filters(client):
    body = client.get("/equipment?site=mrb&equipment_type=PUMP").json()
    assert body["total"] == 3
    assert all(item["site"] == "MRB" and item["equipment_type"] == "pump" for item in body["items"])
    tags = [item["tag"] for item in body["items"]]
    assert tags == sorted(tags)
    assert "open_work_orders" in body["items"][0]

    body = client.get("/equipment?status=out_of_service&criticality=a").json()
    assert all(item["status"] == "out_of_service" and item["criticality"] == "A"
               for item in body["items"])


def test_equipment_pagination_walks_every_item_once(client):
    seen = []
    offset = 0
    while offset is not None:
        page = client.get(f"/equipment?limit=25&offset={offset}").json()
        assert page["limit"] == 25 and page["total"] == 86
        seen += [item["tag"] for item in page["items"]]
        offset = page["next_offset"]
    assert len(seen) == 86 == len(set(seen))

    past_the_end = client.get("/equipment?offset=500").json()
    assert past_the_end["items"] == [] and past_the_end["next_offset"] is None


def test_get_equipment_any_case(client):
    body = client.get("/equipment/p-1201a").json()
    assert body["tag"] == "P-1201A"
    assert body["site"] == "MRB"
    assert body["equipment_type"] == "pump"
    assert body["open_work_orders"] == []


def test_equipment_not_found_and_malformed(client):
    body = assert_error_shape(client.get("/equipment/P-9999"), 404, "not_found")
    assert "P-9999" in body["message"] and "GET /equipment" in body["message"]

    body = assert_error_shape(client.get("/equipment/pump-one"), 422, "validation_failed")
    assert body["problems"] == [{"where": "path.tag", "problem": "must look like P-1201A or HX-3040",
                                 "got": "PUMP-ONE"}]


# ---------------------------------------------------------------------
# Maintenance history
# ---------------------------------------------------------------------


def test_list_history_for_one_tag_newest_first(client):
    body = client.get("/maintenance-history?equipment_tag=p-1201a").json()
    assert body["total"] == 3
    dates = [item["date"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)
    newest = body["items"][0]
    assert newest["work_order_id"] == "WO-118305"
    assert newest["failure_mode"] == "mechanical seal leak"
    assert newest["date"].startswith("2026-05")


def test_list_history_filters(client):
    body = client.get("/maintenance-history?failure_mode=SEAL&since=2026-01-01&until=2026-06-30"
                      "&limit=100").json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert "seal" in item["failure_mode"]
        assert "2026-01-01" <= item["date"] <= "2026-06-30"

    body = client.get("/maintenance-history?site=SHZ&work_type=inspection&limit=100").json()
    assert all(item["site"] == "SHZ" and item["work_type"] == "inspection" for item in body["items"])
    assert all(item["failure_mode"] is None for item in body["items"])


def test_get_history_record(client):
    body = client.get("/maintenance-history/mh-000224").json()
    assert body["record_id"] == "MH-000224"
    assert body["parts"][0] == {"part_number": "30-2201-01",
                                "description": "Mechanical seal cartridge", "quantity": 1}
    assert_error_shape(client.get("/maintenance-history/MH-999999"), 404, "not_found")
    assert_error_shape(client.get("/maintenance-history/224"), 422, "validation_failed")


def test_history_since_after_until(client):
    body = assert_error_shape(client.get("/maintenance-history?since=2026-06-01&until=2026-01-01"),
                              422, "validation_failed")
    assert body["problems"] == [{"where": "query",
                                 "problem": "since (2026-06-01) is after until (2026-01-01)"}]


# ---------------------------------------------------------------------
# Work orders: reads
# ---------------------------------------------------------------------


def test_list_work_orders_filters_newest_first(client):
    body = client.get("/work-orders?status=IN_PROGRESS&priority=2&limit=100").json()
    assert body["total"] >= 1
    assert all(item["status"] == "in_progress" and item["priority"] == 2 for item in body["items"])
    created = [item["created"] for item in body["items"]]
    assert created == sorted(created, reverse=True)

    body = client.get("/work-orders?equipment_tag=P-1201A&work_type=corrective").json()
    assert {item["work_order_id"] for item in body["items"]} >= {"WO-118305"}

    body = client.get("/work-orders?site=ZFL&limit=100").json()
    assert all(item["site"] == "ZFL" for item in body["items"])


def test_get_work_order(client):
    body = client.get("/work-orders/wo-118305").json()
    assert body["equipment_tag"] == "P-1201A"
    assert body["status"] == "completed"
    assert body["raised_via"] == "erp_screen"
    assert_error_shape(client.get("/work-orders/WO-999999"), 404, "not_found")
    assert_error_shape(client.get("/work-orders/118305"), 422, "validation_failed")


def test_list_parameter_errors_read_well(client):
    body = assert_error_shape(client.get("/work-orders?stauts=released"), 422, "validation_failed")
    assert body["problems"][0]["where"] == "query.stauts"
    assert "spelling" in body["problems"][0]["problem"]

    body = assert_error_shape(client.get("/equipment?limit=500"), 422, "validation_failed")
    assert body["problems"][0]["where"] == "query.limit"

    body = assert_error_shape(client.get("/work-orders?site=XYZ"), 422, "validation_failed")
    assert "MRB" in body["problems"][0]["problem"]

    body = assert_error_shape(client.get("/work-orders?source_ticket=12"), 422, "validation_failed")
    assert body["problems"][0]["problem"] == "must look like INC-004412"


# ---------------------------------------------------------------------
# THE ONE WRITE
# ---------------------------------------------------------------------


def test_raise_work_order_and_read_it_back(client):
    before = client.get("/work-orders?limit=1").json()["total"]
    highest = max(int(row["work_order_id"][3:]) for row in load("work_orders"))

    reply = client.post("/work-orders", json=GOOD_BODY)
    assert reply.status_code == 201, reply.text
    order = reply.json()
    new_id = f"WO-{highest + 1:06d}"
    assert order["work_order_id"] == new_id
    assert reply.headers["location"] == f"/work-orders/{new_id}"
    assert order["status"] == "released"
    assert order["raised_via"] == "api"
    assert order["site"] == "MRB"                       # from the equipment master
    assert order["approved_by"] == GOOD_BODY["approved_by"]
    assert order["created"].endswith("+04:00")
    raised_on = date.fromisoformat(order["created"][:10])
    assert order["target_date"] == (raised_on + timedelta(days=2)).isoformat()

    # The state change persists across every kind of read.
    assert client.get(f"/work-orders/{new_id}").json() == order
    by_ticket = client.get("/work-orders?source_ticket=inc-004412").json()
    assert [item["work_order_id"] for item in by_ticket["items"]] == [new_id]
    newest = client.get("/work-orders?limit=1").json()
    assert newest["total"] == before + 1 and newest["items"][0]["work_order_id"] == new_id
    assert client.get("/equipment/P-1201A").json()["open_work_orders"] == [new_id]
    assert client.get("/health").json()["work_orders_raised_since_start"] == 1


def test_same_ticket_twice_is_a_conflict(client):
    first = client.post("/work-orders", json=GOOD_BODY).json()
    body = assert_error_shape(client.post("/work-orders", json=GOOD_BODY), 409, "conflict")
    assert body["existing_work_order_id"] == first["work_order_id"]
    assert first["work_order_id"] in body["message"]
    assert client.get("/health").json()["work_orders_raised_since_start"] == 1


def test_no_ticket_means_no_duplicate_check(client):
    body = {**GOOD_BODY, "source_ticket": None}
    first = client.post("/work-orders", json=body).json()
    second = client.post("/work-orders", json=body).json()
    assert int(second["work_order_id"][3:]) == int(first["work_order_id"][3:]) + 1


def test_write_validation_lists_every_problem(client):
    bad = {**GOOD_BODY, "priority": 7, "prority": 1, "equipment_tag": "pump 1201"}
    del bad["approved_by"]
    body = assert_error_shape(client.post("/work-orders", json=bad), 422, "validation_failed")
    problems = {problem["where"]: problem for problem in body["problems"]}
    assert set(problems) == {"body.equipment_tag", "body.priority", "body.approved_by", "body.prority"}
    assert problems["body.equipment_tag"]["problem"] == "must look like P-1201A or HX-3040"
    assert problems["body.priority"]["problem"] == "input should be 1, 2, 3 or 4"
    assert problems["body.priority"]["got"] == 7
    assert problems["body.approved_by"]["problem"] == "is required"
    assert "spelling" in problems["body.prority"]["problem"]
    assert "Nothing was changed" in body["message"]
    assert client.get("/health").json()["work_orders_raised_since_start"] == 0


def test_write_unknown_tag_writes_nothing(client):
    body = assert_error_shape(client.post("/work-orders", json={**GOOD_BODY, "equipment_tag": "P-4444"}),
                              422, "validation_failed")
    assert body["problems"][0]["where"] == "body.equipment_tag"
    assert "not in the equipment master" in body["problems"][0]["problem"]
    assert client.get("/health").json()["counts"]["work_orders"] == 295


def test_write_malformed_json_is_400(client):
    reply = client.post("/work-orders", content='{"equipment_tag": "P-1201A", "priority": 2,}',
                        headers={"Content-Type": "application/json"})
    body = assert_error_shape(reply, 400, "malformed_body")
    assert "not valid JSON" in body["message"]


def test_write_wrong_content_type_is_415(client):
    reply = client.post("/work-orders", content=json.dumps(GOOD_BODY),
                        headers={"Content-Type": "text/plain"})
    body = assert_error_shape(reply, 415, "unsupported_media_type")
    assert "application/json" in body["message"]


def test_write_empty_or_wrong_shape_body(client):
    body = assert_error_shape(client.post("/work-orders"), 422, "validation_failed")
    assert body["problems"] == [{"where": "body", "problem": "a JSON body is required"}]
    body = assert_error_shape(client.post("/work-orders", json=[GOOD_BODY]), 422, "validation_failed")
    assert body["problems"][0]["problem"].startswith("must be a JSON object")


def test_nothing_can_be_changed_or_deleted(client):
    attempts = [("PUT", "/work-orders/WO-118305"), ("PATCH", "/work-orders/WO-118305"),
                ("DELETE", "/work-orders/WO-118305"), ("PUT", "/equipment/P-1201A"),
                ("DELETE", "/equipment/P-1201A"), ("POST", "/equipment"),
                ("POST", "/maintenance-history"), ("DELETE", "/maintenance-history/MH-000224")]
    for method, path in attempts:
        body = assert_error_shape(client.request(method, path), 405, "method_not_allowed")
        assert method in body["message"]
    body = client.delete("/work-orders/WO-118305").json()
    assert "cannot be changed, cancelled or deleted" in body["message"]


def test_unknown_route_is_a_readable_404(client):
    body = assert_error_shape(client.get("/equipmnt"), 404, "not_found")
    assert "/docs" in body["message"]


def test_concurrent_writes_get_unique_numbers(client):
    store = client.app.state.store
    request = WorkOrderCreate(**{**GOOD_BODY, "source_ticket": None})
    ids = []

    def raise_one():
        ids.append(store.raise_work_order(request)["work_order_id"])

    threads = [threading.Thread(target=raise_one) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(set(ids)) == 20


# ---------------------------------------------------------------------
# Exactly one write, and docs worth reading
# ---------------------------------------------------------------------


def test_exactly_one_write_endpoint(client):
    spec = client.app.openapi()
    writes = [(method.upper(), path) for path, operations in spec["paths"].items()
              for method in operations if method != "get"]
    assert writes == [("POST", "/work-orders")]

    # Routes hidden from the schema count too. (Since FastAPI 0.137
    # app.routes is a tree, so read the two routers main.py builds.)
    route_methods = set()
    for router in (erp_main.router, erp_main.service_router):
        for route in router.routes:
            for method in route.methods:
                route_methods.add((method, route.path))
    non_reads = {pair for pair in route_methods if pair[0] not in ("GET", "HEAD")}
    assert non_reads == {("POST", "/work-orders")}

    # And by behaviour: every write method on every path is refused but one.
    paths = ["/", "/health", "/equipment", "/equipment/P-1201A", "/maintenance-history",
             "/maintenance-history/MH-000224", "/work-orders", "/work-orders/WO-118305"]
    for path in paths:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            if (method, path) == ("POST", "/work-orders"):
                continue
            assert client.request(method, path).status_code == 405, f"{method} {path}"


def test_openapi_is_documented(client):
    spec = client.app.openapi()
    assert "The one write" in spec["info"]["description"]
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method} {path} has no summary"
            assert operation.get("description"), f"{method} {path} has no description"
            assert operation.get("tags"), f"{method} {path} has no tag"
    post = spec["paths"]["/work-orders"]["post"]
    assert set(post["responses"]) >= {"201", "400", "409", "415", "422"}
    assert "not reversible" in post["description"]
    body_schema = spec["components"]["schemas"]["WorkOrderCreate"]
    assert "approved_by" in body_schema["required"]
    assert body_schema["additionalProperties"] is False
    assert body_schema["examples"][0]["equipment_tag"] == "P-1201A"


def test_committed_openapi_matches_the_app(client):
    committed = json.loads((REPO_ROOT / "services" / "mock_erp" / "openapi.json").read_text(encoding="ascii"))
    assert committed == client.app.openapi(), (
        "services/mock_erp/openapi.json is stale: run python -m services.mock_erp.write_openapi")


# ---------------------------------------------------------------------
# The API key (environment secret, no production auth)
# ---------------------------------------------------------------------


def test_api_key_when_set():
    locked = TestClient(create_app(api_key="lab-key-123"))
    assert locked.get("/health").json()["auth"] == "api_key"          # always open
    assert locked.get("/docs").status_code == 200
    body = assert_error_shape(locked.get("/equipment/P-1201A"), 401, "unauthorised")
    assert "X-API-Key" in body["message"]
    assert_error_shape(locked.get("/equipment/P-1201A", headers={"X-API-Key": "wrong"}),
                       401, "unauthorised")
    assert_error_shape(locked.post("/work-orders", json=GOOD_BODY), 401, "unauthorised")
    good = {"X-API-Key": "lab-key-123"}
    assert locked.get("/equipment/P-1201A", headers=good).status_code == 200
    assert locked.post("/work-orders", json=GOOD_BODY, headers=good).status_code == 201
    assert "lab-key-123" not in json.dumps(locked.app.openapi())


def test_api_key_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("MOCK_ERP_API_KEY", "from-env")
    locked = TestClient(create_app())
    assert locked.get("/health").json()["auth"] == "api_key"
    assert locked.get("/equipment", headers={"X-API-Key": "from-env"}).status_code == 200


# ---------------------------------------------------------------------
# Seed data: deterministic, committed, consistent, synthetic
# ---------------------------------------------------------------------


def test_committed_seed_matches_the_generator(tmp_path):
    seed.write_seed(seed.build_seed(42, TICKETS), tmp_path)
    for name in ("equipment", "work_orders", "maintenance_history"):
        assert (tmp_path / f"{name}.json").read_bytes() == (DATA_DIR / f"{name}.json").read_bytes(), (
            f"{name}.json differs from the generator: run python -m services.mock_erp.seed --seed 42")


def test_two_starts_serve_identical_data():
    first = TestClient(create_app(api_key=""))
    second = TestClient(create_app(api_key=""))
    first.post("/work-orders", json=GOOD_BODY)          # a write in the first "run" only
    assert first.get("/health").json()["data_fingerprint"] == second.get("/health").json()["data_fingerprint"]
    assert second.get("/work-orders?source_ticket=INC-004412").json()["total"] == 0
    for path in ("/equipment?limit=100", "/maintenance-history?limit=100&offset=100",
                 "/work-orders/WO-118305", "/equipment/HX-2629"):
        assert TestClient(create_app(api_key="")).get(path).json() == second.get(path).json()


def test_seed_is_consistent_with_the_ticket_corpus():
    equipment = {row["tag"]: row for row in load("equipment")}
    work_orders = {row["work_order_id"]: row for row in load("work_orders")}

    assert sorted({row["site"] for row in equipment.values()}) == sorted(ticket_phrases.SITE_WEIGHTS)
    assert seed.SITES == sorted(ticket_phrases.SITE_WEIGHTS)
    assert sorted(seed.EQUIPMENT_TYPES) == sorted(ticket_phrases.PLANT_TAG_PREFIXES)

    tickets = [json.loads(line) for line in TICKETS.read_text(encoding="utf-8").splitlines()]
    for ticket in tickets:
        text = ticket["subject"] + "\n" + ticket["body"]
        tags = TAG.findall(text)
        for tag in tags:
            assert tag in equipment, f"{ticket['ticket_id']} mentions {tag}, missing from the ERP"
        for work_order_id in re.findall(r"\bWO-\d{6}\b", text):
            assert work_order_id in work_orders, f"{ticket['ticket_id']} mentions {work_order_id}"
            if tags:
                assert work_orders[work_order_id]["equipment_tag"] == tags[0]

    # Brief 4: the seal on P-1201A was replaced under WO-118305 in May 2026.
    may_job = work_orders["WO-118305"]
    assert may_job["equipment_tag"] == "P-1201A" and may_job["completed_date"].startswith("2026-05")


def test_seed_records_hang_together():
    equipment = {row["tag"]: row for row in load("equipment")}
    work_orders = {row["work_order_id"]: row for row in load("work_orders")}
    history = load("maintenance_history")

    for row in equipment.values():
        assert re.fullmatch(r"[A-Z]{1,3}-[0-9]{4}[A-Z]?", row["tag"])
        date.fromisoformat(row["install_date"])
    for row in work_orders.values():
        assert re.fullmatch(r"WO-[0-9]{6}", row["work_order_id"])
        assert row["equipment_tag"] in equipment
        assert row["site"] == equipment[row["equipment_tag"]]["site"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+04:00", row["created"])
        assert (row["completed_date"] is not None) == (row["status"] == "completed")
    ids = [row["record_id"] for row in history]
    assert ids == [f"MH-{number:06d}" for number in range(1, len(history) + 1)]
    for row in history:
        order = work_orders[row["work_order_id"]]
        assert order["status"] == "completed"
        assert order["completed_date"] == row["date"]
        assert (order["equipment_tag"], order["site"]) == (row["equipment_tag"], row["site"])
    # Every out-of-service item has open work on it.
    for row in equipment.values():
        if row["status"] == "out_of_service":
            assert any(order["equipment_tag"] == row["tag"] and order["status"] == "in_progress"
                       for order in work_orders.values())


def test_nothing_in_the_seed_looks_like_a_tag_that_is_not_one():
    """Part numbers, serials and models must never pass for an equipment tag."""
    equipment = {row["tag"] for row in load("equipment")}
    for name in ("equipment", "work_orders", "maintenance_history"):
        text = (DATA_DIR / f"{name}.json").read_text(encoding="ascii")
        strays = set(re.findall(r"\b[A-Z]{1,3}-\d{4}[A-Z]?\b", text)) - equipment
        assert not strays, f"{name}.json has tag-shaped strings that are not tags: {sorted(strays)[:5]}"


def test_seed_is_synthetic():
    text = "\n".join((DATA_DIR / f"{name}.json").read_text(encoding="ascii")
                     for name in ("equipment", "work_orders", "maintenance_history"))
    for term in check_tickets.DENYLIST:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])"
        assert not re.search(pattern, text, flags=re.IGNORECASE), f"real name in seed: {term}"
    for code in check_tickets.REAL_SITE_CODES:
        assert f'"{code}"' not in text
    assert not check_tickets.FAMILY_NAME_PATTERN.search(text)


# ---------------------------------------------------------------------
# A real server in the background: the Colab path, restarts, the tour
# ---------------------------------------------------------------------


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_real_server_in_background_restart_and_tour(tmp_path):
    port = free_port()
    erp = launch.start_in_background(port=port, log_path=tmp_path / "erp.log", api_key="")
    try:
        assert erp.health["work_orders_raised_since_start"] == 0
        fingerprint = erp.health["data_fingerprint"]

        # Starting again on the same port reuses it instead of failing.
        again = launch.start_in_background(port=port, api_key="")
        assert again.process is None and again.base_url == erp.base_url

        # The tour hits every endpoint, including the write, and checks each status.
        tour = subprocess.run([sys.executable, "-m", "services.mock_erp.tour",
                               "--base-url", erp.base_url], cwd=REPO_ROOT,
                              capture_output=True, text=True, timeout=120)
        assert tour.returncode == 0, tour.stdout[-3000:] + tour.stderr[-2000:]
        assert "All 29 replies had the expected status." in tour.stdout
        assert all(len(line) <= 100 for line in tour.stdout.splitlines())
        tour.stdout.encode("ascii")

        _, health = launch.probe(erp.base_url)
        assert health["work_orders_raised_since_start"] == 1
    finally:
        launch.stop(erp)

    # Restart: the write is gone, the data is byte-identical.
    assert launch.probe(erp.base_url)[0] == "nothing"
    erp = launch.start_in_background(port=port, log_path=tmp_path / "erp2.log", api_key="")
    try:
        assert erp.health["data_fingerprint"] == fingerprint
        assert erp.health["work_orders_raised_since_start"] == 0
        assert erp.health["counts"]["work_orders"] == 295
    finally:
        launch.stop(erp)
    assert "WRITE raised" in (tmp_path / "erp.log").read_text(encoding="utf-8")


def test_launch_refuses_a_port_held_by_something_else(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class NotTheErp(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"hello")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), NotTheErp)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(RuntimeError, match="not the mock ERP"):
            launch.start_in_background(port=server.server_address[1], log_path=tmp_path / "x.log")
    finally:
        server.shutdown()
