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
- Environment check: `python setup/setup_check.py` (`--network`: can this network reach every host the week needs - run it on the OQ network)
- Eval: `python scripts/run_eval.py --dataset <path> --endpoint <name>` (`--label`, `--out`, `--json-mode`, `--resume`, `--replies <file>`, `--limit`, `--all`)
- Compare runs: `python scripts/run_eval.py --compare <a_summary.json> <b_summary.json> [...]`
- Image scoring: `python scripts/score_extraction.py --pred <path> --truth <path>`
- Data quality: `python scripts/quality_checks.py --dataset data/finetune` (a folder, or `--dataset <train file> --val <val file>`; `--all` lists every finding)
- Mock ERP: `uvicorn services.mock_erp.main:app --reload` (on Windows drop `--reload`: the reload hangs, playbook 17). Walk every endpoint: `python -m services.mock_erp.tour` (`--base-url`, `--api-key`). Regenerate seed: `python -m services.mock_erp.seed --seed 42`; OpenAPI file: `python -m services.mock_erp.write_openapi`
- Tickets: `python scripts/generate_tickets.py --count 600 --seed 42`
- Ticket checks: `python scripts/check_tickets.py --tickets corpus/tickets/tickets_raw.jsonl --labels data/finetune/ticket_labels.jsonl --schema data/finetune/ticket_schema.json`
- Dataset: `python scripts/build_dataset.py --seed 42` (add `--no-plant --finetune-dir <dir> --eval-dir <dir>` for a clean copy)
- Register the tuned adapter with Ollama: `python scripts/register_adapter.py --adapter <folder>` (`--name`, `--base`, `--print-modelfile`)
- Fine-tune plumbing test, any machine, ~5 min: `OQ_SMOKE_TEST=1 python -m nbconvert --to notebook --execute --output <out.ipynb> solutions/05_finetune.ipynb` (write the output ELSEWHERE, never over the solution)
- Base vs tuned (notebook 06) headless, ~3 min with Ollama 0.12.10 + `llama3.2:1b`: `python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/06_compare_base_tuned.ipynb`
- Fundamentals (notebook 01) headless, ~40 s, needs `OPENAI_API_KEY`: delete `checkpoints/local/01_*.json`, then `python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/01_fundamentals.ipynb`
- Local inference (notebook 02) headless, ~60 s with Ollama running and `llama3.2:1b` pulled, needs `OPENAI_API_KEY` for one call: delete `checkpoints/local/02_*.json`, `ollama stop llama3.2:1b`, then `OLLAMA_BASE_URL=http://localhost:11435 python -m nbconvert --to notebook --execute --output-dir <elsewhere> <copy of solutions/02_local_inference.ipynb placed under checkpoints/>`
- Load test (notebook 03): `python scripts/concurrency_test.py --endpoint local` (`--levels 1,2,4,8,16`, `--requests 16`, `--max-tokens 64`, `--timeout 60`, `--base-url <url>/v1 --model <name>` for any OpenAI-compatible server, `--out`, `--run-id`, `--note`). Exit 2 = nothing measured (preflight failed), never a hang.
- Concurrency (notebook 03) headless, ~2.5 min with Ollama 0.12.10 + `llama3.2:1b`: delete `checkpoints/local/03_*.json` and `checkpoints/local/concurrency`, then `OLLAMA_BASE_URL=http://localhost:11437 python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/03_concurrency.ipynb` (a port with NO server, so the notebook starts one and can read `Parallel:N` from its log)
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
- `solutions/04_dataset_builder.ipynb` outputs are Utkarsh's Colab
  (free-tier CPU runtime) run of 2026-09-21, not a local run. Its
  output differs from a local run only in paths. If the dataset or
  the checker changes, re-execute it in Colab and install the outputs
  the same way; a local re-execution is fine for checking but should
  not replace the retained Colab output.

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
  contains the full report) - in Colab, see the P2 note above.

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
  13/20 - explained in that README and playbook E8; on the 72
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
  column as "about", never chase a one-ticket difference (playbook E10).
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
- `solutions/06_compare_base_tuned.ipynb` outputs are Utkarsh's real
  Colab T4 run (2026-09-21), scoring his OWN adapter from Drive
  (fingerprint b1c0e3d4 - the same weights as the pre-baked one, which
  was copied from that run). It was the participant notebook with the
  TODOs filled in by hand: TODO 1 and 2 had the solution's values;
  TODO 3 keeps the solution's reference answer, with its counts taken
  from the T4 table (that cell prints only `checkpoint saved`). Never
  re-execute it locally - the retained output must stay a T4 run.
  Execution counts are out of order in it (the examples cell ran before
  the compare cell); that is how it was run, leave it.
- T4 facts from that run: Ollama 0.12.10 install 56 s, pull 28 s,
  100% of the model in GPU memory, 0.8 s a ticket, 4.2 min from the
  settings cell to the end INCLUDING hand-filling the TODOs. Base
  column on the T4: schema-valid 10/20, routing 5/20. Tuned column:
  identical to the local and Linux runs, ticket for ticket.
- Colab does NOT save per-cell timings in these files (no
  `executionInfo`, in 04, 05 or 06). A downloaded .ipynb therefore
  cannot supply a section 11 wall-clock figure - only a stopwatch can.
  Do not write a whole-notebook minute count into `docs/timing_log.md`
  that nobody measured.
- `facilitator/prebaked_outputs/eval/06_*` are from a LOCAL run (the
  T4 run's files are on Utkarsh's Drive), and the README there says so.
- STILL OWED for P6: ONE section 11 measurement - fresh runtime, fresh
  kernel, solution version, Run all, stopwatch from the first cell -
  and the Colab disconnect test. (Done since P6 was committed: Ollama
  0.12.10 using the T4 inside Colab, and a run with a
  participant-trained adapter picked up from Drive.)
- STILL OWED for P5: unchanged. The `05_finetune.ipynb` handed over on
  2026-09-21 was the same run already retained in `solutions/05`
  (all 19 outputs identical), not a second run.

### Local inference, notebook 02 + Ollama guide (P8)
- Framing is **self-hosted vs vendor API**, not laptop vs cloud: the
  Colab runtime stands in for OQ's Azure VM. The header and a test
  (`tests/test_notebook_02.py`) pin that wording. The model is
  `llama3.2:1b` (the Day 2 model: one pull serves 02, 03, 05, 06), set
  in the settings cell and pushed into `OLLAMA_MODEL` so
  `get_endpoint("local")` follows it. `.env.example` keeps `llama3.2:3b`
  (P4's reference) - that is deliberate, not a mismatch.
- Ollama comes ONLY from `ollama_utils.ensure_server` / `ensure_model`
  (shared with 06). No second install cell, no `curl`, no `install.sh`
  in any notebook (tested). Additive changes made here:
  `start_server` notices `ollama serve` dying at once and raises
  `explain_server_exit(...)` (port clash reported in 4 s with the real
  log line and the next free port, instead of a 60 s wait);
  `warm_up` also returns `context_length` from `/api/ps`.
- `notebooks/inference_utils.py` holds the 02 helpers: `model_card`
  (/api/show), `chat_timed` (native /api/chat: nanosecond timings ->
  tokens per second), `run_experiments` (same prompt, N settings, twice
  each), `parse_json_reply`, `compare_records`, `marks_text`,
  `side_by_side`. Pure functions are tested in
  `tests/test_inference_utils.py` with stubbed HTTP.
- The key cell (`utils.ensure_api_key`) sits right after the install
  cell per Contract 2 point 6 but has NO assert: a missing key costs
  the comparison cell (TODO 2, which asserts `key_ok`), never the
  self-hosted part. Tested.
- The PULL CELL is separable and idempotent (`ensure_model` skips when
  the model is listed; skip path 2 s). Its time is saved to `02_pull`
  apart from run time. On Colab the pull-ahead cannot help - the
  runtime is ephemeral (install 56 s + pull 28 s on a T4, from 06's
  run); it helps laptops only. The header says so.
- **Research findings 2026-09-22:** current Ollama is v0.34.2
  (2026-09-15); its Linux asset is `.tar.zst` and the unversioned
  `ollama-linux-amd64.tgz` URL now returns 404, so every 2024-25
  "Ollama in Colab" tutorial command is broken. The versioned
  `?version=0.12.10` `.tgz` still resolves (1,875,523,113 bytes).
  Playbook E15. `/v1/chat/completions` on 0.12.10 returns `usage`
  and `finish_reason`; `/api/chat` returns `*_duration` in ns.
- **Measured 2026-09-22.** Local (Windows, Ollama 0.12.10 on port
  11435, model pulled, integrated AMD GPU 77%): whole solution
  notebook about a minute, 50 tokens/s. Clean `python:3.12-slim`
  container, `--cpus=2`: install by hand 226 s, pull 160 s, first call
  10 s incl. load, notebook 160 s, **3.1 tokens/s**, ticket reply 31 s.
  Same container, Colab code path (`ensure_server(in_colab=True)`
  after removing Ollama and the model store): install 209 s, pull
  132 s with progress lines, warm-up 7.7 s. The SAME container pinned
  with `--cpuset-cpus=0,1` (two real cores) is pathological on this
  machine, as P6 found: install 208 s, pull 139 s, then the first
  hand-typed call took 194 s and the notebook died on a 600 s read
  timeout (`not-installed` message still verified there). So the
  Colab CPU runtime is UNMEASURED: the notebook does not refuse it
  but tells people to take the T4; never quote a CPU-runtime speed
  as a Colab figure. Real pull path on Windows
  (`qwen2.5:0.5b`, 0.4 GB, scratch copy of the notebook): 49 s with
  progress lines. Failure modes provoked and their messages checked:
  not running -> helper starts it (6 s); not installed -> guide
  pointer; model not pulled -> `EndpointError` 404 / `OllamaError`
  "Run the pull cell first"; port held by a non-Ollama process ->
  E13. Playbook E13-E15 carry the exact text.
- The untuned 1B's ticket reply is NOT stable across machines (playbook
  E10 again): valid JSON with 2/6 fields on Windows, missing its closing
  brace (`not JSON`) in the Linux container, same request, temperature
  0. TODO 1's "repeatable" setting came back DIFFERENT on Windows and
  IDENTICAL on Linux. The header, the ticket markdown and TODO 1's
  markdown say this; do not write text promising a format win or
  determinism, and do not chase the difference.
- Both .ipynb files are generated from one cell list by a scratch
  script NOT in the repo (same practice as 01 and 06). Edit both files
  with the same change (parity test). To refresh the solution: delete
  `checkpoints/local/02_*.json`, `ollama stop llama3.2:1b`, execute
  headless from a copy under `checkpoints/` with
  `OLLAMA_BASE_URL=http://localhost:11435`, copy the output over
  `solutions/02_local_inference.ipynb`, copy the six `02_*.json` into
  `facilitator/prebaked_outputs/local_inference/`.
- STILL OWED for P8: the cold Colab run (T4 and CPU runtime) with a
  stopwatch, and the Colab disconnect test - the Colab branch of this
  notebook has not run on Colab (the same helper did, inside 06's T4
  run). Not tested: a Mac; copying `~/.ollama/models` between machines
  as the offline backup (the guide marks it untested).

### Concurrency lab, notebook 03 + sizing worksheet (P9)
- 15-minute budget, the tightest in the slice: two TODOs (the levels,
  the latency target), one load test of 80 requests, one text chart,
  one table, three numbers for `facilitator/sizing_worksheet.md`.
  Measured locally 2.5 to 4 min whole notebook; Colab T4 STILL OWED
  (expect install 56 s + pull 28 s + about a minute). A Colab CPU
  runtime is REFUSED by the server cell (80 x 30 s = 40 min).
- `scripts/concurrency_test.py` is the load driver: closed-loop threads
  per level, one POST to `{base}/chat/completions` per request (Contract
  3's protocol, nothing Ollama-specific), a preflight request that exits
  2 with a sentence if the endpoint cannot answer (never a hang: connect
  wait capped at 10 s), failures counted per cause and never averaged
  in, exit 0 whenever the test ran. Pure helpers (`percentile` nearest
  rank, `summarise_level`, `highest_level_within`, `render_table`,
  `text_chart`, `parallel_slots_from_log`) are what the notebook
  imports; the test itself runs through `compare_utils.run_command`.
  The chart is PLAIN TEXT on purpose: matplotlib is not in
  `requirements.txt` (Colab has 3.10.0; adding it is a raise-with-
  Ritesh change) and text survives a projector and a headless run.
- **`OLLAMA_NUM_PARALLEL` on 0.12.10 defaults to 1** (verified in
  `envconfig/config.go` at tag v0.12.10; `sched.go` uses
  `max(NumParallel, 1)`, no auto-4). The FAQ still says "auto-selects 4
  or 1" - the docs are older than the code. `/api/ps` does not report
  it; the server log's model-load line does (`Parallel:N`), which is
  what `parallel_slots_from_log` reads, so the notebook only knows the
  number for a server IT started (`unknown` for a laptop's app).
  Measured with 4 slots: knee moves to 8 callers, ceiling 3.6x higher,
  p95 still 4x at 16. Degradation shows either way with levels up to 16.
- FOUND 2026-09-22, quote carefully: on the build laptop throughput
  RISES from 1 to 4 callers on a one-slot server (0.33 -> 1.05 req/s)
  before it plateaus. The model's own clock says 1.6 s a request; a
  lone caller sees 3.0 s; queued requests land every 0.95 s. Where the
  gap goes was NOT established (Windows? the OpenAI-compat layer?) and
  is unmeasured on a T4. The notebook and the tests assert the PLATEAU
  (last two levels within 15%) and the p95 climb (>= 3x), never a
  fixed throughput gain. The 11435 server started by hand on
  2026-09-20 behaves the same way (its environment was never recorded).
- The integrated AMD GPU's share of the model moves the numbers by a
  third (62% -> 100% share: 4 m 05 s -> 2 m 27 s, knee 4 -> 8 callers)
  without changing the shape. Runs 1-2 vs 3-4 in `docs/timing_log.md`.
  Kill scratch Ollama servers before a reference run.
- A server the notebook starts on Windows dies with the kernel
  (`start_server` uses `start_new_session` only on POSIX), so every
  headless run on port 11437 is a fully cold path. Not changed here.
- Both .ipynb files come from one scratch generator NOT in the repo
  (same practice as 01/02/06); the solution's outputs are merged from
  an executed copy by cell id. Edit both files with the same change
  (parity test). To refresh: the command above, then copy the four
  `03_*` files into `facilitator/prebaked_outputs/concurrency/` and
  update the worked example in `sizing_worksheet.md` (its table is the
  retained run's, by value).
- The worksheet's worked example (brief 1, 200 tickets/day, 3x peak,
  10 s target) comes out at 1 server used 2% of the time at peak: the
  sheet's conclusion is the matrix's - capacity never justifies
  hosting at desk volume. No human group has timed the sheet.

### Day 1 paper artifacts (P12)
- `facilitator/` holds the Day 1 hand-outs: `decision_matrix_template.md`
  (S3), `architecture_spec_template.md` + `cost_model.xlsx` +
  `cost_model.md` (S4), `spec_review_checklist.md` (S5),
  `use_case_briefs.md` (handed out at the START of S4, groups confirmed
  at the close). `facilitator/README.md` is the map. Filled examples for
  brief 1 are in `facilitator/examples/`.
- `cost_model.xlsx` is GENERATED by `scripts/build_cost_model.py`
  (stdlib only - it writes the zip-of-XML itself, with live formulas;
  no spreadsheet library because the dependency list is frozen). Never
  hand-edit the .xlsx: `tests/test_cost_model.py` fails if it differs
  from the script. Prices live in `PRICES` + `SOURCES` in the script;
  edit there, rerun, commit. Verified 2026-09-22 by recalculating in
  Excel 16 (COM, in the test) and LibreOffice headless.
- Pricing sources: OpenAI, Anthropic, Gemini from vendor pages
  (primary); Azure VM prices from the Azure retail prices API
  (primary); Azure OpenAI regional/data-zone uplift is SECONDARY and
  marked VERIFY for Ritesh. T4 and A100 SKUs are NOT offered in UAE
  North / Qatar Central - the A10 (NV12ads A10 v5, $1.30/h) is the
  Gulf-region GPU in the model.
- Token counts in scenario A are MEASURED with the Llama 3.2
  tokenizer: system prompt 250, ticket mean 72 / p95 211, reply mean
  57. The worked conclusion is that at desk volume the API costs under
  $14/month and a hosted VM $1,434/month (a third of it people);
  break-even against Sonnet 5 is 1.76M requests/month. Hosting is
  justified by the gates (residency), never by cost - the matrix and
  the briefs say so and lab text must not claim otherwise.
- The decision matrix worked example (ticket triage) comes out B (buy
  through the tenant) at 430 vs D at 305; the filled spec example takes
  the flip case (gate G1 = no) and chooses D. Both are deliberate:
  Day 2 builds D, the paper shows when that is and is not the answer.
- The filled spec quotes the pre-baked eval numbers and the cost model
  by value; `tests/test_facilitator_docs.py` fails if those files
  change. After refreshing `facilitator/prebaked_outputs/eval/` or the
  prices, update the example's table too.
- The spec template is 11 sections whose minute budgets sum to 75
  (tested). The checklist is 43 questions. Neither was timed by a
  human group yet - Ritesh's Day 1 dry-run is the measurement.
- Briefs 2 and 3 name Day 3 files that do not exist yet
  (`data/eval/rag_adversarial.jsonl`, `golden_answers.jsonl`,
  `image_ground_truth/`) and brief 5 names `capstone/reference_index/`
  (P13). `PENDING_PATHS` in the docs test lists them; remove an entry
  when the file lands so the path check covers it.

### Governance pack, Day 5 S29 (P14)
- `facilitator/governance_pack/`: eight templates (`01_`..`08_`), a
  README with the 30-minute session split (Ritesh presents from the
  filled example; groups fill template 1 and the tool table of 4 in
  the room; the rest is take-away with the owner named in template 1),
  `sources.md`, and `examples/brief3_vision_capture_filled.md`.
  `tests/test_governance_pack.py` enforces the shape: one "Why this
  exists" paragraph per template (60-260 words, cites a source),
  first line `# <n>. <title> (<m> min)` with the budgets summing to
  80 and none over 15, at least 8 fillable rows and a sign-off, every
  `[Sn]` defined in sources.md and every source used, paths real or in
  its PENDING_PATHS, and the example mirroring every `## n.m` section
  with no blank answers.
- Sources are cited as `[S1]`..`[S14]`, each with link, date and a
  "primary"/"secondary" verification note (checked 2026-09-22). NEVER
  add a framework citation from memory: open the page, add a row to
  `sources.md`, then cite. Legal figures (Oman PDPL, 72-hour breach
  clock) are marked VERIFY for the DPO on purpose; keep that.
- The pack defines the three audit event lines (`llm_call`,
  `tool_call`, `index_write`) in template 5. **P13's reference MCP
  server must write the `tool_call` line exactly as 5.1.2 lists it**
  (`trace_id`, `access`, `approval{required,decision,by,ts,reason}`,
  `status` ok/error/refused, `upstream`, hashes, `ms`), and the
  capstone scaffold's ingestion path must write `index_write`. The
  write tool must refuse without an approval (status `refused`) and
  start read-only by default - template 4 and the example say so.
- MCP facts come from the 2026-07-28 spec (opened): human in the loop
  is a SHOULD, annotations are untrusted unless the server is trusted,
  servers MUST rate-limit, MRTR `input_required` replaced
  server-initiated elicitation. Do not describe the older elicitation
  flow.
- The worked example is brief 3 (vision), chosen because it carries
  the Day 3 known-bad extraction, the gated ERP write and the index
  write at once. Its extraction scores are "not measured" on purpose
  (Day 3 builds the image set and the scorer); a test asserts that
  phrase appears. Do not fill them with invented numbers - when the
  Day 3 score table lands, quote the file. The fill time in it is
  machine generation time (4.8 min) and says so; no human group has
  timed the pack. Ritesh's Day 5 dry run is the first measurement.
- Open question raised by the example, for Ritesh/Utkarsh: the week's
  "self-hosted VM in the tenant" is UAE North (no Azure region in
  Oman is used anywhere in the repo), while gate G2 asks whether data
  may leave the country. The example flags it as OPEN for the data
  owner rather than resolving it.

### Mock ERP API (P10)
- `services/mock_erp/`: FastAPI, in memory, loaded from
  `data/*.json` at startup (~1 s). Equipment master (86), maintenance
  history (258), work orders (295). Surface is binding for Day 4 and
  the Day 5 MCP server: `docs/contracts.md`, "Service surface".
- **EXACTLY ONE WRITE: `POST /work-orders`** (raise + release to the
  site crew, `status: released`, no update/cancel/delete anywhere,
  `approved_by` required but never verified, 409 on a repeated
  `source_ticket`). `tests/test_mock_erp.py` fails on a second write,
  checked by route table AND by trying every method on every path. No
  reset endpoint on purpose - a restart is the reset.
- CHOSEN 2026-09-22: the write is a work order (brief 4, Day 4
  approval interrupt), NOT an equipment-record update. The governance
  example (`facilitator/governance_pack/examples/brief3_vision_capture_filled.md`)
  still names `update_equipment_record` as "the one write endpoint of
  the mock ERP" - that is now false. Raised with Utkarsh as a
  decision, not silently edited.
- Seed data is GENERATED (`python -m services.mock_erp.seed --seed 42`,
  stdlib, reads the ticket corpus). Never hand-edit; the test
  regenerates and byte-compares. `/health` shows `data_fingerprint`
  (`84e0cc199798` now). Every plant tag (28) and work order (8) a ticket
  mentions exists; `P-1201A` / `WO-118305` (seal, completed
  2026-05-18) is the brief 4 story; P-1201A has no open work. Part
  numbers are `NN-NNNN-NN` so nothing but a tag looks like a tag
  (tested). Regenerating after a ticket-corpus change changes ids:
  rerun tests, `write_openapi`, refresh
  `facilitator/prebaked_outputs/mock_erp/tour_output.txt`.
- Errors are ONE shape `{"error", "message", ...}`, including
  FastAPI's own: malformed JSON -> 400 (FastAPI says 422
  `json_invalid`), JSON sent as text/plain -> 415 (FastAPI says 422
  `model_attributes_type`), unknown query params -> 422 (query models
  with `extra="forbid"`, FastAPI >= 0.115). Keep the handlers in
  `main.py` if FastAPI is ever bumped and retest.
- FastAPI 0.137+ made `app.routes` a TREE (`_IncludedRouter`, private).
  Do not walk it; read the module's `router` / `service_router`.
- Query-string ints: `Literal[1, 2, 3, 4]` REJECTS `"2"` from a query
  string; the filter uses `int` with `ge/le`, the body keeps `Literal`.
- A pydantic field named `date` typed `date` breaks the class
  (`unevaluable-type-annotation`): models use `datetime.date`.
- Colab: `launch.start_in_background(port=8000)` (child process, log
  to a temp file, polls `/health`, reuses an ERP already on the port,
  refuses a foreign server). Cells are in the service README. Tested
  in `python:3.12-slim` and `python:3.13-slim` containers through a
  Jupyter kernel (two fresh kernels, identical output; the child dies
  with the kernel). NOT yet run on a real Colab runtime - owed, with
  the `serve_kernel_port_as_iframe` check (unverified; the `_window`
  variant is deprecated/broken per Colab's source).
- Windows + `uvicorn --reload` (uvicorn 0.52.4 StatReload): detects the
  change, then hangs restarting the worker - reproduced with a 3-line
  app, with and without a console, upstream issue. Also scans all
  18,094 `.py` under the repo (incl. `.venv`) at 7.2 s a pass. Linux
  reload works (0.7-1.1 s). Do not fix by changing the uvicorn pin.
- Auth: `MOCK_ERP_API_KEY` (env or `.env`) -> `X-API-Key` required on
  everything but `/health` and `/docs`; empty = open (lab default).
  `MOCK_ERP_URL` in `.env.example` for consumers.
- Timestamps carry `+04:00`; dates ISO. New maintenance-record id
  convention `MH-` + 6 digits (contracts naming table).

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

### Fundamentals notebook 01, two paths (P7)
- ONE notebook, TWO paths (BUILD_SPEC section 2, S1). Part A = setup +
  a 10-minute diagnostic; Part B = fundamentals, FULL path only; Part
  C = structured outputs + agent loop, both paths. The COMPRESSED path
  is "run Part A, then Runtime > Run after on the PART C STARTS HERE
  cell". Part C must never use a name defined only in Part B
  (`tests/test_notebook_01.py` scans for it; the compressed path was
  also executed as its own notebook, 2026-09-22, clean).
- Signposting is triple: cell tag `full-path-only` (tooling), first
  line `# [FULL PATH ONLY]` (what a person sees), and three headings
  `THE FORK`, `PART C STARTS HERE`, plus the cell map in the header.
  Keep all three in sync; the tests check tag <-> comment agreement
  and that Part B is one contiguous block between the two headings.
- The diagnostic is 3 probes scored 2 + 2 + 4 = 8, READY at >= 6.
  Probe 1 (resend the history) and probe 2 (a dict with three keys)
  carry half the points ON PURPOSE so a guessed quiz cannot reach
  READY. Room rule, printed by the score cell: READY hands >= two
  thirds -> COMPRESSED. Do not turn it into a percentage or a per-
  person path: the room moves as one.
- The three diagnostic TODOs (1-3) deliberately do NOT fail loudly: a
  gap left as `...` prints `NOT ATTEMPTED -> 0` and the notebook
  carries on (a diagnostic must never stop the room). TODOs 4-7 use
  the normal `assert x is not ..., "TODO n is not filled in yet"`.
  `tests/test_notebook_01.py` enforces both behaviours.
- The quiz answer key lives in `fundamentals_utils.QUIZ_ANSWER_KEY`,
  readable by anyone. Accepted: it is a diagnostic, not an exam, and
  the notebook says so.
- The agent loop is a TEXT protocol (`{"tool":..., "args":...}` /
  `{"final":...}` in JSON mode) on purpose, not the API's native
  `tools` field: it works unchanged on all three endpoints including
  the 1B tuned model, and every moving part is visible in one cell.
  Day 4 introduces native tool calling. Tools read only synthetic data
  (`fu.ASSET_REGISTER`, the ticket corpus); asset rows agree with the
  ticket's site and signer (tested).
- `utils.ensure_api_key(IN_COLAB)` is the ONLY place a notebook gets
  the hosted key on Colab (Colab Secrets, then a hidden paste).
  Conventions doc "Cell 3b", Contract 2 point 6. The Colab branch has
  NOT run on Colab yet (2026-09-22): the first Colab run of 01 is owed.
- Both .ipynb files are generated from one cell list by a scratch
  script that is NOT in the repo (same as 06). Edit both files with
  the same change; the parity test fails otherwise. To refresh the
  solution: delete `checkpoints/local/01_*.json`, execute headless
  (command above), copy the output over `solutions/01_fundamentals.ipynb`,
  copy the five `01_*.json` into `facilitator/prebaked_outputs/fundamentals/`.
- `solutions/01_fundamentals.ipynb` retained output is a LOCAL run
  (2026-09-22, gpt-4o-mini). Expected final line: `READY (8 / 8)`,
  schema-valid 5 / 5, whole record 1 / 5, agent final answer in 3
  steps. gpt-4o-mini at temperature 0 is NOT byte-stable: across six
  headless runs on 2026-09-22 the five-ticket table changed by one
  field (impact on INC-004603, sometimes the queue on INC-004183);
  whole record was 1 / 5 in five runs and 0 / 5 in one. Schema-valid
  5 / 5 and the 3-step agent trace were identical every time. Quote
  whole record as "0 or 1 of 5"; never chase a one-field difference.
  The test asserts only what was stable.
- Measured (section 11 protocol, local, machine time): FULL 42.0 s /
  41.0 s (the retained pair; an earlier pair was 38.9 s / 39.0 s),
  COMPRESSED 24.7 s / 21.1 s. The 60 / 45 min budgets are participant
  time. STILL OWED: a cold Colab run with the key in Colab Secrets,
  and the disconnect test.
- `facilitator/claude_code_session.md` is the reclaimed-45-minutes
  session. Facts verified 2026-09-22 against code.claude.com/docs
  (changelog newest 2.1.278). NOT verified, so not taught: the `#`
  memory shortcut and the exact stable version. It needs a decision
  from Ritesh on how 10-15 people authenticate (no free tier).

### Failure playbook (P15)
- `docs/failure_playbook.md` has THREE parts. Part 1: 15 room entries
  (`## N. title`), each with the fields They say / Radius / Diagnose /
  Fix / Fallback after 60 s / Tested, in that order. They are ordered
  by likelihood x blast radius, with an index table on the first screen.
  Part 2: the demo fallback ladder and Ritesh's Sat 26 check table.
  Part 3: exact-error reference E1-E18.
  `tests/test_failure_playbook.py` holds that shape (index lines < 40,
  anchors land, trust level on every entry, paths exist).
- Numbering rule for citations: "playbook entry N" (N <= 15) = room
  entry N; "playbook EN" = Part 3. E-numbers are the entry numbers used
  before 2026-09-23, so an old "entry 17" still means E17 (the test
  resolves every citation in the repo). Add a new exact-error entry at
  the END of Part 3 as the next E-number; never renumber.
- Every Part 1 entry states REPRODUCED / SIMULATED / NOT REPRODUCED. An
  entry from research only must say so - nobody trusts an untested fix
  under pressure. Colab itself (blocked network, disconnect, GPU quota,
  RAM crash, Drive popup) could NOT be reproduced from the build
  machine; Drive mount failure was SIMULATED with a stand-in
  `google.colab` module running the real first cell.
- Found and fixed while reproducing (2026-09-22):
  - `utils.ensure_api_key` now re-reads `.env`. Before, a `.env` fixed
    mid-session was not seen until a kernel restart, though the cell
    said "re-run this cell". A wrong key already loaded still needs a
    restart, by design.
  - `setup_check.py` FAILs on Python 3.14 (was WARN): pinned
    numpy 2.1.3 has no 3.14 wheel, and pip fails in 13 s with
    `Unknown compiler(s)`. 3.13 stays WARN: every pin has a 3.13 wheel
    (checked with `pip download --only-binary`).
  - `setup_check.py --network` probes 11 hosts. Each needs the exact
    status it gave on an open network; a proxy's own 403 page counts as
    FAIL. The Python view is not the browser's.
- Measured facts the playbook relies on:
  - `HTTP_PROXY` set makes a running local Ollama look dead ("Is
    Ollama running?"). `NO_PROXY=localhost,127.0.0.1` in `.env` fixes
    it.
  - pip behind a blocked proxy ends with the misleading `No matching
    distribution found ... (from versions: none)`: 22 s if the proxy
    refuses, 103 s if it drops.
  - A wheelhouse of `requirements.txt` is 115 files, 70 MB, and
    installs offline in 25 s. It must be built per OS and Python; a Mac
    one cannot be cross-built from Windows (pywin32 marker).
  - An interrupted `ollama pull` resumes. Copying a model's manifest
    and blobs into another store works (Windows tested).
  - A notebook 03 disconnect mid-load-test costs the whole test,
    because the driver saves only at the end.
- Git Bash `sed -i` rewrote CRLF files as LF (the whole file shows as
  changed). Several tracked files are CRLF (`git ls-files --eol`).
  Edit those with the Edit tool, or restore CRLF afterwards.
- STILL OWED: every Sat 26 row from the actual OQ room (Ritesh). The
  15-second lookup was timed with a fresh model session (7-8 s per
  entry, first screen only), NOT with a person. A human stopwatch at the
  dry run is the real measurement.
