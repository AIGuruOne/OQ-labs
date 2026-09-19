# Ollama setup (Colab and local)

> **Stub.** This guide is built with the Day 2 morning slice
> (notebooks 02/03). It will cover: installing and serving Ollama
> inside a Colab runtime, the local install path for Windows/macOS,
> pulling the lab model, and registering the fine-tuned adapter as
> `oq-ticket-tuned`.

Until then, the two facts other files rely on:

- Ollama serves an OpenAI-compatible API at
  `http://localhost:11434/v1` — this is what `config/endpoints.py`
  talks to for the `local` and `tuned` endpoints.
- `setup/setup_check.py` treats an unreachable Ollama as WARN, not
  FAIL: it is only needed from Day 2, and Colab installs it in-notebook.
