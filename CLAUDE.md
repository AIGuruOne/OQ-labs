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
- Eval: `python scripts/run_eval.py --dataset <path> --endpoint <name>`
- Image scoring: `python scripts/score_extraction.py --pred <path> --truth <path>`
- Data quality: `python scripts/quality_checks.py --dataset <path>`
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
`config/endpoints.py`), eval output format (#4), index interface (#5).
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
- `scripts/quality_checks.py` (P3) is not built yet. Notebook 04 has
  its call site: it runs `--dataset data/finetune/train.jsonl` if the
  script exists and prints a note if not. After P3 lands, re-execute
  `solutions/04_dataset_builder.ipynb` so the retained output shows
  the real report. P3 should reuse `find_near_duplicates`,
  `find_leakage`, `find_schema_violations` from `dataset_utils`.
- Notebooks 04's two versions are the same cells except the three TODO
  cells. If you edit one, make the same edit in the other.
