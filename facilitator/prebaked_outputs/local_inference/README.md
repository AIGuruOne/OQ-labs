# Pre-baked output of notebook 02 (Day 2 S7)

The six checkpoint files `solutions/02_local_inference.ipynb` leaves in
`CHECKPOINT_DIR`, from the build machine's retained run of 2026-09-22
(Windows 11, Ollama 0.12.10 on port 11435 with a 4096 context,
`llama3.2:1b` already pulled, no NVIDIA GPU; hosted endpoint
`gpt-4o-mini`). If Ollama cannot be installed or the pull cannot
complete in the room, these are what the notebook would have produced;
the retained outputs in the solution notebook show the same run cell by
cell, which is the thing to put on the projector.

| File | Written by | What it shows |
|---|---|---|
| `02_pull.json` | the PULL CELL | `already there`, 2.1 s: the skip path. A real pull on this machine of a 0.4 GB model took 49 s with progress lines; `llama3.2:1b` (1.3 GB) took 160 s in a clean Linux container over home broadband and 28 s on a Colab T4 (notebook 06's run, 2026-09-21) |
| `02_speed.json` | the speed cell | the server's own clock for one 38-token reply: load 0.11 s, prompt 0.07 s, generate 1.02 s, **37 tokens per second** on the laptop's integrated GPU. Across the day's runs: 33 to 50 tokens/s here, 3.1 in a two-CPU container, about 100 expected on a T4 (not yet measured for this notebook) |
| `02_parameter_runs.json` | TODO 1 | the same prompt under three settings, twice each: `repeatable` (temperature 0, seed 42) IDENTICAL in this run - but DIFFERENT in another sitting the same afternoon; `creative` (temperature 1) DIFFERENT every time; `capped` (12 tokens) cut off with `finish_reason: length` every time |
| `02_ticket_local.json` | the ticket cell | `llama3.2:1b`'s reply to INC-004183 with the house system prompt: **missing its closing brace** in this run (`not JSON`). In an earlier sitting the same afternoon the same request returned valid JSON with 2 of 6 exact fields right. Both are real; the untuned 1B is not stable (playbook entry 10) |
| `02_ticket_hosted.json` | TODO 2 | `gpt-4o-mini`'s reply: valid JSON, 4 of 6 exact fields right (`affected_system` written `TEAMS` for `Teams`; `routing_queue` `apps_support` for `end_user_computing`), 2.7 to 2.8 s in every run |
| `02_comparison.json` | the table cell | the side-by-side rows and the rendered table: where each model ran, who saw the ticket, seconds, format, fields, requested action |

To show the final summary without a model: copy the six files into
`CHECKPOINT_DIR` (`checkpoints/local/` locally), then run the settings
cell and the final cell. The speed, local-ticket and hosted cells load
their checkpoints instead of calling a model; the pull, card and TODO 1
cells always talk to a server, so with no Ollama at all, skip them and
read the solution notebook's outputs instead.
