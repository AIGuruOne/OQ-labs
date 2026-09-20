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

*(Remaining entries — Colab blocked, runtime disconnect on Colab
itself, Ollama won't start, model pull too slow, pip blocked,
OOM, port in use, Drive not mounting — get filled in as they are
actually hit during dry runs. Owner: both slices, whoever hits it
first writes it up.)*
