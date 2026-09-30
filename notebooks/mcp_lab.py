"""Helpers for lab 11a: what a model is allowed to do, and who decides.

Thin on purpose. The server is the repo's own reference MCP server - the same one
the room builds in S26 - and the process handling is its own launch.py. Nothing
here reimplements MCP; it just makes the notebook cells one line each.

    import mcp_lab as mcp
    mcp.start(writes=False)
    mcp.tools()
    mcp.call("get_equipment", tag="P-1201A")
    mcp.audit()

Synthetic throughout: the mock ERP's data is generated, no real OQ material.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.mcp_server_reference import launch as mcp_launch   # noqa: E402
from services.mock_erp import launch as erp_launch               # noqa: E402

# Two ports on purpose: the read-only server and the writes-enabled one run at the
# SAME TIME, from the same server file. That is the whole lesson - a client cannot tell
# them apart from its side, and only the way each was started decides what it offers.
READ_ONLY_PORT = int(os.environ.get("OQ_MCP_PORT", "8100"))
WRITES_PORT = READ_ONLY_PORT + 1
ERP_PORT = int(os.environ.get("OQ_ERP_PORT", "8000"))
AUDIT = Path(os.environ.get("OQ_MCP_AUDIT", REPO_ROOT / "outputs" / "11a" / "audit.jsonl"))

# What each tool is allowed to do. The server owns this list; it is repeated here only
# so the notebook can show it beside the tool names without importing the server.
ACCESS = {"get_equipment": "read", "get_maintenance_history": "read",
          "list_work_orders": "read", "raise_work_order": "WRITE"}

_servers: dict[str, object] = {}


def start(quiet: bool = False):
    """Start the mock ERP and BOTH servers: one read-only, one with writes enabled."""
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    if AUDIT.exists():
        AUDIT.unlink()
    erp_launch.start_in_background(port=ERP_PORT)
    _servers["read_only"] = mcp_launch.start_in_background(
        port=READ_ONLY_PORT, enable_writes=False, audit_log=str(AUDIT))
    _servers["writes"] = mcp_launch.start_in_background(
        port=WRITES_PORT, enable_writes=True, audit_log=str(AUDIT))
    if not quiet:
        print()
        for name, server in _servers.items():
            print(f"{name:10s} {server.url}   {len(server.info['tools'])} tools")
        print("\nSame server file. Same machine. Started two different ways.")
    return _servers


def stop(quiet: bool = False):
    for name, server in list(_servers.items()):
        try:
            mcp_launch.stop(server)
        except Exception:
            pass
        _servers.pop(name, None)
    if not quiet:
        print("servers stopped")


def _post(method: str, params: dict | None = None, server: str = "read_only") -> dict:
    meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "oq-lab-11a", "version": "1"},
            # A client that cannot show a person a form is refused the write outright -
            # the server checks this before the tool runs. Declaring it is what makes the
            # approval round below possible.
            "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}}}
    body = {"jsonrpc": "2.0", "id": 1, "method": method,
            "params": {**(params or {}), "_meta": meta}}
    headers = {"Content-Type": "application/json",
               "Accept": "application/json, text/event-stream",
               "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method}
    if method == "tools/call":
        headers["Mcp-Name"] = (params or {}).get("name", "")
    request = urllib.request.Request(_url(server), data=json.dumps(body).encode(),
                                     method="POST", headers=headers)
    with urllib.request.urlopen(request, timeout=60) as reply:
        payload = json.loads(reply.read().decode())
    if "error" in payload:
        return {"error": payload["error"].get("message", str(payload["error"]))}
    return payload.get("result", {})


def _url(server: str = "read_only") -> str:
    if server not in _servers:
        raise RuntimeError("No servers running. Call mcp_lab.start() first.")
    return _servers[server].url


def tools(server: str = "read_only") -> str:
    """Every tool this server offers a client, and what each one is allowed to do."""
    names = [t["name"] for t in _post("tools/list", server=server)["tools"]]
    width = max(len(n) for n in names)
    lines = [f"{server}: {len(names)} tools offered"]
    for name in names:
        lines.append(f"   {name.ljust(width)}   {ACCESS.get(name, '?')}")
    missing = [n for n in ACCESS if n not in names]
    for name in missing:
        lines.append(f"   {name.ljust(width)}   {ACCESS[name]}  <- NOT offered")
    return "\n".join(lines)


def call(tool: str, server: str = "read_only", **arguments) -> str:
    """Call a tool. Returns what a client would see - the result, or the refusal."""
    result = _post("tools/call", {"name": tool, "arguments": arguments}, server=server)
    if "error" in result:
        return f"REFUSED BEFORE THE TOOL RAN\n   {result['error']}"
    texts = [block.get("text", "") for block in result.get("content", [])
             if block.get("type") == "text"]
    body = "\n".join(t for t in texts if t).strip()
    if result.get("resultType") == "input_required":
        return f"APPROVAL REQUIRED\n   {body[:400]}"
    if result.get("isError"):
        return f"REFUSED\n   {body[:400]}"
    return body[:600] or json.dumps(result.get("structuredContent", {}))[:600]


def audit(count: int = 3) -> str:
    """The last few audit lines, in the governance pack's own fields."""
    if not AUDIT.exists():
        return f"no audit log yet at {AUDIT}"
    rows = [json.loads(line) for line in AUDIT.read_text().splitlines() if line.strip()]
    if not rows:
        return "audit log is empty"
    out = []
    for row in rows[-count:]:
        approval = row.get("approval") or {}
        out.append(f"{row.get('tool'):<22} access={row.get('access'):<6} "
                   f"status={row.get('status'):<8} approval={approval.get('decision', '-')}")
    return "\n".join(out)


# The arguments a real work order needs. Kept here so the notebook cell stays one line.
WORK_ORDER = dict(equipment_tag="P-1201A", work_type="corrective", priority=2,
                  title="Replace weeping mechanical seal",
                  description="Seal weeping at the outboard end, noted on rounds.",
                  requested_by="planner:salim", source_ticket="INC-004412")


def request_write(server: str = "writes") -> str:
    """Ask to raise a work order. On the writes server this returns the approval form."""
    result = _post("tools/call", {"name": "raise_work_order", "arguments": WORK_ORDER},
                   server=server)
    if result.get("resultType") != "input_required":
        return call("raise_work_order", server=server, **WORK_ORDER)
    form = result["inputRequests"]["approval"]["params"]["message"]
    _pending[server] = result
    return "A PERSON IS ASKED FIRST. The server sent this form back:\n\n" + form


_pending: dict[str, dict] = {}


def answer(decision: str, approver: str, reason: str, server: str = "writes") -> str:
    """Answer the approval form: decision is "approve" or "reject".

    Round two of the same call - the server's sealed requestState is echoed back
    exactly, which is how it knows this answer belongs to that request and to no other.
    """
    pending = _pending.get(server)
    if pending is None:
        return "nothing is waiting for an answer - run request_write() first"
    result = _post("tools/call",
                   {"name": "raise_work_order", "arguments": WORK_ORDER,
                    "inputResponses": {"approval": {
                        "action": "accept",
                        "content": {"decision": decision, "approver": approver,
                                    "reason": reason}}},
                    "requestState": pending["requestState"]},
                   server=server)
    _pending.pop(server, None)
    texts = [b.get("text", "") for b in result.get("content", []) if b.get("type") == "text"]
    body = "\n".join(t for t in texts if t).strip()
    if result.get("isError"):
        return f"REFUSED\n   {body[:400]}"
    structured = result.get("structuredContent") or {}
    if structured:
        return (f"WRITTEN. The ERP created work order "
                f"{structured.get('work_order_id', '?')} with status "
                f"{structured.get('status', '?')}, approved_by {structured.get('approved_by', '?')}.")
    return body[:400]
