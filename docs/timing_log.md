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
| 04_dataset_builder | — | Colab free-tier CPU, cold | none | **not yet measured** | 40 | needs the P2 commit pushed (the Colab cell clones `main`) and a Google login; adds Drive mount + clone + one pip no-op to the local figure |
