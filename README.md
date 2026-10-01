# OQ Advanced AI for IT — lab repo

Hands-on lab material for the 5-day **Advanced AI for IT** program
(27 Sept – 1 Oct 2026). Notebooks, synthetic data, eval scripts and
services. Everything in `corpus/` and `data/` is synthetic — no real
OQ material anywhere in this repo (see `corpus/README.md`).

**This repo sets up in 20 minutes.** If it takes longer, something is
wrong — run the environment check (step 4) and read what it tells you.

## Coming back to this after the week

The program ran 27 Sept – 1 Oct 2026. Everything you used is here, and it still
runs. Pick the door that suits what you want to do:

| You want to… | Start here | Needs |
|---|---|---|
| Re-read what a session covered | `resources/` — all five slide decks and every working document | a PDF reader |
| Remind yourself what each lab *taught* | `facilitator/skills_map.md` — one row per lab: the skill, how you check it landed, what uses it next | nothing |
| Show someone else a concept in five minutes | `apps/` — three browser demos (below) | one API key |
| Re-run a lab | `notebooks/` — see the session table below | the setup under *Setup (local)*, or Colab |
| See a finished answer | `solutions/` for labs 01–06; for 07–15 the committed notebook already has its outputs | nothing |
| Apply it to a real OQ system | `facilitator/production_engineering_handout.md`, `facilitator/deployment_checklist.md`, `facilitator/governance_pack/` | nothing |
| Move it off Colab onto Azure | `resources/OQ_Colab_to_Azure.pdf` | nothing |

If something no longer runs, `docs/failure_playbook.md` has the error text and
the fix for every failure we actually hit, including on Colab.

## Setup (local)

Requires Python **3.11 or 3.12** (3.13+ is not supported by the
fine-tuning stack). Check with `python --version`.

```bash
# 1. Clone
git clone https://github.com/AIGuruOne/OQ-labs.git
cd OQ-labs

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
run `python setup/setup_check.py --network`: it says which of the hosts
this material needs (Colab, Google sign-in, Drive, GitHub, PyPI, the
model API, Ollama, Hugging Face) the network can reach. **Run this first
if something stops working at your desk** — a blocked host looks exactly
like broken code, and that is the single most expensive hour to lose.

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

## The week, session by session

Every lab notebook lives in `notebooks/`, numbered in the order the week
runs them. Open one with its **Open in Colab** badge, or run it locally.

| Day | Session | Notebook or file |
|---|---|---|
| **1** Architect | S1. Fundamentals | `notebooks/01_fundamentals.ipynb` |
| | S3. Build, buy or host | `resources/day1/OQ_D1_S3_Decision_Matrix.xlsx` |
| | S4. Architecture spec + cost model | `resources/day1/OQ_D1_S4_Architecture_Spec_Template.docx`, `..._Cost_Model.xlsx` |
| | S5. Spec peer review | `resources/day1/OQ_D1_S5_Spec_Review_Checklist.docx` |
| | Close. Capstone groups form | `resources/day1/OQ_D1_Use_Case_Briefs.pdf` |
| **2** Own the model | S7. Run a model yourself | `notebooks/02_local_inference.ipynb` |
| | S8. What breaks at scale | `notebooks/03_concurrency.ipynb` |
| | S10. Build the dataset | `notebooks/04_dataset_builder.ipynb` |
| | S11. Fine-tune it | `notebooks/05_finetune.ipynb` (Apple Silicon: `05b_finetune_mlx.ipynb`) |
| | S12. Did it work | `notebooks/06_compare_base_tuned.ipynb` |
| **3** Ground it | S15. Full text RAG pipeline | `notebooks/07_rag_pipeline.ipynb` |
| | **S16. Vision, step 1 — START HERE** | `notebooks/08a_vision_basics.ipynb` (15 min, one API key, no GPU, no Ollama) |
| | **S16. Vision, step 2** | `notebooks/09a_vision_review_rule.ipynb` (20 min, ends with the sentence you take to S27) |
| | S16. Vision, lab 1 — diagrams | `notebooks/08_vision_diagram.ipynb` |
| | S16. Supplement — is the image worth sending? | `notebooks/08b_image_triage.ipynb` (15 min, no model, no key) |
| | S16. Vision, lab 2 — scanned work orders | `notebooks/09_vision_scanned.ipynb` |
| | S16. Vision, lab 3 — multimodal retrieval | `notebooks/10_multimodal_retrieval.ipynb` |
| **4** Agents | S19. Tune versus retrieve | `notebooks/11_three_way.ipynb` |
| | **S22. MCP — START HERE** | `notebooks/11a_mcp_basics.ipynb` (20 min, no model, no key, no GPU) |
| | S22. MCP live, the fuller version | `notebooks/11b_mcp_live.ipynb` |
| | S23. The agent graph | `notebooks/12_agent_graph.ipynb` |
| | S24. Control | `notebooks/13_agent_control.ipynb` |
| | S25. Agent safety and patterns | `notebooks/14_agent_safety.ipynb`, `facilitator/harness_and_loop_handout.md` |
| | Close. Integration mapping | `notebooks/15_integration_mapping.ipynb` |
| **5** Integrate and ship | S26. Build an MCP server | `facilitator/mcp_build_sequence.md`, `services/` |
| | S27–S28. Capstone assembly | `capstone/` — your group edits `capstone/my_usecase.py` |
| | S29. Governance pack | `facilitator/governance_pack/` |
| | S30. Showcase and peer review | `facilitator/peer_scoring_sheet.md` |

### Two kinds of notebook

**Days 1, 2 and 5** notebooks have **TODO gaps you fill in**. Their
committed copies in `notebooks/` have outputs cleared, and the completed
reference with outputs is in `solutions/`.

**Days 3 and 4** notebooks (07–15) work differently, on purpose: they have
no TODO gaps — you read and run them — and they ship **with their outputs
kept**, so the lab still reads correctly if a model call fails on venue
Wi-Fi. There is no `solutions/` copy of these; the committed notebook *is*
the reference. Notebooks 12, 13 and 14 go further and carry their whole
working set (corpus, two MCP servers, a chunk index, seed tickets and one
saved run) inside a payload cell, so they run on a bare Colab runtime with
nothing cloned.

Days 3 and 4 also **install their own pinned packages** in their first cell
(`openai`, `rank-bm25`, `sentence-transformers`, `ragas` and friends) rather
than relying on `requirements.txt`. That keeps them self-contained on Colab.
Locally, run them in a **separate virtual environment** — a couple of their
pins differ from `requirements.txt` and would disturb the Day 1/2/5 setup.

## Three browser demos

These are not notebooks. Each is one command and a web page, built because the
concepts land faster when a room can watch them than when they read a cell. They
need **one hosted API key and nothing else** — no GPU, no Ollama, no local model,
no extra packages beyond `requirements.txt`.

```bash
uvicorn apps.oq_helpdesk.main:app --port 8200   # then open http://127.0.0.1:8200
uvicorn apps.oq_vision.main:app   --port 8300
uvicorn apps.oq_agent.main:app    --port 8400
```

| App | Shows | Pairs with |
|---|---|---|
| `apps/oq_helpdesk/` | Retrieval: answers only from a knowledgebase we wrote, and says so when it cannot | Day 3, S14–S15 |
| `apps/oq_vision/` | What a model does when it cannot quite read the page, and how the prompt changes that | Day 3, S16 |
| `apps/oq_agent/` | **Who actually runs a tool.** One job run two ways, in two columns: the model only ever writes text, your program is what acts | Day 4, S22–S24 |

`apps/oq_agent/` is the one to open first if "the model called the tool" still
sounds right to you — it is the misconception the whole page is built to remove.
Each app has its own README with the demo script and the measured results.

## Slides and hand-outs

Both live in `resources/` — see `resources/README.md` for the full index.

- **Slide decks, all five days:** `OQ_Day1_Architect.pdf`,
  `OQ_Day2_Own_the_Model.pdf`, `OQ_Day3_Ground_It.pdf`, `OQ_Day4_Agents.pdf`,
  `OQ_Day5_Integrate_and_Ship.pdf`, plus `OQ_Colab_to_Azure.pdf` for moving what
  you built onto an Azure VM in the OQ tenant.
- **Working documents:** the Office version of everything you filled in during
  the week, under `resources/`, one folder per day — decision matrix, architecture spec,
  cost model, review checklist, sizing worksheet, scorecards, RAG blueprint,
  golden set, vision pack, agent design sheet, risk register, integration map,
  governance templates, deployment checklist, peer scoring — with filled examples
  for briefs 1, 2, 3 and 4.

**No setup at all:** `resources/day5/OQ_Day5_Graph_Walkthrough.html` is the
picnic agent walked through step by step in a single file. Double-click it.

Where a document has a Markdown original, it is in `facilitator/`;
`resources/README.md` says which.

## Layout

| Path | What it is |
|---|---|
| `notebooks/` | Every lab notebook, `01`–`15`, in the order the week runs them |
| `apps/` | Three small browser demos. No notebook, no Jupyter — run one and open a page |
| `solutions/` | Completed Day 1/2/5 notebooks with outputs — the reference for `01`–`06` |
| `resources/` | Slide decks, and the Office versions of every working document (PDF, Excel, Word) |
| `corpus/` | Synthetic tickets, and the folders the Day 3 labs generate their documents and images into |
| `data/` | Fine-tuning datasets and eval sets |
| `config/endpoints.py` | One switch for local Ollama / hosted API / tuned adapter |
| `scripts/` | Eval harness, data generators, quality checks |
| `services/` | Mock ERP API and reference MCP server (Day 5) |
| `capstone/` | Day 5 capstone scaffold: one file per group (`my_usecase.py`), the Contract 5 reference index, a worked brief 5 build |
| `setup/` | Environment check and setup guides |
| `docs/` | Interface contracts, timing log, failure playbook |
| `facilitator/skills_map.md` | What each lab teaches, how you check it landed, and what consumes it downstream |
| `facilitator/` | Day 1 templates (decision matrix, spec, cost model, review checklist), the five capstone briefs, the Day 4 decision table and harness hand-out, the Day 5 governance pack, production handout, deployment checklist, peer scoring sheet, pre-baked outputs |

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

## Copyright

(c) 2026 AI Guru. All rights reserved. This repository is public so
participants can clone it into Colab without a GitHub account - that is a
convenience, not an open-source licence. Participants and OQ staff may run
and modify it freely for their own learning; redistributing it or teaching
from it elsewhere needs written permission. All data is synthetic. See
`LICENSE`.
