"""OQ Helpdesk - a RAG demo you can drive in a browser.

Run it:
    uvicorn apps.oq_helpdesk.main:app --port 8200
    # then open http://127.0.0.1:8200

What it is for: showing, on screen, the three things a RAG system actually does.
    1. retrieve  - text is pulled from a knowledgebase by a search, not by the model
    2. ground    - the model is handed ONLY that text and told to cite it
    3. refuse    - when the text does not answer the question, it says so

The UI deliberately shows step 1, with scores. Hiding retrieval is what makes RAG
look like magic; showing it is the whole lesson.

Every endpoint in the repo speaks through config/endpoints.py (Contract 3), so the
model can be swapped - hosted API, local Ollama, or the Day 2 tuned adapter -
without touching this file.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.oq_helpdesk.index import SCORE_FLOOR, build_index
from capstone.contract import check_hits
from config.endpoints import get_endpoint

STATIC = Path(__file__).resolve().parent / "static"

# The grounding prompt. This is the whole of the "answers only from the
# knowledgebase" promise, so it is written to be read aloud in a session.
SYSTEM_PROMPT = """You are the OQ IT service desk assistant.

Answer ONLY from the knowledgebase extracts given to you in the user message.

Rules, in order of priority:
1. If the extracts do not contain the answer, reply with exactly:
   NOT_IN_KB: <one short sentence saying what is missing>
   Do not guess, do not use general knowledge, and do not answer from memory.
2. When the extracts do answer it, be brief - at most six sentences - and keep the
   desk's own wording for system names, queue names and asset tag formats.
3. Cite the article for every claim, in square brackets, like [KB-004]. A sentence
   with no citation is not allowed.
4. Never invent a system name, a queue name, a deadline or an approval step that is
   not in the extracts."""


def render_context(hits: list[dict]) -> str:
    """The retrieved text, exactly as the model will see it."""
    blocks = []
    for h in hits:
        m = h["metadata"]
        blocks.append(f"[{h['doc_id']}] {m['title']} - section: {m['section']}\n{h['text']}")
    return "\n\n---\n\n".join(blocks)


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(default=4, ge=1, le=10)
    endpoint: str = Field(default="hosted", pattern="^(hosted|local|tuned)$")


app = FastAPI(title="OQ Helpdesk", docs_url="/docs")
INDEX = build_index()
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    described = INDEX.describe()
    try:
        ep = get_endpoint("hosted")
        model = {"model": ep.model, "base_url": ep.base_url, "usable": True}
    except Exception as exc:                       # no key, no network config - still demo-able
        model = {"model": None, "base_url": None, "usable": False, "why": str(exc)[:160]}
    return {"index": described, "score_floor": SCORE_FLOOR, "model": model,
            "articles": len(INDEX.articles())}


@app.get("/kb")
def kb():
    return {"articles": INDEX.articles(), "index": INDEX.describe()}


@app.post("/ask")
def ask(req: Ask):
    started = time.time()
    hits = INDEX.search(req.question, k=req.k)
    check_hits(hits, req.k)                        # Contract 5, enforced on every search

    # Guard 1: retrieval found nothing worth showing. No model call at all.
    if not hits or hits[0]["score"] < SCORE_FLOOR:
        return {"question": req.question, "hits": hits, "answer": None, "refused": True,
                "reason": "nothing_retrieved",
                "detail": f"Best match scored {hits[0]['score'] if hits else 0.0:.2f}, "
                          f"below the floor of {SCORE_FLOOR}. No model was called.",
                "citations": [], "model": None, "elapsed_ms": int((time.time() - started) * 1000)}

    context = render_context(hits)
    user = (f"Knowledgebase extracts:\n\n{context}\n\n"
            f"---\n\nQuestion from a colleague: {req.question}")

    try:
        endpoint = get_endpoint(req.endpoint)
    except Exception as exc:
        return {"question": req.question, "hits": hits, "answer": None, "refused": False,
                "reason": "no_model",
                "detail": f"Retrieval only - no model configured ({str(exc)[:120]}). "
                          f"The extracts above are what a model would be given.",
                "citations": [], "model": None, "elapsed_ms": int((time.time() - started) * 1000)}

    try:
        reply = endpoint.chat(
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user}],
            temperature=0.0, max_tokens=400, timeout=120).strip()
    except Exception as exc:
        return {"question": req.question, "hits": hits, "answer": None, "refused": False,
                "reason": "model_error", "detail": str(exc)[:200], "citations": [],
                "model": endpoint.model, "elapsed_ms": int((time.time() - started) * 1000)}

    # Guard 2: the model itself says the extracts do not answer it.
    refused = reply.startswith("NOT_IN_KB")
    cited = list(dict.fromkeys(h["doc_id"] for h in hits if f"[{h['doc_id']}]" in reply))   # unique, in rank order

    return {"question": req.question, "hits": hits,
            "answer": reply.removeprefix("NOT_IN_KB:").strip() if refused else reply,
            "refused": refused,
            "reason": "model_says_not_in_kb" if refused else "answered",
            "detail": ("The model was given the extracts above and reported that they do not "
                       "answer this question." if refused else
                       "Answered from the extracts above." if cited else
                       "Answered, but the reply cited no article - treat it with suspicion."),
            "citations": cited, "model": endpoint.model,
            "elapsed_ms": int((time.time() - started) * 1000)}
