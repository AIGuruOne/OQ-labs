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
- Register the tuned adapter with Ollama: `python scripts/register_adapter.py --adapter <folder>` (`--name`, `--base`, `--print-modelfile`)
- Fine-tune plumbing test, any machine, ~5 min: `OQ_SMOKE_TEST=1 python -m nbconvert --to notebook --execute --output <out.ipynb> solutions/05_finetune.ipynb` (write the output ELSEWHERE, never over the solution)
- Base vs tuned (notebook 06) headless, ~3 min with Ollama 0.12.10 + `llama3.2:1b`: `python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/06_compare_base_tuned.ipynb`
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

### Fine-tune lab (P5)
- Stack is plain transformers 5.16.1 + peft 0.20.0 + bitsandbytes
  0.50.2, NOT unsloth. Reasons, sources, timing arithmetic and the T4
  checklist: `docs/finetune_stack.md`. unsloth 2026.9.7 caps
  transformers<=5.5.0, so it would downgrade a cold Colab runtime and
  force a restart. On Colab notebook 05 installs bitsandbytes ONLY -
  `tests/test_notebook_05.py` fails if it ever installs torch,
  transformers, peft, accelerate or unsloth.
- transformers 5.x renamed Trainer arguments: `warmup_ratio`,
  `group_by_length`, `evaluation_strategy` are GONE (now
  `warmup_steps=0.1`, `train_sampling_strategy="group_by_length"`,
  `eval_strategy`, `processing_class=`). 4.x tutorial code crashes.
- Default model is Llama 3.2 **1B** via the ungated mirror
  `unsloth/Llama-3.2-1B-Instruct` (Meta's repo is gated). Measured on a
  free T4 2026-09-20: 7.1 min training for 72 steps (budget 25). 3B is
  selectable (`MODEL_NAME`) but only ~1.4x inside the budget, unmeasured.
  Because tuned is 1B, the fair "base" for S12 is `llama3.2:1b`, not
  the `llama3.2:3b` that P4 scored.
- `finetune_utils.LLAMA3_SERVING_TEMPLATE` exists because HF's Llama
  3.2 chat template writes "Today Date: <today>" into the system block
  and Ollama's does not. Training uses Ollama's exact text (tested byte
  for byte). Do not "simplify" it back to the tokenizer's own template.
- `generate_reply` sets temperature/top_p to 1.0 and an explicit total
  `max_length` on a COPY of the model's generation config. Setting them
  to None does not work in 5.16.1 (refilled from Llama's defaults, with
  warnings on every call).
- The 25-minute budget is enforced in code: `ProgressCallback` stops at
  23 min of accumulated training time (across resumes) and saves.
- Resume safety: `check_run_folder` refuses to resume a run folder whose
  settings differ (new `RUN_NAME` instead). `find_last_checkpoint`
  skips a checkpoint folder with no `trainer_state.json`.
- `solutions/05_finetune.ipynb` outputs are Utkarsh's real T4 run. The
  two TODO cells were hand-filled participant cells with identical
  values; only their wording was swapped to the solution text. Never
  re-execute it on CPU - the retained output must stay a T4 run.
- The untuned 1B returns VALID JSON; it fails on content (copies the
  prompt's example tag LAP-04412 into every ticket, wrong queues). Do
  not write lab text that promises a schema-validity win.
- `routing_queue` is a free string in the locked schema: an invented
  queue is the eval harness's "invented values", not a schema failure.
- Build-machine gotchas: run notebooks with `python -m nbconvert`, NOT
  `python -m jupyter nbconvert` (the latter dispatches to whichever
  `jupyter-nbconvert.exe` is first on PATH - the base `.venv`), and
  with `env -u VIRTUAL_ENV`. The fine-tune venv is `.venv-finetune`.
  mlx's Windows wheel has no backend; use `mlx[cpu]` in a Linux
  container. Do not run a CPU training job and the MLX container at
  the same time - 27 GB RAM is not enough and background jobs get killed.
- Pre-baked adapter: `checkpoints/adapter_prebaked/` is Utkarsh's real
  T4 run (README there has hyperparameters, sha256, scores, and the
  urgency discussion). Tuned vs its own base on the held-out 20:
  routing 7->16, requested_action 1->16, whole record 2->4, urgency
  4->7, invented values 3->0. Urgency 7/20 is BELOW the untuned 3B's
  13/20 - explained in that README and playbook entry 8; on the 72
  validation tickets urgency is 55/72. Do NOT retrain to lift the
  held-out urgency number: that is tuning to the exam.
- Ollama serving costs a little: the same adapter through PyTorch
  scores 1 to 3 tickets higher on three fields (Ollama applies it on
  its Q8 base). Reference numbers are the Ollama ones on purpose.
- Notebook 05b (MLX): one epoch per call + `mlx_progress.json`, because
  mlx-lm resumes weights only. `finetune_utils.convert_mlx_adapter_to_
  peft` makes its output the SAME PEFT format as notebook 05 (verified
  against PyTorch to 0.0013 in logits). Executed only on MLX's Linux
  CPU backend in a container - NEVER on a Mac. `solutions/05b` has no
  retained outputs on purpose; a Linux smoke run is not a reference.
- STILL OWED for P5 (all need hardware this machine lacks): second
  timed T4 run of 05 with the whole-notebook stopwatch; the Colab
  disconnect test; any run of 05b on Apple Silicon (speed, memory, the
  real 1B model). Steps: `docs/finetune_stack.md` sections 4 and 5.

### Base vs tuned, notebook 06 (P6)
- One command, one table: the notebook SCORES NOTHING itself. It runs
  `scripts/run_eval.py` three times (base, tuned, `--compare`) through
  `compare_utils.run_command`; base and tuned differ only in endpoint,
  label and run id (tested). Do not add scoring or analysis cells.
- **OLLAMA IS PINNED TO 0.12.10** (`ollama_utils.OLLAMA_VERSION`).
  Tested 2026-09-20: the LoRA `ADAPTER` import that makes the `tuned`
  endpoint works on 0.12.10, fails on 0.33.3, and 0.34.2 says `LoRA
  adapters are no longer supported`. Colab gets the pinned `.tgz`
  unpacked by `ollama_utils.install_on_linux` - never pipe the moving
  `install.sh`. Do NOT bump the pin without re-running register + both
  evals.
- **DECISION 2026-09-21: the tuned endpoint (so notebook 06) is COLAB
  T4 ONLY.** A laptop is documented as UNSUPPORTED for the tuned
  model, not as a fallback - do not write text that recommends it or
  asks participants to install/downgrade Ollama. The notebook still
  runs locally (prints `LOCAL RUN - NOT A SUPPORTED PATH`) because the
  build machine has 0.12.10: that is how the reference output and the
  tests are produced. The one machine that must have 0.12.10 on
  purpose is the facilitator's (fallback ladder, BUILD_SPEC 15). The
  pre-program email should ask anyone who already has Ollama to report
  `ollama --version` (`setup/ollama_setup.md`).
- Adapter choice is `compare_utils.find_adapter`: the participant's
  own (`CHECKPOINT_DIR/05_finetune/<model>_<run>/adapter_final`, then
  `checkpoints/adapter_<model>_<run>`), else the pre-baked one. It
  validates the safetensors length (a save cut off by a disconnect is
  rejected), prints every folder checked with a verdict, and the
  choice is printed again beside the final numbers. Never make the
  fallback quiet. The base column is the model THE ADAPTER IN USE sits
  on, not `OLLAMA_MODEL` from `.env`.
- Results go to `CHECKPOINT_DIR/eval` with run ids
  `06_base_<model_key>` and `06_tuned_<source>_<fingerprint>`
  (contracts.md, Contract 4). Both runs always pass `--resume`; that
  is only safe because the tuned run id carries the sha256 fingerprint
  of the weights.
- The four side-by-side tickets are picked by fixed rules
  (`compare_utils.pick_examples`: format fixed, biggest content gain,
  tuned worse, still wrong). Never hand-pick. A test fails if the
  reference run stops containing a ticket where tuned did worse.
- The tuned column wins every aggregate row, and that was checked, not
  assumed: held-out is leak-free (tested in P2), the big gains are the
  house conventions (requested_action 0->16, routing 7->16, format
  13->20), urgency (5->7) and whole record (2->4) stay poor and inside
  the noise, and tuned is WORSE on INC-005370 and INC-005480.
- The untuned 1B is NOT stable at temperature 0: 9 to 12 of its 20
  replies change between sittings or machines (schema-valid seen at 9,
  12 and 13 of 20); one extra warm-up request is enough. The tuned
  replies were byte-identical on Windows and Linux. Quote the base
  column as "about", never chase a one-ticket difference (playbook 10).
- A Colab CPU runtime cannot run this lab (two cores: a ticket exceeds
  the endpoint's 120 s timeout), so the Ollama cell stops at once on
  Colab without a GPU, and its message no longer offers a laptop.
- The build machine's "CPU only" timings are not quite that: Ollama
  puts most of a 1B model on the integrated AMD GPU (`ollama ps`).
- Both versions are generated from one cell list so they cannot
  drift; the generator was a scratch script and is NOT in the repo.
  Edit both .ipynb files with the same change (tested), then re-execute
  the solution from a cold state: delete `checkpoints/local/eval`,
  `ollama stop` both models, run with `OLLAMA_BASE_URL=http://localhost:11435`,
  write elsewhere, copy outputs in, refresh the `06_*` files in
  `facilitator/prebaked_outputs/eval/`. The solution's TODO 3 numbers
  must match its own retained table (tested).
- `solutions/06` retained outputs are a LOCAL run on the build machine
  (Ollama 0.12.10), i.e. the unsupported path - the only one available
  here. Replace them with the first clean Colab T4 run, as was done for
  notebook 05, and update the header's measured minutes.
- STILL OWED for P6: two stopwatch runs on a cold free-tier Colab T4
  (nobody has yet seen Ollama 0.12.10 use the T4 inside Colab - check
  the warm-up line), the Colab disconnect test, and a run with a real
  participant-trained adapter (the fallback tests used a copy of the
  pre-baked one).

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
