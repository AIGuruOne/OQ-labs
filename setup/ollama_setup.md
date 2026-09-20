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
- **In Colab, notebooks never run "latest".** `notebooks/ollama_utils.py`
  installs ONE pinned release (`OLLAMA_VERSION`, currently 0.12.10 - the
  release every reference score in this repo was measured on) by
  unpacking `https://ollama.com/download/ollama-linux-amd64.tgz?version=<pin>`
  under `/usr/local`, starts `ollama serve` with
  `OLLAMA_CONTEXT_LENGTH=4096`, and pulls models over the HTTP API.
  Notebook 06 uses it today; notebooks 02/03 should call the same
  helper (`ollama_utils.ensure_server`, `ollama_utils.ensure_model`)
  rather than grow a second install cell.
- On a laptop the helper uses whatever Ollama is already running (or
  starts the installed one) and prints a NOTE if its version is not the
  pinned one.

## The tuned endpoint is Colab T4 only (decision, 2026-09-21)

**Notebook 06, and anything else that needs the `tuned` endpoint, is
supported on Google Colab's free T4 runtime and nowhere else.** A
laptop is NOT a supported path for the tuned model, and participants
are not asked to install or downgrade anything to make it one.

Why: the `tuned` endpoint exists only after `ollama create` has turned
the LoRA adapter folder into a model (`scripts/register_adapter.py`).
Tested 2026-09-20 with `checkpoints/adapter_prebaked`:

| Ollama | `ollama create` with `ADAPTER <folder>` |
|---|---|
| 0.12.10 (Windows, and Linux in a container) | works - every reference score was measured on it |
| 0.33.3 | fails: `no Modelfile or safetensors files found` |
| 0.34.2 (current) | refused: `Error: LoRA adapters are no longer supported` |

In Colab the notebook installs 0.12.10 itself, so the version is ours.
On a laptop it is whatever the participant installed, and anyone
installing this month gets a release that refuses adapters. A Colab
*CPU* runtime is not an alternative either: on two cores one ticket
takes longer than the endpoint's 120-second timeout, and the notebook
stops at once when it finds no GPU.

What this does NOT change: the `local` endpoint - a plain pulled model,
notebooks 02 and 03 - needs no adapter and is not affected by the
removal. (Pulling `llama3.2:1b` was seen to work on 0.33.3 and 0.34.2;
chatting with it on those releases was not tested here.)

What a laptop run of notebook 06 does: it still runs, prints `LOCAL RUN
- NOT A SUPPORTED PATH FOR THIS LAB`, and says whether the Ollama it
found is 0.12.10. With 0.12.10 it works - that is how the build machine
produces the reference output and how the tests were run. With anything
newer the register cell stops with a sentence pointing back to Colab.
Do not reinstall Ollama in the room.

**For the pre-program email:** ask anyone who ALREADY has Ollama
installed to run `ollama --version` and send back the line it prints.
Nobody is asked to install, upgrade or downgrade for the tuned model.
The answers tell us before Sunday how many laptops carry a release
that refuses adapters, and so how hard Day 2 S12 and Day 4 S19 lean on
Colab being reachable from OQ's network.

**One machine is the exception - the facilitator's.** The demo fallback
ladder (BUILD_SPEC section 15: Colab, hotspot, fully local) ends on
Ritesh's laptop, and "fully local" includes the tuned model. That one
machine needs Ollama 0.12.10 installed deliberately and checked with
`ollama --version` on the morning of Day 2 (the desktop app can update
itself; how to stop that on 0.12.10 was not tested here). Installers
for that release are still published:
`https://github.com/ollama/ollama/releases/download/v0.12.10/OllamaSetup.exe`
(Windows), `.../Ollama.dmg` (macOS), `.../ollama-linux-amd64.tgz`
(Linux).
