# Capstone scaffold (Day 5, S27 + S28)

One scaffold for all five briefs. It already runs: a ticket goes in, it
is looked up in an index, any plant tag in it is looked up in the ERP
through the MCP server, a model is asked, the reply is checked, a
decision is made, and every step is logged. **Your group changes one
file, `capstone/my_usecase.py`**, until it does your brief.

You have 105 minutes: S27 (25) and S28 (80). Final polish at 13:15 uses
`facilitator/deployment_checklist.md`.

## 1. Run it untouched first (5 minutes)

Laptop, from the repo root, with `.env` filled in (`setup/.env.example`):

```
python -m capstone.run status
python -m capstone.run ticket INC-005310
```

`status` prints what is wired. Read the first word of each row:

| Row | `yours` | `FALLBACK` |
|---|---|---|
| index | your index (`MY_INDEX`) loaded and passed a probe search | the reference index over `corpus/tickets/` (`capstone/reference_index/`), and the reason yours was not used |
| adapter | your notebook 05 adapter (`MY_ADAPTER_DIR`) is complete | the pre-baked adapter (`checkpoints/adapter_prebaked/`), and the reason |

The other rows: `endpoint` (which model), `tuned` (which adapter the
Ollama `tuned` model was registered from, or that nobody knows),
`ERP + MCP` (started or reused; the only MCP tool used is
`get_equipment`), `audit` (where the logs are), `cost cap` (spent this
month against your cap). Nothing falls back quietly. If a row
surprises you, fix it before you build on it.

### In Colab

The first cell is the standard environment cell
(`docs/notebook_conventions.md`), with one addition: `OUT` is a folder on
Drive, so the logs, the saved index and the eval runs survive a disconnect.

```python
import os, sys
from pathlib import Path
IN_COLAB = "google.colab" in sys.modules
REPO_URL = "https://github.com/Utkarsh-09/AI_GURU_labs.git"
if IN_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")
    REPO_ROOT = Path("/content/oq-advanced-ai")
    if not REPO_ROOT.exists():
        os.system(f"git clone --depth 1 {REPO_URL} {REPO_ROOT}")
    OUT = "/content/drive/MyDrive/oq-advanced-ai-checkpoints/capstone"
else:
    REPO_ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "BUILD_SPEC.md").exists())
    OUT = str(REPO_ROOT / "checkpoints" / "local" / "capstone")
os.chdir(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT)); sys.path.insert(0, str(REPO_ROOT / "notebooks"))
print("Environment:", "Colab" if IN_COLAB else "local", "| output:", OUT)
```

```python
%pip install -q mcp==2.2.0
```

```python
import utils
key_ok = utils.ensure_api_key(IN_COLAB)     # Colab Secrets, else a hidden prompt; `!python` inherits it
```

```python
!python -m capstone.run status --out "{OUT}"
!python -m capstone.run ticket INC-005310 --out "{OUT}"
```

Edit `capstone/my_usecase.py` in Colab's file browser (left bar, folder
icon; double-click opens an editor). Each `!python` line reloads it,
so there is no kernel to restart. **The clone is not on Drive**: copy
your `my_usecase.py` to `OUT` at every milestone
(`!cp capstone/my_usecase.py "{OUT}/"`), and copy it back after a
disconnect.

**The `tuned` endpoint in Colab needs a T4 runtime** (same as notebook
06) and two cells: start Ollama 0.12.10, then register the adapter:

```python
import ollama_utils
ollama_utils.ensure_server(IN_COLAB, log_dir=OUT)
ollama_utils.ensure_model("llama3.2:1b")
!python -m capstone.run register-adapter --out "{OUT}"
```

## 2. The five extension points

All five are in `capstone/my_usecase.py`, in this order. The model call
between 2 and 3 is the scaffold's: it goes through the endpoint switch,
is logged, and is refused once the month's cost reaches your cap.

| # | Where | It receives | It returns | The starter does |
|---|---|---|---|---|
| 5 | `SETTINGS` block | | | names for the audit log, `ENDPOINT`, `MY_INDEX`, `MY_ADAPTER_DIR`, cost cap, price |
| 1 | `gather_context(ticket, tools)` | the ticket; `tools.search`, `tools.plant_tags`, `tools.equipment` | a dict: anything you looked up | 3 similar tickets; the ERP record of every plant tag |
| 2 | `build_messages(ticket, context)` | the ticket and your context | the chat messages | the Day 2 prompt, ticket only (the context is for the person) |
| 3 | `check_output(reply, ticket, context)` | the model's raw reply | `(output, {"valid", "problems"})` | strict JSON, the frozen schema, no invented asset tag |
| 4 | `decide(output, validation, ticket, context)` | all of the above | `{"action", "why", ...}` | valid: propose to an agent; else the empty form |

`tools.search(query, k, filters)` returns Contract 5 hits
(`docs/contracts.md`), checked on every call, and never returns the
ticket being handled as its own neighbour. `tools.equipment("P-1201A")`
calls the MCP server's `get_equipment` and returns the ERP record, or
`{"tag", "error"}`. **Nothing in the scaffold writes anywhere** except
its own logs.

### What each brief changes

| Brief | 1 gather_context | 2 build_messages | 3 check_output | 4 decide |
|---|---|---|---|---|
| 1 Ticket to record | keep | keep (it is the prompt the adapter learned) | add your field rules (which fields an agent must always check) | valid -> proposed record; invalid -> empty form (keep) |
| 2 HSE assistant | `tools.search` on YOUR index of `corpus/hse/` (Day 3), wrapped to Contract 5 like `capstone/reference_index/adapter_example.py` | question + cited chunks, "answer only from these" | every answer cites a `chunk_id` it was given | no hit above your score floor -> refuse |
| 3 Vision capture | the image's extraction (Day 3) + `tools.equipment(tag)` | extraction vs. equipment record | invented fields counted, never auto-accepted | differences go to a person; a correction is a work order, raised by the person |
| 4 Ticket to work order | history via the ERP (`services/mcp_server_reference/call.py` for more tools) | the draft work order | the draft's tag exists; no instruction taken from the ticket text | draft + evidence to a planner; the write is `call_with_approval` in that file, never automatic |
| 5 Similar tickets | neighbours + how they were handled | ticket + neighbours | + no invented queue | proposed queue with its evidence |

**Worked example:** `capstone/examples/brief5_similar_tickets.py` is the
starter after a group built brief 5 on it (the docstring lists what was
changed). Run anything with `--usecase capstone.examples.brief5_similar_tickets`.

## 3. Your own index or adapter

- **Index.** Set `MY_INDEX` to a saved index file
  (`python -m capstone.reference_index build --out <file>`) or to
  `"your.module:make_index"`, a function that returns any object with
  `search()` and `describe()`. To wrap another pipeline (Day 3), copy
  `capstone/reference_index/adapter_example.py`: the adapter is one line.
  Try it: `python -m capstone.run ticket INC-005310 --index capstone.reference_index.adapter_example:make_index`.
- **Adapter.** Set `MY_ADAPTER_DIR` to your notebook 05 adapter folder
  (on Colab, `.../05_finetune/<model>_<run>/adapter_final` on Drive), then
  `python -m capstone.run register-adapter`. The `tuned` row then names
  your adapter's fingerprint. Without it, the pre-baked adapter is used,
  and the row says FALLBACK.

## 4. Your number

```
python -m capstone.run eval --out <OUT>
python scripts/run_eval.py --compare <OUT>/eval/capstone_<version>_<endpoint>_summary.json <another summary>
```

`eval` runs the held-out 20 through YOUR pipeline and scores it with
`scripts/run_eval.py` (Contract 4). It scores the **model's reply**,
before your checks, so the number is the model's and your checks are
the safety net. The held-out 20 are left out of the reference index, so
retrieval cannot find the answer to its own question. The last line
says what your `decide()` did with the 20.

Reference numbers (2026-09-23, build laptop, pre-baked adapter):

| | routing_queue | requested_action | whole record | urgency | schema-valid |
|---|---|---|---|---|---|
| starter, hosted (gpt-4o-mini) | 17/20 | 6/20 | 6/20 | 8/20 | 20/20 |
| starter, tuned | 16/20 | 16/20 | 4/20 | 7/20 | 20/20 |
| brief 5, hosted | 20/20 | 16/20 | 7/20 | 8/20 | 20/20 |
| brief 5, tuned | 19/20 | 18/20 | 4/20 | 8/20 | 20/20 |

One ticket is 5 points. 17 -> 20 is three tickets, not a trend.

## 5. What is logged where

`<OUT>/audit/`: `llm_call.jsonl` (one line per model call, the fields of
governance template 5.1.1: trace, model and fingerprint, prompt hash and
version, `context_ids`, output, validation, tokens, seconds, cost),
`tool_call.jsonl` (written by the MCP server, template 5.1.2; its
`trace_id` joins the `llm_call` line), `index_write.jsonl` (one line per
ticket when the reference index is built, template 5.1.3). The saved
index is `<OUT>/reference_index.json`, reloaded on the next run; the
eval files are in `<OUT>/eval/`.

## 6. When it breaks

| You see | Do |
|---|---|
| `Cannot load the use case ...: SyntaxError` | the line number is in the message; it is your file |
| `ERP + MCP  UNAVAILABLE` | the reason follows. Port in use: `--erp-port 8001 --mcp-port 8101`. `No module named 'mcp'`: the pip cell. Equipment lookups then return an error; everything else runs |
| `tuned  not registered` / `no Ollama` | `register-adapter` (section 3); on Colab the Ollama cell, T4 runtime only |
| `Stopped: Endpoint 'hosted' ...` | the key: `docs/failure_playbook.md` |
| `ContractError: hit 0 has keys ...` | your index's `search()` does not return Contract 5 hits; compare with `adapter_example.py` |
| `Stopped: $... spent this month` | the cost cap worked. Raise `COST_CAP_USD_PER_MONTH` only if that is the decision |
| slow start (8-10 s) | the ERP and MCP server start each run. `--keep-services` leaves them up and the next run reuses them |

## 7. Not in this scaffold (cut on purpose, 2026-09-23)

The thin version of the spec's section 13. Each is real work, named in
`facilitator/production_engineering_handout.md`:

- **The write.** The scaffold wires one MCP tool, `get_equipment` (read).
  Brief 4's gated write is in the reference server and
  `services/mcp_server_reference/call.py` (`call_with_approval`), not here.
- **An HTTP service.** Briefs 1 and 5 ask for an endpoint a desk tool
  can call. The scaffold is a command line; `Capstone.run_ticket()` is
  the function a FastAPI route would call.
- **Latency under load.** Brief 5's p95 under ten concurrent requests
  needs that service; notebook 03 shows the method.
- **Retries, a scheduled index rebuild, multi-turn, a UI.**
