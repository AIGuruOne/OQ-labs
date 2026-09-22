# From lab to something OQ can run (production engineering handout)

**When:** handed out at the start of S27 (Day 5, 09:50), read in the
first ten minutes of S28, kept afterwards. **Length:** a 10-minute read.

The capstone scaffold is a working integration: endpoint switch, index,
MCP tool, checks, decision, audit log, cost cap. It is **not** a
production service. This page says what changes between the two, row by
row, and names what the week did not cover at all. None of it is exotic;
all of it is work someone has to be given time for.

## 1. What changes

| Concern | What the lab does (where) | What a production service needs |
|---|---|---|
| **Error handling** | Every failure becomes a sentence and an exit code (`capstone/run.py`, `config/endpoints.py` `EndpointError`). A model reply that fails `check_output` goes to the empty form or the neighbour vote, never onwards | The same rule: a failed step has a defined, tested outcome. Plus: errors counted and alerted on, not only printed. A human-visible fallback for every step, not only the model |
| **Retries** | None in the scaffold. The eval harness retries a failed call once (`scripts/run_eval.py`). The ERP refuses a repeated `source_ticket` with a 409, so a retried write cannot double-raise | Retry only what is safe to repeat (reads; a write that carries an idempotency key such as `source_ticket`). Backoff with jitter, a cap on attempts, and no retry on 4xx. A retry is a new audit line |
| **Timeouts** | Model call 120 s (`config/endpoints.py`), ERP 10 s (`services/mcp_server_reference/erp_client.py`), MCP 30 s (`call.py`) | A budget for the whole request (brief 5: 2 s), split across the steps, and a defined answer when it runs out. Notebook 03 showed what a queue does to latency: measure p95 under load, not one call |
| **Observability** | Three JSON-line logs per governance template 5.1 (`llm_call`, `tool_call`, `index_write`), joined by `trace_id`, written to a folder | Ship them to OQ's central log store; W3C `traceparent` end to end; dashboards for error rate, p95, cost per day, and fallback rate. A fallback rate that rises is the first sign of drift (template 8) |
| **Cost control** | An estimate per call from token counts and a price you type in; a monthly cap that refuses the call (`COST_CAP_USD_PER_MONTH`) | Prices from the contract, not a handout. The cap enforced at the gateway, not in each client. Alert at 50/80%. Self-hosted is a fixed monthly cost (`facilitator/cost_model.xlsx`), and the per-call number is 0 on purpose |
| **Versioning** | `PROMPT_VERSION` in every `llm_call` line; adapter sha256 fingerprint; index `build_id`; ERP `data_fingerprint`; exact pins in `requirements.txt` | Every one of those in a release record (template 7.3), plus the code commit. A change to any one is a change, with an eval before promotion |
| **Rollback** | Switching `ENDPOINT` or `MY_ADAPTER_DIR` back is one line; the pre-baked adapter is always there | Keep the previous model, prompt and index build deployable. Rehearse it (template 7.4): a rollback nobody has run is a hope |
| **Evaluation in production** | 20 held-out tickets, scored by `run_eval.py`, before anything is shown | Three loops: the fixed held-out set before every promotion; a sample of live traffic scored weekly by a person (template 3); agent corrections captured as labels. 20 tickets detect only large changes: one ticket is 5 points |
| **Access and secrets** | `.env`, an API key, `X-API-Key` on the ERP, `caller` = `unverified-client:<name>` | OIDC / managed identity for every hop, the approver's identity verified (the ERP only records `approved_by`), secrets in a vault, no shared keys |
| **Data handling** | Synthetic data; prompts hashed in the log; the brief 5 example shows neighbours' subjects, never bodies | The data classification of template 2 applied to prompts, logs, the index and the model host. Retention cut-offs enforced by a job, not a promise. Note from our own run: ticket subjects can carry names ("approved by Anil") |
| **Change of model** | One setting; the eval reruns in two minutes | The same, plus a shadow period: the new model runs beside the old one on live traffic, scored, before it answers anyone |

## 2. What the week did not cover (real work, not pretended away)

These are named in BUILD_SPEC section 14 as out of scope for the labs.
They are not out of scope for OQ.

- **CI.** Tests on every change (this repo has 20+ test files; nothing
  runs them automatically), and an eval gate before a merge that
  changes a prompt, a model or an index.
- **Containerisation.** The ERP, the MCP server and Ollama run here as
  child processes of a notebook. In production each is a container
  image with a health check, resource limits and a restart policy.
- **Packaging for redistribution.** The scaffold is a folder in a repo
  with `sys.path` edits. A service is a versioned package or image
  with its dependencies locked.
- **A user interface.** No desk-tool plugin, no dashboard. The
  deliverable is the service contract; the UI is someone's project.
- **Serving at production concurrency.** Notebook 03 measured one small
  model on one runtime. Sizing for OQ is the worksheet plus a load test
  on the real VM.
- **Production authentication** (OIDC) on the ERP and the MCP server.
- **Also not in the thin scaffold** (cut 2026-09-23 to fit the week):
  an HTTP endpoint around `Capstone.run_ticket()`, the gated write
  wired into the scaffold, retries, a scheduled index rebuild. See
  `capstone/README.md` section 7.

## 3. The one question to ask of any AI integration

*When it is wrong, who finds out, how fast, and what did it already do?*
If the answer is "nobody, never, and it already wrote to the ERP", it is
not ready, whatever its accuracy.
