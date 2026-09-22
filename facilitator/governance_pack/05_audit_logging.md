# 5. Audit and logging requirements (8 min)

**Why this exists.** On Day 3 a wrong extraction was cited in an
answer. The question that follows is not "why was the model wrong"
but "which answers cited it, who read them, and what did they do
next?" That question is only answerable if three kinds of event were
written down as they happened: every model call, every tool call, and
every write into an index or a system of record. The MCP spec tells
clients to log tool usage for audit and to show tool inputs before
calling [S9]; the NCSC/CISA secure AI guidelines put logging and
monitoring under "secure operation" [S10]; the EU AI Act's
record-keeping article asks that logs make it possible to identify
situations where the system presents a risk and to monitor its
operation [S4, Art. 12]. The reference MCP server built in S26 writes
one JSON line per tool call, in the shape below. This template says
what the other two lines contain, where all three go, who reads them
and how long they live. The bar is a month later: a person who was not
there reconstructs one output from the log alone.

**Paste from:** spec §8 (audit log fields), §3 (where the text is
stored after the call). New writing: the three event shapes, the
retention row, the two queries.

**Done when:** each of the three event types has its field list
ticked, the log has a place and a retention, and the two reconstruction
queries have been run once against a real log.

---

## 5.1 The three events

Every line is one JSON object, append-only, UTC timestamps in ISO
8601, ids that join across the three types. Prompt text and image
bytes are **not** in the log by default (hash them); a copy of the
text stays in the system that already holds it. If you do log text,
template 2 has a row for it.

### 5.1.1 `llm_call` (one per model request; spec §8)

| Field | Content | Present? |
|---|---|---|
| `ts` | request time, UTC | |
| `event` | `"llm_call"` | |
| `trace_id` | joins the model call, its tool calls and any write; W3C `traceparent` if you have tracing (the MCP spec documents propagating it in `_meta` [S9]) | |
| `system_id`, `caller` | template 1 id; the service or person that called | |
| `item_id` | the ticket, image or question id | |
| `endpoint`, `model`, `model_fingerprint` | `local` / `hosted` / `tuned`; model name; adapter sha256 or vendor model version (template 7) | |
| `prompt_sha256`, `prompt_version` | hash of the full prompt; the system-prompt version | |
| `context_ids` | `chunk_id`s and tool-call ids that were put into the prompt | |
| `output` | the structured output (the record, the answer with citations), or its hash if it is long or sensitive | |
| `validation` | `valid: true/false` and the reasons | |
| `tokens_in`, `tokens_out`, `seconds`, `truncated` | | |
| `cost_estimate` | from the cost model's unit prices | |

### 5.1.2 `tool_call` (one per MCP tool invocation; written by the server)

This is the line the reference MCP server (`services/mcp_server_reference/`,
S26) writes. If your server writes something else, change the server.

| Field | Content | Present? |
|---|---|---|
| `ts` | UTC | |
| `event` | `"tool_call"` | |
| `trace_id`, `request_id` | the trace from 5.1.1; the JSON-RPC request id | |
| `server`, `server_version` | e.g. `oq-erp-mcp`, `0.1.0` | |
| `caller` | the authenticated principal or client id, never a shared secret | |
| `tool` | tool name | |
| `access` | `"read"` or `"write"` (the class from template 4, not the annotation) | |
| `args_sha256`, `args_redacted` | hash of the arguments; the arguments with secrets and personal data removed | |
| `approval` | `{"required": false}` or `{"required": true, "decision": "approved" / "rejected", "by": "<approver>", "ts": "...", "reason": "..."}` | |
| `status` | `"ok"`, `"error"`, `"refused"` (refused = write attempted without approval, or rate-limited) | |
| `upstream` | the downstream system and its status (`{"system": "mock_erp", "status": 201}`) | |
| `result_sha256`, `records` | hash of the result; number of records returned or written | |
| `ms` | duration | |

### 5.1.3 `index_write` (one per item added to, or removed from, an index or a knowledge base)

The Day 3 line. Without it, a bad chunk cannot be traced or pulled.

| Field | Content | Present? |
|---|---|---|
| `ts`, `event` (`"index_write"`), `trace_id` | | |
| `action` | `"add"`, `"replace"`, `"remove"`, `"quarantine"` | |
| `doc_id`, `chunk_id` | Contract 5 ids | |
| `source` | what it was made from: file path and hash, or `image_id` + `extraction_id` | |
| `produced_by` | `"human"` or the `model` + `model_fingerprint` that extracted it | |
| `score_line` | for an extraction: fields correct / missed / **invented**, confidence | |
| `approval` | as in 5.1.2; a machine-produced chunk is a W2 write (template 4) | |
| `index_build_id` | which build of the index it belongs to (template 7) | |

## 5.2 Where the log lives

| | |
|---|---|
| Written to (file, table, log service), by which component | |
| Shipped to the central log store: how, how often | |
| Retention (days), and who decided it (template 2 row "audit log") | |
| Who can read it; who can delete it (should be nobody before retention) | |
| Personal data in the log: none / which fields, and the legal basis [S5] | |
| Clock source, so `ts` joins across the VM, the MCP server and the desk tool | |

## 5.3 The two queries that must work

Run both against the real log before go-live and write the date.

| Query | How it is answered (the fields joined) | Run on (date), took (minutes) |
|---|---|---|
| **Reconstruct one output:** given an `item_id`, show the model call, every tool call, the context ids, the output, the validation and the approval, in order | | |
| **Blast radius of one bad chunk:** given a `chunk_id`, list every `llm_call` whose `context_ids` contained it, every output that cited it, and who received those outputs | | |

## 5.4 What is never logged

> Secrets, tokens, raw passwords from ticket bodies, national ids,
> image bytes, and anything template 2.4 lists. Mechanism (redaction
> function, field allow-list), and where it is tested:
>

## 5.5 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Security | | |

Sources: [S9] MCP specification 2026-07-28, Tools: security
considerations ("log tool usage for audit purposes") and the changelog
entry on OpenTelemetry trace context in `_meta`. [S10] NCSC/CISA
secure AI system development, "secure operation and maintenance:
logging and monitoring". [S4] EU AI Act Art. 12. [S5] Oman PDPL for
personal data in logs.
