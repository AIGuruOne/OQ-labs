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
| 04_dataset_builder (solution) | 2026-09-19 | local, Windows 11, Python 3.11.15, cold kernel, checkpoints deleted first (`jupyter nbconvert --execute`) | none | 0.09 (5.3 s) | 40 | run 1 of 2. No retries. Machine time only - the 40 min budget is participant working time on 3 TODOs |
| 04_dataset_builder (solution) | 2026-09-19 | same | none | 0.09 (5.2 s) | 40 | run 2 of 2. Within 20% of run 1 |
| 04_dataset_builder (solution) | 2026-09-20 | local, Windows 11, Python 3.11.15, cold kernel, checkpoints deleted first (`jupyter nbconvert --execute`). After P3: real `quality_checks.py` wired in (one subprocess run + one module run), dataset unchanged at 400/80 | none | 0.11 (6.8 s) | 40 | run 1 of 2. No retries. Machine time only |
| 04_dataset_builder (solution) | 2026-09-20 | same | none | 0.11 (6.7 s) | 40 | run 2 of 2. Within 20% of run 1. Supersedes the 2026-09-19 rows |
| 04_dataset_builder | — | Colab free-tier CPU, cold | none | **not yet measured** | 40 | needs the P2 + P3 commits pushed (the Colab cell clones `main`) and a Google login; adds Drive mount + clone + one pip no-op to the local figure |

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
| `run_eval.py --endpoint local` | — | Colab free-tier T4, cold | **not yet measured** | needs notebook 02/06's Ollama-in-Colab install cell. Add the model load (first call) to the figure |
| `run_eval.py --endpoint tuned` | — | — | **not yet measured** | needs the adapter from notebook 05 |

A first call against a model that is not loaded yet adds the load
time (about 8 s for llama3.2:3b on the build machine).

