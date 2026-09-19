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

*(Remaining entries — Colab blocked, runtime disconnect, GPU
unavailable, Ollama won't start, model pull too slow, pip blocked,
OOM, port in use, Drive not mounting — get filled in as they are
actually hit during dry runs. Owner: both slices, whoever hits it
first writes it up.)*
