# Reference MCP server (S26): pre-baked output

The S26 type-along walked once as a participant would, on the build
laptop (Windows 11, Python 3.11, `mcp==2.2.0`, 2026-09-22): each
checkpoint in `services/mcp_server_reference/steps/` (then `server.py`)
copied over `s26_server.py` in the repo root, started, and the step's
commands from `facilitator/mcp_build_sequence.md` run against it, with
the mock ERP on port 8000.

| File | What it shows |
|---|---|
| `step1.txt` | `server/discover` with every header; `get_equipment P-1201A` |
| `step2.txt` | `tools/list` with the tag's pattern; a bad tag refused before the ERP is called |
| `step3.txt` | three read tools, `readOnlyHint`, `ttlMs`; history and work orders for P-1201A |
| `step4.txt` | an ok call, an ERP 404, an unknown tool refused - one audit line each |
| `step5a.txt`, `step5b.txt` | the ERP demands a key: the server without it (`ERP said 401`), then with it from the environment |
| `step6a.txt` | the write on a read-only server: refused |
| `step6b.txt` | **the three exchanges**: `input_required` with the approval form, the retry with `inputResponses` and the echoed `requestState`, the released work order `WO-195893`, then read back |
| `step7.txt` | a rejection, a client that cannot show forms, an approver not on the list: all refused |
| `step8.txt` | `test_inspector.py --module s26_server --inspector`: 62 / 62 PASS, including the MCP Inspector CLI 2.7.0 |
| `audit_after_walk.jsonl` | the audit log after steps 4 to 7: 14 lines, one per tool call |
| `timings.json` | machine seconds per step, and lines typed |
| `work_order.json`, `work_order_2.json` | the requests steps 6 and 7 send (tickets `INC-004412`, `INC-004413`) |

Show these if a laptop - or the room - cannot run the server. The ERP's
data is deterministic, so a live run prints the same records and the
same work order number (`WO-195893`, the first write after every ERP
start); timestamps, `trace_id`s, request-state tokens and hashes of
results that contain a timestamp differ.

Refresh after any change to the server, its helpers, the checkpoints or
the ERP (ports 8000 and 8100 free, Node.js installed for step 8):

    python scripts/walk_s26_steps.py --out facilitator/prebaked_outputs/mcp_server

then update the timing table in `facilitator/mcp_build_sequence.md` from
`timings.json`, and the audit sample in `services/mcp_server_reference/README.md`
if you want it to match.
