"""Two ways to run one job, so a room can watch the difference.

The job is a picnic, on purpose: nobody in the room has opinions about picnics, so the
argument stays on the mechanism instead of on the domain.

Two engines, same task, same three tools:

    plain   the model decides what to call and when. That is the whole loop.
    gated   code decides the order, and the one tool that changes the world
            stops and waits for a person.

Nothing here talks to a real service. The three tools are dictionaries.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import requests

MODEL = os.environ.get("OQ_AGENT_MODEL", "gpt-4.1-mini")
BASE_URL = os.environ.get("HOSTED_BASE_URL", "https://api.openai.com/v1")

REQUEST = ("We want a picnic in Harbor City on Saturday 10 October. Go ahead only if the "
           "weather is good and I am free. If yes, send an invite to Sara and Omar for the "
           "Harbor Park lawn. Tell me what you did.")

# Each tool says what it is for, because the model reads these descriptions every turn.
# `writes` is ours, not the model's: it is how code knows which one changes the world.
TOOLS = [
    {"name": "get_forecast", "writes": False,
     "description": "Weather for a city on a date.",
     "parameters": {"type": "object", "required": ["city", "date"],
                    "properties": {"city": {"type": "string"}, "date": {"type": "string"}}}},
    {"name": "check_calendar", "writes": False,
     "description": "Is the user free on a date?",
     "parameters": {"type": "object", "required": ["date"],
                    "properties": {"date": {"type": "string"}}}},
    {"name": "send_invite", "writes": True,
     "description": "Send an invite to people. This changes the world.",
     "parameters": {"type": "object", "required": ["date", "place", "to"],
                    "properties": {"date": {"type": "string"}, "place": {"type": "string"},
                                   "to": {"type": "array", "items": {"type": "string"}}}}},
]
WRITES = {t["name"] for t in TOOLS if t["writes"]}

# Everything the "world" remembers. Reset between demos.
SENT: list[dict] = []


def run_tool(name: str, args: dict, broken: bool = False) -> dict:
    if name == "get_forecast":
        if broken:
            return {"error": "TimeoutError: the forecast service did not respond"}
        return {"date": "2026-10-10", "condition": "sunny", "high_c": 31, "rain_pct": 10}
    if name == "check_calendar":
        return {"date": "2026-10-10", "free": True, "conflicts": []}
    if name == "send_invite":
        SENT.append(args)
        return {"status": "sent", "invite_id": f"INV-{len(SENT):03d}"}
    return {"error": f"no such tool: {name}"}


@dataclass
class Step:
    who: str          # "model" or "code" - who decided this happened
    what: str         # a short label
    detail: str = ""
    result: dict | None = None
    writes: bool = False


@dataclass
class Run:
    engine: str
    steps: list[Step] = field(default_factory=list)
    order: list[str] = field(default_factory=list)
    invites: int = 0
    answer: str = ""
    waiting: dict | None = None     # a pending write, when the gate holds one


def _chat(messages: list[dict], with_tools: bool = True) -> dict:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    body = {"model": MODEL, "temperature": 0, "messages": messages}
    if with_tools:
        body["tools"] = [{"type": "function",
                          "function": {k: t[k] for k in ("name", "description", "parameters")}}
                         for t in TOOLS]
    r = requests.post(f"{BASE_URL}/chat/completions", json=body, timeout=90,
                      headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]


# --------------------------------------------------------------- the plain loop

def run_plain(broken: bool = False, cap: int = 8) -> Run:
    """The whole mechanism: ask the model, run what it asks for, repeat."""
    run = Run(engine="plain")
    messages = [{"role": "system", "content": "You are an assistant that can call tools to get a job done."},
                {"role": "user", "content": REQUEST}]

    for _ in range(cap):
        reply = _chat(messages)
        messages.append(reply)
        calls = reply.get("tool_calls") or []
        if not calls:
            run.answer = reply.get("content") or ""
            run.steps.append(Step("model", "stopped", "no tool call, so the loop ends"))
            return run
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            run.order.append(name)
            result = run_tool(name, args, broken)
            if name in WRITES:
                run.invites += 1
            run.steps.append(Step("model", name, json.dumps(args), result, name in WRITES))
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})
    run.steps.append(Step("code", "safety stop", f"{cap} model calls and still going"))
    return run


# --------------------------------------------------------------- the gated version

def run_gated(broken: bool = False) -> Run:
    """The same job, with the order decided by code and the write held for a person.

    Read it beside run_plain: the model is still doing the thinking, in exactly two
    places. Everything else is an ordinary program.
    """
    run = Run(engine="gated")

    # Step 1 and 2 are ours. We know the weather and the calendar are independent,
    # so nothing has to decide the order - there isn't one that matters.
    forecast = run_tool("get_forecast", {"city": "Harbor City", "date": "2026-10-10"}, broken)
    run.order.append("get_forecast")
    run.steps.append(Step("code", "get_forecast", "we always check the weather first",
                          forecast))
    calendar = run_tool("check_calendar", {"date": "2026-10-10"})
    run.order.append("check_calendar")
    run.steps.append(Step("code", "check_calendar", "and the calendar", calendar))

    if "error" in forecast:
        run.steps.append(Step("code", "ask a person",
                              "the forecast failed and we have a rule for that: stop and say so"))
        run.answer = ("I could not get the weather for Harbor City on 10 October, so I did not "
                      "send anything. Your calendar is free.")
        return run

    # The one judgement call worth a model: is this good enough to go ahead?
    decision = _chat([{"role": "system",
                       "content": 'Answer with JSON only: {"go": true|false, "why": "one line"}'},
                      {"role": "user",
                       "content": f"Forecast: {json.dumps(forecast)}\nCalendar: {json.dumps(calendar)}\n"
                                  f"Should we go ahead with the picnic?"}], with_tools=False)
    try:
        verdict = json.loads(decision.get("content", "").strip().strip("`").removeprefix("json"))
    except Exception:
        verdict = {"go": False, "why": "the model's answer was not readable, so we do not go"}
    run.steps.append(Step("model", "decide", "the one judgement call", verdict))

    if not verdict.get("go"):
        run.answer = f"Not going ahead: {verdict.get('why', 'no reason given')}. Nothing was sent."
        return run

    # The write does not run. It waits.
    run.waiting = {"tool": "send_invite",
                   "args": {"date": "2026-10-10", "place": "Harbor Park lawn",
                            "to": ["Sara", "Omar"]}}
    run.steps.append(Step("code", "gate", "this is the call that would run. Nothing is sent yet.",
                          run.waiting, writes=True))
    return run


def approve(run: Run) -> Run:
    """A person said yes. Now, and only now, the write runs."""
    if not run.waiting:
        return run
    result = run_tool(run.waiting["tool"], run.waiting["args"])
    run.invites += 1
    run.order.append(run.waiting["tool"])
    run.steps.append(Step("code", "send_invite", "approved by a person", result, writes=True))
    run.answer = (f"Weather is sunny and you are free, so I sent the invite to Sara and Omar "
                  f"for the Harbor Park lawn ({result['invite_id']}).")
    run.waiting = None
    return run


def reject(run: Run) -> Run:
    run.waiting = None
    run.steps.append(Step("code", "rejected", "a person said no, so nothing was sent"))
    run.answer = "A person rejected it. Nothing was sent."
    return run
