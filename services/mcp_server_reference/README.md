# Reference MCP server: `oq-erp-mcp`

The MCP server the room builds in Day 5 S26, over the mock ERP
(`services/mock_erp/`). Built to the **MCP 2026-07-28 specification**
with the official Python SDK, `mcp==2.2.0`.

- **Typed tools.** Three reads and one write, every one with an input
  and an output schema taken from its Python types (the outputs are the
  mock ERP's own pydantic models).
- **Read-only by default.** The write tool does not exist unless a
  person starts the server with `--enable-writes`.
- **The write is gated.** `raise_work_order` asks a person first, as a
  Multi Round-Trip Request (`input_required`), and writes only on a
  retry that carries an approval the server asked for, for exactly
  those arguments, from an approver on its list, once.
- **Secrets from the environment.** The ERP key is read from
  `MOCK_ERP_API_KEY` and goes in one HTTP header; never a tool
  argument, never in a result or a log line.
- **One audit line per tool call**, in the shape of governance template
  5.1.2, written by one middleware around every tool.

The 80-minute type-along that builds it: `facilitator/mcp_build_sequence.md`.
The proof it works: `test_inspector.py` (62 checks).

## Run it

Three terminals, all in the repo root:

```
uvicorn services.mock_erp.main:app                                   # A: the ERP, port 8000
python -m services.mcp_server_reference.server                       # B: read-only, port 8100
python -m services.mcp_server_reference.call get_equipment tag=P-1201A   # C: a call, every byte shown
```

With the write: `python -m services.mcp_server_reference.server --enable-writes`, then

```
python -m services.mcp_server_reference.call raise_work_order --args-file facilitator/prebaked_outputs/mcp_server/work_order.json
```

and answer the approval form at the prompt (or add `--approve planner:salim --reason "..."`).

Flags (`server.py` and every step file): `--host` (127.0.0.1), `--port`
(8100), `--enable-writes`, `--audit-log PATH` (default
`checkpoints/local/mcp_audit/tool_call.jsonl`, git-ignored),
`--transport http|stdio` (stdio for a host that launches the server
itself).

Prove it before anything connects to it:

```
python services/mcp_server_reference/test_inspector.py               # 59 checks, ~15 s
python services/mcp_server_reference/test_inspector.py --inspector   # + the MCP Inspector CLI, 62 checks, ~20 s
python services/mcp_server_reference/test_inspector.py --module s26_server   # a participant's own file
```

It starts its own fresh ERP (with a random API key) on port 8010 and two
servers on 8110 (read-only) and 8111 (writes), each with a new audit
log, and stops them all at the end. Exit 0 = no FAIL.

## Run it in a notebook (Colab)

A cell cannot run a server in the foreground, so `launch.py` starts it
as a child process (the same pattern as the mock ERP). After the
standard environment cell (`docs/notebook_conventions.md`), which clones
the repo and makes it the working directory:

```python
%pip install -q mcp==2.2.0
```

```python
# The ERP and the MCP server in the background: this runtime plays the part of the VM.
from services.mock_erp.launch import start_in_background as start_erp
from services.mcp_server_reference.launch import start_in_background as start_mcp

erp = start_erp(port=8000)
mcp_server = start_mcp(port=8100, enable_writes=True, audit_log="/tmp/tool_call.jsonl")
print(mcp_server.url, mcp_server.info["tools"])
```

```python
!python -m services.mcp_server_reference.call get_equipment tag=P-1201A --brief
```

```python
!python -m services.mcp_server_reference.call raise_work_order --args-file facilitator/prebaked_outputs/mcp_server/work_order.json --approve planner:salim --reason "seal history checked" --brief
```

```python
!cat /tmp/tool_call.jsonl
```

Colab preinstalls everything else the server needs. Running the start
cell again reuses both servers; a restarted runtime starts clean (the
children die with the kernel). Measured in a `python:3.12-slim`
container through a real Jupyter kernel (2026-09-22): 13 s for all five
cells including the `%pip install`, no kernel restart needed, the write
landed, three audit lines. **Not run on Colab itself** - owed.

## Tools

| Tool | Class (`TOOL_ACCESS`) | Annotations | ERP call | Output |
|---|---|---|---|---|
| `get_equipment(tag)` | read | `readOnlyHint: true` | `GET /equipment/{tag}` | `Equipment` |
| `get_maintenance_history(tag, limit=10)` | read | `readOnlyHint: true` | `GET /maintenance-history` | `HistoryPage` |
| `list_work_orders(equipment_tag?, status?, source_ticket?, limit=10)` | read | `readOnlyHint: true` | `GET /work-orders` | `WorkOrderPage` |
| `raise_work_order(equipment_tag, work_type, priority, title, description, requested_by, source_ticket?)` | **write**, only with `--enable-writes` | `readOnlyHint: false`, `destructiveHint: false` | `POST /work-orders` after an approval | `WorkOrder`, or `input_required` |

`tag` must match `^[A-Z]{1,3}-[0-9]{4}[A-Z]?$` (`P-1201A`), so a bad tag
is refused by the schema before the ERP is called. An ERP error comes
back as a tool result with `isError: true` and the ERP's own sentence
(`ERP said 404: No equipment with tag X-0000...`), which the model can
read and act on.

**The class table decides, not the annotations.** Annotations are hints
the spec says a client must not trust; `TOOL_ACCESS` in `server.py` is
what the server enforces. A tool missing from the table is refused as
if it were a write.

## The gate: an approval as a Multi Round-Trip Request

2026-07-28 removed server-initiated requests: a server cannot push an
`elicitation/create` to the client in the middle of a call any more. A
tool that needs a person's answer **returns** the question, and the
client retries. Exactly what goes over the wire (from a real run,
`facilitator/prebaked_outputs/mcp_server/step6b.txt`):

```
1  -> tools/call raise_work_order {arguments}
   <- {"resultType": "input_required",
       "inputRequests": {"approval": {"method": "elicitation/create",
            "params": {"mode": "form", "message": "APPROVAL NEEDED ... POST /work-orders {...}",
                       "requestedSchema": {decision: approve|reject,
                                           approver: one of OQ_MCP_APPROVERS, reason}}}},
       "requestState": "v1.LWDNg...  (about 500 characters, sealed)"}
   (the client shows the person the form)
2  -> tools/call raise_work_order {the same arguments}, a new JSON-RPC id,
      "inputResponses": {"approval": {"action": "accept",
                         "content": {"decision": "approve", "approver": "planner:salim", "reason": "..."}}},
      "requestState": "<echoed exactly>"
   <- {"resultType": "complete", "structuredContent": {"work_order_id": "WO-195893",
       "status": "released", "approved_by": "planner:salim", ...}}
3  -> tools/call list_work_orders {"source_ticket": "INC-004412"}  finds WO-195893
```

Who guarantees what:

| Rule | Where | Refused how |
|---|---|---|
| The `requestState` was minted by this server, for `tools/call` of this tool with these exact arguments, within 10 minutes, for this audience | The SDK's `RequestStateBoundary` (AES-256-GCM, `approval.state_security()`) | JSON-RPC `-32602 Invalid or expired requestState`; the audit line says `refused` |
| An answer arrived with a `requestState` at all | `approval.check` | tool result `isError`, `refused` |
| The state's argument hash matches (belt and braces) | `approval.check` | `refused` |
| Each approval is used **once** (the spec says one-time use MUST be enforced server-side) | `approval.check`, a nonce set in memory | `refused: ... already used once` |
| The approver is on `OQ_MCP_APPROVERS`; decision and reason are present | `approval.check` | `refused` |
| The client declared the elicitation (form) capability (the spec: never send an `inputRequests` a client did not declare) | `approval.ask` | `refused`, no form sent |
| Writes are switched on at all | `AuditMiddleware.refusal_for` | `refused: ... started READ-ONLY` |
| At most 10 write calls a minute per caller (each round counts); 120 reads | `AuditMiddleware` rate limiter | `refused: rate limit` |

**What the gate does not prove: that a human answered.** It proves the
server asked about these exact arguments and got a decision from the
client within 10 minutes, naming an allowed approver. Who clicked is the
host application's job, and in production its login (OIDC, a talk topic,
BUILD_SPEC section 14). The mock ERP records `approved_by` and cannot
check it either; the audit line is where a false approval would be found.

## The audit line

One JSON line per `tools/call`, appended to the audit log, written by
`audit.AuditMiddleware`. It is installed first on the server's
middleware list, outside the SDK's own request-state check, so it also
logs the calls the SDK rejects before any tool runs. The fields are
governance template 5.1.2, in order, and nothing else
(`tests/test_mcp_server.py` reads them from the template):

```json
{"ts": "2026-09-22T19:41:10.770Z", "event": "tool_call", "trace_id": "e350bddbd5bd9ad97bec35c74ac52101",
 "request_id": 2, "server": "oq-erp-mcp", "server_version": "0.1.0",
 "caller": "unverified-client:oq-wire-client", "tool": "raise_work_order", "access": "write",
 "args_sha256": "bcda2bbf896b5ebc...", "args_redacted": {"equipment_tag": "P-1201A", "work_type": "corrective",
   "priority": 2, "...": "...", "source_ticket": "INC-004412"},
 "approval": {"required": true, "decision": "approved", "by": "planner:salim",
              "ts": "2026-09-22T19:41:10.771Z", "reason": "seal history checked"},
 "status": "ok", "upstream": {"system": "mock_erp", "status": 201},
 "result_sha256": "7bbdf5da545e00e0...", "records": 1, "ms": 8.1}
```

(Round 2 of the approval in the step walk, `facilitator/prebaked_outputs/mcp_server/audit_after_walk.jsonl`,
wrapped and shortened here.)

- `status`: `ok`, `error` (the tool or the ERP failed), `refused`
  (nothing written on purpose). The first round of an approval is
  `refused` with `"decision": "pending"`: the question went out.
- `approval.by` is the approver, or `"server"` when the server's own
  rules refused (read-only, forged, replayed, rate limit), with the rule
  as `reason`.
- `trace_id` comes from `_meta.traceparent`, so both rounds of one
  approval join up. **Only if the client sends one:** `call.py` does;
  the SDK's own `Client` (2.2.0, no OpenTelemetry set up) does not, and
  then each round gets a fresh id (measured). Join on `args_sha256` instead.
- `caller` is `unverified-client:<clientInfo.name>`: self-reported, and
  the line says so. With real authorisation it becomes the principal.
- `args_redacted` drops any argument whose name looks like a secret and
  cuts text over 200 characters; the ERP key is never an argument.

## Settings (environment or the repo-root `.env`)

| Variable | Default | What |
|---|---|---|
| `MOCK_ERP_URL` | `http://127.0.0.1:8000` | where the ERP answers |
| `MOCK_ERP_API_KEY` | empty | the ERP's key, if it was started with one. A secret |
| `OQ_MCP_APPROVERS` | `planner:salim,planner:aisha,planner:nasser` | who may approve a work order (governance template 4.4) |
| `OQ_MCP_STATE_KEY` | empty = a fresh key per start | seals the approval state; set it (32+ characters) so a restart or a second copy accepts a pending approval (tested: an approval asked before a restart wrote after it). A secret. Caveat: the list of used approvals is in memory, so with a shared key a restart within 10 minutes forgets it; production needs a shared store |
| `MCP_SERVER_URL` | `http://127.0.0.1:8100/mcp` | where `call.py` sends requests |

## Files

| File | What | Typed in S26? |
|---|---|---|
| `server.py` | the server: tools, class table, wiring | yes (steps 1-6) |
| `steps/step1_first_tool.py` ... `step4_audit.py` | the checkpoint after each step, each a complete server | no: copy one to catch up |
| `erp_client.py` | the ERP over HTTP; the key from the environment; notes the upstream status for the audit line | no |
| `audit.py` | the audit line, the class-table / read-only / rate-limit rules, as middleware | no (read in step 4) |
| `approval.py` | the approval: the form, the checks, one-time use, the sealing key | no (read in step 6) |
| `launch.py` | `serve`, `run_from_command_line`, `start_in_background` / `stop` for notebooks and tests | no |
| `call.py` | a hand-rolled 2026-07-28 client over plain HTTP that prints every header and body | no |
| `test_inspector.py` | the proof: protocol, tools, gate, audit, official clients | no (run in step 8) |

## Versions, and where they were checked (2026-09-22)

| What | Version | Source |
|---|---|---|
| MCP specification | 2026-07-28 (current) | modelcontextprotocol.io/specification/2026-07-28: changelog, basic/versioning, basic/transports/streamable-http, basic/patterns/mrtr, server/discover |
| Python SDK | `mcp==2.2.0`, with `mcp-types==2.2.0` | PyPI / github.com/modelcontextprotocol/python-sdk release v2.2.0; the installed package's source (`mcp/server/request_state.py`, `mcp/server/mcpserver/resolve.py`, `mcp/server/_streamable_http_modern.py`) was read, not assumed. v2.x implements 2026-07-28 and every earlier revision; 1.x does not |
| MCP Inspector | `@modelcontextprotocol/inspector@2.7.0` (2026-09-16, newest) | npm registry; its `--help` and `docs/cli-smoke-testing.md` (exit codes 0-6, `--format json`, `--protocol-era`). Needs Node >= 22.19 |

`mcp==2.2.0` was already pinned in `requirements.txt` (P0). Colab does
not preinstall `mcp`; it preinstalls every one of its dependencies
except `mcp-types` and `sse-starlette` (checked against
googlecolab/backend-info `pip-freeze.gpu.txt`).

## Behaviour worth knowing (all observed, 2026-09-22)

- **The endpoint is dual-era.** The SDK serves 2025-11-25 clients
  (`initialize`, sessions) on the same URL. The Inspector connects in
  both eras. A request with no `MCP-Protocol-Version` header is treated
  as legacy: a bare GET gets `400 Missing session ID` with an
  `mcp-session-id` header - that is the old protocol answering. A GET
  that says 2026-07-28 gets `405`, `Allow: POST`.
- **`server/discover` advertises `prompts` and `resources`** (the SDK's
  defaults) although the server has none; both lists are empty.
- **The Inspector CLI declares no elicitation capability**, so the
  server refuses it the write (exit 5) instead of sending it a form it
  cannot show. That is the spec working, not a bug.
- **The Inspector CLI 2.7.0 on Windows crashes on an unknown tool
  name**: it prints `tool_not_found` correctly, then `Assertion failed:
  !(handle->flags & UV_HANDLE_CLOSING)` and exits 127 instead of 5
  (Node 24.11, three runs out of three). The server never sees the call.
  Playbook E19.
- The first write after an ERP start is always `WO-195893`; a second
  approved write for the same `source_ticket` gets the ERP's `409`
  (`status: "error"`, `upstream` 409 in the audit line).

## What was tested, and what was not

| | |
|---|---|
| Windows 11, Python 3.11, the pinned stack | `test_inspector.py --inspector`: 62 / 62 PASS; the 80-minute sequence walked twice with every checkpoint (machine time 62 s and 44 s); `tests/test_mcp_server.py` |
| The official Python SDK client (`mcp.Client`, mode 2026-07-28) | does the whole approval by itself through `elicitation_callback` (PASS) |
| MCP Inspector CLI 2.7.0, modern and legacy era | lists and calls the tools (PASS) |
| MCP Inspector web UI | **NOT tested.** It starts; nobody clicked through an approval form in it |
| Linux: `python:3.12-slim` and `python:3.13-slim` containers (Colab's two images), only the pinned packages this server needs | `test_inspector.py` 58 / 58 + 1 SKIP (no Node in the container) and `tests/test_mcp_server.py` 24 / 24 on both; pip install 9 s. The notebook cells above through a Jupyter kernel on 3.12: clean, 13 s |
| Colab | **NOT run.** The container + kernel run is the same code path; the first real Colab run is owed |
| Mac | **NOT run** |
| A human room | **NOT timed.** See the timing section of `facilitator/mcp_build_sequence.md` |
