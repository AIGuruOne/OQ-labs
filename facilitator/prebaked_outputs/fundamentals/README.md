# Pre-baked output of notebook 01 (Day 1 S1)

The five checkpoint files `solutions/01_fundamentals.ipynb` leaves in
`CHECKPOINT_DIR`, from the build machine's run of 2026-09-22 against
`gpt-4o-mini` (the hosted endpoint). If the hosted API is unreachable
in the room, these are what the notebook would have produced; the
retained outputs in the solution notebook show the same run cell by
cell, which is the thing to put on the projector.

| File | Written by | What it shows |
|---|---|---|
| `01_diagnostic.json` | the score cell (Part A) | the verdict line for a participant who filled in all three probes: `READY (8 / 8)` |
| `01_part_b.json` | the last Part B cell (FULL path only) | the roles, memory, tokens and prompting replies |
| `01_extractions.json` | the five-ticket cell (Part C) | five held-out tickets, each schema-valid on the first attempt, with field-by-field verdicts against the labelled record: whole record 1 / 5 in this run. Across six runs on 2026-09-22 the table moved by one field between sittings (gpt-4o-mini at temperature 0 is not byte-stable): whole record 1 / 5 five times, 0 / 5 once; schema-valid 5 / 5 every time |
| `01_agent.json` | the agent cell (Part C) | the trace: `get_ticket` -> `get_asset` -> final answer in 3 steps, identical in every run |
| `01_reflection.json` | TODO 7 (Part C) | the solution's reference answers |

To show the final summary without any model call: copy the five files
into `CHECKPOINT_DIR` (`checkpoints/local/` locally), run the setup
cells (Part A up to the ping) and the schema cell in Part C (it defines
`validator`), then the final cell, which reads only the checkpoints.
The five-ticket cell also loads its checkpoint instead of calling the
model; the diagnostic and agent cells always call the model.
