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

*(Remaining entries — Colab blocked, runtime disconnect, GPU
unavailable, Ollama won't start, model pull too slow, pip blocked,
OOM, port in use, Drive not mounting — get filled in as they are
actually hit during dry runs. Owner: both slices, whoever hits it
first writes it up.)*
