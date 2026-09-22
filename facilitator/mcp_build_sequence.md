# S26 build sequence: a custom MCP server, typed along in 80 minutes

Day 5, Thursday 1 October, 08:30 to 09:50. Guided class build: Ritesh
types on the projector, groups type the same into their own file, and
after every step everyone runs the same command and sees the same new
thing. At the end each group has `oq-erp-mcp`: the reference MCP server
in `services/mcp_server_reference/`, wrapping the mock ERP, built to the
MCP 2026-07-28 specification.

| | |
|---|---|
| What the room builds | `s26_server.py` in the repo root: 3 read tools, 1 gated write, an audit line per call |
| What they import, not type | `erp_client.py` (the ERP over HTTP, key from the environment), `audit.py` (the audit middleware), `approval.py` (the approval as a Multi Round-Trip Request), `launch.py` (serve) |
| Checkpoints | `services/mcp_server_reference/steps/step1_first_tool.py` ... `step4_audit.py`, then `services/mcp_server_reference/server.py`. Each is a complete server; copying one over `s26_server.py` puts a group at that step |
| Stack | `mcp==2.2.0` (the official Python SDK, implements 2026-07-28), `fastapi==0.141.1`, `uvicorn==0.52.4`, all already in `requirements.txt`. Nothing new to install |
| Optional | Node.js >= 22.19 for the MCP Inspector (`npx @modelcontextprotocol/inspector@2.7.0`). Not needed for any step |
| Pre-baked output of every step | `facilitator/prebaked_outputs/mcp_server/` |

## The room: three terminals per laptop

| Terminal | Runs | Started |
|---|---|---|
| A | the mock ERP: `uvicorn services.mock_erp.main:app` | once, step 0; restarted once in step 5 |
| B | your server: `python s26_server.py` | after every step: Ctrl+C, up-arrow, Enter |
| C | the client: `python -m services.mcp_server_reference.call ...` | the checks |

All three from the repo root, in the environment from `requirements.txt`.
Windows commands shown (they work in both cmd and PowerShell, except
setting a variable: cmd `set NAME=value`, PowerShell `$env:NAME="value"`).
On a Mac or Linux use `cp` for `copy`, `cat` for `type`, `grep` for
`findstr` and `export NAME=value`.

**Catching up.** Anyone behind at the start of a step copies the
previous checkpoint and carries on:
`copy services\mcp_server_reference\steps\step3_more_reads.py s26_server.py`.
It is a complete server; nothing else is needed. Say this out loud at
08:35 and again at every step.

---

## Timetable

| Step | Clock | Min | Adds (the one visible capability) | Typed | Checkpoint after it |
|---|---|---|---|---|---|
| 0 | 08:30 | 5 | Ready: ERP up, the SDK imports | 0 | — |
| 1 | 08:35 | 12 | A server with one tool; `server/discover` with no handshake | 20 lines | `steps/step1_first_tool.py` |
| 2 | 08:47 | 6 | The input is a contract: a bad tag is refused before the ERP is called | 6 | `steps/step2_typed_contract.py` |
| 3 | 08:53 | 9 | Three read tools, marked read-only; a cacheable, ordered tool list | 15 (+21 pasted) | `steps/step3_more_reads.py` |
| 4 | 09:02 | 10 | One audit line per tool call, whatever happens | 10 | `steps/step4_audit.py` |
| 5 | 09:12 | 5 | Secrets from the environment: the ERP key never in code or log | 0 | `steps/step4_audit.py` (no change) |
| 6 | 09:17 | 16 | The one write, gated: an approval as a Multi Round-Trip Request | 26 (+12 pasted) | `server.py` |
| 7 | 09:33 | 7 | Try to get round the gate; every attempt refused and logged | 0 | `server.py` |
| 8 | 09:40 | 6 | Prove it: `test_inspector.py`, 62 checks | 0 | `server.py` |
| — | 09:46 | 4 | Buffer, then S27 at 09:50 | | |
| | | **80** | | **77 typed** | |

**If the room is behind at 09:17** (start of step 6): everyone copies
`server.py` over `s26_server.py` instead of typing step 6, and Ritesh
reads the new tool aloud. Step 6 goes from 16 minutes to about 8, and
the three MRTR exchanges - the point of the session - still happen on
every laptop. Do not cut step 6 itself; cut the typing.

---

## Step 0 (08:30, 5 min): ready

Terminal A:

```
uvicorn services.mock_erp.main:app
```

Terminal C:

```
python -c "import mcp, importlib.metadata as m; print('mcp', m.version('mcp'))"
python -m services.mock_erp.tour
```

**Correct:** `mcp 2.2.0`; the tour ends `All 29 replies had the expected status.`
Anything else: playbook entry 3 (pip install fails), entry 8 (ModuleNotFoundError), or
entry 14 / E18 (port 8000 in use).

**Say:** we are going to wrap this ERP so that an agent can use it
through MCP, and make the one dangerous call in it - raising a work
order - impossible without a named person saying yes.

## Step 1 (08:35, 12 min): a server with one tool

Create `s26_server.py` in the repo root and type:

```python
from mcp.server import MCPServer

from services.mcp_server_reference import erp_client
from services.mcp_server_reference.launch import run_from_command_line
from services.mock_erp.models import Equipment

SERVER_NAME = "oq-erp-mcp"
SERVER_VERSION = "0.1.0"


def build_server():
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP.",
    )

    @mcp.tool()
    def get_equipment(tag: str) -> Equipment:
        """One equipment master record by tag, with its open work orders."""
        record = erp_client.get(f"/equipment/{tag}")
        return Equipment.model_validate(record)

    return mcp


if __name__ == "__main__":
    run_from_command_line(build_server)
```

Terminal B: `python s26_server.py`. Terminal C:

```
python -m services.mcp_server_reference.call discover
python -m services.mcp_server_reference.call get_equipment tag=P-1201A
```

**Correct:** discover returns `supportedVersions: ["2026-07-28"]` and
`serverInfo` `oq-erp-mcp 0.1.0`; the call returns `structuredContent`
with `"description": "Crude transfer pump"`, `"site": "MRB"`.

**Point at the screen:** the request is ONE POST with three headers
(`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`) and a `_meta` block
carrying the version, the client's name and its capabilities. There
was no `initialize`, and the reply has no `Mcp-Session-Id`: 2026-07-28
is stateless, so any copy of this server behind a load balancer could
have answered. The headers exist so a gateway can route without
reading the body; the server checks they agree with it.

## Step 2 (08:47, 6 min): the input is a contract

Add the imports and the `Tag` type, and use it:

```python
from typing import Annotated

from pydantic import Field
from services.mock_erp.models import EQUIPMENT_TAG_PATTERN, Equipment

Tag = Annotated[str, Field(pattern=EQUIPMENT_TAG_PATTERN,
                           description="Equipment tag, upper case, e.g. P-1201A")]

    def get_equipment(tag: Tag) -> Equipment:
```

Restart B. Terminal C:

```
python -m services.mcp_server_reference.call list --brief
python -m services.mcp_server_reference.call get_equipment tag=pump-one --brief
```

**Correct:** `inputSchema.properties.tag` now has the `pattern` and the
`description`; `outputSchema` is the ERP's `Equipment` model. The bad
tag comes back `isError: true`, and the `[error]` lines under the reply
say `String should match pattern`; terminal A shows no request: the ERP
was never called.

**Say:** the type hints ARE the schema the model reads. A description
here is prompt text; a pattern here is a guard the model cannot talk
its way past.

## Step 3 (08:53, 9 min): three reads, marked read-only, a cacheable list

Type the new imports, `READ_ONLY`, the `cache_hints` and
`get_maintenance_history`; **paste** `list_work_orders` from
`steps/step3_more_reads.py` (its body is the same shape, with four
optional filters):

```python
from typing import Annotated, Literal

from mcp.server.caching import CacheHint
from mcp_types import ToolAnnotations
from services.mock_erp.models import (
    EQUIPMENT_TAG_PATTERN, TICKET_ID_PATTERN, Equipment, HistoryPage, WorkOrderPage,
)

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

        cache_hints={"tools/list": CacheHint(ttl_ms=300_000, scope="public"),
                     "server/discover": CacheHint(ttl_ms=300_000, scope="public")},

    @mcp.tool(annotations=READ_ONLY)          # on all three tools

    @mcp.tool(annotations=READ_ONLY)
    def get_maintenance_history(
        tag: Tag,
        limit: Annotated[int, Field(ge=1, le=50, description="How many records, newest first")] = 10,
    ) -> HistoryPage:
        """Completed maintenance on one piece of equipment, newest first."""
        page = erp_client.get("/maintenance-history", {"equipment_tag": tag, "limit": limit})
        return HistoryPage.model_validate(page)
```

Restart B. Terminal C:

```
python -m services.mcp_server_reference.call list --brief
python -m services.mcp_server_reference.call get_maintenance_history tag=P-1201A limit=2 --brief
```

**Correct:** three tools, each with `"readOnlyHint": true`; the list
reply carries `"ttlMs": 300000, "cacheScope": "public"`; the history
starts `MH-000224`, `WO-118305`, `2026-05-18`, `mechanical seal leak`.

**Say:** `ttlMs` is new in 2026-07-28: a client may cache the tool list
for five minutes, and because the order never changes, the model's
prompt cache stays warm. `readOnlyHint` is a hint to the client; the
next step shows the server does not trust its own hints either.

## Step 4 (09:02, 10 min): one audit line per tool call

Type the class table and the three lines that install the audit
middleware:

```python
from services.mcp_server_reference import audit, erp_client

TOOL_ACCESS = {
    "get_equipment": "read",
    "get_maintenance_history": "read",
    "list_work_orders": "read",
}

def build_server(audit_log_path=audit.DEFAULT_LOG_PATH):

    # One audit line per tool call - first on the list, so it sees everything.
    audit_log = audit.AuditLog(audit_log_path)
    mcp.middleware.insert(0, audit.AuditMiddleware(
        audit_log, SERVER_NAME, SERVER_VERSION, TOOL_ACCESS, writes_enabled=False))
```

Restart B. Terminal C:

```
python -m services.mcp_server_reference.call get_equipment tag=P-1201A --brief
python -m services.mcp_server_reference.call get_equipment tag=X-0000 --brief
python -m services.mcp_server_reference.call delete_everything --brief
type checkpoints\local\mcp_audit\tool_call.jsonl
```

**Correct:** three lines. `status` `ok` with `upstream` status 200;
`error` with upstream 404; `refused` with
`"approval": {"required": true, "decision": "rejected", "by": "server",
"reason": "'delete_everything' is not in this server's class table..."}`.
Every line has the 17 fields of governance template 5.1.2, in order.

**Say:** open `audit.py` and show `AuditMiddleware.__call__`: the line is
written in ONE place, around every tool, so a tool someone adds next
month cannot forget to log. The class table - not the annotation -
decides read or write, and a tool missing from it is treated as a
write. This is template 4's tool table and template 5's line, in code.

## Step 5 (09:12, 5 min): secrets from the environment

No code. Terminal A: Ctrl+C, then

```
set MOCK_ERP_API_KEY=s26-lab-key-7f3a
uvicorn services.mock_erp.main:app
```

Terminal C: `python -m services.mcp_server_reference.call get_equipment tag=P-1201A --brief`
-> `ERP said 401: The ERP refused the MCP server's key (401). Set
MOCK_ERP_API_KEY for the MCP server...`. Terminal B: Ctrl+C,
`set MOCK_ERP_API_KEY=s26-lab-key-7f3a`, `python s26_server.py`. Call
again: works. Then `findstr s26-lab-key checkpoints\local\mcp_audit\tool_call.jsonl`
finds nothing.

**Correct:** 401 sentence without the key, the pump with it, and the
key in no audit line and no reply. (Clear it afterwards:
`set MOCK_ERP_API_KEY=` in A and B and restart both, or keep it - the
remaining steps work either way.)

**Say:** the key lives in the server's environment (a `.env` locally,
the VM's secret store in production) and in one header in
`erp_client.py`. It is never a tool argument, so the model never sees
it and cannot leak it. This is an environment secret, not production
auth - OIDC is the talk.

## Step 6 (09:17, 16 min): the one write, gated

The write is `POST /work-orders`: it releases a work order to the site
crew at once, and the API cannot undo it. Under 2026-07-28 the server
may not call the client, so the approval is a **Multi Round-Trip
Request**: the first call returns the question (`input_required`), the
client asks a person, and calls again with the answer.

Type the small changes, **paste** the tool's signature from
`server.py`, and type its body:

```python
from mcp.server.mcpserver import Context
from mcp_types import InputRequiredResult, ToolAnnotations
from services.mcp_server_reference import approval, audit, erp_client
from services.mock_erp.models import (..., WorkOrder, WorkOrderPage)

    "raise_work_order": "write",                 # a new row in TOOL_ACCESS

GATED_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                              idempotent_hint=False, open_world_hint=False)

def build_server(enable_writes=False, audit_log_path=audit.DEFAULT_LOG_PATH):
        instructions="... of the mock ERP. Reads are free. raise_work_order needs a named approver.",
        request_state_security=approval.state_security(),
        ...  TOOL_ACCESS, writes_enabled=enable_writes))

    if enable_writes:

        @mcp.tool(annotations=GATED_WRITE)
        def raise_work_order(ctx: Context, equipment_tag: Tag, ...) -> WorkOrder | InputRequiredResult:
            """Raise a work order for the site crew. NEEDS A PERSON'S APPROVAL (a form)."""
            proposal = {"equipment_tag": equipment_tag, "work_type": work_type,
                        "priority": priority, "title": title, "description": description,
                        "requested_by": requested_by, "source_ticket": source_ticket}

            answer = approval.answer_in(ctx)
            if answer is None:
                # Round 1: show the person the exact request, and what we checked.
                equipment = erp_client.get(f"/equipment/{equipment_tag}")
                evidence = (f"{equipment['tag']} is '{equipment['description']}' at "
                            f"{equipment['site']}, criticality {equipment['criticality']}, "
                            f"status {equipment['status']}, open work orders: "
                            f"{', '.join(equipment['open_work_orders']) or 'none'}.")
                return approval.ask(ctx, proposal, evidence)

            # Round 2: only an approval this server asked for, for these arguments, once.
            approver = approval.check(ctx, proposal, answer)
            created = erp_client.post("/work-orders", {**proposal, "approved_by": approver})
            return WorkOrder.model_validate(created)
```

First show the default. Restart B as it was (`python s26_server.py`);
terminal C, with the file `facilitator/prebaked_outputs/mcp_server/work_order.json`:

```
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator\prebaked_outputs\mcp_server\work_order.json --brief
```

-> `Refused: 'raise_work_order' writes to the ERP and this server was
started READ-ONLY`. Now restart B with `python s26_server.py --enable-writes`
and run the same command **without** `--brief` and without answers, so
it asks you:

```
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator\prebaked_outputs\mcp_server\work_order.json
```

**Correct - the three exchanges:**

1. `tools/call` -> `"resultType": "input_required"`, `inputRequests.approval`
   is an `elicitation/create` form whose message contains the exact
   `POST /work-orders` body, plus a `requestState` of about 500 characters.
2. The client shows the form (no network traffic); answer `approve`,
   `planner:salim`, a reason. The client calls the same tool AGAIN, new
   JSON-RPC id, same arguments, plus `inputResponses` and the
   `requestState` echoed exactly.
3. -> `"resultType": "complete"`, `structuredContent` a work order
   `WO-195893`, `"status": "released"`, `"approved_by": "planner:salim"`.
   Then `call list_work_orders source_ticket=INC-004412 --brief` finds it:
   the write landed.

(The first write after an ERP start is always `WO-195893`; a second
approval for the same ticket gets the ERP's `409` - use another
`source_ticket` in the file.)

**Say:** read `approval.py`'s docstring aloud. The `requestState` is
sealed by the SDK (AES-GCM), bound to this tool and these exact
arguments, and expires in 10 minutes; `approval.check` adds the rule
the spec leaves to us - an approval is used once. And what it does NOT
prove: that a human answered. That is the host's job, and in production
its login.

## Step 7 (09:33, 7 min): try to get round the gate

Terminal C, with writes still enabled. `work_order_2.json` is the same
request for another ticket (`INC-004413`), so the ERP's own duplicate
check (`409` for a ticket that already has a work order) does not
answer instead of the gate:

```
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator\prebaked_outputs\mcp_server\work_order_2.json --brief --reject planner:aisha --reason "duplicate of the job raised in step 6"
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator\prebaked_outputs\mcp_server\work_order_2.json --brief --no-forms
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator\prebaked_outputs\mcp_server\work_order_2.json --brief --approve intern:bob --reason "looks fine"
type checkpoints\local\mcp_audit\tool_call.jsonl
```

**Correct:** `rejected by planner:aisha: duplicate ... (nothing
written)`; `this client did not declare the elicitation (form)
capability, so it cannot show a person the approval form`; `'intern:bob'
is not on the approver list (OQ_MCP_APPROVERS)`. In the log: each
attempt is a `pending` line followed by a `refused` line whose
`approval.by` says who decided - the planner, or `server`.

Groups that finish early: change one character of a `requestState` by
hand (the `test_inspector.py` source shows how) and see JSON-RPC
`-32602 Invalid or expired requestState` - the SDK's seal - and the
`refused` line the audit middleware still writes for it. The same error
appears when a group restarts the server between the two rounds:
playbook E20.

## Step 8 (09:40, 6 min): prove it

Stop B (the script starts its own copies on other ports). Terminal C:

```
python services/mcp_server_reference/test_inspector.py --module s26_server
```

**Correct:** `59 checks: 58 PASS, 0 FAIL, 1 SKIP` in about 15 seconds
(the SKIP is the Inspector). With Node.js installed, add `--inspector`:
`62 checks: 62 PASS` in about 20 seconds - the official MCP Inspector
CLI 2.7.0 lists and calls the tools in both protocol eras, and is itself
refused the write because it cannot show a form.

**Say:** this is what "proves the server works before anything connects
to it" means: the checks a person would click through in the MCP
Inspector, plus the governance ones, rerunnable in 15 seconds after
every change. It is also the evidence governance template 3.3 and 4.2
ask for ("tested on, how").

For the MCP Inspector's own window (optional, not part of the timing):
`npx @modelcontextprotocol/inspector@2.7.0`, transport Streamable HTTP,
URL `http://127.0.0.1:8100/mcp`.

---

## Timing: what was measured and what was not

Measured on the build laptop (Windows 11, Python 3.11, 2026-09-22) by
walking the sequence as a participant: each checkpoint copied over
`s26_server.py`, the server started, the step's commands run. Machine
time only - `docs/timing_log.md` has the table.

| Step | Server start | The step's commands | Lines typed (not blank, not comments) |
|---|---|---|---|
| 1 | 3.3 s | 0.4 s | 20 |
| 2 | 1.3 s | 0.4 s | 6 |
| 3 | 1.3 s | 0.5 s | 36, of which 21 pasted |
| 4 | 1.3 s | 0.5 s | 10 |
| 5 | 3.3 s, then 1.3 s | 0.4 s | 0 |
| 6 | 3.3 s, then 1.3 s | 0.6 s | 38, of which 12 pasted |
| 7 | 1.3 s | 0.6 s | 0 |
| 8 | (starts its own) | 18.8 s with `--inspector`, 62 / 62 PASS | 0 |
| **Whole walk** | | **43.5 s** of machine time (a first walk: 62 s) | 110 lines, 77 typed |

The committed run is `facilitator/prebaked_outputs/mcp_server/timings.json`,
with every step's transcript beside it (`step1.txt` ... `step8.txt`).

**Does it fit? On paper, yes, with little slack; it has not been
measured with people.** The machine is never the bottleneck: the
slowest command is the 15-second proof. The session's length is typing
and reading. At an assumed two lines a minute for a room typing along
from a projector, the 77 typed lines are about 40 minutes; eight runs
of "restart, call, read the output together" at about three minutes
each are 24; setup is 5. That is 69 of the 80 minutes, which leaves the
11-minute buffer the timetable shows (4 at the end plus the slack inside
the steps). Two lines a minute is an assumption, not a measurement. If
the room types at one line a minute, the typing alone is 77 minutes and
the session does not fit - which is why steps 3 and 6 paste their
longest blocks, and why the 09:17 rule above exists. Ritesh's Day 5 dry
run is the first real measurement: time steps 1 and 4 with a stopwatch
and apply the 09:17 rule from what they show.
