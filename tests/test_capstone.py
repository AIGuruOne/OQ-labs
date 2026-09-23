"""Tests for the Day 5 capstone scaffold and the Contract 5 reference index (P13).

    python -m pytest tests/test_capstone.py -v

No network and no model: the endpoint is a stub, the ERP / MCP server
are not started (their own tests cover them). What is pinned here:
Contract 5 as docs/contracts.md writes it, every fallback being visible,
the audit lines matching governance template 5.1, the cost cap, and the
starter and the brief 5 example keeping the same five extension points.
"""

import inspect
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import capstone.wiring as wiring  # noqa: E402
from capstone import my_usecase  # noqa: E402
from capstone.contract import HIT_KEYS, ContractError, check_description, check_hits  # noqa: E402
from capstone.examples import brief5_similar_tickets  # noqa: E402
from capstone.reference_index import build_index, load_index, plant_tags_in  # noqa: E402
from capstone.reference_index.adapter_example import WordOverlapIndex  # noqa: E402
from capstone.reference_index.bm25 import read_ids  # noqa: E402

HELDOUT = REPO_ROOT / "data" / "eval" / "heldout_20.jsonl"
TEMPLATE_5 = REPO_ROOT / "facilitator" / "governance_pack" / "05_audit_logging.md"
CONTRACTS = REPO_ROOT / "docs" / "contracts.md"


@pytest.fixture(scope="module")
def index():
    return build_index()


# ---------------------------------------------------------------------
# Contract 5, the reference index
# ---------------------------------------------------------------------


def test_reference_index_leaves_out_the_heldout_20(index):
    heldout_ids = set(read_ids(HELDOUT))
    indexed_ids = {item["doc_id"] for item in index.items}
    assert len(heldout_ids) == 20
    assert len(indexed_ids) == 580
    assert heldout_ids.isdisjoint(indexed_ids)


def test_build_id_is_repeatable(index):
    assert build_index().describe()["build_id"] == index.describe()["build_id"]
    check_description(index.describe())


def test_hits_are_exactly_contract_5(index):
    hits = index.search("vpn drops after ten seconds", k=5)
    check_hits(hits, 5)
    assert len(hits) == 5
    assert all(sorted(hit) == sorted(HIT_KEYS) for hit in hits)
    assert hits[0]["chunk_id"] == hits[0]["doc_id"] + "#000"
    assert hits[0]["metadata"]["family"] == "ticket"


def test_a_tag_is_one_token(index):
    hits = index.search("HX-2629", k=3)
    assert hits and "HX-2629" in hits[0]["text"]
    assert plant_tags_in("pump P-1201A and LAP-04412 and WO-118305 and HX-3040") == ["P-1201A", "HX-3040"]


def test_filters_and_unknown_filter_keys(index):
    hits = index.search("printer", k=5, filters={"site": "MRB"})
    assert hits and all(hit["metadata"]["site"] == "MRB" for hit in hits)
    tagged = index.search("printer", k=5, filters={"equipment_tags": "HX-2629"})
    assert [hit["doc_id"] for hit in tagged] == ["INC-006432"]
    with pytest.raises(ValueError, match="Unknown filter"):
        index.search("printer", filters={"owner": "me"})


def test_save_and_load_give_the_same_hits(index, tmp_path):
    path = index.save(tmp_path / "index.json")
    again = load_index(path)
    assert again.search("password reset", k=5) == index.search("password reset", k=5)


def test_contract_check_catches_a_broken_index():
    good = {"doc_id": "A", "chunk_id": "A#000", "text": "t", "score": 1.0, "metadata": {}}
    with pytest.raises(ContractError, match="exactly"):
        check_hits([{"id": "A", "score": 1.0}], 5)
    with pytest.raises(ContractError, match="descending"):
        check_hits([good, {**good, "score": 2.0}], 5)
    with pytest.raises(ContractError, match="for k=1"):
        check_hits([good, good], 1)


def test_the_second_implementation_satisfies_the_contract():
    other = WordOverlapIndex()
    check_description(other.describe())
    hits = check_hits(other.search("vpn drops after update", k=5), 5)
    assert len(hits) == 5
    with pytest.raises(ValueError):
        other.search("x", filters={"owner": "me"})


def test_contracts_md_matches_the_code():
    text = CONTRACTS.read_text(encoding="utf-8")
    section = text[text.index("## Contract 5"):text.index("## Service surface — mock ERP")]
    assert "**Final**" in section
    for key in HIT_KEYS + ["describe()", "build_index", "capstone/reference_index/", "adapter_example.py"]:
        assert key in section, key


# ---------------------------------------------------------------------
# Fallbacks are visible
# ---------------------------------------------------------------------


def test_missing_index_falls_back_and_says_why(tmp_path):
    index, row = wiring.resolve_index(str(tmp_path / "nope.json"), tmp_path, wiring.AuditLog(tmp_path / "iw.jsonl"))
    assert row["source"] == "FALLBACK"
    assert "nope.json did not load" in row["note"]
    assert index.describe()["name"] == "reference-bm25-tickets"


def test_module_index_is_used_as_yours(tmp_path):
    index, row = wiring.resolve_index("capstone.reference_index.adapter_example:make_index", tmp_path,
                                      wiring.AuditLog(tmp_path / "iw.jsonl"))
    assert row["source"] == "yours"
    assert index.describe()["name"] == "adapter-example-word-overlap"


def test_reference_index_is_saved_and_reloaded(tmp_path):
    log = wiring.AuditLog(tmp_path / "audit" / "index_write.jsonl")
    first_index, first_note = wiring.reference_index(tmp_path, log)
    second_index, second_note = wiring.reference_index(tmp_path, log)
    assert "built now" in first_note and "loaded" in second_note
    assert len(log.lines()) == 580                     # written once, at the build


def test_broken_adapter_falls_back_to_prebaked(tmp_path):
    broken = tmp_path / "adapter"
    broken.mkdir()
    shutil.copy(wiring.PREBAKED_ADAPTER / "adapter_config.json", broken)
    data = (wiring.PREBAKED_ADAPTER / "adapter_model.safetensors").read_bytes()
    (broken / "adapter_model.safetensors").write_bytes(data[:len(data) // 2])
    row = wiring.resolve_adapter(str(broken))
    assert row["source"] == "FALLBACK"
    assert "cut off" in row["note"]
    assert row["path"] == str(wiring.PREBAKED_ADAPTER)
    assert wiring.resolve_adapter(None)["note"].startswith("MY_ADAPTER_DIR is not set")


# ---------------------------------------------------------------------
# One ticket through the pipeline, with a stub model
# ---------------------------------------------------------------------

GOOD_RECORD = {"category": "network", "affected_system": "GateKey VPN", "asset_tag": None,
               "urgency": "medium", "impact": "single_user",
               "requested_action": "Restore the VPN connection", "routing_queue": "network_ops"}


class StubEndpoint:
    name = "hosted"
    model = "stub-model"
    base_url = "http://stub"

    def __init__(self, reply):
        self.reply = reply
        self.last_reply_info = None
        self.sent = []

    def chat(self, messages, temperature, max_tokens):
        self.sent.append(messages)
        self.last_reply_info = {"usage": {"prompt_tokens": 1000, "completion_tokens": 100},
                                "model": "stub-model-2026-09", "finish_reason": "stop"}
        return self.reply


def make_capstone(tmp_path, monkeypatch, usecase=my_usecase, reply=json.dumps(GOOD_RECORD)):
    stub = StubEndpoint(reply)
    monkeypatch.setattr(wiring, "get_endpoint", lambda name: stub)
    monkeypatch.setattr(wiring, "ollama_models", lambda: None)
    capstone = wiring.Capstone(usecase, out_dir=tmp_path, endpoint="hosted", start_services=False)
    return capstone, stub


def template_fields(heading, next_heading):
    text = TEMPLATE_5.read_text(encoding="utf-8")
    section = text[text.index(heading):text.index(next_heading)]
    fields = []
    for line in section.splitlines():
        if line.startswith("| `"):
            fields += re.findall(r"`([a-z_0-9]+)`", line.split("|")[1])
    return fields


def test_llm_call_line_is_exactly_template_5_1_1(tmp_path, monkeypatch):
    capstone, stub = make_capstone(tmp_path, monkeypatch)
    result = capstone.run_ticket({"ticket_id": "INC-005310", "text": "Subject: vpn\n\nGateKey VPN drops"})
    line = capstone.llm_log.lines()[-1]
    assert list(line) == template_fields("### 5.1.1", "### 5.1.2")
    assert line["model_fingerprint"] == "stub-model-2026-09"
    assert line["context_ids"] and all(cid.endswith("#000") for cid in line["context_ids"])
    assert line["cost_estimate"] == round(1000 * 0.75 / 1e6 + 100 * 4.50 / 1e6, 6)
    assert result["decision"]["action"] == "propose_to_agent"


def test_index_write_line_is_exactly_template_5_1_3(tmp_path):
    log = wiring.AuditLog(tmp_path / "index_write.jsonl")
    build_index(index_log=log)
    line = log.lines()[0]
    assert list(line) == template_fields("### 5.1.3", "## 5.2")


def test_a_ticket_is_never_its_own_neighbour(tmp_path, monkeypatch):
    capstone, stub = make_capstone(tmp_path, monkeypatch)
    text = "Subject: warehouse label printer cutting off tags like HX-2629"
    result = capstone.run_ticket({"ticket_id": "INC-006432", "text": text})
    ids = [hit["doc_id"] for hit in result["context"]["neighbours"]]
    assert "INC-006432" not in ids and len(ids) == my_usecase.NEIGHBOURS


def test_without_services_equipment_says_so(tmp_path, monkeypatch):
    capstone, stub = make_capstone(tmp_path, monkeypatch)
    result = capstone.run_ticket({"ticket_id": "X", "text": "pump P-1201A sounds wrong"})
    assert result["context"]["equipment"] == [{"tag": "P-1201A", "error": "ERP/MCP not running"}]


def test_cost_cap_stops_the_call(tmp_path, monkeypatch):
    capstone, stub = make_capstone(tmp_path, monkeypatch)
    monkeypatch.setattr(my_usecase, "COST_CAP_USD_PER_MONTH", 0.001)
    capstone.run_ticket({"ticket_id": "A", "text": "vpn"})          # 0.00120 spent
    with pytest.raises(wiring.CostCapReached, match="No model call was made"):
        capstone.run_ticket({"ticket_id": "B", "text": "vpn"})
    assert len(stub.sent) == 1


def test_starter_checks(tmp_path, monkeypatch):
    ticket = {"ticket_id": "A", "text": "my laptop prn-01388 is broken"}
    upper = dict(GOOD_RECORD, asset_tag="PRN-01388")
    output, validation = my_usecase.check_output(json.dumps(upper), ticket, {})
    assert validation["valid"], validation            # case differs, still in the ticket
    invented = dict(GOOD_RECORD, asset_tag="LAP-04412")
    output, validation = my_usecase.check_output(json.dumps(invented), ticket, {})
    assert not validation["valid"] and "invented" in validation["problems"][0]
    output, validation = my_usecase.check_output("```json\n{}\n```", ticket, {})
    assert output is None and my_usecase.decide(output, validation, ticket, {})["action"] == "empty_form"


def test_brief5_example_falls_back_to_the_vote(tmp_path, monkeypatch):
    capstone, stub = make_capstone(tmp_path, monkeypatch, usecase=brief5_similar_tickets, reply="not json")
    result = capstone.run_ticket({"ticket_id": "X", "text": "Subject: GateKey VPN\n\nvpn drops after 10 sec"})
    assert result["decision"]["action"] == "show_neighbours_only"
    assert result["decision"]["proposed_queue"] == "network_ops"
    sent_user_text = stub.sent[0][1]["content"]
    assert "Similar past tickets" in sent_user_text
    # Privacy rule of the example: a neighbour's body never reaches the prompt.
    neighbour_bodies = [hit for hit in result["context"]["neighbours"] if "text" in hit]
    assert neighbour_bodies == []


def test_both_use_case_files_keep_the_five_extension_points():
    for module in [my_usecase, brief5_similar_tickets]:
        for name, parameters in [("gather_context", ["ticket", "tools"]),
                                 ("build_messages", ["ticket", "context"]),
                                 ("check_output", ["reply", "ticket", "context"]),
                                 ("decide", ["output", "validation", "ticket", "context"])]:
            assert list(inspect.signature(getattr(module, name)).parameters) == parameters, (module, name)
        for setting in ["GROUP", "SYSTEM_ID", "USE_CASE", "PROMPT_VERSION", "ENDPOINT", "MY_INDEX",
                        "MY_ADAPTER_DIR", "COST_CAP_USD_PER_MONTH", "HOSTED_PRICE_PER_MTOK"]:
            assert hasattr(module, setting), (module, setting)


def test_status_and_result_print_ascii_within_100_columns(tmp_path, monkeypatch, capsys):
    from capstone.run import print_result
    capstone, stub = make_capstone(tmp_path, monkeypatch, usecase=brief5_similar_tickets)
    capstone.print_status()
    result = capstone.run_ticket({"ticket_id": "X", "text": "Subject: GateKey VPN\n\nvpn drops, café wifi"})
    print_result(result, capstone)
    printed = capsys.readouterr().out
    assert "FALLBACK" in printed
    for line in printed.splitlines():
        assert len(line) <= 100, line
        line.encode("ascii")


# ---------------------------------------------------------------------
# The paper that goes with it
# ---------------------------------------------------------------------

FAC = REPO_ROOT / "facilitator"
CAPSTONE_DOCS = [REPO_ROOT / "capstone" / "README.md", FAC / "production_engineering_handout.md",
                 FAC / "deployment_checklist.md", FAC / "peer_scoring_sheet.md",
                 FAC / "examples" / "deployment_checklist_brief5_filled.md"]
PREBAKED = FAC / "prebaked_outputs" / "capstone"


def test_checklist_fits_its_30_minutes():
    text = (FAC / "deployment_checklist.md").read_text(encoding="utf-8")
    minutes = [int(m) for m in re.findall(r"^## .*\((\d+) min\)", text, re.M)]
    assert sum(minutes) == 30, minutes
    checks = re.findall(r"^\| ([A-E]\d) \|", text, re.M)
    assert len(checks) == 22 and len(set(checks)) == 22


def test_filled_checklist_answers_every_check():
    blank = re.findall(r"^\| ([A-E]\d) \|", (FAC / "deployment_checklist.md").read_text(encoding="utf-8"), re.M)
    filled_text = (FAC / "examples" / "deployment_checklist_brief5_filled.md").read_text(encoding="utf-8")
    for check in blank:
        row = re.search(rf"^\| {check} \|.*\| (.+) \|$", filled_text, re.M)
        assert row and row.group(1).strip(), check


def test_peer_sheet_slots_add_up_to_65():
    text = (FAC / "peer_scoring_sheet.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\| [1-6] \| \*\*", text, re.M)) == 6
    assert "11 min: demo 7, questions 2, silent scoring 2" in text
    assert 5 * 11 <= 65 and 6 * 9 + 11 == 65


def test_paths_named_in_the_capstone_docs_exist():
    missing = []
    for doc in CAPSTONE_DOCS:
        for match in re.findall(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_./-]*)`", doc.read_text(encoding="utf-8")):
            if match.startswith(("http", "/content", "<")) or "<" in match:
                continue
            # checkpoints/local/ is created by the first run and git-ignored:
            # a fresh clone does not have it yet.
            if match.startswith("checkpoints/local"):
                continue
            path = match.split(":")[0]
            if not (REPO_ROOT / path).exists() and not (PREBAKED / path).exists():
                missing.append((doc.name, match))
    assert not missing, missing


def test_readme_reference_numbers_match_the_retained_comparison():
    comparison = json.loads((PREBAKED / "eval" / "comparison.json").read_text(encoding="utf-8"))
    values = {metric["metric"]: metric["values"] for metric in comparison["metrics"]}
    readme = (REPO_ROOT / "capstone" / "README.md").read_text(encoding="utf-8")
    rows = {"starter, hosted": "starter-1-hosted", "starter, tuned": "starter-1-tuned",
            "brief 5, hosted": "brief5-1-hosted", "brief 5, tuned": "brief5-1-tuned"}
    columns = ["routing_queue", "requested_action", "overall_exact_match", "urgency", "schema_valid_rate"]
    for label, run in rows.items():
        line = next(line for line in readme.splitlines() if line.startswith(f"| {label}"))
        shown = [int(cell.split("/")[0]) for cell in re.findall(r"\d+/20", line)]
        expected = [round(values[column][run] * 20) for column in columns]
        assert shown == expected, (label, shown, expected)
