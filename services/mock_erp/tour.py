"""Walk every endpoint of a running mock ERP and print each request and reply.

    python -m services.mock_erp.tour                          # http://127.0.0.1:8000
    python -m services.mock_erp.tour --base-url http://127.0.0.1:8001 --api-key abc

What it shows, in order: health; every read endpoint with filters and
pagination; the ONE write, then reads proving the new work order is
there; a repeat of the write (409); and every error path (404, 422,
400 malformed JSON, 415 wrong content type, 405).

It raises ONE real work order (for an unused ticket id INC-0090nn), so
run it against a lab server, not a shared one you care about.

Exit code 0 = every reply had the expected status; 1 = at least one
did not (the line is marked MISMATCH); 2 = nothing answered.
Output is ASCII and at most 100 columns, for a console or a projector.
"""

import argparse
import json
import sys

import requests

WIDTH = 100
MAX_BODY_LINES = 14


def show_json(data):
    """Pretty JSON, long lists cut to their first 2 items, at most MAX_BODY_LINES."""
    if isinstance(data, dict) and isinstance(data.get("items"), list) and len(data["items"]) > 2:
        kept = len(data["items"])
        data = {**data, "items": data["items"][:2] + [f"... {kept - 2} more items on this page"]}
    text = json.dumps(data, indent=1, ensure_ascii=True)
    lines = []
    for line in text.splitlines():
        if len(line) > WIDTH - 4:
            line = line[:WIDTH - 7] + "..."
        lines.append("    " + line)
    if len(lines) > MAX_BODY_LINES:
        lines = lines[:MAX_BODY_LINES] + [f"    ... ({len(lines) - MAX_BODY_LINES} more lines)"]
    return "\n".join(lines)


class Tour:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_key:
            self.session.headers["X-API-Key"] = api_key
        self.mismatches = 0
        self.step = 0

    def call(self, title, method, path, expected, json_body=None, raw_body=None, headers=None):
        self.step += 1
        print("=" * WIDTH)
        print(f"{self.step:2d}. {title}")
        print(f">>> {method} {path}")
        if json_body is not None:
            print(show_json(json_body))
        if raw_body is not None:
            shown = raw_body if len(raw_body) <= 50 else raw_body[:47] + "..."
            print(f"    (raw body, Content-Type: {(headers or {}).get('Content-Type')}) {shown}")

        reply = self.session.request(method, self.base_url + path, json=json_body,
                                     data=raw_body, headers=headers, timeout=10,
                                     allow_redirects=False)
        verdict = "ok" if reply.status_code == expected else f"MISMATCH, expected {expected}"
        if reply.status_code != expected:
            self.mismatches += 1
        print(f"<<< {reply.status_code} {reply.reason}   [{verdict}]")
        for header in ("Location", "Allow"):
            if header in reply.headers:
                print(f"    {header}: {reply.headers[header]}")
        try:
            body = reply.json()
        except ValueError:
            body = None
        if body is not None:
            print(show_json(body))
        return body

    def unused_ticket(self):
        """INC-009001, INC-009002 ... the first with no work order yet."""
        for number in range(9001, 9100):
            ticket = f"INC-{number:06d}"
            reply = self.session.get(f"{self.base_url}/work-orders",
                                     params={"source_ticket": ticket}, timeout=10)
            if reply.status_code == 200 and reply.json()["total"] == 0:
                return ticket
        raise RuntimeError("INC-009001 to INC-009099 all have work orders: restart the ERP.")


def run_tour(tour):
    tour.call("Is it up, and with which data?", "GET", "/health", 200)

    # ---- Equipment master -------------------------------------------
    tour.call("List equipment: pumps at MRB, 2 per page", "GET",
              "/equipment?site=MRB&equipment_type=pump&limit=2", 200)
    tour.call("Next page (offset = the next_offset from the reply above)", "GET",
              "/equipment?site=MRB&equipment_type=pump&limit=2&offset=2", 200)
    before = tour.call("Get one piece of equipment (any case works)", "GET", "/equipment/p-1201a", 200)

    # ---- Maintenance history ----------------------------------------
    tour.call("What has been done to P-1201A before? Newest first", "GET",
              "/maintenance-history?equipment_tag=P-1201A", 200)
    tour.call("Seal failures anywhere since 2026-01-01", "GET",
              "/maintenance-history?failure_mode=seal&since=2026-01-01&limit=3", 200)
    tour.call("Get one maintenance record", "GET", "/maintenance-history/MH-000224", 200)

    # ---- Work orders ------------------------------------------------
    tour.call("List work orders in progress, priority 2", "GET",
              "/work-orders?status=in_progress&priority=2&limit=2", 200)
    tour.call("Get one work order: the May seal job", "GET", "/work-orders/WO-118305", 200)

    # ---- THE ONE WRITE ----------------------------------------------
    ticket = tour.unused_ticket()
    tour.call(f"Does {ticket} already have a work order? (check before writing)", "GET",
              f"/work-orders?source_ticket={ticket}", 200)
    body = {
        "equipment_tag": "P-1201A",
        "work_type": "corrective",
        "priority": 2,
        "title": "P-1201A abnormal noise, suspect seal",
        "description": "Control room reports P-1201A screen red and the pump sounds wrong. "
                       "Seal replaced under WO-118305 in May 2026. Inspect seal and bearings.",
        "requested_by": "Control room operator, MRB",
        "approved_by": "Salim (maintenance planner, MRB)",
        "source_ticket": ticket,
    }
    created = tour.call("THE ONE WRITE: raise a work order, released to the site crew", "POST",
                        "/work-orders", 201, json_body=body)
    new_id = created["work_order_id"] if created and "work_order_id" in created else "WO-000000"

    tour.call("Read it back by id", "GET", f"/work-orders/{new_id}", 200)
    tour.call("Read it back by ticket", "GET", f"/work-orders?source_ticket={ticket}", 200)
    after = tour.call("The equipment now lists it as open work", "GET", "/equipment/P-1201A", 200)
    tour.call("Health counts the write", "GET", "/health", 200)
    tour.call("Send the same write again (a retry after a timeout): refused", "POST",
              "/work-orders", 409, json_body=body)

    # ---- Error paths ------------------------------------------------
    tour.call("404: a well-formed tag that does not exist", "GET", "/equipment/P-9999", 404)
    tour.call("404: no such work order", "GET", "/work-orders/WO-999999", 404)
    tour.call("404: no such endpoint", "GET", "/equipmnt", 404)
    tour.call("422: not a tag at all", "GET", "/equipment/pump-one", 422)
    tour.call("422: a typo in a filter name is refused, not ignored", "GET",
              "/work-orders?stauts=released", 422)
    tour.call("422: limit out of range", "GET", "/equipment?limit=500", 422)
    tour.call("422: since after until", "GET",
              "/maintenance-history?since=2026-06-01&until=2026-01-01", 422)
    bad = {**body, "priority": 7, "prority": 1, "equipment_tag": "pump 1201", "source_ticket": None}
    del bad["approved_by"]
    tour.call("422: four problems in one body, all listed", "POST", "/work-orders", 422,
              json_body=bad)
    tour.call("422: a tag that is not in the equipment master", "POST", "/work-orders", 422,
              json_body={**body, "equipment_tag": "P-4444", "source_ticket": None})
    tour.call("400: malformed JSON (trailing comma)", "POST", "/work-orders", 400,
              raw_body='{"equipment_tag": "P-1201A", "priority": 2,}',
              headers={"Content-Type": "application/json"})
    tour.call("415: JSON sent as text/plain", "POST", "/work-orders", 415,
              raw_body=json.dumps(body), headers={"Content-Type": "text/plain"})
    tour.call("405: there is no way to delete a work order", "DELETE", f"/work-orders/{new_id}", 405)
    tour.call("405: or to change equipment", "PATCH", "/equipment/P-1201A", 405,
              json_body={"status": "out_of_service"})

    print("=" * WIDTH)
    open_before = before["open_work_orders"] if before else "?"
    open_after = after["open_work_orders"] if after else "?"
    print(f"State change: P-1201A open work orders before {open_before} -> after {open_after}")


def main():
    parser = argparse.ArgumentParser(description="Walk every mock ERP endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="", help="only if the server has MOCK_ERP_API_KEY set")
    args = parser.parse_args()

    tour = Tour(args.base_url, args.api_key)
    try:
        tour.session.get(tour.base_url + "/health", timeout=5)
    except requests.RequestException as problem:
        print(f"Nothing answered at {args.base_url}: {problem.__class__.__name__}. Start it with "
              f"`uvicorn services.mock_erp.main:app` from the repo root.")
        sys.exit(2)

    run_tour(tour)
    if tour.mismatches:
        print(f"{tour.mismatches} of {tour.step} replies had an unexpected status (MISMATCH above).")
        sys.exit(1)
    print(f"All {tour.step} replies had the expected status.")


if __name__ == "__main__":
    main()
