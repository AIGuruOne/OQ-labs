# Timing log

Measured wall-clock durations from the protocol in BUILD_SPEC.md
section 11: fresh cold runtime, clock starts at the first cell, top to
bottom with no manual intervention, clock stops when the declared
output exists. Two runs each; investigate if they differ by more than
20 percent.

"It took about twenty minutes" is not a measurement. If it is not in
this table, it has not been timed.

| Notebook | Date | Runtime type | Accelerator | Measured (min) | Budget (min) | Retries / notes |
|---|---|---|---|---|---|---|
| _template | — | — | — | — | — | not a lab; smoke-tested in CI-style runs only |
| 01_fundamentals (solution, FULL path, all 53 cells) | 2026-09-22 | local, Windows 11, Python 3.11.15, cold kernel, `01_*` checkpoints deleted first (`python -m nbconvert --execute`), hosted endpoint `gpt-4o-mini` over home broadband | none | 0.70 (42.0 s) | 60 | run 1 of 2. No retries, no errors. 33 model calls. Machine time only: the 60 min budget is participant time (10 min diagnostic + 20 min Part B + 30 min Part C, 7 TODOs). An earlier pair the same afternoon, before a last helper edit: 38.9 s and 39.0 s |
| 01_fundamentals (solution, FULL path) | 2026-09-22 | same | none | 0.68 (41.0 s) | 60 | run 2 of 2. Within 3% of run 1. This is the run retained in `solutions/01_fundamentals.ipynb`. Final line: `READY (8 / 8)`, 5/5 schema-valid, agent in 3 steps. Across all six runs of the day the five-ticket table moved by one field between sittings (gpt-4o-mini at temperature 0 is not byte-stable); whole record was 1/5 five times, 0/5 once |
| 01_fundamentals (solution, COMPRESSED path: the 38 cells NOT tagged `full-path-only`, executed as one notebook) | 2026-09-22 | same | none | 0.41 (24.7 s) | 45 (incl. the 10 min diagnostic) | run 1 of 2. No errors: proves Part C runs after Part A alone. 19 model calls. Participant time: 10 min diagnostic + 35 min Part C |
| 01_fundamentals (solution, COMPRESSED path) | 2026-09-22 | same | none | 0.35 (21.1 s) | 45 | run 2 of 2. 15% faster than run 1 (API latency), inside the 20% rule. Same final line |
| 01_fundamentals | — | Colab free-tier CPU, cold, with `OPENAI_API_KEY` in Colab Secrets | none | **not yet measured** | 60 / 45 | needs the P7 commit pushed (the Colab cell clones `main`) and a Google login. Expect Drive mount + clone to add about a minute to the local figure. The Colab Secrets branch of `utils.ensure_api_key` has not run on Colab yet |
| 02_local_inference (solution) | 2026-09-22 | local, Windows 11, Python 3.11.15, cold kernel, `02_*` checkpoints deleted and the model unloaded first (`python -m nbconvert --execute`). Ollama 0.12.10 already running on port 11435 (4096 context), `llama3.2:1b` **already pulled** - so this is RUN time; pull time is in the rows below. Hosted comparison call to `gpt-4o-mini` | none (Ollama put 54-77% of the model on the integrated AMD GPU; 0% in the retained run) | 1.03 (61.5 s) | 40 | run 1 of 2. No retries, no errors. 11 local model calls + 1 hosted. Machine time only: the 40 min budget is participant time on 2 TODOs plus reading. An earlier run the same afternoon, before three wording edits: 58.2 s |
| 02_local_inference (solution) | 2026-09-22 | same | same | 1.02 (61.3 s) | 40 | run 2 of 2. Within 1% of run 1. A third run (61.6 s) after a header-only edit is the one retained in `solutions/02_local_inference.ipynb`. Local model speed 33-50 tokens/s across the runs. The untuned 1B's ticket reply flipped between sittings: valid JSON (2/6 fields) in the first run of the day, missing its closing brace in the last three |
| 02_local_inference, **pull time** (kept apart from run time on purpose) | 2026-09-22 | local, Windows 11, home broadband, real pull of a model not on the server (`qwen2.5:0.5b`, 0.4 GB, via a scratch copy of the solution with `MODEL_NAME` swapped) | none | 0.8 (49 s) for 0.4 GB; skip path when already pulled: 2.0 s | - | one run. `llama3.2:1b` is 1.3 GB: 160 s (`ollama pull` by hand) and 132 s (`ensure_model`) in the Linux container rows below; **28 s on a Colab T4** (notebook 06's run, 2026-09-21). Venue Wi-Fi is the unknown - pull at the Day 1 tech check |
| 02_local_inference (solution), Linux | 2026-09-22 | `python:3.12-slim` container on the build machine, `--cpus=2` (a CPU-time quota over 24 visible threads). Ollama 0.12.10 installed by hand from the pinned `.tgz` (**226 s**, not counted), `ollama pull llama3.2:1b` (**160 s**, not counted), first hand call 10 s incl. load | none (100% CPU) | 2.66 (159.7 s) | 40 | one run, clean. **3.1 tokens/s**; ticket reply 31 s; hosted call 2.7 s. The local reply came back without its closing brace (`not JSON`). Proves the Linux path end to end |
| 02_local_inference (solution), Linux, two pinned cores | 2026-09-22 | same image, `--cpuset-cpus=0,1` (2 visible cores). Install 208 s, pull 139 s | none | **FAILED: 600 s read timeout** after 694 s | 40 | the first hand-typed call took 194 s including the load; the notebook then died on a 600 s request timeout. Same pathology P6 saw for notebook 06 with cpuset on this machine. NOT a Colab measurement: the Colab CPU runtime is still unmeasured, and the notebook now tells a no-GPU Colab user to take the T4 |
| 02_local_inference | - | Colab free tier, **cold**, stopwatch from the first cell, T4 runtime (and once on a CPU runtime) | T4 | **not yet measured** | 40 | STILL OWED: the Colab branch of this notebook has not run on Colab. Expect Ollama install ~56 s + pull ~28 s (from 06's T4 run) + about a minute of run time. Also owed: the disconnect test |
| 03_concurrency (solution) | 2026-09-22 | local, Windows 11, Python 3.11.15, cold kernel, `03_*` checkpoints and `checkpoints/local/concurrency` deleted first (`python -m nbconvert --execute`). `OLLAMA_BASE_URL=http://localhost:11437`, a port with NO server: the notebook started `ollama serve` itself (Ollama 0.12.10, default `OLLAMA_NUM_PARALLEL` = 1, read back from the server log), `llama3.2:1b` already pulled | none (Ollama put **62%** of the model on the integrated AMD GPU: two other servers held the rest of its memory) | 4.08 (4 m 05 s) | 15 | run 1 of 4. No retries, no errors. 82 model calls (warm-up, one timed request, 80 in the load test). One request alone 3.1 s (31 tokens/s); table: p95 4.58 s at 1 caller -> 34.1 s at 16 (7.4x), throughput 0.23 -> 0.44 req/s and flat from 2 callers on; target p95 <= 10 s -> 4 callers, 1,584 requests/hour |
| 03_concurrency (solution) | 2026-09-22 | same | same (62%) | 4.07 (4 m 04 s) | 15 | run 2 of 4. Within 1% of run 1; same knee (4 callers) |
| 03_concurrency (solution) | 2026-09-22 | same, after the other Ollama servers had unloaded their models | none (**100%** of the model on the integrated GPU) | 2.45 (2 m 27 s) | 15 | run 3 of 4. One request alone 1.5 s (76 tokens/s); p95 3.13 -> 14.64 s (4.7x); throughput 0.33 -> 1.04 req/s, flat from 4 callers on; knee at 8 callers, 3,780 requests/hour. The 40% difference from runs 1-2 is the GPU share, not noise: same shape, every latency about a third shorter |
| 03_concurrency (solution) | 2026-09-22 | same | same (100%) | 2.45 (2 m 27 s) | 15 | run 4 of 4, **the run retained in `solutions/03_concurrency.ipynb`** and copied to `facilitator/prebaked_outputs/concurrency/`. Within 1% of run 3: one request 1.56 s (100 tokens/s), p95 3.19 -> 14.01 s (4.4x), throughput 0.33 -> 1.06 req/s, knee 8 callers at p95 7.8 s, 3,708 requests/hour, 0 failed. Notebook's own clock: 2.4 min from the settings cell |
| 03_concurrency (solution), re-run after a "disconnect" with everything saved | 2026-09-23 | local, Windows 11, same as run 1 (port 11437, notebook starts the server). A full run first (213 s, clean), then the same notebook again | none (integrated GPU) | 0.33 (19.6 s) | 15 | resume test for P15. `03_single` and the load-test summary reloaded from checkpoint (`(from checkpoint - ...)` lines); only the server start and the capacity cell ran |
| 03_concurrency (solution), process tree killed 30 s into the load test, then re-run | 2026-09-23 | same. Kill at 60 s from start (`03_single` saved at 22 s), no summary on disk | none (integrated GPU) | 3.32 (198.9 s) for the re-run | 15 | resume test for P15. `03_single` reused; the WHOLE load test ran again - `concurrency_test.py` writes its files only at the end, so a disconnect mid-test costs the test (about a minute on a T4, by the T4 reply times). The reference checkpoints were moved aside for these runs and restored afterwards |
| 03_concurrency | - | Colab free tier, **cold**, stopwatch from the first cell, T4 runtime | T4 | **not yet measured** | 15 | STILL OWED. Expect Ollama install ~56 s + pull ~28 s (from 06's T4 run) + about a minute for 80 requests at under a second each. Also owed: the disconnect test (the load-test cell reloads its saved summary from Drive). A Colab CPU runtime is refused by the server cell: 80 requests at notebook 02's 30 s a reply is 40 minutes |
| 04_dataset_builder (solution) | 2026-09-19 | local, Windows 11, Python 3.11.15, cold kernel, checkpoints deleted first (`jupyter nbconvert --execute`) | none | 0.09 (5.3 s) | 40 | run 1 of 2. No retries. Machine time only - the 40 min budget is participant working time on 3 TODOs |
| 04_dataset_builder (solution) | 2026-09-19 | same | none | 0.09 (5.2 s) | 40 | run 2 of 2. Within 20% of run 1 |
| 04_dataset_builder (solution) | 2026-09-20 | local, Windows 11, Python 3.11.15, cold kernel, checkpoints deleted first (`jupyter nbconvert --execute`). After P3: real `quality_checks.py` wired in (one subprocess run + one module run), dataset unchanged at 400/80 | none | 0.11 (6.8 s) | 40 | run 1 of 2. No retries. Machine time only |
| 04_dataset_builder (solution) | 2026-09-20 | same | none | 0.11 (6.7 s) | 40 | run 2 of 2. Within 20% of run 1. Supersedes the 2026-09-19 rows |
| 04_dataset_builder (participant version, TODOs filled in by hand) | 2026-09-21 (file save time) | Colab free tier, CPU runtime, run by Utkarsh. Drive mounted by the first cell, execution counts start at 1 | none | **ran clean, NOT timed** - the file holds no per-cell timings | 40 | all seven final checks `ok`, `DATASET READY - environment=Colab`, 373 / 72 / 20 rows. Proves the Colab path; not a measurement. Retained as the output of `solutions/04_dataset_builder.ipynb` since 2026-09-22 (the TODO answers were the solution's; every other output matches the local run above except the paths) |
| 04_dataset_builder | — | Colab free-tier CPU, cold | none | **not yet measured** | 40 | needs the P2 + P3 commits pushed (the Colab cell clones `main`) and a Google login; adds Drive mount + clone + one pip no-op to the local figure |
| 05_finetune (participant version, TODOs filled with the hinted values) | 2026-09-20 | Colab free tier, run by Utkarsh. Data rebuilt from `data/finetune` (no notebook 04 output on that Drive). Llama 3.2 1B, 4-bit, r=16 all seven layers, 3 epochs, 72 steps | T4 | **training: 7.1** (from the notebook's own clock: `Starting at step 0` to step 72, including 7 Drive checkpoints and 3 validation passes). **Whole notebook: NOT measured** - no stopwatch figure was recorded and Colab saved no per-cell timings | training 25; block 90 | run 1 of 2. No retries, no restart prompt, no errors. Loss 0.742 -> 0.020; validation 0.136 / 0.055 / 0.047. 5 of 5 replies schema-valid after load-back. Whether the runtime was cold (first open on that account) is not recorded |
| 05_finetune | - | Colab free tier, **cold**, stopwatch from first cell | T4 | **not yet measured** | training 25; block 90 | run 2 of 2 still owed (spec section 11), with the whole-notebook wall-clock this time. (A `05_finetune.ipynb` handed over on 2026-09-21 was checked cell by cell: all 19 outputs and execution counts are identical to the run in the row above and the file is dated 2026-09-20 16:05 - it is that SAME run, not a second one, and it carries no per-cell timings either.) Steps: `docs/finetune_stack.md` section 4 |
| 05_finetune (solution, `OQ_SMOKE_TEST=1`: 135M model, 20 rows) | 2026-09-20 | local, Windows 11, Python 3.11.15, CPU, cold kernel (`python -m nbconvert --execute`) | none | 5.0 whole notebook (3.2 training) | - | plumbing test, not a lab timing. Kill-and-resume run: 2.0 min, resumed at step 4 of 6 |
| 05b_finetune_mlx | - | **Apple Silicon Mac** | Apple GPU | **not yet measured** | training 25 | no Mac on the build side. First Mac to run it: time it and replace this row |
| 05b_finetune_mlx (solution, `OQ_SMOKE_TEST=1`: 135M model, 4 rows, 3 epochs) | 2026-09-20 | Linux container (python:3.12-slim, `mlx[cpu]==0.32.2`, mlx-lm 0.31.3) on the Windows build machine | none (MLX CPU backend, one core) | 17.8 training; about 30 whole notebook across two sittings | - | plumbing test ONLY - says nothing about Mac speed (this backend needs ~70 s per training row). Hard-killed mid-epoch 3, re-run resumed at `epochs done: 2 of 3` |
| 06_compare_base_tuned (solution, pre-baked adapter via the automatic fallback) | 2026-09-20 | local, Windows 11, Python 3.11.15, cold kernel, eval folder deleted and models unloaded first (`python -m nbconvert --execute`). Ollama 0.12.10 already running, `llama3.2:1b` already pulled. No NVIDIA GPU; Ollama put 89% of the model on the laptop's integrated AMD GPU | none (integrated graphics) | 2.83 (2 m 50 s) | 25 | run 1 of 2. No retries. 40 model calls, median 3.4 s (base) and 3.6 s (tuned) per ticket. Machine time only - the budget is participant time on 3 TODOs plus reading |
| 06_compare_base_tuned (solution) | 2026-09-20 | same | same | 2.81 (2 m 49 s) | 25 | run 2 of 2. Within 1% of run 1, identical table. Two earlier runs the same evening, before the warm-up call was added: 2 m 50 s and 2 m 42 s. A third run on 2026-09-21, after the Colab-T4-only wording went in (this is the run retained in the solution): 2 m 33 s, identical table. NOTE: a local run is the UNSUPPORTED path for this lab - these rows time the machine work, they are not the lab's timing. The Colab T4 rows below are the ones that count |
| 06_compare_base_tuned (solution), killed mid-run then re-run | 2026-09-20 | same. Process tree killed with 7 of 20 tuned replies saved | same | 1.0 for the re-run | 25 | resume test: 20 base + 7 tuned replies reused, 13 asked, table identical to the uninterrupted run. A re-run with everything saved: 14 s |
| 06_compare_base_tuned (solution), Linux | 2026-09-20 | python:3.12-slim container on the build machine, `--cpus=2` (24 threads sharing two CPUs' worth of time - slower than two real cores would be with two threads). Ollama 0.12.10 installed by `ollama_utils.install_on_linux` (218 s over home broadband, not counted), model pull 126 s (counted) | none | **30.2 - OVER BUDGET** | 25 | one run. Proves the Linux path end to end; median 36 s (base), 44 s (tuned) per ticket. Pinned to two cores (`--cpuset-cpus=0,1`) every first ticket exceeded the 120 s endpoint timeout. Conclusion: a Colab CPU runtime cannot run this lab; the notebook now stops at once on Colab without a GPU |
| 06_compare_base_tuned (participant version, the three TODOs filled in by hand; Utkarsh's own adapter from Drive, fingerprint b1c0e3d4) | 2026-09-21 (from the file's save time; the file holds no timestamps) | Colab free tier, run by Utkarsh. Ollama, the model and the eval were cold: the notebook installed Ollama 0.12.10, pulled `llama3.2:1b` and found 0 saved replies. The kernel was NOT fresh: the first cell is execution 5 and Drive was already mounted | T4 (`NVIDIA GPU: Tesla T4`, 100% of the model in GPU memory) | **whole notebook by stopwatch: NOT measured.** From the notebook's own printed clocks: Ollama install 56 s, model pull 28 s, warm-up 3.4 s, base eval 16.8 s of model time (median 0.78 s a ticket), tuned eval 20.7 s (median 0.83 s). Settings cell to final cell: **4.2 min, including a person filling in three TODOs** | 25 | run 1 of 2. No errors, no retries. NOT a section 11 measurement: Colab saved no per-cell timings (`executionInfo` is absent), the cells were not run strictly top to bottom (execution order 12, 14, 16, 18: the examples cell ran before the compare cell), and the 4.2 min starts at the settings cell, after clone and Drive mount. It does show the budget is not in danger: about 2 minutes of machine work. Retained as the output of `solutions/06_compare_base_tuned.ipynb` |
| 06_compare_base_tuned | - | Colab free tier, **cold** (fresh runtime AND fresh kernel), stopwatch from the first cell, solution version, Run all | T4 | **not yet measured** | 25 | STILL OWED: the one section 11 figure (run 2 of 2, no manual steps). Also owed: the Colab disconnect test |

## Scripts (not notebooks, no section 2 budget of their own)

`scripts/run_eval.py` runs inside notebook 06 (25 min of 45) and
notebook 11 (25 min of 40), so its wall-clock time is part of their
budgets. Measured with `time`, whole command, held-out 20, temperature
0, JSON mode off.

| Command | Date | Where | Measured | Notes |
|---|---|---|---|---|
| `run_eval.py --endpoint local` (llama3.2:3b, Ollama 0.12.10, 4096 ctx) | 2026-09-20 | local, Windows 11, **CPU only**, model already loaded | 95.4 s | run 1 of 2. Median 4.6 s per ticket. No retries |
| same | 2026-09-20 | same | 94.6 s | run 2 of 2. Within 1%. Identical scores to run 1 |
| `run_eval.py --endpoint hosted` (gpt-4o-mini) | 2026-09-20 | local, home broadband | 28.2 s | run 1 of 2. Median 1.3 s per ticket |
| same | 2026-09-20 | same | 26.8 s | run 2 of 2. Within 5%. Identical scores to run 1 |
| `run_eval.py --endpoint local` with `OLLAMA_MODEL=llama3.2:1b` (inside notebook 06) | 2026-09-21 | Colab free-tier T4, Ollama 0.12.10, model warmed up first | 16.8 s of model time (the report's own figure; the whole command was not timed) | one run. Median 0.78 s per ticket. `llama3.2:3b` on a T4: still not measured |
| `run_eval.py --endpoint tuned` (`oq-ticket-tuned` = llama3.2:1b + pre-baked adapter, Ollama 0.12.10, 4096 ctx) | 2026-09-20 | local, Windows 11, **CPU only**, model NOT loaded yet | 48.0 s | run 1 of 2. Median 2.1 s per ticket. Includes the first-call model load |
| same | 2026-09-20 | same, model already loaded | 39.9 s | run 2 of 2. 17% faster (no load). Identical scores to run 1 |
| `run_eval.py --endpoint local` with `OLLAMA_MODEL=llama3.2:1b` | 2026-09-20 | same | 76.8 s | one run. Median 3.5 s per ticket - slower than tuned because the untuned model writes longer, pretty-printed replies |
| `run_eval.py --endpoint tuned` (inside notebook 06) | 2026-09-21 | Colab free-tier T4, Ollama 0.12.10 | 20.7 s of model time (the report's own figure; the whole command was not timed) | one run. Median 0.83 s per ticket; the first ticket took 3.8 s (the tuned model's load) |

A first call against a model that is not loaded yet adds the load
time (about 8 s for llama3.2:3b on the build machine).

`scripts/concurrency_test.py` runs inside notebook 03 (15 min of 40).
Measured with `time`, whole command, default settings unless stated
(levels 1,2,4,8,16; 16 requests a level; 64-token cap; 60 s timeout;
prompts = the 20 held-out tickets with the house system prompt).

| Command | Date | Where | Measured | Notes |
|---|---|---|---|---|
| `concurrency_test.py --endpoint local` (llama3.2:1b, Ollama 0.12.10 on port 11435, started by hand on 2026-09-20 with an unrecorded environment) | 2026-09-22 | local, Windows 11, integrated GPU | 3 m 25 s | one run, 0 failed. p95 4.45 -> 30.3 s, throughput 0.24 -> 0.49 req/s, flat from 2 callers on. The two runs inside notebook 03 (port 11437, `Parallel:1` in the log) show the same shape; the notebook's rows above are the reference |
| `concurrency_test.py --base-url http://localhost:11436/v1 --model llama3.2:1b` against a scratch server started with **`OLLAMA_NUM_PARALLEL=4`** (log: `Parallel:4 ... KvSize:16384`) | 2026-09-22 | local, Windows 11, **CPU only** (the integrated GPU had 466 MiB free, so Ollama put 0% there) | 2 m 51 s | one run, 0 failed. p95 4.24 -> 17.6 s (4.1x); throughput 0.25 -> 0.66 (4 callers) -> 0.9 req/s (8) and flat at 16. Batching moves the knee to 8 and raises the ceiling 3.6x; it does not remove the knee. The summary file was not kept (found missing at the P16 freeze check, 2026-09-23); these numbers are the record |
| `concurrency_test.py --endpoint hosted --levels 1,4,16 --requests 8` (gpt-4o-mini) | 2026-09-22 | local, home broadband | 27 s | one run, 0 failed. p95 2.84 (1 caller) / 2.09 (4) / 2.46 s (16); throughput 0.45 -> 2.09 -> 3.25 req/s and still rising: a fleet, not a server. The summary file was not kept (found missing at the P16 freeze check, 2026-09-23); these numbers are the record |
| `concurrency_test.py --base-url http://localhost:9/v1 --model x` (nothing listening) | 2026-09-22 | local | 4.4 s | exit 2, `NOTHING MEASURED. Preflight failed after 4.1 s: nothing answered at that address ...`, no files written. Windows takes about 4 s to refuse a localhost connection (Linux: at once) |
| `concurrency_test.py --base-url http://10.255.255.1/v1 --model x --timeout 5` (non-routable address) | 2026-09-22 | local | 5.2 s | exit 2 at exactly the timeout: `no reply within 5.0 s ...`. Proves a black-hole endpoint cannot hang the room; the connect wait is capped at 10 s whatever `--timeout` says |
| `concurrency_test.py --base-url http://localhost:11435/v1 --model nosuchmodel` | 2026-09-22 | local | 2.3 s | exit 2, `the server answered HTTP 404. Check the model name ...` |

**About "CPU only" in the rows above (found 2026-09-20, P6):** the build
machine has no NVIDIA GPU, but `ollama ps` shows Ollama placing most of
a small model on its integrated AMD Radeon graphics (`26%/74% CPU/GPU`
for `llama3.2:1b`). The per-ticket times above are therefore faster
than a laptop with no usable GPU would give. Treat them as a lower
bound for participant laptops.

## Day 5 S26: the MCP server type-along (80 min, not a notebook)

S26 is a guided type-along, so there is no notebook to run cold. What
can be timed without people is the machine part of each step: start the
checkpoint as `s26_server.py`, run the step's commands
(`scripts/walk_s26_steps.py`, which follows
`facilitator/mcp_build_sequence.md`). The step budgets are participant
time: typing and reading, which only a room can measure.

| What | Date | Where | Measured | Budget | Notes |
|---|---|---|---|---|---|
| Walk of all 8 steps, machine time | 2026-09-22 | local, Windows 11, Python 3.11, `mcp==2.2.0`, mock ERP on 8000, server on 8100 | 62 s | 80 min | walk 1 of 3 (by hand-driven scratch script). Every step showed its capability; step 8 `test_inspector.py --module s26_server --inspector` 62 / 62 PASS in 23.8 s |
| same | 2026-09-22 | same | 43.5 s | 80 min | walk 2 of 3, **the run retained in `facilitator/prebaked_outputs/mcp_server/`** (`timings.json`). Server start 1.3-3.3 s a step; each step's commands 0.2-0.6 s; step 8 18.8 s |
| same, via the committed `scripts/walk_s26_steps.py` | 2026-09-22 | same | 42.9 s | 80 min | walk 3 of 3. Within 2% of walk 2; outputs identical apart from timestamps, trace ids and sealed state |
| `test_inspector.py` (no Inspector) | 2026-09-22 | same | 13.5-15.6 s | 6 min (step 8) | 59 checks, 58 PASS + 1 SKIP (the Inspector). Starts its own ERP and two servers |
| `test_inspector.py --inspector` | 2026-09-22 | same, Node 24.11.0, Inspector 2.7.0 already in the npx cache | 17.6-23.8 s | 6 min (step 8) | 62 / 62 PASS. The first `npx` download of the Inspector is extra: the package installed in 21 s over home broadband |
| **The room: 77 typed lines + 8 runs** | - | people | **not yet measured** | 80 min | STILL OWED: Ritesh's Day 5 dry run. On paper: 77 lines at an assumed 2 lines a minute = ~40 min, 8 runs x ~3 min = 24, setup 5 -> 69 of 80. At 1 line a minute it does not fit; `mcp_build_sequence.md` has the 09:17 rule (paste step 6) for that |

## Day 5 S27 + S28: capstone assembly (105 min, not a notebook)

Groups build on `capstone/` rather than follow steps, so the only thing
that can be timed without people is the machine part and one author's
assembly of a brief. The brief 5 build is 78 added lines over the
starter (`capstone/examples/brief5_similar_tickets.py`, about 17 of them
docstring).

| What | Date | Where | Measured | Budget | Notes |
|---|---|---|---|---|---|
| `capstone.run status`, cold (empty `--out`) | 2026-09-23 | local, Windows 11, Python 3.11 | 8-11 s | - | ERP 0.8-1.3 s + MCP server 1.0-1.3 s to start, reference index built (580 tickets, 0.02 s) and saved. Most of the rest is Python start-up and the stop at exit |
| one ticket, hosted (gpt-4o-mini) | 2026-09-23 | same | 10 s whole command; pipeline 1.5-3.2 s | - | pipeline = index search + MCP lookup + model call + checks |
| one ticket, tuned (Ollama 0.12.10, `oq-ticket-tuned`, port 11435) | 2026-09-23 | same, integrated AMD GPU | 18 s whole command; pipeline 4.6-8.7 s | - | first call includes the model load |
| `register-adapter` (pre-baked) | 2026-09-23 | same | 4.6 s | - | model already pulled |
| `capstone.run eval`, held-out 20 | 2026-09-23 | same | hosted 39-44 s; tuned 86-98 s | - | four runs, twice each (two out folders): counts identical between the two sittings |
| Brief 5 assembled by the author, from copying the starter to four evals and the comparison | 2026-09-23 | same | about 7 min | 105 min | **author time, not a group's**: the author wrote the scaffold. Two bugs found and fixed on the way (a `\n` mangled by a shell heredoc, a repo-root path) |
| README Colab cells, stand-in `google.colab`, Jupyter kernel | 2026-09-23 | `python:3.12-slim` and `python:3.13-slim` containers | 16-22 s for the cells | - | env cell, `%pip install mcp==2.2.0`, key from the stand-in Secrets, status, one ticket, a 3-ticket eval, brief 5 with an MCP lookup, all on the "Drive" path. NOT run on Colab itself |
| Deployment checklist, filled for the brief 5 build | 2026-09-23 | same laptop | about 25 min | 30 min | author time, including the four evals. `facilitator/examples/deployment_checklist_brief5_filled.md` |
| **The room: a group of 2-3 building its brief** | - | people | **not yet measured** | 105 min | STILL OWED: the Day 5 dry run. On paper: README 10 min, untouched run 5, the four functions 40-60 (78 lines for brief 5), evals 5, the rest is slack for a Day 3/4 artifact that did not come out |

## P16 freeze check (2026-09-23): cold and warm re-runs, local

A verification pass, not the section 11 protocol: machine time on the
build laptop, NOT Colab, so none of these rows closes a "not yet measured"
Colab row above. Every solution ran headless (`python -m nbconvert
--execute`) from a copy under `checkpoints/`, with its `checkpoints/local`
files moved aside first (**cold**), then again straight after with the
checkpoints left in place (**warm** = what a reconnect sees). Ollama 0.12.10
on port 11435 (02, 06) or started by the notebook on 11437 (03);
integrated AMD GPU. No retries unless stated.

| Notebook | Cold | Warm (resume) | Result, and what the warm run reused |
|---|---|---|---|
| _template | 7.1 s | - | `TEMPLATE OK` |
| 01_fundamentals (solution, FULL path) | 47.4 s | 36.0 s | `READY (8 / 8)`, 5 / 5 schema-valid, whole record 1 / 5, agent in 3 steps, both times. Warm: the five extractions reloaded `(from checkpoint)`; the short teaching calls ran again |
| 02_local_inference (solution) | 66.1 s | 50.9 s | clean both times; the local reply was not readable JSON (0/6), as the header warns |
| 03_concurrency (solution) | 244.4 s | **hung once (killed at 30 min)**, then 23.5 s and 22 s | cold: clean, 0 failed. Warm: the load test reloaded its saved summary. The hang did not reproduce in two retries and its cause was not found; Windows, notebook-started server on 11437. Four orphaned `ollama runner` processes (their `ollama serve` parents gone) were on the machine at the time |
| 04_dataset_builder (solution) | 11.7 s | 10.5 s | `DATASET READY`, 373 / 72 / 20, both times |
| 06_compare_base_tuned (solution, pre-baked adapter) | 248.3 s | 28.5 s | tuned column identical to the retained run (routing 16/20, urgency 7/20, invented 0); base column 5/20 urgency, 5/20 routing. Warm: all 40 replies reused |
| 05_finetune (solution, `OQ_SMOKE_TEST=1`, `.venv-finetune`: transformers 5.16.1, peft 0.20.0, Python 3.11) | 414.9 s | - | 19 / 19 cells, `ADAPTER READY` |
| 05_finetune (solution, `OQ_SMOKE_TEST=1`, **Colab's 2026-09-21 versions**: transformers 5.17.0, peft 0.21.0, accelerate 1.15.0, huggingface_hub 1.31.0, tokenizers 0.23.2, torch 2.11.0 CPU, Python 3.13) | 334.4 s | - | 19 / 19 cells, `ADAPTER READY`, no new warnings. CPU plumbing only: the T4 / CUDA 13 path of the new Colab image is still unrun |
| Participant versions 01-06 | 7.5-110.5 s | - | each stops at its first hard TODO with `TODO n is not filled in yet` (01 at TODO 4: TODOs 1-3 are the diagnostic and never stop the room), nothing earlier |

Cold `pip install --no-cache-dir -r requirements.txt` into a fresh venv:
Python 3.11.15 102 s, Python 3.12.11 101 s, `pip check` clean, setup_check
all PASS. The same install failed with `OSError ... Windows Long Path
support` (on a jedi file, which ipykernel pulls in) from a venv folder 132
characters long. The deepest file in the finished venv is 142
characters below the venv folder (debugpy), so on Windows without long
paths enabled the venv folder must be under about 116 characters.
Playbook E22.
