# Interface contracts

The five places the two slices touch. A contract that only exists in a
conversation is not a contract — this file is the record. Changing
anything here is a raise-with-Ritesh change, not a quiet edit.

| # | Contract | Status |
|---|---|---|
| 1 | Corpus layout and document frontmatter | **Final** (tickets final; Preety may extend document families the same way) |
| 2 | Notebook conventions | **Final** — full text in `docs/notebook_conventions.md` |
| 3 | Endpoint config | **Final** — implemented in `config/endpoints.py` |
| 4 | Eval output format | **Shape fixed now; finalised in P4** (eval harness build) |
| 5 | Index interface | **Shape fixed now; finalised in P13** (Day 5 capstone build) |

---

## Contract 1 — corpus layout and frontmatter

### Directory layout (from BUILD_SPEC.md section 7)

```
corpus/
  manuals/       equipment manuals (Markdown)
  hse/           HSE procedures (Markdown)
  maintenance/   work-order / maintenance history (structured records)
  tickets/       service-desk tickets (JSONL)
  images/        rendered image set + spec files
  README.md      provenance statement + these conventions
```

### Document frontmatter (manuals/, hse/, maintenance/)

Every Markdown document opens with YAML frontmatter between `---`
fences. Required keys:

```yaml
---
doc_id: MAN-0007            # <FAMILY>-<4 digits>; families: MAN, HSE, MNT
title: "P-1201A Centrifugal Pump — O&M Manual"
family: manual              # manual | hse | maintenance
site: MRB                   # three-letter invented site code
equipment_tags: [P-1201A]   # every tag the document mentions, [] if none
revision: 3
revision_date: 2026-05-11   # ISO 8601
supersedes: null            # doc_id of the doc this replaces, or null
---
```

`equipment_tags`, `revision`/`revision_date` and `supersedes` exist so
the planted retrieval traps (same tag with two revision dates, a
superseding procedure with no cross-reference) are machine-checkable.

### Ticket format (corpus/tickets/)

One JSONL file, `corpus/tickets/tickets_raw.jsonl`, one ticket per
line:

```json
{
  "ticket_id": "INC-004412",
  "created": "2026-08-14T09:31:00",
  "site": "MRB",
  "channel": "portal",
  "subject": "cant login to erp again",
  "body": "free text — deliberately messy, see BUILD_SPEC.md section 9"
}
```

- `ticket_id` is unique, `INC-` + 6 digits.
- `channel` is one of `portal | email | phone | walk_in`.
- `subject` may be empty (`""`); `body` never is.
- The structured LABELS for a ticket (category, urgency...) live in
  `data/finetune/*.jsonl`, NOT here — the corpus holds raw inputs only,
  so retrieval labs can ingest tickets without seeing answers.

### Naming conventions (both slices)

| Thing | Format | Example |
|---|---|---|
| Equipment tag | letters `-` 4 digits, optional suffix | `P-1201A`, `HX-3040` |
| Site code | three invented letters | `MRB`, `SHZ` |
| Ticket ID | `INC-` + 6 digits | `INC-004412` |
| Work order | `WO-` + 6 digits | `WO-118305` |
| IT asset | prefix + 5 digits | `LAP-04412` |
| Dates | ISO 8601 | `2026-08-14` |

---

## Contract 2 — notebook conventions

Full text with copy-pasteable cells: `docs/notebook_conventions.md`.
Reference implementation: `notebooks/_template.ipynb`. Summary of the
binding parts:

1. Header cell declares expected runtime, needs, and what a correct
   result looks like.
2. First code cell is the environment-detection cell (verbatim from
   the conventions doc): sets `IN_COLAB`, `REPO_ROOT`,
   `CHECKPOINT_DIR`, mounts Drive on Colab, fixes `sys.path`.
3. Pinned install cell: exact `==` pins matching `requirements.txt`,
   only what the notebook needs, Colab-only guard.
4. TODO markers: `# ── TODO <n> ─...` with a hint and an `...` gap.
5. Checkpoint at every milestone via `notebooks/utils.py`
   (`save_json` / `load_json` / `save_pickle` / `load_pickle`);
   milestone cells load-if-exists.

---

## Contract 3 — endpoint config

Implemented and documented in `config/endpoints.py`. The stable
surface Day 3/4 notebooks and the capstone consume:

```python
from config.endpoints import get_endpoint, list_endpoints

llm = get_endpoint("local" | "hosted" | "tuned")   # or get_endpoint()
llm.chat(prompt, *, system=None, temperature=0.2,
         max_tokens=1024, timeout=120) -> str       # or chat(messages=[...])
llm.chat_json(prompt, ...) -> dict                  # strict-JSON variant
llm.name / llm.model / llm.base_url                 # read-only info
list_endpoints() -> dict[str, str]                  # no secrets
```

- All three backends speak OpenAI-compatible `POST /chat/completions`;
  configuration comes from `.env` (see `setup/.env.example`), never
  hardcoded.
- Errors raise `config.endpoints.EndpointError` with a
  what-to-do-about-it message.
- Additive changes (new kwargs with defaults) are allowed; changing an
  existing signature is a raise-with-Ritesh change.

---

## Contract 4 — eval output format

**Shape fixed now; finalised in P4 (eval harness).** Everything that
scores anything emits this shape, so Day 2 S12 (base vs tuned) and
Day 4 S19 (three-way) compose from the same files.

CLI:

```
python scripts/run_eval.py --dataset <path.jsonl> --endpoint <local|hosted|tuned> --out <dir>
```

Two output files per run, written to `--out`:

`<run_id>_rows.jsonl` — one line per (item, field):

```json
{
  "run_id": "2026-09-21_hosted_heldout20",
  "endpoint": "hosted",
  "model": "gpt-4o-mini",
  "item_id": "INC-004412",
  "field": "urgency",
  "expected": "high",
  "predicted": "medium",
  "correct": false,
  "score_type": "exact"        // exact | judged
}
```

`<run_id>_summary.json` — one object per run:

```json
{
  "run_id": "2026-09-21_hosted_heldout20",
  "endpoint": "hosted",
  "model": "gpt-4o-mini",
  "dataset": "data/eval/heldout_20.jsonl",
  "n_items": 20,
  "per_field_accuracy": {"category": 0.95, "urgency": 0.80},
  "schema_valid_rate": 0.90,
  "overall_exact_match": 0.71
}
```

Composition rule: a comparison table (S12, S19) is a concat of
summaries — one row per `run_id`, columns from `per_field_accuracy` +
`schema_valid_rate`. Nothing downstream parses `rows` files to build
the comparison; they exist for drill-down.

---

## Contract 5 — index interface

**Shape fixed now; finalised in P13 (capstone scaffold).** The
retrieval index the agent notebooks and the Day 5 capstone call. Any
retrieval pipeline can be wrapped to this with a thin adapter.

```python
class Index(Protocol):
    def search(
        self,
        query: str,
        k: int = 5,
        filters: dict | None = None,   # e.g. {"family": "hse", "site": "MRB"}
    ) -> list[dict]:
        ...
```

Each result dict (a "hit") has exactly these keys:

```json
{
  "doc_id": "HSE-0003",
  "chunk_id": "HSE-0003#004",
  "text": "the retrieved chunk text",
  "score": 0.83,
  "metadata": {"family": "hse", "site": "MRB", "title": "...",
               "equipment_tags": ["P-1201A"]}
}
```

- Results ordered by descending `score`; `score` is comparable within
  one search call only (no cross-backend meaning).
- `filters` keys match frontmatter keys from Contract 1; unknown keys
  raise `ValueError`.
- A reference implementation ships with the Day 5 capstone scaffold
  (`capstone/reference_index/`, built in P13) over `corpus/tickets/`,
  so the capstone runs end to end with no dependency on the Day 3
  pipeline. The Day 3 pipeline can be wrapped to the same Protocol
  with a thin adapter.
