# Interface contracts

The five places the two slices touch. A contract that only exists in a
conversation is not a contract — this file is the record. Changing
anything here is a raise-with-Ritesh change, not a quiet edit.

| # | Contract | Status |
|---|---|---|
| 1 | Corpus layout and document frontmatter | **Final** (tickets final; Preety may extend document families the same way) |
| 2 | Notebook conventions | **Final** — full text in `docs/notebook_conventions.md` |
| 3 | Endpoint config | **Final** — implemented in `config/endpoints.py` |
| 4 | Eval output format | **Final** — implemented in `scripts/run_eval.py` + `scripts/eval_scoring.py`; rubric in `data/eval/rubric.md` awaits Ritesh's sign-off |
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

- `ticket_id` is unique, `INC-` + 6 digits, rising with `created`.
- `created` is ISO 8601 local time, no offset.
- `site` is one of the invented codes `MRB SHZ KTF WQR ZFL HBT TMQ`.
- `channel` is one of `portal | email | phone | walk_in`.
- `subject` may be empty (`""`); `body` never is. Both are input text:
  anything that feeds a model a ticket feeds it `subject` + `body`.
- The structured LABELS for a ticket (category, urgency...) live in
  `data/finetune/*.jsonl`, NOT here — the corpus holds raw inputs only,
  so retrieval labs can ingest tickets without seeing answers.
- Generated, never hand-edited:
  `python scripts/generate_tickets.py --count 600 --seed 42`.
  Deterministic; the committed files are the seed-42 output and
  `tests/test_generate_tickets.py` enforces that.

### Ticket ground truth (data/finetune/ticket_labels.jsonl)

One line per ticket, same order as `tickets_raw.jsonl`, joined on
`ticket_id`:

```json
{
  "ticket_id": "INC-004412",
  "record": { "...the seven BUILD_SPEC 8B fields, in spec order..." },
  "meta": {"scenario": "access.password_reset", "persona": "terse",
           "features": ["system_unnamed"], "word_count": 6}
}
```

- `record` validates against `data/finetune/ticket_schema.json`, the
  machine-readable form of the section 8B schema (enums, nullable
  strings, `asset_tag` pattern `^[A-Z]{3}-[0-9]{5}$`, one-line
  `requested_action`). The schema file is frozen with the schema.
- `routing_queue` is one of: `identity_access, end_user_computing,
  network_ops, erp_support, apps_support, telecom_voice, security_ops,
  service_desk_l1`.
- `meta` is generator bookkeeping for error analysis. It is never a
  training target and never shown to a model.
- The labelling rules (how each field follows from the text) are in
  `corpus/README.md`. `train.jsonl`, `val.jsonl` and
  `data/eval/heldout_20.jsonl` are all built from this file by the
  dataset builder — nothing else is a source of labels.

### Fine-tuning pair format (train.jsonl, val.jsonl, heldout_20.jsonl)

Built by `python scripts/build_dataset.py --seed 42`. All three files
share one row shape:

```json
{
  "ticket_id": "INC-004412",
  "messages": [
    {"role": "system",    "content": "<dataset_utils.SYSTEM_PROMPT>"},
    {"role": "user",      "content": "Subject: cant login\n\n<ticket body>"},
    {"role": "assistant", "content": "{\"category\": \"access\", ...}"}
  ]
}
```

- **Model-neutral on purpose.** Rows hold role/content messages, never
  a model's special tokens. The chat template is applied by whatever
  owns it: the tokenizer at training time
  (`tokenizer.apply_chat_template`; TRL's `SFTTrainer` does it
  automatically for a `messages` column, Unsloth and mlx-lm accept the
  same shape), and Ollama at inference time through
  `/v1/chat/completions`. Same three roles both times - that is what
  keeps training and inference in step.
- `messages[0]` is always `dataset_utils.SYSTEM_PROMPT`
  (`notebooks/dataset_utils.py`). It is the ONLY copy of the prompt:
  training and the Day 4 three-way comparison import it; `run_eval.py`
  sends the copy inside each dataset row and warns if that copy no
  longer matches. Editing it means rebuilding the dataset and the
  adapter.
- `messages[1]` is `dataset_utils.format_ticket_text(ticket)`:
  `"Subject: <subject or (none)>\n\n<body>"`.
- `messages[2]` is the seven-field record as one line of JSON
  (`json.dumps(record, ensure_ascii=False)`, keys in section 8B order)
  and nothing else - no prose, no code fence.
- To run a model on a row: send `messages[:2]` via
  `get_endpoint(...).chat(messages=...)` (Contract 3); the expected
  answer is `json.loads(messages[2]["content"])`.
- A trainer that rejects extra columns should select `messages` only.
- `data/eval/heldout_20.jsonl` is exactly 20 rows, never in train or
  val, stratified (all 7 categories, >= 1 critical, >= 1 enterprise,
  several arguable-urgency tickets) and has no lookalike (word-set
  Jaccard >= 0.6) anywhere in train/val. It is byte-stable: seed 42,
  enforced by `tests/test_build_dataset.py`. Day 2 S12 and Day 4 S19
  both score against it.
- `train.jsonl` / `val.jsonl` carry **planted** quality problems for
  the Day 2 S10 lab; the answer key is
  `data/finetune/planted_problems.json` (facilitators only). A clean
  build is `--no-plant`. See `data/README.md`.

### Naming conventions (both slices)

| Thing | Format | Example |
|---|---|---|
| Equipment tag | letters `-` 4 digits, optional suffix | `P-1201A`, `HX-3040` |
| Site code | three invented letters | `MRB`, `SHZ` |
| Ticket ID | `INC-` + 6 digits | `INC-004412` |
| Work order | `WO-` + 6 digits | `WO-118305` |
| IT asset | 3-letter prefix + 5 digits (`LAP DSK MON PRN PHN MOB`) | `LAP-04412` |
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
6. (Added 2026-09-22, P7, additive.) A notebook that calls the hosted
   endpoint puts `utils.ensure_api_key(IN_COLAB)` right after the
   install cell: `.env` locally, Colab Secrets (`OPENAI_API_KEY`) or a
   one-time hidden paste on Colab. The key is never printed. Reference
   cell: `notebooks/01_fundamentals.ipynb`, cell `key`. (Added
   2026-09-22, P8, additive.) A notebook whose hosted call is a
   side-by-side extra, not the lab itself, keeps the cell in the same
   place but prints a warning instead of asserting, and asserts
   `key_ok` in the one cell that needs the key - so a missing key
   costs that cell, not the lab. Reference: `02_local_inference`.
7. (P7.) A notebook with two facilitator paths marks the skippable
   cells with the cell tag `full-path-only` AND a first-line comment
   `# [FULL PATH ONLY]`, keeps them in one contiguous block, and makes
   the cells after the block independent of it (tested in
   `tests/test_notebook_01.py`). Only notebook 01 has two paths today.

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

### What `"tuned"` is, and how it comes to exist (P5)

`get_endpoint("tuned")` is an Ollama model named `oq-ticket-tuned`
(`TUNED_MODEL` in `.env`). It does not exist until an adapter is
registered:

```
python scripts/register_adapter.py --adapter checkpoints/adapter_prebaked
```

- **Adapter format (binding):** a folder holding
  `adapter_model.safetensors` + `adapter_config.json` in Hugging Face
  PEFT LoRA layout. Notebook 05 writes it directly; notebook 05b (MLX)
  converts to it. Anything that produces this folder can be the tuned
  model; nothing downstream knows which notebook made it.
- **Where adapters live:** `checkpoints/adapter_prebaked/` (committed,
  the insurance copy, scores in its README) and
  `checkpoints/adapter_<model>_<run>/` (a participant's own, git-ignored;
  also in their run folder under `CHECKPOINT_DIR/05_finetune/`).
- The script reads `base_model_name_or_path` from the adapter config
  and picks the SAME model in Ollama through
  `finetune_utils.MODEL_CHOICES` (`unsloth/Llama-3.2-1B-Instruct` ->
  `llama3.2:1b`). An adapter on any other base model is noise.
- The Modelfile it writes is `FROM <base>`, `ADAPTER <folder>`,
  `PARAMETER num_ctx 4096`. No `TEMPLATE`: the adapter was trained on
  the text Ollama's own llama3.2 template produces
  (`finetune_utils.LLAMA3_SERVING_TEMPLATE`), so the base model's
  template is already the right one.
- The tuned model is Llama 3.2 **1B**. A like-for-like "base" column is
  therefore `llama3.2:1b` (`OLLAMA_MODEL=llama3.2:1b`), not the default
  local model `llama3.2:3b`. Both reference runs are in
  `facilitator/prebaked_outputs/eval/`.
- **Where `"tuned"` is supported (decision 2026-09-21): Colab, free T4
  runtime, only.** Registration needs Ollama 0.12.10; 0.33.3 fails to
  import an adapter and 0.34.2 refuses (`LoRA adapters are no longer
  supported`). In Colab `ollama_utils.ensure_server` installs the
  pinned release, so a consumer there gets it for free. A laptop is
  not a supported path for `"tuned"` (`setup/ollama_setup.md`);
  `"local"` and `"hosted"` are unaffected.
- A consumer (Day 4 S19, the capstone) needs only: Ollama running, the
  registration command above run once, then `get_endpoint("tuned")`.

---

## Contract 4 — eval output format

**Final (P4).** Implemented by `scripts/run_eval.py` (running, files,
tables) and `scripts/eval_scoring.py` (every scoring rule); enforced by
`tests/test_run_eval.py`. The human-facing rules are
`data/eval/rubric.md` (Ritesh signs that off). Everything that scores
the ticket task emits this shape, so Day 2 S12 (base vs tuned) and
Day 4 S19 (three-way) compose from the same files.

### Running

```
python scripts/run_eval.py --dataset <pairs.jsonl> --endpoint <local|hosted|tuned>
                           [--label NAME] [--out DIR] [--json-mode] [--resume]
                           [--replies FILE] [--limit N] [--all] [--run-id ID]
python scripts/run_eval.py --compare A_summary.json B_summary.json [C_summary.json] [--out DIR]
```

- `--dataset` is a file in the fine-tuning pair format (Contract 1).
  For each row the harness sends `messages[:2]` through
  `get_endpoint(name).chat(messages=..., temperature=0.0,
  max_tokens=512)` (Contract 3) and compares the reply with
  `json.loads(messages[2]["content"])`. `item_id` is the row's
  `ticket_id`. A row whose *expected* answer is not a valid record is
  skipped and listed in `skipped_dataset_lines`, never scored.
- `--endpoint` is the ONLY model-specific input. There is no
  model-specific code in the harness.
- `--label` names the run in a comparison (default: the endpoint
  name). `run_id` is `<YYYY-MM-DD>_<label>_<dataset stem>`.
- `--out` defaults to `eval_runs/` (git-ignored). Notebooks pass
  `CHECKPOINT_DIR / "eval"` so results land on Drive.
- JSON mode is OFF unless `--json-mode` is given, and the setting is
  recorded in the summary.
- Exit code 0 = the run completed (whatever the scores); 2 = it could
  not run, with a sentence, never a stack trace.

From a notebook (a sketch) — this is how a run with retrieval in front of the
model (Day 4 S19) uses the same harness with no change to it:

```python
import run_eval                                  # scripts/ on sys.path

def ask(messages):                               # [system, user] -> reply text
    context = my_index.search(messages[1]["content"], k=3)      # Contract 5
    return llm.chat(messages=add_context(messages, context), temperature=0.0)

summary = run_eval.run_evaluation(
    dataset_path, ask, endpoint_name="local", model=llm.model,
    label="base+retrieval", out_dir=CHECKPOINT_DIR / "eval")
```

`ask(messages) -> str` is the whole interface. It may raise; a failed
call is retried once, then recorded as `no_reply`. The questions
fingerprint is taken from the dataset rows, not from what `ask` does
with them, so a retrieval run still composes with the plain runs.

### Files per run, written to `--out`

| File | Content |
|---|---|
| `<run_id>_summary.json` | one object, every number in the report. **The only file a comparison reads** |
| `<run_id>_rows.jsonl` | one line per (ticket, field), for drill-down |
| `<run_id>_replies.jsonl` | raw model replies, appended as each arrives. Input to `--resume` and `--replies` |
| `<run_id>_report.txt` | the rendered table: ASCII, at most 100 columns |

`<run_id>_rows.jsonl` — 8 lines per ticket: the seven fields plus one
`"(schema)"` line, so format is a column like any other
(`rows.pivot(index="item_id", columns="field", values="correct")`):

```json
{"run_id": "2026-09-20_hosted_heldout_20", "label": "hosted",
 "endpoint": "hosted", "model": "gpt-4o-mini",
 "item_id": "INC-004467", "field": "urgency",
 "expected": "high", "predicted": "critical",
 "score": 0.0, "correct": false, "score_type": "exact"}
```

- `score_type`: `exact` (six fields; `score` is 1.0 or 0.0),
  `similarity` (`requested_action`; `score` is the similarity,
  `correct` is `score >= 0.5`), `schema` (the `"(schema)"` line:
  `expected` is `"valid"`, `predicted` is `"valid"` or the list of
  schema problems).
- `predicted` is `null` when the reply had no such field or no
  readable record.

`<run_id>_replies.jsonl`:

```json
{"item_id": "INC-004467", "model": "gpt-4o-mini", "messages_sha": "5b1c...",
 "reply": "{\"category\": ...}", "error": null, "seconds": 1.12}
```

`<run_id>_summary.json` — keys (all always present):

```json
{
  "contract": "eval-summary/1",
  "run_id": "2026-09-20_hosted_heldout_20",
  "label": "hosted", "endpoint": "hosted", "model": "gpt-4o-mini",
  "dataset": "data/eval/heldout_20.jsonl",
  "dataset_sha256": "9f92ad8c9de71479",
  "system_prompt_matches": true,
  "created": "2026-09-20T01:26:57",
  "settings": {"temperature": 0.0, "max_tokens": 512, "json_mode": false},
  "item_ids": ["INC-004183", "..."],
  "skipped_dataset_lines": [],

  "n_items": 20,
  "n_parsed": 20,
  "parse": {"clean": 20, "recovered": 0, "failed": 0, "no_reply": 0},
  "schema_valid_rate": 1.0,

  "per_field_accuracy": {"category": 0.95, "affected_system": 0.75, "asset_tag": 1.0,
                         "urgency": 0.4, "impact": 0.95, "requested_action": 0.3,
                         "routing_queue": 0.85},
  "per_field_accuracy_when_parsed": {"...same seven keys...": 0.0},
  "requested_action": {"measure": "word-set Jaccard ...", "match_threshold": 0.5,
                       "mean_similarity": 0.377, "limits": "It compares WORDS ..."},

  "overall_exact_match": 0.3,
  "overall_exact_match_fields": ["category", "affected_system", "asset_tag",
                                 "urgency", "impact", "routing_queue"],

  "invented": {"total": 0,
               "by_kind": {"not_in_allowed_list": 0, "unexpected_field": 0,
                           "asset_tag_not_in_ticket": 0},
               "examples": [{"item_id": "...", "field": "...", "value": "...", "kind": "..."}]},

  "per_class": {"category": {"erp": {"n": 2, "field_correct": 1, "record_exact": 1,
                                     "thin": true}}, "urgency": {}, "impact": {}},
  "urgency_errors": {"shape": {"over_by_1": 10, "over_by_2_or_more": 2, "under_by_1": 0,
                               "under_by_2_or_more": 0, "not_a_level": 0,
                               "no_usable_reply": 0},
                     "misses": [{"item_id": "INC-004467", "expected": "high",
                                 "predicted": "critical", "step": 1}]},
  "review": {"H1_urgency": ["INC-005962", "INC-006285", "INC-004467"],
             "H1_arguable_total": 12, "H1_direction": "over-escalates",
             "H2_requested_action": ["...at most 5 ids..."],
             "H2_below_threshold_total": 14},

  "seconds_total": 25.8,
  "seconds_per_item_median": 1.25,
  "items": [{"item_id": "INC-004183", "parse": "clean", "schema_valid": true,
             "exact_fields_correct": 5, "record_exact": false,
             "action_similarity": 0.333,
             "wrong_fields": ["requested_action", "routing_queue"]}],
  "limitations": ["20 tickets: one ticket is 5 percentage points. ...", "..."]
}
```

What the numbers mean (the binding part):

- **Four measurements, never folded together:** `schema_valid_rate`
  (format), `per_field_accuracy` (fields), `overall_exact_match`
  (record), `invented` (a count).
- `schema_valid_rate`: `json.loads()` on the raw reply gives an object
  AND it passes `ticket_schema.json`. `parse: "recovered"` (JSON found
  only after stripping a fence or prose) has its content scored but is
  NOT schema-valid.
- Every rate is over **all** `n_items`; an unreadable reply is wrong on
  every field. `per_field_accuracy_when_parsed` is over the `n_parsed`
  readable replies only.
- `overall_exact_match`: all six exact-match fields right on one
  ticket. `requested_action` is excluded.
- `per_class` holds counts, not rates; `thin` = fewer than 5 tickets.
  Every allowed class is listed, including classes with `n: 0` - a
  class the dataset never tested is reported ("NOT TESTED"), not
  omitted. Cleaned `val.jsonl` has no `critical` and no `enterprise`
  ticket at all.
- `dataset_sha256` fingerprints the questions and expected answers
  actually used (so `--limit 5` gives a different fingerprint).
- `system_prompt_matches`: every row's system message equals
  `dataset_utils.SYSTEM_PROMPT`. `false` means the file is stale.
- `limitations` must be shown wherever the numbers are shown.

### Composition rule

A comparison (S12, S19) is built from **summary files only** —
`run_eval.compare_summaries([summary, ...])` or `--compare`. Two to
four runs; one column per run, named by `label` (by `run_id` if two
labels collide). It **refuses** runs whose `dataset_sha256` differ: a
table comparing different exams is worse than no table. With `--out`
it writes `comparison.json` and `comparison.txt`:

```json
{
  "contract": "eval-comparison/1",
  "dataset": "data/eval/heldout_20.jsonl", "dataset_sha256": "9f92ad8c9de71479",
  "n_items": 20,
  "runs": [{"name": "base", "run_id": "...", "endpoint": "local",
            "model": "llama3.2:3b", "json_mode": false}],
  "metrics": [{"metric": "schema_valid_rate", "kind": "rate",
               "values": {"base": 0.85, "hosted": 1.0}}],
  "per_class": {"urgency": [{"class": "low", "n": 10, "thin": false,
                             "field_correct": {"base": 9, "hosted": 2}}]},
  "per_item": [{"item_id": "INC-004183",
                "exact_fields_correct": {"base": 5, "hosted": 5}}],
  "limitations": ["..."]
}
```

`metrics` rows, in order: `schema_valid_rate`, the seven fields,
`requested_action_mean_similarity`, `overall_exact_match`,
`invented_values`, `seconds_per_item_median`. `kind` is `rate`,
`score`, `count` or `seconds`. In `per_item`, `null` means no readable
reply.

Additive changes (new keys) are allowed and keep `eval-summary/1`.
Renaming or redefining a key is a raise-with-Ritesh change and bumps
the contract string.

### Where notebook 06 (Day 2 S12) leaves its runs (P6)

Notebook 06 calls the CLI above and nothing else; it scores nothing
itself. Everything lands in `CHECKPOINT_DIR / "eval"` (Drive on
Colab), so a later notebook - Day 4 S19 - can add a column with
`--compare` and never re-run these two:

| File | What |
|---|---|
| `06_base_<model_key>_{summary.json,rows.jsonl,replies.jsonl,report.txt}` | the untuned model the adapter sits on. `<model_key>` is a key of `finetune_utils.MODEL_CHOICES`, e.g. `llama3.2-1b`; endpoint `local` with `OLLAMA_MODEL` set to that model's Ollama name; label `base` |
| `06_tuned_<source>_<fingerprint>_{...}` | the tuned model. `<source>` is `yours` or `prebaked`; `<fingerprint>` is the first 8 hex digits of the sha256 of `adapter_model.safetensors`; endpoint `tuned`; label `tuned` |
| `06_adapter_in_use.json` | what `compare_utils.find_adapter` decided: `source`, `path`, `fingerprint`, `model_key`, `ollama_base`, every folder it `checked` with a verdict |
| `06_base_vs_tuned/comparison.{json,txt}` | the S12 table (`eval-comparison/1`) |
| `06_reflection.json` | the group's rubric tally sheet (TODO 3) |

- Both runs always pass `--resume`. That is safe only because the run
  id names the model: the tuned id carries the adapter's fingerprint,
  so a retrained adapter gets a new id and its replies are never mixed
  with an older adapter's. Anything else that calls `--resume` must
  keep that property.
- **Adapter choice (binding for S12 and S19):** the participant's own
  adapter if usable (`CHECKPOINT_DIR/05_finetune/<model>_<run>/adapter_final`,
  then `checkpoints/adapter_<model>_<run>/`), else
  `checkpoints/adapter_prebaked/`. "Usable" = config parses, the base
  model has an Ollama twin, and the safetensors file is as long as its
  own header says. The choice is printed, saved in
  `06_adapter_in_use.json`, and printed again next to the final
  numbers. Never a silent substitution.
- The base column is the model **the adapter in use** sits on, read
  from its `adapter_config.json` - not `OLLAMA_MODEL` from `.env`.
- Ollama in Colab is ONE pinned release,
  `ollama_utils.OLLAMA_VERSION` (0.12.10: the release every reference
  score was measured on), unpacked from the versioned `.tgz` - the
  moving `install.sh` is never piped into a shell.

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
