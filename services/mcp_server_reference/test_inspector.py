"""Prove the MCP server works before anything connects to it.

    python services/mcp_server_reference/test_inspector.py              # the reference server
    python services/mcp_server_reference/test_inspector.py --inspector  # + the official MCP Inspector
    python services/mcp_server_reference/test_inspector.py --module s26_server   # YOUR server file

What it does, from nothing: starts a fresh mock ERP (with an API key, so
the key has to come from the environment), then TWO copies of the
server - one read-only (the default), one started with --enable-writes -
each with its own new audit log. Then it checks, over plain HTTP, what
the MCP Inspector checks and what the governance pack asks for:

  protocol   server/discover; no session; the 2026-07-28 header rules
             (Mcp-Method, Mcp-Name, MCP-Protocol-Version); GET is 405;
             cacheable, deterministic tools/list
  tools      every tool has input and output schemas; every read tool
             called against the live ERP, its result checked against
             its own outputSchema; bad input and unknown tags fail cleanly
  the gate   read-only by default; the write asks for approval
             (input_required), writes only after the retry, once; a
             rejection, a forged approval, a tampered or re-used
             requestState, a client that cannot show forms, an approver
             not on the list and a burst over the rate limit are refused
  audit      exactly ONE line per tool call, every field of governance
             template 5.1.2 and nothing else; both rounds of an approval
             share a trace; the ERP key is in no line and no reply
  clients    the official Python SDK client (mcp 2.2.0) does the whole
             approval round trip by itself; with --inspector, the MCP
             Inspector CLI (Node >= 22.19) lists and calls the tools

Exit 0 = every check PASSed (SKIP is not a failure); 1 = a check FAILed;
2 = the servers could not be started. Output is ASCII, at most 100 columns.

The MCP Inspector (github.com/modelcontextprotocol/inspector) is the
official tool for poking a server by hand; this script is the scripted
version of that session, so it can be rerun in 20 seconds after every
change. Its --inspector part runs the Inspector itself, pinned.
"""

import argparse
import asyncio
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jsonschema  # noqa: E402
import requests  # noqa: E402

from services.mcp_server_reference.call import McpWire  # noqa: E402
from services.mcp_server_reference.launch import start_in_background, stop  # noqa: E402
from services.mock_erp.launch import start_in_background as start_erp  # noqa: E402
from services.mock_erp.launch import stop as stop_erp  # noqa: E402

WIDTH = 100
INSPECTOR_PACKAGE = "@modelcontextprotocol/inspector@2.7.0"   # pinned: npx must not pick a newer one
READ_TOOLS = ["get_equipment", "get_maintenance_history", "list_work_orders"]
WRITE_TOOL = "raise_work_order"
AUDIT_FIELDS = ["ts", "event", "trace_id", "request_id", "server", "server_version", "caller",
                "tool", "access", "args_sha256", "args_redacted", "approval", "status",
                "upstream", "result_sha256", "records", "ms"]
APPROVER = "planner:salim"


def new_work_order(ticket):
    """A valid raise_work_order request for a ticket id nobody has used."""
    return {"equipment_tag": "P-1201A", "work_type": "corrective", "priority": 2,
            "title": "P-1201A abnormal noise, suspect seal",
            "description": "Control room reports the pump sounds wrong. Seal replaced under "
                           "WO-118305 in May 2026.",
            "requested_by": "Control room operator, MRB", "source_ticket": ticket}


def approval_answer(decision="approve", approver=APPROVER, reason="seal history checked"):
    return {"approval": {"action": "accept",
                         "content": {"decision": decision, "approver": approver,
                                     "reason": reason}}}


class Report:
    def __init__(self):
        self.rows = []

    def check(self, group, name, passed, detail=""):
        verdict = "PASS" if passed else "FAIL"
        self.rows.append((verdict, group, name, detail))
        line = f"{verdict}  {group:<8} {name}"
        if detail and (not passed or len(line) + len(detail) < WIDTH - 3):
            line += f"  ({detail})"
        print(line[:WIDTH])
        return passed

    def skip(self, group, name, why):
        self.rows.append(("SKIP", group, name, why))
        print(f"SKIP  {group:<8} {name}  ({why})"[:WIDTH])

    def count(self, verdict):
        return sum(1 for row in self.rows if row[0] == verdict)


def result_of(reply):
    return reply.get("result") or {}


def error_code(reply):
    return (reply.get("error") or {}).get("code")


def text_of(result):
    return " ".join(block.get("text", "") for block in result.get("content", []))


def erp_work_orders_for(erp_url, api_key, ticket):
    reply = requests.get(f"{erp_url}/work-orders", params={"source_ticket": ticket},
                         headers={"X-API-Key": api_key}, timeout=10)
    return reply.json()["total"]


# ---------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------


def check_protocol(report, wire, url):
    group = "protocol"
    status, reply = wire.send("server/discover")
    result = result_of(reply)
    info = (result.get("_meta") or {}).get("io.modelcontextprotocol/serverInfo", {})
    report.check(group, "server/discover answers without any handshake",
                 status == 200 and "2026-07-28" in result.get("supportedVersions", []),
                 f"supportedVersions {result.get('supportedVersions')}")
    report.check(group, "discover names the server and its tools capability",
                 info.get("name") == "oq-erp-mcp" and "tools" in result.get("capabilities", {}),
                 f"serverInfo {info}")
    report.check(group, "discover is cacheable (ttlMs, cacheScope)",
                 isinstance(result.get("ttlMs"), int) and result.get("cacheScope") in
                 ("public", "private"), f"ttlMs {result.get('ttlMs')}, {result.get('cacheScope')}")
    session_headers = [h for h in wire.exchanges[-1]["response_headers"]
                       if h.lower() == "mcp-session-id"]
    report.check(group, "no Mcp-Session-Id is minted (stateless)", not session_headers)

    reply = requests.get(url, headers={"Accept": "text/event-stream",
                                       "MCP-Protocol-Version": "2026-07-28"}, timeout=10)
    report.check(group, "a 2026-07-28 GET is 405, Allow: POST (no GET stream any more)",
                 reply.status_code == 405 and reply.headers.get("Allow") == "POST",
                 f"HTTP {reply.status_code}")

    status, reply = wire.send("tools/list", headers_override={"Mcp-Method": None})
    report.check(group, "missing Mcp-Method header -> 400 HeaderMismatch (-32020)",
                 status == 400 and error_code(reply) == -32020, f"HTTP {status}, {error_code(reply)}")

    status, reply = wire.send("tools/call", {"name": "get_equipment", "arguments": {"tag": "P-1201A"}},
                              headers_override={"Mcp-Name": "raise_work_order"})
    report.check(group, "Mcp-Name that disagrees with the body -> 400 (-32020)",
                 status == 400 and error_code(reply) == -32020, f"HTTP {status}, {error_code(reply)}")

    status, reply = wire.send("tools/list", headers_override={"MCP-Protocol-Version": "1900-01-01"})
    report.check(group, "header version != _meta version -> 400 (-32020)",
                 status == 400 and error_code(reply) == -32020, f"HTTP {status}, {error_code(reply)}")

    from_the_past = McpWire(url, client_name="old-client", quiet=True, protocol_version="1900-01-01")
    status, reply = from_the_past.send("tools/list")
    supported = ((reply.get("error") or {}).get("data") or {}).get("supported")
    report.check(group, "unsupported version -> 400 (-32022) listing supported ones",
                 status == 400 and error_code(reply) == -32022 and bool(supported),
                 f"supported {supported}")

    reply = requests.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                                     "params": {"_meta": wire.meta()}},
                          headers={"Content-Type": "application/json",
                                   "Accept": "application/json, text/event-stream",
                                   "MCP-Protocol-Version": "2026-07-28",
                                   "Mcp-Method": "tools/list",
                                   "Origin": "http://evil.example"}, timeout=10)
    report.check(group, "a foreign Origin is refused (DNS rebinding guard)",
                 reply.status_code == 403, f"HTTP {reply.status_code}")


def check_tool_list(report, wire, expect_write):
    group = "tools"
    status, first = wire.send("tools/list")
    status, second = wire.send("tools/list")
    tools = result_of(first).get("tools", [])
    names = [tool["name"] for tool in tools]
    expected = READ_TOOLS + ([WRITE_TOOL] if expect_write else [])
    report.check(group, f"tools/list is exactly {len(expected)} tools", sorted(names) == sorted(expected),
                 ", ".join(names))
    report.check(group, "tools/list order is the same on every call (cache-friendly)",
                 [t["name"] for t in result_of(second).get("tools", [])] == names)
    report.check(group, "tools/list is cacheable (ttlMs)", isinstance(result_of(first).get("ttlMs"), int),
                 f"ttlMs {result_of(first).get('ttlMs')}")
    by_name = {tool["name"]: tool for tool in tools}
    for name in names:
        tool = by_name[name]
        has_schemas = "inputSchema" in tool and "outputSchema" in tool
        read_only = (tool.get("annotations") or {}).get("readOnlyHint")
        expected_hint = name != WRITE_TOOL
        report.check(group, f"{name}: input + output schema, readOnlyHint {expected_hint}",
                     has_schemas and read_only is expected_hint)
    return by_name


def check_reads(report, wire, tools):
    group = "reads"
    calls = [
        ("get_equipment", {"tag": "P-1201A"}),
        ("get_maintenance_history", {"tag": "P-1201A", "limit": 3}),
        ("list_work_orders", {"equipment_tag": "P-1201A", "status": "completed"}),
        ("list_work_orders", {"status": "released", "limit": 5}),
    ]
    for name, arguments in calls:
        status, reply = wire.call_tool(name, arguments)
        result = result_of(reply)
        structured = result.get("structuredContent")
        try:
            jsonschema.validate(structured, tools[name]["outputSchema"])
            valid = True
            problem = ""
        except jsonschema.ValidationError as error:
            valid = False
            problem = error.message[:60]
        report.check(group, f"{name}({', '.join(f'{k}={v}' for k, v in arguments.items())})",
                     not result.get("isError") and valid, problem or "result matches outputSchema")
    status, reply = wire.call_tool("get_equipment", {"tag": "P-1201A"})
    structured = result_of(reply).get("structuredContent", {})
    report.check(group, "get_equipment P-1201A is the brief 4 pump",
                 structured.get("description") == "Crude transfer pump" and structured.get("site") == "MRB")

    status, reply = wire.call_tool("get_equipment", {"tag": "X-0000"})
    result = result_of(reply)
    report.check(group, "unknown tag -> isError with the ERP's 404 sentence",
                 result.get("isError") is True and "404" in text_of(result), text_of(result)[:50])
    status, reply = wire.call_tool("get_equipment", {"tag": "not a tag"})
    result = result_of(reply)
    report.check(group, "input that breaks the schema -> isError, ERP never called",
                 result.get("isError") is True)


def check_read_only_default(report, wire):
    group = "gate"
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009701"))
    result = result_of(reply)
    report.check(group, "read-only server: raise_work_order is refused",
                 result.get("isError") is True and "READ-ONLY" in text_of(result),
                 text_of(result)[:60])
    status, reply = wire.call_tool("delete_all_work_orders", {})
    report.check(group, "a tool not in the class table is refused as a write",
                 result_of(reply).get("isError") is True)


def check_write_gate(report, wire, erp_url, erp_key):
    """The MRTR approval: the three exchanges, then every way to get round it."""
    group = "gate"
    ticket = "INC-009711"
    request = new_work_order(ticket)

    # Exchange 1: the call. Nothing may be written yet.
    status, reply = wire.call_tool(WRITE_TOOL, request, title="EXCHANGE 1: tools/call")
    result = result_of(reply)
    form = (result.get("inputRequests") or {}).get("approval", {})
    message = (form.get("params") or {}).get("message", "")
    report.check(group, "exchange 1: resultType input_required, approval form, requestState",
                 result.get("resultType") == "input_required"
                 and form.get("method") == "elicitation/create" and bool(result.get("requestState")))
    report.check(group, "the form shows the exact request that will be sent",
                 json.dumps(request["description"]) in message and "POST /work-orders" in message)
    report.check(group, "nothing written after exchange 1",
                 erp_work_orders_for(erp_url, erp_key, ticket) == 0)
    state = result.get("requestState")

    # Exchange 2: the retry with the person's answer.
    status, reply = wire.call_tool(WRITE_TOOL, request, title="EXCHANGE 2: retry + inputResponses",
                                   inputResponses=approval_answer(), requestState=state)
    created = result_of(reply).get("structuredContent") or {}
    report.check(group, "exchange 2: work order released, approved_by = the approver",
                 created.get("status") == "released" and created.get("approved_by") == APPROVER,
                 created.get("work_order_id", text_of(result_of(reply))[:50]))

    # Exchange 3: read it back, through MCP and straight from the ERP.
    status, reply = wire.call_tool("list_work_orders", {"source_ticket": ticket},
                                   title="EXCHANGE 3: read it back")
    items = (result_of(reply).get("structuredContent") or {}).get("items", [])
    report.check(group, "exchange 3: the write landed (MCP read and ERP read agree)",
                 len(items) == 1 and erp_work_orders_for(erp_url, erp_key, ticket) == 1,
                 items[0]["work_order_id"] if items else "not found")

    # Replay: the same approval, again.
    status, reply = wire.call_tool(WRITE_TOOL, request, inputResponses=approval_answer(),
                                   requestState=state)
    report.check(group, "replaying a used approval is refused",
                 result_of(reply).get("isError") is True and "already used" in text_of(result_of(reply)),
                 text_of(result_of(reply))[:60])

    # Forged: an answer the server never asked for.
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009712"),
                                   inputResponses=approval_answer())
    report.check(group, "an approval without the server's requestState is refused",
                 result_of(reply).get("isError") is True, text_of(result_of(reply))[:60])

    # Tampered: flip one character of the sealed state.
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009713"))
    real_state = result_of(reply).get("requestState", "")
    flipped = real_state[:-5] + ("A" if real_state[-5] != "A" else "B") + real_state[-4:]
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009713"),
                                   inputResponses=approval_answer(), requestState=flipped)
    report.check(group, "a tampered requestState -> -32602, nothing written",
                 error_code(reply) == -32602 and erp_work_orders_for(erp_url, erp_key, "INC-009713") == 0)

    # Swapped: a real state, presented with other arguments (priority 1 instead of 2).
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009714"))
    state_for_p2 = result_of(reply).get("requestState")
    changed = {**new_work_order("INC-009714"), "priority": 1}
    status, reply = wire.call_tool(WRITE_TOOL, changed, inputResponses=approval_answer(),
                                   requestState=state_for_p2)
    report.check(group, "an approval for other arguments -> -32602, nothing written",
                 error_code(reply) == -32602 and erp_work_orders_for(erp_url, erp_key, "INC-009714") == 0)

    # Rejected by the person.
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009715"))
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009715"),
                                   inputResponses=approval_answer("reject", "planner:aisha",
                                                                  "duplicate of an open job"),
                                   requestState=result_of(reply).get("requestState"))
    report.check(group, "a rejection is refused and says who rejected it",
                 result_of(reply).get("isError") is True and "planner:aisha" in text_of(result_of(reply))
                 and erp_work_orders_for(erp_url, erp_key, "INC-009715") == 0)

    # An approver who is not on the list.
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009716"))
    status, reply = wire.call_tool(WRITE_TOOL, new_work_order("INC-009716"),
                                   inputResponses=approval_answer(approver="intern:bob"),
                                   requestState=result_of(reply).get("requestState"))
    report.check(group, "an approver not on OQ_MCP_APPROVERS is refused",
                 result_of(reply).get("isError") is True
                 and erp_work_orders_for(erp_url, erp_key, "INC-009716") == 0)

    # A client that cannot show a form must never be sent one.
    formless = McpWire(wire.url, client_name="formless-client", forms=False, quiet=True)
    status, reply = formless.call_tool(WRITE_TOOL, new_work_order("INC-009717"))
    report.check(group, "a client without the elicitation capability is refused, not asked",
                 result_of(reply).get("isError") is True
                 and "inputRequests" not in result_of(reply))
    return formless


def check_rate_limit(report, url):
    group = "gate"
    burst = McpWire(url, client_name="burst-client", quiet=True)
    refused_at = None
    for attempt in range(1, 13):
        status, reply = burst.call_tool(WRITE_TOOL, new_work_order("INC-009720"))
        if "rate limit" in text_of(result_of(reply)):
            refused_at = attempt
            break
    report.check(group, "write rate limit: the 11th write call in a minute is refused",
                 refused_at == 11, f"refused at call {refused_at}")
    return burst


def check_official_client(report, url):
    """The SDK's own client does the approval round trip without help."""
    group = "clients"
    try:
        from mcp import Client
        from mcp_types import ElicitResult, Implementation
    except ImportError as error:
        report.skip(group, "official Python SDK client", f"cannot import mcp: {error}")
        return 0

    asked = []

    async def answer_form(context, params):
        asked.append(params.message)
        return ElicitResult(action="accept", content={"decision": "approve", "approver": APPROVER,
                                                      "reason": "checked by the SDK client test"})

    async def run():
        async with Client(url, mode="2026-07-28", elicitation_callback=answer_form,
                          client_info=Implementation(name="sdk-client-test", version="1")) as client:
            equipment = await client.call_tool("get_equipment", {"tag": "P-1201A"})
            created = await client.call_tool(WRITE_TOOL, new_work_order("INC-009730"))
            return client.protocol_version, equipment, created

    try:
        version, equipment, created = asyncio.run(run())
    except Exception as error:                      # report, never crash the whole run
        report.check(group, "official Python SDK client (mcp 2.2.0)", False, repr(error)[:70])
        return 0
    report.check(group, "SDK client negotiates 2026-07-28 and reads a tool",
                 version == "2026-07-28" and equipment.structured_content["tag"] == "P-1201A",
                 f"protocol {version}")
    work_order = created.structured_content or {}
    report.check(group, "SDK client: form answered by callback, retried, work order written",
                 len(asked) == 1 and work_order.get("approved_by") == APPROVER,
                 work_order.get("work_order_id", "no work order"))
    return 3          # tool calls made: the read, then the write twice (round 1, round 2)


def check_audit(report, audit_path, calls_sent, erp_key, all_wires, label):
    group = "audit"
    lines = [json.loads(text) for text in Path(audit_path).read_text(encoding="utf-8").splitlines()]
    report.check(group, f"{label}: one line per tool call", len(lines) == calls_sent,
                 f"{len(lines)} lines for {calls_sent} tools/call requests")
    exact = all(list(line) == AUDIT_FIELDS for line in lines)
    report.check(group, f"{label}: every line has exactly the template 5.1.2 fields", exact)
    statuses = sorted({line["status"] for line in lines})
    report.check(group, f"{label}: status is only ok / error / refused",
                 set(statuses) <= {"ok", "error", "refused"}, ", ".join(statuses))
    everything = Path(audit_path).read_text(encoding="utf-8")
    for wire in all_wires:
        everything += json.dumps([exchange["response"] for exchange in wire.exchanges])
    report.check(group, f"{label}: the ERP key appears in no audit line and no reply",
                 erp_key not in everything)
    return lines


def check_audit_story(report, lines):
    """The approved write, read back from the log alone."""
    group = "audit"
    approved = [line for line in lines if line["approval"].get("decision") == "approved"
                and line["status"] == "ok"]
    first = approved[0] if approved else None
    report.check(group, "the approved write: approver, reason and upstream 201 recorded",
                 first is not None and first["approval"]["by"] == APPROVER
                 and first["upstream"] == {"system": "mock_erp", "status": 201})
    if first is None:
        return
    same_trace = [line for line in lines if line["trace_id"] == first["trace_id"]
                  and line["tool"] == WRITE_TOOL]
    report.check(group, "round 1 (pending) and round 2 (approved) share one trace_id",
                 [line["approval"].get("decision") for line in same_trace][:2] == ["pending", "approved"])
    kinds = sorted({(line["status"], line["approval"].get("by") or "-") for line in lines
                    if line["access"] == "write"})
    report.check(group, "refusals say who decided (server policy or a named approver)",
                 ("refused", "server") in kinds and ("refused", "planner:aisha") in kinds)


def check_inspector(report, url_read_only, url_writes):
    group = "clients"
    npx = shutil.which("npx")
    if npx is None:
        report.skip(group, "MCP Inspector CLI", "Node.js not installed (needs Node >= 22.19)")
        return 0
    base = [npx, "--yes", INSPECTOR_PACKAGE, "--cli", "--transport", "http", "--format", "json"]
    calls = 0

    def run(url, era, *method_args):
        command = base + ["--server-url", url, "--protocol-era", era] + list(method_args)
        started = time.monotonic()
        done = subprocess.run(command, capture_output=True, text=True, timeout=180,
                              encoding="utf-8", errors="replace")
        try:
            body = json.loads(done.stdout) if done.stdout.strip() else {}
        except ValueError:
            body = {}
        return done.returncode, body, time.monotonic() - started

    for era in ("modern", "legacy"):
        code, body, seconds = run(url_read_only, era, "--method", "tools/list")
        names = [tool["name"] for tool in (body.get("result") or {}).get("tools", [])]
        report.check(group, f"Inspector {era} era: tools/list exit 0, three read tools",
                     code == 0 and sorted(names) == sorted(READ_TOOLS), f"exit {code}, {seconds:.0f} s")

    code, body, seconds = run(url_read_only, "modern", "--method", "tools/call",
                              "--tool-name", "get_equipment", "--tool-args-json", '{"tag": "P-1201A"}')
    calls += 1
    structured = (body.get("result") or {}).get("structuredContent") or {}
    report.check(group, "Inspector: tools/call get_equipment exit 0, P-1201A",
                 code == 0 and structured.get("tag") == "P-1201A", f"exit {code}")

    arguments = json.dumps(new_work_order("INC-009740"))
    code, body, seconds = run(url_writes, "modern", "--method", "tools/call",
                              "--tool-name", WRITE_TOOL, "--tool-args-json", arguments)
    calls += 1
    report.check(group, "Inspector CLI (no forms): the write is refused, exit 5",
                 code == 5 and "elicitation" in text_of(body.get("result") or {}), f"exit {code}")
    return calls


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def tool_calls_sent(*wires):
    total = 0
    for wire in wires:
        for exchange in wire.exchanges:
            # A header rejection (-32020, -32022) is answered by the HTTP layer
            # before any middleware runs: that request never became a tool call.
            code = (exchange["response"].get("error") or {}).get("code")
            reached_server = code not in (-32020, -32022)
            if exchange["request"]["method"] == "tools/call" and reached_server:
                total += 1
    return total


def main():
    parser = argparse.ArgumentParser(description="Prove the MCP server works.")
    parser.add_argument("--module", default="services.mcp_server_reference.server",
                        help="the server module to test (python -m <module>)")
    parser.add_argument("--inspector", action="store_true",
                        help=f"also run the official MCP Inspector CLI ({INSPECTOR_PACKAGE})")
    parser.add_argument("--erp-port", type=int, default=8010)
    parser.add_argument("--port", type=int, default=8110,
                        help="read-only server port; the writes server uses port + 1")
    parser.add_argument("--verbose", action="store_true", help="print every HTTP exchange")
    parser.add_argument("--transcript", type=Path,
                        help="save every request and reply (with headers) to this JSON file")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="oq_mcp_test_"))
    erp_key = "lab-" + secrets.token_hex(12)
    audit_read_only = workdir / "audit_read_only.jsonl"
    audit_writes = workdir / "audit_writes.jsonl"
    env = {"MOCK_ERP_URL": f"http://127.0.0.1:{args.erp_port}", "MOCK_ERP_API_KEY": erp_key}
    print("=" * WIDTH)
    print(f"Testing {args.module}")
    print(f"Scratch folder (logs, audit files): {workdir}")
    print("=" * WIDTH)

    started = time.monotonic()
    servers = []
    erp = None
    try:
        erp = start_erp(port=args.erp_port, api_key=erp_key, log_path=workdir / "erp.log")
        servers.append(start_in_background(port=args.port, module=args.module, env=env,
                                           audit_log=audit_read_only,
                                           log_path=workdir / "mcp_read_only.log"))
        servers.append(start_in_background(port=args.port + 1, module=args.module, env=env,
                                           enable_writes=True, audit_log=audit_writes,
                                           log_path=workdir / "mcp_writes.log"))
    except RuntimeError as error:
        print(f"Could not start the servers: {error}")
        for server in servers:
            stop(server)
        if erp is not None:
            stop_erp(erp)
        return 2
    read_only, writes = servers
    print()

    report = Report()
    quiet = not args.verbose
    wire_ro = McpWire(read_only.url, client_name="inspector-test-ro", quiet=quiet)
    wire_rw = McpWire(writes.url, client_name="inspector-test-rw", quiet=quiet)
    try:
        check_protocol(report, wire_ro, read_only.url)
        tools = check_tool_list(report, wire_ro, expect_write=False)
        check_reads(report, wire_ro, tools)
        check_read_only_default(report, wire_ro)
        check_tool_list(report, wire_rw, expect_write=True)
        formless = check_write_gate(report, wire_rw, erp.base_url, erp_key)
        burst = check_rate_limit(report, writes.url)
        sdk_calls = check_official_client(report, writes.url)
        inspector_calls = 0
        if args.inspector:
            inspector_calls = check_inspector(report, read_only.url, writes.url)
        else:
            report.skip("clients", "MCP Inspector CLI", "add --inspector to run it (needs Node)")

        ro_calls = tool_calls_sent(wire_ro) + (1 if args.inspector else 0)
        rw_calls = tool_calls_sent(wire_rw, formless, burst) + sdk_calls + (1 if args.inspector else 0)
        check_audit(report, audit_read_only, ro_calls, erp_key, [wire_ro], "read-only")
        lines = check_audit(report, audit_writes, rw_calls, erp_key, [wire_rw, formless, burst],
                            "writes")
        check_audit_story(report, lines)
    finally:
        for server in servers:
            stop(server)
        stop_erp(erp)

    if args.transcript:
        args.transcript.parent.mkdir(parents=True, exist_ok=True)
        args.transcript.write_text(json.dumps({"read_only": wire_ro.exchanges,
                                               "writes": wire_rw.exchanges}, indent=1),
                                   encoding="utf-8")
        print(f"Transcript: {args.transcript}")

    seconds = time.monotonic() - started
    print("=" * WIDTH)
    print(f"{len(report.rows)} checks: {report.count('PASS')} PASS, {report.count('FAIL')} FAIL, "
          f"{report.count('SKIP')} SKIP, in {seconds:.1f} s.")
    print(f"Audit logs: {workdir}")
    return 1 if report.count("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
