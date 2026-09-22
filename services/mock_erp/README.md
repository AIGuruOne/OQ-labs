# Mock ERP API

A small, fake ERP: **equipment master, maintenance history, work
orders**. Read endpoints across all three, and **exactly one write**:
`POST /work-orders`, which raises a work order and releases it to the
site crew. That write is what the Day 4 approval interrupt gates and
what the Day 5 S26 MCP server wraps behind its gate.

Everything in it is synthetic (BUILD_SPEC section 9). It stands in for
the plant maintenance system the tickets call *AssetHive*.

| Who uses it | For what |
|---|---|
| Day 4 agent labs (S23, S24) | Tools an agent calls; the write is the action the approval interrupt stops |
| Day 5 S26 | The system the reference MCP server wraps (typed tools, read-only by default, the write gated) |
| Capstone brief 4 | Ticket names `P-1201A` -> equipment + history -> drafted work order -> planner approves -> the one write |
| Capstone brief 3 | Reads only: `GET /equipment/{tag}` to compare a nameplate with the master |

FastAPI 0.141.1, uvicorn 0.52.4, pydantic 2.13.5 - the pins in
`requirements.txt`, which are also what Colab preinstalls. No database:
the data sits in memory, loaded from `data/*.json` at startup (under
1.5 s, measured below).

---

## Run it on a laptop

From the repo root, with the environment from `requirements.txt`:

```bash
uvicorn services.mock_erp.main:app              # http://127.0.0.1:8000/docs
python -m services.mock_erp.tour                # walk every endpoint, check every status
```

The CLAUDE.md command adds `--reload`. It serves exactly the same, but
**on Windows the reload itself hangs** (an upstream uvicorn issue,
reproduced here with a three-line app; playbook entry 17). Nobody in
the room needs it - participants call the ERP, they do not edit it.
To reset the ERP, stop it (Ctrl+C) and start it again.

`/docs` is the interactive reference: every endpoint, every field, the
allowed values, an example body for the write, and a *Try it out*
button. `openapi.json` in this folder is the same document as a file.

## Run it in Colab

A notebook cell cannot run `uvicorn` in the foreground - the cell
would never finish. `launch.py` starts it as a child process, sends its
output to a log file and waits for `GET /health`. These are the cells,
in order (the first is the standard environment cell from
`docs/notebook_conventions.md`, which clones the repo and puts
`REPO_ROOT` on `sys.path`). Nothing needs installing: Colab already has
every package at the pinned version.

```python
# Start the mock ERP in the background: this runtime plays the part of the VM.
from services.mock_erp.launch import start_in_background

erp = start_in_background(port=8000)
ERP_URL = erp.base_url
print(erp.health)
```

```python
# Read one piece of equipment from the equipment master.
import requests

reply = requests.get(f"{ERP_URL}/equipment/P-1201A", timeout=10)
print(reply.status_code)
print(reply.json())
```

```python
# What has been done to this pump before? Newest first.
reply = requests.get(f"{ERP_URL}/maintenance-history",
                     params={"equipment_tag": "P-1201A"}, timeout=10)
history = reply.json()
print(history["total"], "records")
for record in history["items"]:
    print(record["date"], record["work_order_id"], record["failure_mode"])
```

```python
# THE ONE WRITE. In the labs an agent never sends this without a person approving it first.
new_work_order = {
    "equipment_tag": "P-1201A",
    "work_type": "corrective",
    "priority": 2,
    "title": "P-1201A abnormal noise, suspect seal",
    "description": "Control room reports the pump sounds wrong. Seal replaced under WO-118305 in May 2026.",
    "requested_by": "Control room operator, MRB",
    "approved_by": "Salim (maintenance planner, MRB)",
    "source_ticket": "INC-004412",
}
reply = requests.post(f"{ERP_URL}/work-orders", json=new_work_order, timeout=10)
print(reply.status_code, reply.headers.get("Location"))
created = reply.json()
print(created)
```

```python
# Read it back: the write persists for as long as the server runs.
work_order_id = created["work_order_id"]
print(requests.get(f"{ERP_URL}/work-orders/{work_order_id}", timeout=10).json()["status"])
print(requests.get(f"{ERP_URL}/equipment/P-1201A", timeout=10).json()["open_work_orders"])
```

What those cells print (Linux container run, 2026-09-22): `Mock ERP up
at http://127.0.0.1:8000 in 0.5 s`, then `200` and the `P-1201A` row,
`3 records` (`2026-05-18 WO-118305 mechanical seal leak` first), `201
/work-orders/WO-195893`, `released`, `['WO-195893']`.

- **Running the start cell twice** finds the ERP already up and reuses
  it (it says so, with how many work orders it has raised). It never
  starts a second copy.
- **A restarted kernel or a new runtime** gets a clean ERP: the child
  process dies with the kernel, the next start cell reloads the seed,
  and the first work order raised is `WO-195893` again. Measured: two
  fresh kernels in a row, identical output.
- **There is nothing to save to Drive.** The ERP's starting state is
  in the repo and is identical everywhere (`data_fingerprint` in
  `/health`); what a lab writes into it is meant to disappear on
  restart. A notebook that uses the ERP checkpoints its OWN results
  (the agent's decisions, the approval log) as usual.
- **Seeing `/docs` from Colab** (optional, NOT verified on Colab): a
  browser cannot reach the runtime's localhost. Colab's own helper
  embeds it in the output:

  ```python
  from google.colab import output
  output.serve_kernel_port_as_iframe(8000, path="/docs", height=600)
  ```

  `serve_kernel_port_as_window` is marked DEPRECATED and broken in
  Colab's source; the iframe variant has an open "broken" bug report
  (googlecolab/colabtools #4037, 2023). If the frame is blank, read
  `openapi.json` in this folder, or the table below.

## Endpoints

| Method | Path | What | Filters (all optional, AND) |
|---|---|---|---|
| GET | `/health` | Up? Which data? How many writes? Always open | - |
| GET | `/equipment` | Equipment master, by tag | `site`, `equipment_type`, `criticality`, `status` |
| GET | `/equipment/{tag}` | One row + `open_work_orders` | - |
| GET | `/maintenance-history` | Completed work, newest first | `equipment_tag`, `site`, `work_type`, `failure_mode` (substring), `since`, `until` |
| GET | `/maintenance-history/{record_id}` | One record: failure, action, parts | - |
| GET | `/work-orders` | Work orders, newest first | `equipment_tag`, `site`, `status`, `work_type`, `priority`, `source_ticket` |
| GET | `/work-orders/{work_order_id}` | One work order | - |
| **POST** | **`/work-orders`** | **THE ONE WRITE: raise + release a work order** | - |

- Lists are pages: `?limit=` (1-100, default 20), `?offset=`. Every
  list reply is `{"total", "limit", "offset", "next_offset", "items"}`;
  `next_offset` is `null` on the last page.
- Unknown query parameters are **refused** (422). `?stauts=released`
  is an error that names the typo, not an unfiltered list that looks
  like an answer - which matters when the caller is an agent.
- Ids and codes are case-insensitive on the way in (`p-1201a`, `mrb`),
  upper case on the way out.
- Ids: equipment `P-1201A`, work order `WO-118305`, maintenance record
  `MH-000224`, ticket `INC-004412`. Dates ISO 8601; timestamps carry
  the Gulf offset (`2026-09-22T10:41:07+04:00`).

## The one write, and why it looks the way it does

`POST /work-orders` is designed so that gating it is the obvious thing
to do:

- **Consequential.** The work order is created as `released`: it is on
  the site crew's list the moment the call returns. Priority 1 means a
  crew is called out now (target date = today).
- **Irreversible through the API.** There is no PUT, PATCH or DELETE
  anywhere. Trying gets a 405 that says work orders cannot be changed,
  cancelled or deleted through this API. Only a planner in the real ERP
  undoes one.
- **It names a person.** `approved_by` is required. The ERP records it
  and cannot check it: the check is upstream (the agent loop's
  approval interrupt, then the MCP server's gate). A write whose
  `approved_by` nobody actually gave is exactly what an audit log
  should catch - governance template 4 and 5.
- **Retries are safe per ticket.** With `source_ticket` set, a second
  POST for the same ticket gets `409 Conflict` naming the existing work
  order, instead of a duplicate crew dispatch. Without `source_ticket`
  there is no duplicate check.
- **Strict body.** Unknown fields are refused (`prority` is an error);
  the tag must exist in the equipment master; `site` is taken from the
  master, never from the caller.
- Every successful write prints one line to the server log:
  `[mock-erp] WRITE raised WO-195893 on P-1201A (MRB), priority 2, approved_by='Salim (...)', source_ticket=INC-004412`.

Success is `201 Created`, the new work order as the body, and
`Location: /work-orders/WO-195893`.

## Errors

Every error has one shape: `{"error": "<code>", "message": "<a sentence>"}`,
plus `problems` for validation and `existing_work_order_id` for a
conflict.

| Status | `error` | When |
|---|---|---|
| 400 | `malformed_body` | The body is not valid JSON (message says where) |
| 401 | `unauthorised` | Only with `MOCK_ERP_API_KEY` set: `X-API-Key` missing or wrong |
| 404 | `not_found` | A well-formed id that does not exist, or no such endpoint |
| 405 | `method_not_allowed` | Any write other than `POST /work-orders` |
| 409 | `conflict` | `source_ticket` already has a work order |
| 415 | `unsupported_media_type` | A body sent without `Content-Type: application/json` |
| 422 | `validation_failed` | Anything else wrong. `problems` lists EVERY problem as `{where, problem, got}`, e.g. `{"where": "body.priority", "problem": "input should be 1, 2, 3 or 4", "got": 7}` |

A failed write writes nothing, and its message says so.

## Auth: an environment secret, nothing more

No production authentication (BUILD_SPEC section 14; OIDC is a talk
topic). By default the ERP needs no key. Set `MOCK_ERP_API_KEY` (in the
environment or the repo-root `.env`) to any string and every endpoint
except `/health` and `/docs` demands the header `X-API-Key: <that
string>` (401 otherwise). `/docs` then shows an *Authorize* button. In
Colab: `start_in_background(port=8000, api_key="some-lab-secret")`.
The key is never printed or put in the OpenAPI document.

## The data

| File | Rows | What |
|---|---|---|
| `data/equipment.json` | 86 | 12 per site (14 at MRB), seven invented sites `HBT KTF MRB SHZ TMQ WQR ZFL` |
| `data/work_orders.json` | 295 | 265 completed (258 with a maintenance record; 7 are work orders that tickets from before July mention), 18 released, 7 in progress, 3 on hold, 2 cancelled |
| `data/maintenance_history.json` | 258 | One per completed work order since 2024-01-01: failure mode, action, parts, downtime |

Consistent with the ticket corpus on purpose (`tests/test_mock_erp.py`
checks each):

- every plant tag any ticket mentions (28 of them) is in the equipment
  master, at the site of the first ticket that mentions it;
- every work order a ticket mentions (8) exists, on the tag that ticket
  names;
- the brief 4 story is true: `P-1201A` (crude transfer pump, MRB) had
  its mechanical seal replaced under `WO-118305`, completed 2026-05-18,
  and has no open work - so the capstone's new work order is the only
  one;
- the same site codes and tag prefixes as the tickets; part numbers
  (`30-2201-01`), serials and models can never be mistaken for a tag.

**Deterministic.** The files are generated, never hand-edited:
`python -m services.mock_erp.seed --seed 42` (it reads
`corpus/tickets/tickets_raw.jsonl`). The test suite regenerates them
and fails if a byte differs. `/health` reports `data_fingerprint`
(sha256 of the three files): `84e0cc199798` on every machine and every
restart. `.gitattributes` forces LF so a Windows checkout keeps it.
Regenerating (after a corpus change) changes ids and the fingerprint:
rerun the tests, `python -m services.mock_erp.write_openapi` if the
models changed, and refresh `facilitator/prebaked_outputs/mock_erp/`.

Manufacturer names (`Veltrane Pumps`, `Kalvik Fluidworks`, `Halvard
Compression`, ...) are invented; a test greps the data against the
same real-name denylist as the ticket corpus.

## State

In memory, one process. Writes last until the process stops; a
restart is a clean ERP. Run ONE worker (the default) - two workers
would be two ERPs that disagree. There is deliberately no reset
endpoint: it would be a second write.

## Files

| File | What |
|---|---|
| `main.py` | HTTP routes, error handling, the API key check, the OpenAPI text |
| `models.py` | Every shape: fields, allowed values, examples (what `/docs` shows) |
| `store.py` | The data and the rules: filters, pages, the write |
| `seed.py` | Generates `data/*.json`; never run by the server |
| `launch.py` | `start_in_background` / `stop` for notebooks and tests (stdlib only) |
| `tour.py` | Hits every endpoint and error path, prints each pair, exit 0 if every status is as expected |
| `write_openapi.py` | Regenerates `openapi.json` |
| `openapi.json` | The OpenAPI 3.1 document, as a file |

## Tests

`python -m pytest tests/test_mock_erp.py -q` - 37 tests, about 10 s:
every endpoint, every error path, pagination, the one-write rule (by
route table AND by trying every write method on every path), the API
key, concurrent writes, the committed seed and OpenAPI file against
their generators, consistency with the ticket corpus, the denylist,
and a real server started in the background, toured, stopped and
restarted.

## Measured (2026-09-22)

| Where | Result |
|---|---|
| Windows 11 laptop, Python 3.11, `uvicorn services.mock_erp.main:app --reload` | `/health` answers 1.2 s after launch; tour 29 / 29; reload hangs (above) |
| `python:3.12-slim` container, 2 CPUs, pinned packages only (Colab's pinnable runtime is 3.12) | pip install 19 s; 37 tests pass; the Colab cells above via a Jupyter kernel: ERP up in 0.5 s, whole notebook 5 s, twice in fresh kernels, identical; `--reload` restarts 0.7 to 1.1 s after a save (three runs) |
| `python:3.13-slim` container (Colab's new default image is 3.13) | Same results |
| A real Colab runtime | **NOT RUN.** The build machine has no Colab session. The container runs the same code path (a kernel starting a child process, calls to localhost); the first real Colab run is owed, with the iframe check above |
