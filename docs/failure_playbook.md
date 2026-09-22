# Failure playbook

The likeliest breakages in the room, with fixes. Populated from REAL
errors hit during the build and dry runs, not imagined ones — an entry
without a "seen on" date has not earned its place yet.

Format per entry: symptom → cause → fix → seen on.

## Entries

### 1. `OPENAI_API_KEY not set` (or 401 from the hosted API)
- **Symptom:** `setup_check.py` FAIL row, or `EndpointError: ... needs OPENAI_API_KEY`.
- **Cause:** no `.env` at repo root, or the variable is misspelled
  (seen in the wild as `OPEN_API_KEY` — setup_check names the
  misspelling when it sees one).
- **Fix:** `cp setup/.env.example .env`, set `OPENAI_API_KEY=...`
  exactly, re-run `python setup/setup_check.py`.
- **Seen on:** 2026-09-19 (build machine).

### 2. Ollama: `model requires more system memory (15.9 GiB) than is available`
- **Symptom:** `EndpointError: Endpoint 'local' returned HTTP 500:
  {"error":{"message":"model requires more system memory (15.9 GiB)
  than is available (4.2 GiB)"...` for a model that is only 2 GB on
  disk. `run_eval.py` stops with "The endpoint is not answering".
- **Cause:** not the model - the context window. The Ollama desktop
  app has a context-length setting; at its maximum (262144 tokens) the
  KV cache alone needs many GB. `server.log` shows the giveaway line
  `requested context size too large for model num_ctx=262144`. A
  laptop with little free RAM hits this even at moderate settings.
- **Fix:** lower the context length in the Ollama app settings to
  4096 (the ticket prompts are under 1,000 tokens), or leave the app
  alone and start a second server:
  `OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 ollama serve`,
  then set `OLLAMA_BASE_URL=http://localhost:11435` in `.env`. In
  Colab the notebook starts the server itself, so set
  `OLLAMA_CONTEXT_LENGTH=4096` there too. Do NOT switch to a smaller
  or bigger model to get around it.
- **Seen on:** 2026-09-20 (build machine, Ollama 0.12.10, Windows 11,
  27.6 GB RAM with 3.2 GB free).

### 3. Fine-tune notebook: `TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'warmup_ratio'`
- **Symptom:** a participant pastes training arguments from a tutorial
  or a chatbot into notebook 05 and the `trainer` cell dies with an
  unexpected keyword: `warmup_ratio`, `group_by_length`,
  `evaluation_strategy`, or `tokenizer=` on `Trainer(...)`.
- **Cause:** Colab ships transformers 5.x. Those names are from 4.x
  and were removed. Almost everything on the web is still 4.x.
- **Fix:** use the 5.x names the notebook already has:
  `warmup_steps=0.1` (a float is a fraction), `train_sampling_strategy=
  "group_by_length"`, `eval_strategy=`, `processing_class=`. Do NOT
  `pip install` an older transformers to make the pasted code work.
- **Seen on:** 2026-09-20 (build machine, transformers 5.16.1 -
  found by introspecting the installed package before writing the cell).

### 4. Fine-tune notebook: `RuntimeError: The run folder ... was started with different settings (changed: lora_rank)`
- **Symptom:** the `runfolder` cell stops after a participant changes a
  TODO value and re-runs.
- **Cause:** by design. The run folder on Drive holds checkpoints made
  with the OLD settings; resuming them under new settings would
  produce a model nobody can describe.
- **Fix:** give the experiment a new `RUN_NAME` in the settings cell
  (`"run2"`) and Run all - the first run stays intact next to it. To
  really start over, delete the run folder it names.
- **Seen on:** 2026-09-20 (build machine; covered by
  `tests/test_finetune_utils.py`).

### 5. Fine-tune notebook: `GPU : NONE` and training crawls
- **Symptom:** the settings cell prints `GPU : NONE. A full run on a
  CPU takes hours`; the first training step takes minutes.
- **Cause:** the Colab runtime is a CPU runtime (the default), or the
  free GPU quota for that Google account is used up.
- **Fix:** *Runtime > Change runtime type > T4 GPU*, then Run all -
  nothing is lost, nothing had trained yet. Quota gone: pair up with a
  group that has a GPU, or skip training and use
  `checkpoints/adapter_prebaked/` in notebook 06 - that is what it is
  for. Measured for scale: 7.1 min on a T4, about 3.5 HOURS on a
  12-core laptop CPU. Do NOT reach for a paid tier.
- **Seen on:** 2026-09-20 (build machine has no GPU: ~40 tokens/s).

### 6. `ModuleNotFoundError: No module named 'torch'` when running a notebook headless, though torch IS installed
- **Symptom:** `python -m jupyter nbconvert --execute ...` fails on
  `import torch` inside the notebook, while `python -c "import torch"`
  works in the same terminal.
- **Cause:** two virtual environments. `python -m jupyter nbconvert`
  does not run nbconvert from the current interpreter - it launches
  the first `jupyter-nbconvert` on `PATH`, which belongs to whichever
  environment is *activated*, and the kernel starts there.
- **Fix:** call the module directly: `python -m nbconvert --to notebook
  --execute ...` using the interpreter of the environment you mean. If
  a stale `VIRTUAL_ENV` is set, clear it for the command
  (`env -u VIRTUAL_ENV ...`).
- **Seen on:** 2026-09-20 (build machine, `.venv` activated while
  running `.venv-finetune`).

### 7. Background work dies, or Ollama/Docker stop answering: the machine is out of RAM
- **Symptom:** long jobs vanish or stall with no error; everything is
  slow; Task Manager shows under 1 GB free.
- **Cause:** a killed notebook run can leave its kernel process alive,
  holding the whole model (9 GB seen here), and a Docker container
  left running holds its VM's memory. They do not show up as "the
  notebook", so they are easy to miss.
- **Fix:** Task Manager > Details > sort by memory > end orphaned
  `python.exe` processes; `docker ps` then `docker stop <id>`; in
  Ollama, `ollama stop <model>` unloads a model without stopping the
  server. One heavy job at a time on a 16 to 32 GB laptop.
- **Seen on:** 2026-09-20 (build machine, 27.6 GB RAM: a CPU training
  run and a container test together left 0.6 GB free).

### 8. Tuned model scores WORSE on urgency than the untuned 3B
- **Symptom:** in the S12 table the tuned 1B gets urgency 7/20 and the
  untuned `llama3.2:3b` gets 13/20. Somebody concludes fine-tuning
  made it worse.
- **Cause:** not a bug. The held-out 20 is half `low` and the 3B says
  `low` almost every time; the tuned model escalates by one level, as
  `gpt-4o-mini` does. Against its OWN base (`llama3.2:1b`, 4/20) the
  tuned model improved, and on the 72 validation tickets it gets 76%.
- **Fix:** show `comparison_base1b_vs_tuned.txt` (same model, before
  and after) first, then the four-way table, and use the per-class
  urgency rows to make the point. Full reasoning:
  `checkpoints/adapter_prebaked/README.md`, "Urgency".
- **Seen on:** 2026-09-20 (first run of `run_eval.py --endpoint tuned`).

### 9. Notebook 06 says `ADAPTER IN USE: THE PRE-BAKED ONE` but the group did train
- **Symptom:** the adapter cell of notebook 06 prints the pre-baked
  line for a group whose notebook 05 reached `ADAPTER READY`.
- **Cause:** read the `->` verdicts printed just above that line; it is
  one of three. `folder does not exist`: `MODEL_NAME` / `RUN_NAME` in
  notebook 06 are not the names used in notebook 05 (a second
  experiment was saved as `run2`), or notebook 05 ran under a different
  Google account, so a different Drive. `the weights file is cut off`:
  the runtime died while the adapter was being written. `no twin in
  Ollama`: the run was a smoke test.
- **Fix:** set the two names to match notebook 05 and re-run from the
  settings cell; the base run is reused, only the tuned run is asked
  again. For a cut-off file, re-run notebook 05: it resumes from its
  last checkpoint and saves the adapter again. If neither is quick,
  carry on with the pre-baked adapter and say so when presenting -
  that is what it is for.
- **Seen on:** 2026-09-20 (build machine: adapter folder deleted, and a
  weights file truncated to 9 MB, both on purpose;
  `tests/test_compare_utils.py`).

### 10. The base column in notebook 06 is a ticket off the header / the slides
- **Symptom:** the untuned model scores `category 9/20, urgency 5/20`
  where a reference table says `8/20, 4/20`; or two groups' base
  columns differ slightly. Somebody asks which one is right.
- **Cause:** both. `llama3.2:1b` untuned is not stable at temperature
  0 under Ollama: 9 of its 20 replies differed between two runs on the
  build machine on the same day, and the same single request sent
  twice gave two different replies (one of them missing its closing
  brace). Greedy decoding still depends on what the server processed
  just before (prompt cache, batch shapes), and a 1B model has many
  near-tied tokens. The tuned model moved on 1 reply of 20. Two
  complete runs from the same server state were identical. Across
  machines it is wider: the same Ollama 0.12.10 in a Linux container
  changed 12 of the 20 base replies (schema-valid 9/20 there, 12/20 on
  Windows; whole record 2/20 on both) and **0 of the 20 tuned
  replies**. On a Colab T4 (2026-09-21) the base scored 10/20
  schema-valid and routing 5/20, while the tuned column matched the
  other machines ticket for ticket.
- **Fix:** nothing to fix - use it. It is the "base model is
  inconsistent" point of BUILD_SPEC section 3, measured. Do not chase
  the difference, and do not build an argument on a single base
  ticket. The harness's own warning applies: one ticket is 5 points.
- **Seen on:** 2026-09-20 (build machine, Ollama 0.12.10, CPU; and a
  python:3.12-slim container on the same machine).

### 11. `Cannot register the adapter: this Ollama release has dropped LoRA adapters`
- **Symptom:** somebody runs notebook 06 (or
  `scripts/register_adapter.py`) on a laptop and the register cell
  stops; by hand, `ollama create` prints `Error: LoRA adapters are no
  longer supported`. `ollama list` shows the base model but no
  `oq-ticket-tuned`. The Ollama cell above it had already printed
  `LOCAL RUN - NOT A SUPPORTED PATH FOR THIS LAB`.
- **Cause:** the laptop has a current Ollama. Adapter import works on
  0.12.10, the release this repo is built and measured on; it fails on
  0.33.3 (`no Modelfile or safetensors files found`) and is refused on
  0.34.2. This is why the tuned endpoint is **Colab T4 only** (decision
  2026-09-21, `setup/ollama_setup.md`): in Colab the notebook installs
  0.12.10 itself.
- **Fix:** open notebook 06 in Colab on a T4 runtime. That is the
  supported path, not a workaround. Do NOT reinstall or downgrade
  Ollama on a participant's laptop in the room, and do NOT score a
  different model under the `tuned` name. If Colab is unreachable, show
  the pre-baked table (entry 12 says where it is).
- **Seen on:** 2026-09-20 (`ollama/ollama:0.34.2` and `:0.33.3`
  containers on the build machine, with `checkpoints/adapter_prebaked`).

### 12. Notebook 06 on a Colab CPU runtime: `No GPU in this Colab runtime`
- **Symptom:** the Ollama cell of notebook 06 stops with that message.
- **Cause:** by design. On two CPU cores one ticket takes longer than
  the endpoint's 120-second timeout, so the eval would die with `The
  endpoint is not answering` after a 1.9 GB download. Measured in a
  Linux container pinned to two cores: both first tickets timed out
  twice. With two CPUs' worth of time spread over many threads it
  limps: about 37 s per ticket, 30 minutes for the notebook - over its
  25-minute budget.
- **Fix:** *Runtime > Change runtime type > T4 GPU*, Run all. GPU quota
  used up after notebook 05: pair with a group that has a GPU, or show
  the pre-baked table - the no-model `--compare` command is in
  `facilitator/prebaked_outputs/eval/README.md`, the table itself in
  `06_base_vs_tuned/comparison.txt` there. A laptop is NOT the way out:
  the tuned endpoint is unsupported there (entry 11).
- **Seen on:** 2026-09-20 (python:3.12-slim containers, `--cpuset-cpus=0,1`
  and `--cpus=2`, Ollama 0.12.10).

*(Remaining entries — Colab blocked, runtime disconnect on Colab
itself, Ollama won't start, model pull too slow, pip blocked,
OOM, port in use, Drive not mounting — get filled in as they are
actually hit during dry runs. Owner: both slices, whoever hits it
first writes it up.)*
