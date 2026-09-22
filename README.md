# OQ Advanced AI for IT — lab repo

Hands-on lab material for the 5-day **Advanced AI for IT** program
(27 Sept – 1 Oct 2026). Notebooks, synthetic data, eval scripts and
services. Everything in `corpus/` and `data/` is synthetic — no real
OQ material anywhere in this repo (see `corpus/README.md`).

**This repo sets up in 20 minutes.** If it takes longer, something is
wrong — run the environment check (step 4) and read what it tells you.

## Setup (local)

Requires Python **3.11 or 3.12** (3.13+ is not supported by the
fine-tuning stack). Check with `python --version`.

```bash
# 1. Clone
git clone <repo-url> oq-advanced-ai
cd oq-advanced-ai

# 2. Virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. Install (pinned, ~5 minutes on a normal connection)
pip install -r requirements.txt

# 4. Configure and verify
cp setup/.env.example .env     # then fill in OPENAI_API_KEY
python setup/setup_check.py
```

`setup_check.py` prints a pass/fail table. Every row should be PASS or
an explained WARN before Day 1. It needs no packages installed — you
can run it before step 3 to check your machine. On the OQ network, also
run `python setup/setup_check.py --network` and send the result to the
facilitator: it says which of the hosts the week needs (Colab, Google
sign-in, Drive, GitHub, PyPI, the model API, Ollama, Hugging Face) this
network can reach, so a block is found before Sunday, not during it.

**Day 2 on a laptop** also needs Ollama (a model server, not a Python
package) and one pulled model. Install it and run
`ollama pull llama3.2:1b` (1.3 GB) **before Day 2** — at the Day 1 tech
check, not over venue Wi-Fi in the session. Full guide, including
what to do when your machine behaves differently: `setup/ollama_setup.md`.
On Colab the notebooks install Ollama themselves.

## Setup (Colab)

Nothing to install by hand. Open any notebook via its **Open in Colab**
badge; the first cells detect Colab, install pinned requirements, and
mount Google Drive for checkpoints. Free tier is enough — no notebook
in this repo requires Colab Pro.

Notebooks that call the hosted model (Day 1's `01_fundamentals` is the
first) read the key from **Colab Secrets**: key icon in the left
sidebar, add a secret named exactly `OPENAI_API_KEY`, switch on
*Notebook access*. Do it once; it persists across runtimes.

## Layout

| Path | What it is |
|---|---|
| `notebooks/` | Participant notebooks, with TODO gaps to fill |
| `solutions/` | Completed notebooks with outputs — the reference |
| `corpus/` | Synthetic documents, tickets and images the labs consume |
| `data/` | Fine-tuning datasets and eval sets |
| `config/endpoints.py` | One switch for local Ollama / hosted API / tuned adapter |
| `scripts/` | Eval harness, data generators, quality checks |
| `services/` | Mock ERP API and reference MCP server (Day 5) |
| `setup/` | Environment check and setup guides |
| `docs/` | Interface contracts, timing log, failure playbook |
| `facilitator/` | Day 1 templates (decision matrix, spec, cost model, review checklist), the five capstone briefs, the Day 5 governance pack, pre-baked outputs |

## Commands

```bash
python setup/setup_check.py                                  # environment check
python setup/setup_check.py --network                        # + can this network reach every host the week needs
python scripts/run_eval.py --dataset <path> --endpoint <name>  # eval
python scripts/build_dataset.py --seed 42                      # rebuild train/val/heldout
python scripts/quality_checks.py --dataset data/finetune       # data quality (folder, or file + --val)
python scripts/concurrency_test.py --endpoint local            # load test: latency and throughput as callers rise
uvicorn services.mock_erp.main:app --reload                    # mock ERP (Windows: drop --reload)
python -m services.mock_erp.tour                               # hit every mock ERP endpoint
```

Read `BUILD_SPEC.md` before changing anything, and `CLAUDE.md` if you
are an AI agent working on this repo.
