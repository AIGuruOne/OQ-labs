"""One job, run two ways, with every step attributed to whoever actually did it.

The job is a picnic, on purpose: nobody in the room has opinions about picnics, so the
argument stays on the mechanism instead of on the domain.

The point this file exists to make is narrower than "agents are useful". It is this:

    THE MODEL NEVER RUNS A TOOL.

    It reads text and it writes text. When it "calls a tool" it writes a bit of text
    that NAMES a tool and its arguments. Your program reads that text, decides whether
    to obey it, runs the real function itself, and types the answer back as more text.

So every step carries an `actor`, and there are three of them:

    person      a human typed something, or said yes or no
    program     ordinary code ran a function. This is the only actor that touches
                the world - every invite that ever gets sent is sent on one of these
                lines, in both engines.
    model       text came back. Nothing else happened.

Two engines, same task, same three tools:

    plain   the model decides what to ask for and when. That is the whole loop.
    gated   code decides the order, and the one tool that changes the world
            stops and waits for a person.

Nothing here talks to a real service. The three tools are dictionaries.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import requests

# Importing this loads the repo-root .env into os.environ. Contract 3's module is
# the one place that parsing lives, so the demo borrows it rather than keeping a
# second copy. It still speaks raw HTTP below, because it needs to send `tools`,
# which get_endpoint().chat() deliberately does not expose.
from config import endpoints as _contract3  # noqa: F401

MODEL = os.environ.get("OQ_AGENT_MODEL", "gpt-4.1-mini")
BASE_URL = os.environ.get("HOSTED_BASE_URL", "https://api.openai.com/v1")

PERSON, PROGRAM, MODEL_ACTOR = "person", "program", "model"

REQUEST = ("We want a picnic in Harbor City on Saturday 10 October. Go ahead only if the "
           "weather is good and I am free. If yes, send an invite to Sara and Omar for the "
           "Harbor Park lawn. Tell me what you did.")

# Each tool says what it is for, because the model reads these DESCRIPTIONS every turn.
# It never receives the code. `writes` is ours, not the model's: it is how our program
# knows which one changes the world.
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
    """The real functions. Note who can reach this: our program, and nobody else."""
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
    actor: str                  # person | program | model - who actually did this
    what: str                   # a short label
    detail: str = ""            # why, in a sentence
    result: dict | None = None  # what came back, when something ran
    writes: bool = False        # did this line change the world?
    crossing: str = ""          # "to-model" | "from-model" - text moved across the line
    raw: str = ""               # for a model step: the literal text the model returned
    ran: bool = False           # for a program step: a real function was called


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


def _as_text(reply: dict) -> str:
    """What the model actually sent back, as text, with nothing tidied away.

    Worth showing verbatim: `arguments` arrives as a STRING, not an object. The model
    wrote characters. Something has to parse them before anything can happen.
    """
    if reply.get("tool_calls"):
        # One call per line. It has to fit on a projector beside the step that runs it.
        lines = [json.dumps({"function": {"name": c["function"]["name"],
                                          "arguments": c["function"]["arguments"]}})
                 for c in reply["tool_calls"]]
        return '{"tool_calls": [\n  ' + ',\n  '.join(lines) + '\n]}'
    return json.dumps({"content": reply.get("content") or ""})


def _person_asks(run: Run) -> None:
    """Every run starts here. Nothing in this app ever starts itself."""
    run.steps.append(Step(PERSON, "a person types the request", REQUEST))


# --------------------------------------------------------------- the plain loop

def run_plain(broken: bool = False, obey: bool = True, cap: int = 8) -> Run:
    """The whole mechanism: ask the model, run what it asks for, repeat.

    `obey=False` is the proof that our program is in charge: the model asks for exactly
    the same things, and we simply decline to run them. It cannot tell the difference
    between a tool that failed and a tool we refused, because both come back as text.
    """
    run = Run(engine="plain")
    _person_asks(run)

    messages = [{"role": "system", "content": "You are an assistant that can call tools to get a job done."},
                {"role": "user", "content": REQUEST}]

    for turn in range(cap):
        if turn == 0:
            # Only on the first turn. After that, the step that types a tool result back
            # IS the thing that crosses the line, so saying it twice is just noise.
            run.steps.append(Step(PROGRAM, "sends it all to the model",
                                  f"the conversation so far, plus the NAME and DESCRIPTION of "
                                  f"{len(TOOLS)} tools. Not their code.",
                                  crossing="to-model"))
        reply = _chat(messages)
        messages.append(reply)
        calls = reply.get("tool_calls") or []

        if not calls:
            run.answer = reply.get("content") or ""
            run.steps.append(Step(MODEL_ACTOR, "writes an answer, and asks for nothing",
                                  "no tool named, so our loop has nothing to run and stops",
                                  crossing="from-model", raw=_as_text(reply)))
            return run

        asked = ", ".join(c["function"]["name"] for c in calls)
        run.steps.append(Step(MODEL_ACTOR, f"writes text asking for {asked}",
                              "that is the whole of what the model did. It ran nothing.",
                              crossing="from-model", raw=_as_text(reply)))

        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            writes = name in WRITES

            if not obey:
                result = {"error": "this program did not run that tool"}
                run.steps.append(Step(PROGRAM, f"does NOT run {name}()",
                                      "you turned obeying off. Our program read the request "
                                      "and skipped it. The model has no say in this line.",
                                      result, writes=writes))
            else:
                run.order.append(name)
                result = run_tool(name, args, broken)
                if writes:
                    run.invites += 1
                run.steps.append(Step(PROGRAM, f"runs {name}({json.dumps(args)})",
                                      "our program called the real function. This is the line "
                                      "where something actually happened.",
                                      result, writes=writes, ran=True))

            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})

        run.steps.append(Step(PROGRAM, "types the result back as text, and asks again",
                              "whatever the function returned goes back as an ordinary "
                              "message. The model cannot tell a real result from one we "
                              "made up.",
                              crossing="to-model"))

    run.steps.append(Step(PROGRAM, "safety stop", f"{cap} model calls and still going"))
    return run


# --------------------------------------------------------------- the gated version

def run_gated(broken: bool = False) -> Run:
    """The same job, with the order decided by code and the write held for a person.

    Read it beside run_plain and watch the model's column: it has exactly one line in it.
    """
    run = Run(engine="gated")
    _person_asks(run)

    # Steps 1 and 2 are ours. We know the weather and the calendar are independent,
    # so nothing has to decide the order - there isn't one that matters.
    forecast = run_tool("get_forecast", {"city": "Harbor City", "date": "2026-10-10"}, broken)
    run.order.append("get_forecast")
    run.steps.append(Step(PROGRAM, 'runs get_forecast("Harbor City", "2026-10-10")',
                          "no model involved. Our code knows the weather comes first.",
                          forecast, ran=True))
    calendar = run_tool("check_calendar", {"date": "2026-10-10"})
    run.order.append("check_calendar")
    run.steps.append(Step(PROGRAM, 'runs check_calendar("2026-10-10")',
                          "and the calendar, for the same reason", calendar, ran=True))

    if "error" in forecast:
        run.steps.append(Step(PROGRAM, "stops, and tells the person",
                              "the forecast failed and we have a rule for that. The model was "
                              "never asked, because there is nothing to judge."))
        run.answer = ("I could not get the weather for Harbor City on 10 October, so I did not "
                      "send anything. Your calendar is free.")
        return run

    # The one judgement call worth a model: is this good enough to go ahead?
    run.steps.append(Step(PROGRAM, "asks the model ONE question",
                          "both results, and no tools at all. There is nothing it could "
                          "ask for even if it wanted to.",
                          crossing="to-model"))
    decision = _chat([{"role": "system",
                       "content": 'Answer with JSON only: {"go": true|false, "why": "one line"}'},
                      {"role": "user",
                       "content": f"Forecast: {json.dumps(forecast)}\nCalendar: {json.dumps(calendar)}\n"
                                  f"Should we go ahead with the picnic?"}], with_tools=False)
    try:
        verdict = json.loads(decision.get("content", "").strip().strip("`").removeprefix("json"))
    except Exception:
        verdict = {"go": False, "why": "the model's answer was not readable, so we do not go"}
    run.steps.append(Step(MODEL_ACTOR, "writes a judgement, in text",
                          "the only thing the model does in this whole engine",
                          verdict, crossing="from-model", raw=_as_text(decision)))

    if not verdict.get("go"):
        run.answer = f"Not going ahead: {verdict.get('why', 'no reason given')}. Nothing was sent."
        run.steps.append(Step(PROGRAM, "sends nothing",
                              "our code read the judgement and took the other branch"))
        return run

    # The write does not run. It waits.
    run.waiting = {"tool": "send_invite",
                   "args": {"date": "2026-10-10", "place": "Harbor Park lawn",
                            "to": ["Sara", "Omar"]}}
    run.steps.append(Step(PROGRAM, "holds send_invite() at a gate",
                          "our program has the arguments and could call it on the next line. "
                          "It does not. Nothing has been sent.",
                          run.waiting, writes=True))
    return run


def approve(run: Run) -> Run:
    """A person said yes. Now, and only now, the write runs."""
    if not run.waiting:
        return run
    run.steps.append(Step(PERSON, "a person says yes", "the model is not consulted about this"))
    result = run_tool(run.waiting["tool"], run.waiting["args"])
    run.invites += 1
    run.order.append(run.waiting["tool"])
    run.steps.append(Step(PROGRAM, f"runs send_invite({json.dumps(run.waiting['args'])})",
                          "this is the line that sent the invite", result,
                          writes=True, ran=True))
    run.answer = (f"Weather is sunny and you are free, so I sent the invite to Sara and Omar "
                  f"for the Harbor Park lawn ({result['invite_id']}).")
    run.waiting = None
    return run


def reject(run: Run) -> Run:
    run.waiting = None
    run.steps.append(Step(PERSON, "a person says no", "and that is the end of it"))
    run.steps.append(Step(PROGRAM, "never calls send_invite()", "nothing was sent"))
    run.answer = "A person rejected it. Nothing was sent."
    return run
