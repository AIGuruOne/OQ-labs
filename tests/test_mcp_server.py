"""Tests for the reference MCP server (services/mcp_server_reference/, Day 5 S26).

In-process where possible (the SDK's in-memory client runs through the
same middleware as HTTP), against a real mock ERP started in the
background, plus one run of test_inspector.py over real HTTP. Also
holds the server to the documents it must agree with: the audit fields
of governance template 5.1.2, the build sequence's timetable and its
step 1 code, the contract, the pins.

    python -m pytest tests/test_mcp_server.py -q
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from mcp import Client  # noqa: E402
from mcp_types import ElicitResult, Implementation  # noqa: E402

from services.mcp_server_reference import approval, audit  # noqa: E402
from services.mcp_server_reference import server as reference  # noqa: E402
from services.mock_erp import launch as erp_launch  # noqa: E402

PACKAGE = REPO_ROOT / "services" / "mcp_server_reference"
TEMPLATE_5 = REPO_ROOT / "facilitator" / "governance_pack" / "05_audit_logging.md"
SEQUENCE = REPO_ROOT / "facilitator" / "mcp_build_sequence.md"
READS = ["get_equipment", "get_maintenance_history", "list_work_orders"]
STEPS = {
    "step1_first_tool": ["get_equipment"],
    "step2_typed_contract": ["get_equipment"],
    "step3_more_reads": READS,
    "step4_audit": READS,
}


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def erp(tmp_path_factory):
    """A real mock ERP with an API key; the MCP server finds it through the environment."""
    key = "test-key-4f1c9a"
    port = free_port()
    running = erp_launch.start_in_background(port=port, api_key=key,
                                             log_path=tmp_path_factory.mktemp("erp") / "erp.log")
    saved = {name: os.environ.get(name) for name in ("MOCK_ERP_URL", "MOCK_ERP_API_KEY")}
    os.environ["MOCK_ERP_URL"] = running.base_url
    os.environ["MOCK_ERP_API_KEY"] = key
    yield SimpleNamespace(url=running.base_url, key=key)
    erp_launch.stop(running)
    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def run(coroutine):
    return asyncio.run(coroutine)


def answer_with(decision, approver="planner:salim", reason="checked in the test"):
    async def callback(context, params):
        return ElicitResult(action="accept",
                            content={"decision": decision, "approver": approver, "reason": reason})
    return callback


async def call(mcp, name, arguments, callback=None, client_name="pytest"):
    async with Client(mcp, mode="2026-07-28", elicitation_callback=callback,
                      client_info=Implementation(name=client_name, version="1")) as client:
        return await client.call_tool(name, arguments)


def work_order(ticket):
    return {"equipment_tag": "P-1201A", "work_type": "corrective", "priority": 3,
            "title": "Test work order from pytest", "description": "Raised by tests/test_mcp_server.py.",
            "requested_by": "pytest", "source_ticket": ticket}


def audit_lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------
# The documents the server must agree with
# ---------------------------------------------------------------------


def template_audit_fields():
    """The tool_call field names, in order, from governance template 5.1.2."""
    text = TEMPLATE_5.read_text(encoding="utf-8")
    section = text[text.index("### 5.1.2"):text.index("### 5.1.3")]
    fields = []
    for line in section.splitlines():
        if line.startswith("| `"):
            first_cell = line.split("|")[1]
            fields += re.findall(r"`([a-z_0-9]+)`", first_cell)
    return fields


def test_audit_line_is_exactly_template_5_1_2(tmp_path, erp):
    expected = template_audit_fields()
    assert len(expected) == 17
    log = tmp_path / "audit.jsonl"
    mcp = reference.build_server(audit_log_path=log)
    run(call(mcp, "get_equipment", {"tag": "P-1201A"}))
    line = audit_lines(log)[0]
    assert list(line) == expected
    from services.mcp_server_reference import test_inspector
    assert test_inspector.AUDIT_FIELDS == expected
    assert line["event"] == "tool_call" and line["server"] == "oq-erp-mcp"
    assert line["upstream"] == {"system": "mock_erp", "status": 200}
    assert line["approval"] == {"required": False}


def test_build_sequence_timetable_is_80_minutes_and_paths_exist():
    text = SEQUENCE.read_text(encoding="utf-8")
    table = text[text.index("## Timetable"):text.index("**If the room is behind")]
    minutes = [int(row.split("|")[3]) for row in table.splitlines()
               if re.match(r"\| (\d|—) \|", row)]
    assert sum(minutes) == 80
    for path in re.findall(r"`(services/mcp_server_reference/[\w/]+\.py)`", text):
        assert (REPO_ROOT / path).exists(), path
    for step in re.findall(r"steps/(step\d_\w+)\.py", text):
        assert (PACKAGE / "steps" / f"{step}.py").exists(), step
    for module in re.findall(r"python -m (services\.[\w.]+)", text):
        assert importlib.util.find_spec(module) is not None, module
    assert (REPO_ROOT / "facilitator" / "prebaked_outputs" / "mcp_server" / "work_order.json").exists()
    assert (REPO_ROOT / "facilitator" / "prebaked_outputs" / "mcp_server" / "work_order_2.json").exists()


def test_step_1_code_in_the_doc_is_the_checkpoint():
    """What Ritesh types in step 1 is exactly the step 1 checkpoint."""
    text = SEQUENCE.read_text(encoding="utf-8")
    step = text[text.index("## Step 1 "):text.index("## Step 2 ")]
    typed = step.split("```python\n")[1].split("```")[0]
    checkpoint = (PACKAGE / "steps" / "step1_first_tool.py").read_text(encoding="utf-8")
    code = checkpoint.split('"""', 2)[2].lstrip("\n")
    assert typed == code


def test_step_6_code_in_the_doc_matches_the_server():
    """Every line of the tool body the room types in step 6 is in server.py."""
    text = SEQUENCE.read_text(encoding="utf-8")
    step = text[text.index("## Step 6 "):text.index("## Step 7 ")]
    typed = step.split("```python\n")[1].split("```")[0]
    server_text = (PACKAGE / "server.py").read_text(encoding="utf-8")
    body_started = False
    for line in typed.splitlines():
        if "proposal = {" in line:
            body_started = True
        if body_started and line.strip():
            assert line in server_text, line


def test_pins_agree():
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "mcp==2.2.0" in requirements
    import importlib.metadata
    assert importlib.metadata.version("mcp") == "2.2.0"
    from services.mcp_server_reference import test_inspector
    assert test_inspector.INSPECTOR_PACKAGE == "@modelcontextprotocol/inspector@2.7.0"
    assert "inspector@2.7.0" in SEQUENCE.read_text(encoding="utf-8")


def test_contract_documents_the_tools():
    contracts = (REPO_ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    section = contracts[contracts.index("## Service surface — reference MCP server"):]
    for name in READS + ["raise_work_order", "input_required", "inputResponses", "requestState",
                         "--enable-writes", "OQ_MCP_APPROVERS"]:
        assert name in section, name


def test_no_secret_in_the_code():
    assignment = re.compile(r"(API_KEY|STATE_KEY|SECRET)\w*\s*=\s*[\"'][^\"']+[\"']")
    for path in PACKAGE.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not assignment.search(text), path


# ---------------------------------------------------------------------
# Read-only by default, and the class table
# ---------------------------------------------------------------------


def tool_names(mcp):
    return [tool.name for tool in run(mcp.list_tools())]


def test_read_only_by_default(tmp_path):
    signature = inspect.signature(reference.build_server)
    assert signature.parameters["enable_writes"].default is False
    assert tool_names(reference.build_server(audit_log_path=tmp_path / "a.jsonl")) == READS


def test_enable_writes_adds_exactly_the_one_write(tmp_path):
    names = tool_names(reference.build_server(enable_writes=True, audit_log_path=tmp_path / "a.jsonl"))
    assert names == READS + ["raise_work_order"]
    for name in names:
        assert name in reference.TOOL_ACCESS, name
    assert [name for name, access in reference.TOOL_ACCESS.items() if access == "write"] == \
        ["raise_work_order"]


def test_the_write_is_refused_and_logged_on_a_read_only_server(tmp_path):
    log = tmp_path / "a.jsonl"
    mcp = reference.build_server(audit_log_path=log)
    result = run(call(mcp, "raise_work_order", work_order("INC-009801")))
    assert result.is_error and "READ-ONLY" in result.content[0].text
    line = audit_lines(log)[0]
    assert line["status"] == "refused" and line["access"] == "write"
    assert line["approval"]["by"] == "server"


def test_a_tool_missing_from_the_class_table_is_refused(tmp_path):
    log = tmp_path / "a.jsonl"
    mcp = reference.build_server(audit_log_path=log)
    result = run(call(mcp, "drop_tables", {}))
    assert result.is_error
    assert audit_lines(log)[0]["status"] == "refused"
    assert audit_lines(log)[0]["access"] == "write"


def test_every_checkpoint_builds_and_lists_its_tools(tmp_path):
    for module_name, expected in STEPS.items():
        module = importlib.import_module(f"services.mcp_server_reference.steps.{module_name}")
        options = {}
        if "audit_log_path" in inspect.signature(module.build_server).parameters:
            options["audit_log_path"] = tmp_path / f"{module_name}.jsonl"
        assert tool_names(module.build_server(**options)) == expected, module_name


def test_checkpoints_add_one_capability_each():
    step1 = run(importlib.import_module("services.mcp_server_reference.steps.step1_first_tool")
                .build_server().list_tools())[0]
    step2 = run(importlib.import_module("services.mcp_server_reference.steps.step2_typed_contract")
                .build_server().list_tools())[0]
    assert "pattern" not in json.dumps(step1.input_schema)
    assert "pattern" in json.dumps(step2.input_schema)
    assert step1.output_schema is not None                       # the output contract from step 1
    step3 = run(importlib.import_module("services.mcp_server_reference.steps.step3_more_reads")
                .build_server().list_tools())
    assert all(tool.annotations.read_only_hint for tool in step3)
    step3_source = (PACKAGE / "steps" / "step3_more_reads.py").read_text(encoding="utf-8")
    assert "audit" not in step3_source.split('"""', 2)[2]
    step4_source = (PACKAGE / "steps" / "step4_audit.py").read_text(encoding="utf-8")
    assert "AuditMiddleware" in step4_source and "raise_work_order" not in step4_source


def test_a_checkpoint_copied_to_the_repo_root_still_works(tmp_path):
    """Participants copy a checkpoint over s26_server.py; no path may depend on where it sits."""
    copy = tmp_path / "s26_server.py"
    copy.write_text((PACKAGE / "server.py").read_text(encoding="utf-8"), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("s26_server_copy", copy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert inspect.signature(module.build_server).parameters["audit_log_path"].default == \
        audit.DEFAULT_LOG_PATH
    assert tool_names(module.build_server(audit_log_path=tmp_path / "a.jsonl")) == READS


# ---------------------------------------------------------------------
# The gate, in process, against the real ERP
# ---------------------------------------------------------------------


def test_the_official_client_approves_and_the_write_lands(tmp_path, erp):
    log = tmp_path / "a.jsonl"
    mcp = reference.build_server(enable_writes=True, audit_log_path=log)
    result = run(call(mcp, "raise_work_order", work_order("INC-009811"), answer_with("approve")))
    assert not result.is_error
    created = result.structured_content
    assert created["status"] == "released" and created["approved_by"] == "planner:salim"
    listed = run(call(mcp, "list_work_orders", {"source_ticket": "INC-009811"}))
    assert listed.structured_content["items"][0]["work_order_id"] == created["work_order_id"]
    lines = audit_lines(log)
    assert [line["approval"].get("decision") for line in lines[:2]] == ["pending", "approved"]
    assert [line["status"] for line in lines[:2]] == ["refused", "ok"]
    assert lines[1]["upstream"] == {"system": "mock_erp", "status": 201}
    assert erp.key not in log.read_text(encoding="utf-8")


def test_a_rejection_writes_nothing(tmp_path, erp):
    log = tmp_path / "a.jsonl"
    mcp = reference.build_server(enable_writes=True, audit_log_path=log)
    result = run(call(mcp, "raise_work_order", work_order("INC-009812"),
                      answer_with("reject", "planner:aisha", "not needed")))
    assert result.is_error and "rejected by planner:aisha" in result.content[0].text
    listed = run(call(mcp, "list_work_orders", {"source_ticket": "INC-009812"}))
    assert listed.structured_content["total"] == 0
    assert audit_lines(log)[1]["approval"]["by"] == "planner:aisha"


def test_an_approver_off_the_list_is_refused(tmp_path, erp, monkeypatch):
    monkeypatch.setenv("OQ_MCP_APPROVERS", "planner:salim")
    mcp = reference.build_server(enable_writes=True, audit_log_path=tmp_path / "a.jsonl")
    result = run(call(mcp, "raise_work_order", work_order("INC-009813"),
                      answer_with("approve", approver="planner:aisha")))
    assert result.is_error and "not on the approver list" in result.content[0].text


def test_a_client_that_cannot_show_forms_is_never_sent_one(tmp_path, erp):
    mcp = reference.build_server(enable_writes=True, audit_log_path=tmp_path / "a.jsonl")
    result = run(call(mcp, "raise_work_order", work_order("INC-009814"), callback=None))
    assert result.is_error and "elicitation" in result.content[0].text


def test_the_erp_key_comes_only_from_the_environment(tmp_path, erp, monkeypatch):
    monkeypatch.setenv("MOCK_ERP_API_KEY", "wrong-key")
    mcp = reference.build_server(audit_log_path=tmp_path / "a.jsonl")
    result = run(call(mcp, "get_equipment", {"tag": "P-1201A"}))
    assert result.is_error and "401" in result.content[0].text
    assert "wrong-key" not in result.content[0].text


# ---------------------------------------------------------------------
# The pieces
# ---------------------------------------------------------------------


def fake_ctx(request_state, responses=None):
    return SimpleNamespace(request_state=request_state, input_responses=responses)


def approve_answer(approver="planner:salim"):
    return ElicitResult(action="accept",
                        content={"decision": "approve", "approver": approver, "reason": "ok ok"})


def sealed_state(proposal):
    return json.dumps({"v": 1, "proposal_sha256": audit.sha256_of(proposal),
                       "nonce": os.urandom(8).hex(), "asked_at": audit.utc_now()})


def test_check_refuses_every_shortcut():
    proposal = work_order("INC-009820")
    state = sealed_state(proposal)
    with pytest.raises(approval.Refused, match="without the server's requestState"):
        approval.check(fake_ctx(None), proposal, approve_answer())
    with pytest.raises(approval.Refused, match="different arguments"):
        approval.check(fake_ctx(state), {**proposal, "priority": 1}, approve_answer())
    assert approval.check(fake_ctx(state), proposal, approve_answer()) == "planner:salim"
    with pytest.raises(approval.Refused, match="already used once"):
        approval.check(fake_ctx(state), proposal, approve_answer())
    with pytest.raises(approval.Refused, match="declined"):
        approval.check(fake_ctx(sealed_state(proposal)), proposal, ElicitResult(action="decline"))
    with pytest.raises(approval.Refused, match="not on the approver list"):
        approval.check(fake_ctx(sealed_state(proposal)), proposal, approve_answer("intern:bob"))


def test_redact_and_hash():
    safe = audit.redact({"tag": "P-1201A", "api_key": "abc", "db_password": "x", "text": "y" * 500})
    assert safe["api_key"] == "[redacted]" and safe["db_password"] == "[redacted]"
    assert safe["tag"] == "P-1201A" and safe["text"].endswith("(500 chars)")
    assert audit.sha256_of({"a": 1, "b": 2}) == audit.sha256_of({"b": 2, "a": 1})


def test_trace_id_comes_from_traceparent():
    trace = "0af7651916cd43dd8448eb211c80319c"
    assert audit.trace_id_of({"traceparent": f"00-{trace}-b7ad6b7169203331-01"}) == trace
    assert len(audit.trace_id_of({})) == 32


def test_rate_limiter_allows_ten_writes_a_minute():
    limiter = audit.RateLimiter({"read": 120, "write": 10})
    allowed = [limiter.allow("client-a", "write") for _ in range(11)]
    assert allowed == [True] * 10 + [False]
    assert limiter.allow("client-b", "write")            # per caller


# ---------------------------------------------------------------------
# The whole thing, over real HTTP
# ---------------------------------------------------------------------


def test_inspector_script_passes():
    script = PACKAGE / "test_inspector.py"
    ports = [free_port() for _ in range(2)]
    done = subprocess.run([sys.executable, str(script), "--erp-port", str(ports[0]),
                           "--port", str(ports[1])],
                          capture_output=True, text=True, timeout=240, cwd=REPO_ROOT,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert " 0 FAIL" in done.stdout
    for line in done.stdout.splitlines():
        assert len(line) <= 100, line
        assert line.isascii(), line
