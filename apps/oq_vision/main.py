"""OQ Vision - what a vision model does when it cannot quite read the page.

    uvicorn apps.oq_vision.main:app --port 8300      # then open http://127.0.0.1:8300

One work order, three photograph qualities, two prompts. **No GPU, no Ollama, no
local model** - one hosted API key and nothing else, so this cannot break the way a
self-hosted model can.

The point, in one sentence: a vision model that cannot read a field does not say so.
It returns a value of the right shape, and nothing downstream can tell the difference.

The three photographs are pre-rendered (see forms.py, `python -m apps.oq_vision.forms`),
so this module imports no Pillow and adds no dependency.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from pathlib import Path

import requests
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from apps.oq_vision.forms import FIELDS, LEVELS, TRUTH
from config.endpoints import get_endpoint

STATIC = Path(__file__).resolve().parent / "static"

# Vision model. The hosted endpoint in .env is usually a text model (gpt-4o-mini),
# and labs 08/09/10 all use gpt-4.1-mini for images, so this matches them.
# Worth knowing: gpt-4o-mini refuses far less reliably under the careful prompt -
# it still guessed 4 of 6 where gpt-4.1-mini refused all 6. Set OQ_VISION_MODEL
# to try it, and you get a second, harder lesson: the prompt fix is model-dependent.
VISION_MODEL = os.environ.get("OQ_VISION_MODEL", "gpt-4.1-mini")
KEYS = ", ".join(key for _, key in FIELDS)

# Three prompts. The middle one is the reason this demo exists: it is the fix
# everybody writes first, it sounds careful, and on this image it changes NOTHING.
# Measured 2026-09-30, gpt-4.1-mini, temperature 0, three runs each on level 2:
#   naive  -> 0 refused, 5 wrong   (every run)
#   soft   -> 0 refused, 5 wrong   (every run)
#   strict -> 6 refused, 0 wrong   (every run)
PROMPTS = {
    "naive": f"Read this maintenance work order and return ONLY JSON with exactly these keys: {KEYS}.",

    "soft": (f"Read this maintenance work order and return ONLY JSON with exactly these keys: {KEYS}.\n"
             "Only report a value you can actually READ in the image, character by character.\n"
             'If a value is blurred, cut off, or you are guessing any character, write "NOT_LEGIBLE".\n'
             "A wrong value is far worse than NOT_LEGIBLE. Do not infer a value from the shape of the field."),

    "strict": ("You are transcribing a photograph of a maintenance work order.\n\n"
               f"Return ONLY JSON with exactly these keys: {KEYS}.\n\n"
               "RULES:\n"
               "1. This photograph is low resolution. Assume you CANNOT read most of it.\n"
               "2. For each field ask: can I make out every single character with certainty?\n"
               '3. If the answer is no for ANY character, the value is exactly "NOT_LEGIBLE".\n'
               "4. Identifiers (work order, equipment tag, permit, dates) are the ones to be\n"
               "   strictest about: a plausible-looking wrong identifier is the worst output.\n"
               '5. Never reconstruct a value from its expected format. "It looks like a permit\n'
               '   number" is not reading it. When in doubt, "NOT_LEGIBLE".'),
}
PROMPT_LABELS = {"naive": "Just read it",
                 "soft": 'Read it — "say NOT_LEGIBLE if unsure"',
                 "strict": "Read it — assume you cannot"}


def level_bytes(level_id: int) -> bytes:
    return (STATIC / f"level_{level_id}.jpg").read_bytes()


class ReadRequest(BaseModel):
    level: int = Field(default=0, ge=0, le=2)
    prompt: str = Field(default="naive", pattern="^(naive|soft|strict)$")


app = FastAPI(title="OQ Vision", docs_url="/docs")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    try:
        ep = get_endpoint("hosted")
        model = {"model": VISION_MODEL, "base_url": ep.base_url, "usable": True}
    except Exception as exc:
        model = {"model": None, "usable": False, "why": str(exc)[:160]}
    return {"levels": LEVELS, "truth": TRUTH,
            "fields": [{"label": lab, "key": k} for lab, k in FIELDS],
            "model": model, "prompts": PROMPTS, "prompt_labels": PROMPT_LABELS}


@app.post("/read")
def read(req: ReadRequest):
    level = LEVELS[req.level]
    png = level_bytes(level["id"])
    prompt = PROMPTS[req.prompt]
    started = time.time()

    try:
        reply = _vision_call(get_endpoint("hosted"), prompt, png)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "level": level, "prompt": req.prompt}

    match = re.search(r"\{.*\}", reply, re.S)
    got = json.loads(match.group()) if match else {}

    rows = []
    for label, key in FIELDS:
        value = str(got.get(key, "")).strip()
        flagged = "NOT_LEGIBLE" in value.upper()
        rows.append({"label": label, "key": key, "want": TRUTH[key], "got": value,
                     "ok": value == TRUTH[key], "flagged": flagged})

    return {"level": level, "prompt": req.prompt, "rows": rows,
            "correct": sum(1 for r in rows if r["ok"]),
            "wrong": sum(1 for r in rows if not r["ok"] and not r["flagged"]),
            "flagged": sum(1 for r in rows if r["flagged"]),
            "raw": reply, "ms": int((time.time() - started) * 1000)}


def _vision_call(endpoint, prompt: str, png: bytes) -> str:
    """The image call. Same base_url, model and key as every other hosted call here.

    config/endpoints.py (Contract 3) stays the single place the endpoint is chosen;
    its `chat` is text-only, so this adds the image part of the payload and nothing else.
    """
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set (repo-root .env or the environment)")
    b64 = base64.b64encode(png).decode()
    body = {"model": VISION_MODEL, "temperature": 0, "max_tokens": 400,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]}
    r = requests.post(f"{endpoint.base_url}/chat/completions", json=body, timeout=120,
                      headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
