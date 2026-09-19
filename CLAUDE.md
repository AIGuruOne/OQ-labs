# OQ Advanced AI for IT: lab repo

Teaching material for a 5-day onsite program with OQ (Oman energy company) IT
practitioners, 27 Sept to 1 Oct 2026. Read BUILD_SPEC.md before doing anything.

## What this repo is
Notebooks, synthetic data, eval scripts and services for hands-on labs.
This is teaching material, not production code. Legibility beats elegance
every time.

## Hard rules
- NEVER run `pip install -U` or add unpinned dependencies. The stack freezes
  24 Sept. Ask before adding any dependency.
- NEVER change the ticket schema in data/finetune. Every eval depends on it.
- NEVER change lab durations or session order. The schedule is time-budgeted.
- NEVER move to a bigger model or accelerator to make something work. Fix the
  approach or raise it.
- NEVER commit secrets, or notebook outputs containing them.
- All synthetic data only. No real OQ material, names, sites or asset tags.

## Notebook style
- One idea per cell. Explicit intermediate variables. Plain names.
- A markdown cell before every code cell explaining why, not what.
- Print the shape or a sample of what just happened. No silent success.
- Helpers go in utils.py and get imported, not inlined at 80 lines.
- Test: can a participant read a cell and modify it in under a minute?

## Two versions of every notebook
- notebooks/ has TODO gaps for participants. Outputs cleared before commit.
- solutions/ runs clean end to end. Outputs retained as the reference.

## Every notebook must
- Detect Colab versus local in the first code cell and branch accordingly.
- Save to Drive at every milestone. Runtimes disconnect.
- Resume from the last checkpoint after a reconnect.
- Declare at the top: expected runtime, requirements, what correct looks like.
- Run on a cold free-tier Colab runtime within its declared budget.

## Conventions
- Equipment tags: P-1201A. Site codes: three invented letters. Tickets:
  INC-004412. Work orders: WO-118305. IT assets: LAP-04412. Dates: ISO 8601.
- Scripts take arguments. No hardcoded paths.
- Pinned versions only, exact, no ranges.

## Commands
- Environment check: `python setup/setup_check.py`
- Eval: `python scripts/run_eval.py --dataset <path> --endpoint <name>` (`--label`, `--out`, `--json-mode`, `--resume`, `--replies <file>`, `--limit`, `--all`)
- Compare runs: `python scripts/run_eval.py --compare <a_summary.json> <b_summary.json> [...]`
- Image scoring: `python scripts/score_extraction.py --pred <path> --truth <path>`
- Data quality: `python scripts/quality_checks.py --dataset data/finetune` (a folder, or `--dataset <train file> --val <val file>`; `--all` lists every finding)
- Mock ERP: `uvicorn services.mock_erp.main:app --reload`
- Tickets: `python scripts/generate_tickets.py --count 600 --seed 42`
- Ticket checks: `python scripts/check_tickets.py --tickets corpus/tickets/tickets_raw.jsonl --labels data/finetune/ticket_labels.jsonl --schema data/finetune/ticket_schema.json`
- Dataset: `python scripts/build_dataset.py --seed 42` (add `--no-plant --finetune-dir <dir> --eval-dir <dir>` for a clean copy)
- Tests: `python -m pytest tests/`

---

## Session knowledge (added during the build — keep current)

### Interface contracts
The five contracts live in `docs/contracts.md` and are binding:
corpus layout + frontmatter (#1), notebook conventions (#2, full text
in `docs/notebook_conventions.md`, reference in
`notebooks/_template.ipynb`), endpoint config (#3, implemented in
`config/endpoints.py`), eval output format (#4, final, implemented in
`scripts/run_eval.py`), index interface (#5).
Do not change a contract silently — that is a raise-with-Ritesh change.

### Endpoints and env vars
- The hosted API key is `OPENAI_API_KEY` — exactly that name, in a
  repo-root `.env` (template: `setup/.env.example`). A common failure
  is a misspelled variable name; `setup_check.py` detects near-misses.
- All three endpoints (local Ollama, hosted, tuned adapter) speak
  OpenAI-compatible `POST {base}/v1/chat/completions`.
  `config/endpoints.py` is the only place that protocol lives —
  notebooks never hand-roll HTTP to a model.
- `config/endpoints.py` and `setup/setup_check.py` parse `.env`
  themselves (stdlib) so both work before `pip install`.

### Python versions (verified 2026-09-19)
- Colab is mid-rollout: new default image is Python 3.13.15 /
  Ubuntu 24.04; the pinnable previous runtime "2026.07" is Python
  3.12.13 / Ubuntu 22.04. Colab preinstalls torch 2.11.0+cu128,
  transformers 5.16.1, numpy 2.1.3, pandas 2.2.3, requests 2.32.4,
  pydantic 2.13.5, accelerate 1.14.0, datasets 4.8.5, httpx 0.28.1.
  Authority: github.com/googlecolab/backend-info (pip-freeze.gpu.txt).
- `requirements.txt` pins match Colab's preinstalled versions where
  Colab ships the package. Do not "upgrade" a pin to the newest PyPI
  version — matching Colab is the point.
- Local work targets Python 3.11/3.12. Do NOT use 3.13/3.14 locally:
  the fine-tuning stack does not support them. The build machine has
  3.14 as default `python` — use the uv-managed 3.11 for venvs.
- The GPU fine-tuning stack lives in `requirements-finetune.txt`
  (Linux/Colab T4 only), installed by the Day 2 notebooks' pinned
  install cell — NOT in base `requirements.txt`, because it cannot
  install on participants' Windows laptops.

### setup_check.py behaviour
- stdlib only, on purpose. PASS/WARN/FAIL/INFO rows; exits non-zero
  only on FAIL. Ollama missing = WARN (only needed Day 2). GPU absent
  = INFO, never a failure.

### Repo state notes
- Remote: https://github.com/Utkarsh-09/AI_GURU_labs.git — this is the
  URL the notebooks' environment-detection cell clones in Colab
  (`REPO_URL` in notebooks/_template.ipynb and
  docs/notebook_conventions.md; keep all three in sync).
- `notebooks/_template.ipynb` must always run top-to-bottom clean; it
  is the reference for Contract #2.

### Ticket corpus (P1)
- `corpus/tickets/tickets_raw.jsonl` + `data/finetune/ticket_labels.jsonl`
  are GENERATED (seed 42, count 600). Never hand-edit them. The
  generator is stdlib-only and byte-deterministic across OS and Python
  3.11-3.14; `tests/test_generate_tickets.py` fails if the committed
  files and the generator disagree.
- Editing `scripts/ticket_scenarios.py` or `scripts/ticket_phrases.py`
  changes the corpus. After any edit: regenerate, run
  `check_tickets.py` (must end "All checks passed", including the
  real-name denylist), update the two SHA-256 values in
  `corpus/README.md`, then rebuild everything downstream (dataset,
  adapter, eval tables).
- Label rules live in `corpus/README.md` ("Labelling rules"). The one
  people get wrong: urgency follows the stated business effect, never
  the tone; a two-problem ticket is labelled for its FIRST problem.
- People in tickets are first names only, on purpose (no generated
  name can match a real employee). Enterprise system names are
  invented; OQ's real ERP (SAP, project "e-Symphony") is on the
  denylist.
- `.gitattributes` forces LF on `*.jsonl` so the hashes survive a
  Windows checkout.

### Fine-tuning dataset (P2)
- Sizes are train 400 / val 80 / heldout 20 (BUILD_SPEC 8B), the
  builder defaults. 500 / 100 was tried on 2026-09-20 and reverted:
  only 580 tickets remain after the held-out 20, so a `--no-plant`
  build at 500 + 100 cannot be supplied. The builder now exits with
  "Not enough tickets" instead of silently writing a short val.jsonl
  (tested). Do not raise the sizes without growing the corpus.
- `data/finetune/{train,val}.jsonl`, `data/eval/heldout_20.jsonl`,
  `split_manifest.json` and `planted_problems.json` are GENERATED by
  `scripts/build_dataset.py --seed 42`. Never hand-edit them. The
  build is byte-deterministic (verified on Python 3.11-3.14) and
  `tests/test_build_dataset.py` fails if committed files and builder
  disagree. `.gitattributes` forces LF on them.
- Row format is `{"ticket_id", "messages": [system, user, assistant]}`
  (Contract 1, "Fine-tuning pair format"). Role/content only - never
  bake a model's chat-template tokens into the data. The tokenizer
  applies the template at training time, Ollama at inference time.
- `dataset_utils.SYSTEM_PROMPT` (`notebooks/dataset_utils.py`) is the
  ONLY copy of the prompt. Training, eval and the three-way comparison
  import it. Changing it means: rebuild dataset, retrain adapter,
  rerun eval tables, re-execute solutions notebooks.
- train/val carry PLANTED problems on purpose (20 near-duplicates, 5
  leaked rows, 10 schema violations). Do not "fix" them.
  `planted_problems.json` + `scripts/plant_problems.py` are the
  facilitator answer key - never load either from a participant
  notebook. `data/README.md` has the detail.
- The near-duplicate measure is word-set Jaccard on subject + body,
  threshold 0.8 (`dataset_utils.NEAR_DUPLICATE_THRESHOLD`). At 0.8 the
  checks find exactly the 20 plants; the closest natural pair in the
  corpus is 0.78. Changing the threshold or the measure changes what
  the lab finds - rebuild and rerun the tests.
- `heldout_20.jsonl` must stay identical with and without `--no-plant`
  (tested). It is stratified by `dataset_utils.select_heldout`, which
  also refuses any ticket with a lookalike (>= 0.6) in the corpus.
- Notebook 04 expected final numbers: 373 clean train, 72 clean val
  (header cell and final cell; both versions).
- Notebooks 04's two versions are the same cells except the three TODO
  cells. If you edit one, make the same edit in the other.

### Quality checks (P3)
- `scripts/quality_checks.py`: five checks, each `check_x(dataset,
  options) -> result` with the SAME result shape. No check calls
  another and the report printer only reads result dicts, so one check
  can be removed or left as a `raise NotImplementedError` TODO (it
  then shows as `TODO` in the report) - tested for every check. Keep
  that property when editing.
- Near-duplicates, leakage, schema = FAIL (exit 1). Coverage,
  imbalance = WARN (exit 0). Unreadable input = exit 2 with a
  sentence, never a stack trace. One broken line is reported and the
  rest of the file is still checked.
- Class imbalance is REPORTED, NEVER CORRECTED. Do not add a
  rebalance/resample helper; `tests/test_quality_checks.py` fails on
  one. The decision belongs to the participants.
- It reuses `find_near_duplicates`, `find_leakage` and
  `find_schema_violations` from `dataset_utils`. Those now also return
  row positions (`first_row`, `second_row`, `row`) and structured
  `errors`; `quality_checks.violation_kind` turns a schema error into
  the answer key's vocabulary (invalid_enum_value, missing_field,
  stray_prose, malformed_asset_tag, plus null_not_allowed, wrong_type,
  unexpected_field, empty_value, completion_not_json).
- Findings point at `file:line` (1-based, as an editor shows it), the
  same numbering as `planted_problems.json`.
- Report output is ASCII only and at most 100 columns (tested): it has
  to survive a cp1252 Windows console and a projector.
- Leakage = same ticket_id in both splits OR same text (>= threshold)
  under different ids across the split. Near-duplicates are searched
  INSIDE each split only, so nothing is reported twice.
- After any change to the dataset or the checker: run the tests, then
  re-execute `solutions/04_dataset_builder.ipynb` (its retained output
  contains the full report).

### Eval harness (P4)
- Two files on purpose: `scripts/eval_scoring.py` holds EVERY scoring
  rule (pure functions, no network, no files); `scripts/run_eval.py`
  asks the model, writes the Contract 4 files, renders tables and does
  `--compare`. A rule change goes in `eval_scoring.py` AND
  `data/eval/rubric.md` - they must say the same thing.
- `data/eval/rubric.md` is a DRAFT until Ritesh signs it (the block at
  its end). It carries one open question for him: the system prompt
  does not define the urgency levels, so untuned models are marked
  against a convention they never saw. Do not "fix" that by editing
  `SYSTEM_PROMPT` - it means a full rebuild and it is his call.
- Four measurements, never folded together: format
  (`schema_valid_rate`), fields (`per_field_accuracy`), record
  (`overall_exact_match`, six exact fields, no requested_action),
  invented values (a count). Do not add a blended score;
  `tests/test_run_eval.py` checks each has its own report heading.
- Schema-valid is STRICT: `json.loads(raw reply)` works AND the schema
  passes. Fenced / prose-wrapped JSON is "recovered": content scored,
  format failed. `null` in an enum is a schema problem, not an
  invented value.
- `requested_action` = word-set Jaccard (`du.text_similarity`), match
  at >= 0.5. Calibrated on 40 real replies: no false matches at >= 0.5,
  but plenty of adequate answers below it - so it is reported as a
  FLOOR and rubric H2 samples below it. Changing the threshold or the
  measure invalidates every saved summary.
- The harness has no model-specific code. `ask(messages) -> str` is the
  whole model interface (`run_eval.run_evaluation`), which is how Day 4
  S19 adds retrieval without touching the harness.
- JSON mode is OFF by default so the score shows the model unaided;
  `--json-mode` is a talking point, not the baseline.
- A run always calls the model again unless `--resume` is given
  (stale replies after a retrain would be silent and wrong).
  `--replies <file>` re-scores a saved run with no model call - use it
  after any scoring change to refresh
  `facilitator/prebaked_outputs/eval/`.
- `--compare` reads summary files only and REFUSES runs whose
  `dataset_sha256` differ (e.g. one run used `--limit`).
- Rows whose EXPECTED answer is broken are skipped, not scored - so
  the harness can be pointed at `val.jsonl` (it skips the planted
  schema violations and says so).
- Small-sample honesty is built in: per-class output is counts, never
  percentages; classes under 5 are flagged `thin`; the limitations
  block is in the summary JSON, the report and the comparison. Do not
  remove it. A class with n = 0 is listed as NOT TESTED, never
  omitted (tested).
- KNOWN DATA GAP (P2, not fixed here): `val.jsonl` has exactly ONE
  `critical` / `enterprise` row (INC-004736, line 38) and the planter
  put a schema violation on it, so the cleaned val set (72 rows) has
  zero of either. The split stratifies by category only. Fixing it
  means changing the builder or the planter, which changes the
  byte-pinned dataset, notebook 04's numbers and everything
  downstream - a decision for Utkarsh / Ritesh, not a quiet edit.
- Report output is ASCII only and at most 100 columns (tested). Model
  output is escaped before printing.
- Reference runs (2026-09-20, held-out 20): llama3.2:3b 17/20
  schema-valid, 2/20 whole record, ~95 s on the build machine's CPU;
  gpt-4o-mini 20/20 schema-valid, 6/20 whole record, ~27 s, urgency
  8/20 with all 12 misses over-escalations.
- Build-machine gotcha: the Ollama desktop app here is set to a
  262144-token context, so llama3.2:3b asks for 15.9 GiB and fails to
  load. Run a second server instead of touching the app:
  `OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 ollama serve`
  and set `OLLAMA_BASE_URL=http://localhost:11435` for the run.
