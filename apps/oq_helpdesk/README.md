# OQ Helpdesk — RAG in a browser

A small web app that answers IT questions **only** from a knowledgebase we wrote, and
says so when it cannot. Built to demonstrate retrieval in a room, in front of people
who are still finding their way around a notebook.

```bash
uvicorn apps.oq_helpdesk.main:app --port 8200
# open http://127.0.0.1:8200
```

Nothing to install: FastAPI, uvicorn and pydantic are already pinned in
`requirements.txt`. The index is stdlib-only and starts in well under a second, so
the demo survives a venue network.

## What is on screen, and why

The page has three panels on purpose:

| Panel | What it shows | Why it is there |
|---|---|---|
| 1 · You asked | the question | — |
| **2 · Retrieved from the knowledgebase** | every retrieved section, its **score**, and the exact text handed to the model | Hiding this is what makes RAG look like magic. Showing it is the lesson |
| 3 · Answer | the answer with `[KB-004]` citations, or a refusal | Grounding is visible: every claim points at an article |

Panel 2 is the one to dwell on. The model is not "looking things up" — a search ran,
it returned text, and the model was handed that text and nothing else.

## The demo, in four questions

1. **"How do I get access to Tavrona ERP?"** — answers, cites `KB-004`. Open the
   *Show the exact text* fold and point out that the answer is a rewrite of the
   retrieved section. Nothing was recalled.
2. **"How many days of annual leave do I get?"** — refuses. There is no article.
   Note the top score is only ~4.2 against ~8–17 for a covered question.
3. **"Can you disable MFA for me just for today?"** — the best one. Retrieval finds
   the right article (`KB-002`, scoring ~7) and the answer is *still* a refusal,
   because the extract says the desk cannot do it. Retrieval succeeded and the
   answer is still no. That is grounding doing its job.
4. **Stop the model** (unset `OPENAI_API_KEY` and restart) — the app keeps working in
   retrieval-only mode and shows the extracts with no answer. Useful for making the
   point that retrieval and generation are separate stages.

## The two guards

**Guard 1, before any model call.** If the best retrieved section scores below
`SCORE_FLOOR` (2.0), the app refuses without calling the model at all. Cheap, and it
is what you want when a question matches nothing.

**Guard 2, the prompt.** The model is told to answer only from the extracts, to cite
every claim, and to reply `NOT_IN_KB:` when the extracts do not answer the question.
`SYSTEM_PROMPT` in `main.py` is the whole of the "only from the knowledgebase"
promise — it is short enough to read aloud.

### A measured honesty about the floor

Measured on this corpus, 2026-09-29:

| | top score |
|---|---|
| covered question, full sentence | 7.98 – 16.79 |
| covered question, one word (`laptop`) | 2.95 – 10.24 |
| off-corpus question (`annual leave`) | 0.00 – 4.17 |

**Those ranges overlap**, so no single BM25 score separates a question the
knowledgebase covers from one it does not. That is a property of lexical retrieval,
not a bug to tune away, and it is exactly why `notebooks/07_rag_pipeline.ipynb` moves
on to embeddings and a reranker. The floor here is only a "did we retrieve anything
at all" guard; the refusal that matters is guard 2.

While calibrating, `phishing` scored **0.00** because `KB-022` only said "suspicious
email". The article now names both. Vocabulary mismatch is BM25's failure mode, and
it is worth showing.

## How it fits the repo

- **Contract 5.** `index.py` is a second implementation of the index interface, next
  to `capstone/reference_index/bm25.py` which indexes tickets. `main.py` runs the
  repo's own `capstone.contract.check_hits` on every search, so a contract breach
  stops with a sentence instead of failing inside a prompt.
- **Contract 3.** The model call goes through `config/endpoints.py`, so `hosted`,
  `local` (Ollama) and `tuned` (the Day 2 adapter) all work. `POST /ask` takes an
  `endpoint` field.
- **Synthetic only.** Every article is invented, using the same systems as the ticket
  corpus — Tavrona ERP, GateKey VPN, DocHarbor, StaffGate, AssetHive, KeyNest,
  VoxLine, MyPortal — and the same eight routing queues. No real OQ material.

## Not what this is

A demo aid, not lab material. No notebook depends on it, no test outside
`tests/test_helpdesk_app.py` touches it, and it adds no dependency. It is closest to
capstone **brief 2** (HSE procedure assistant), so a group taking that brief can read
it as a worked reference — but it is deliberately simpler than the bar brief 2 sets:
no eval with a number, no audit log, no freshness rule.

## Files

| Path | What it is |
|---|---|
| `kb/*.md` | 15 synthetic articles, frontmatter + markdown |
| `index.py` | BM25 over article sections, Contract 5 |
| `main.py` | FastAPI: `/ask`, `/kb`, `/health`, and the grounding prompt |
| `static/index.html` | the page. One file, no build step, no CDN |
