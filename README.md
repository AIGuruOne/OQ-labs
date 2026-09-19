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
can run it before step 3 to check your machine.

## Setup (Colab)

Nothing to install by hand. Open any notebook via its **Open in Colab**
badge; the first cells detect Colab, install pinned requirements, and
mount Google Drive for checkpoints. Free tier is enough — no notebook
in this repo requires Colab Pro.

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

## Commands

```bash
python setup/setup_check.py                                  # environment check
python scripts/run_eval.py --dataset <path> --endpoint <name>  # eval
python scripts/build_dataset.py --seed 42                      # rebuild train/val/heldout
python scripts/quality_checks.py --dataset <path>              # data quality
uvicorn services.mock_erp.main:app --reload                    # mock ERP
```

Read `BUILD_SPEC.md` before changing anything, and `CLAUDE.md` if you
are an AI agent working on this repo.
