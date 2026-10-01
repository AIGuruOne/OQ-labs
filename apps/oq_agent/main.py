"""OQ Agent - one job, run two ways, so a room can see the difference.

    uvicorn apps.oq_agent.main:app --port 8400      # then open http://127.0.0.1:8400

No GPU, no Ollama, no new dependency. One hosted API key.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.oq_agent import agent

STATIC = Path(__file__).resolve().parent / "static"
app = FastAPI(title="OQ Agent", docs_url="/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

_pending: dict[str, agent.Run] = {}          # a gated run waiting for a person


class RunRequest(BaseModel):
    engine: str = Field(default="plain", pattern="^(plain|gated)$")
    broken: bool = False
    obey: bool = True          # plain only: run what the model asks for, or decline it


class Decision(BaseModel):
    approve: bool


def _payload(run: agent.Run) -> dict:
    """The three tallies are the whole argument, so they are computed here, not in JS.

    `functions_actually_run` is the one that settles the room's question: it counts
    program steps that called a real function, and it is never anything but a program
    step, in either engine.
    """
    def count(actor):
        return sum(1 for s in run.steps if s.actor == actor)

    return {"engine": run.engine, "order": run.order, "answer": run.answer,
            "waiting": run.waiting, "invites_this_run": run.invites,
            "invites_total": len(agent.SENT),
            "steps": [asdict(s) for s in run.steps],
            "person_steps": count(agent.PERSON),
            "program_steps": count(agent.PROGRAM),
            "model_steps": count(agent.MODEL_ACTOR),
            "functions_actually_run": sum(1 for s in run.steps if s.ran),
            "functions_run_by_the_model": 0}


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"model": agent.MODEL, "request": agent.REQUEST,
            "tools": [{"name": t["name"], "writes": t["writes"],
                       "description": t["description"]} for t in agent.TOOLS],
            "invites_total": len(agent.SENT)}


@app.post("/run")
def run(req: RunRequest):
    try:
        result = (agent.run_plain(req.broken, req.obey) if req.engine == "plain"
                  else agent.run_gated(req.broken))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    if result.waiting:
        _pending["run"] = result
    return _payload(result)


@app.post("/decide")
def decide(d: Decision):
    held = _pending.pop("run", None)
    if held is None:
        return {"error": "nothing is waiting for a decision"}
    return _payload(agent.approve(held) if d.approve else agent.reject(held))


@app.post("/reset")
def reset():
    agent.SENT.clear()
    _pending.clear()
    return {"invites_total": 0}
