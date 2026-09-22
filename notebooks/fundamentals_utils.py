"""Helpers for notebook 01 (fundamentals): the diagnostic, the raw REST
call, JSON parsing and validation, sample tickets, and the agent tools.

Import after the environment-detection cell has run:

    import fundamentals_utils as fu

Everything here is short and plain on purpose. The notebook shows the
IDEA in each cell; the bookkeeping (scoring a probe, stripping a code
fence, reading five tickets) lives here so the cells stay readable.

No model call in this module changes anything: the only network use is
`raw_chat_completion` (one POST) and `score_probe_1` (one chat call),
and both are asked for explicitly by a notebook cell.
"""

import json
import os
import re
import time
from pathlib import Path

import jsonschema
import requests

import dataset_utils as du

# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------


def banner(text):
    """A line nobody can miss on a projector."""
    rule = "=" * 64
    print(rule)
    print(f" {text}")
    print(rule)


def show(label, text, limit=400):
    """Print a labelled model reply, cut at `limit` characters."""
    text = str(text)
    cut = text if len(text) <= limit else text[:limit] + " ...[cut]"
    print(f"--- {label} ---")
    print(cut)
    print()


# ---------------------------------------------------------------------------
# Part A: endpoint ping
# ---------------------------------------------------------------------------


def ping(llm):
    """One tiny call. Returns {"model", "seconds", "reply"}."""
    started = time.time()
    reply = llm.chat("Reply with the single word OK.", temperature=0.0, max_tokens=5)
    seconds = round(time.time() - started, 2)
    result = {"model": llm.model, "seconds": seconds, "reply": reply.strip()}
    print(f"endpoint '{llm.name}' answered in {seconds}s: {reply.strip()!r} (model {llm.model})")
    return result


# ---------------------------------------------------------------------------
# Part A: the diagnostic (three probes, scored 2 + 2 + 4 = 8)
# ---------------------------------------------------------------------------

# Probe 1: the API has no memory. The tag is given in an earlier turn.
PROBE_1_EARLIER_USER = "Hi, my laptop is LAP-04412 and it will not boot."
PROBE_1_EARLIER_ASSISTANT = "Sorry to hear that. Does it show any error on screen?"
PROBE_1_FOLLOW_UP = "No error. Which asset tag did I give you? Reply with the tag only."
PROBE_1_EXPECTED_TAG = "LAP-04412"

# Probe 2: structured output from a ticket.
PROBE_2_TICKET = (
    "Subject: laptop dead\n\n"
    "LAP-07731 will not power on since this morning, I have a customer "
    "demo at 14:00 and my slides are on it."
)
PROBE_2_KEYS = {"category", "urgency", "asset_tag"}
PROBE_2_EXPECTED = {"category": "hardware", "asset_tag": "LAP-07731"}
PROBE_2_URGENCY_OK = {"high", "critical"}

# Probe 3: four concept questions, one letter each.
QUIZ = [
    ("q1", "temperature=0 means the model ...",
     {"a": "answers faster",
      "b": "uses fewer tokens",
      "c": "picks the most likely token at every step, so the same prompt gives nearly the same answer",
      "d": "refuses creative tasks"}),
    ("q2", "max_tokens=50 limits ...",
     {"a": "the OUTPUT length; a longer answer is cut off mid-sentence",
      "b": "the INPUT length",
      "c": "both input and output",
      "d": "the number of API calls per minute"}),
    ("q3", "The model returns valid JSON wrapped in ```json fences. json.loads(reply) ...",
     {"a": "accepts it",
      "b": "never happens with a hosted API",
      "c": "only happens with local models",
      "d": "fails; strip the fence, or use JSON mode, and always validate"}),
    ("q4", "In a tool-calling agent loop, who runs the tool (say, a database lookup)?",
     {"a": "the model, inside the API",
      "b": "your code; then you send the result back to the model as a message",
      "c": "the API provider's server",
      "d": "nobody, the model already knows the answer"}),
]
QUIZ_ANSWER_KEY = {"q1": "c", "q2": "a", "q3": "d", "q4": "b"}

DIAGNOSTIC_MAX = 8
DIAGNOSTIC_READY_AT = 6   # 6 of 8 or more -> READY


def print_quiz():
    """Show the four questions so the answers can be typed in a cell."""
    for key, question, options in QUIZ:
        print(f"{key}: {question}")
        for letter, text in options.items():
            print(f"     {letter}) {text}")
        print()


def _is_message_list(messages):
    if not isinstance(messages, list) or not messages:
        return False
    for message in messages:
        if not isinstance(message, dict):
            return False
        if "role" not in message or "content" not in message:
            return False
    return True


def score_probe_1(llm, messages):
    """Probe 1 (2 points): did the follow-up reply contain the tag?

    `messages` is what the participant built. Ellipsis or a malformed
    list scores 0 without stopping the notebook: the diagnostic must
    never crash the room.
    """
    if messages is Ellipsis:
        print("probe 1: NOT ATTEMPTED (messages is still ...)  -> 0 / 2")
        return 0
    if not _is_message_list(messages):
        print("probe 1: messages is not a list of {role, content} dicts  -> 0 / 2")
        return 0
    try:
        reply = llm.chat(messages=messages, temperature=0.0, max_tokens=30)
    except Exception as err:  # noqa: BLE001 - a bad role name is a 400
        print(f"probe 1: the API rejected the messages ({err})  -> 0 / 2")
        return 0
    passed = PROBE_1_EXPECTED_TAG in reply
    points = 2 if passed else 0
    print(f"probe 1: model replied {reply.strip()!r}  -> {points} / 2")
    return points


def score_probe_2(record):
    """Probe 2 (2 points): a dict with the three keys and the right values.

    2 = keys and values right; 1 = a dict with the right keys; 0 = else.
    """
    if record is Ellipsis:
        print("probe 2: NOT ATTEMPTED (record is still ...)  -> 0 / 2")
        return 0
    if not isinstance(record, dict):
        print(f"probe 2: record is a {type(record).__name__}, not a dict  -> 0 / 2")
        return 0
    if set(record) != PROBE_2_KEYS:
        print(f"probe 2: keys are {sorted(record)}, wanted {sorted(PROBE_2_KEYS)}  -> 0 / 2")
        return 0
    values_ok = (
        record.get("category") == PROBE_2_EXPECTED["category"]
        and record.get("asset_tag") == PROBE_2_EXPECTED["asset_tag"]
        and record.get("urgency") in PROBE_2_URGENCY_OK
    )
    points = 2 if values_ok else 1
    print(f"probe 2: record = {record}  -> {points} / 2")
    return points


def score_quiz(answers):
    """Probe 3 (4 points): one point per correct letter."""
    if answers is Ellipsis or not isinstance(answers, dict):
        print("quiz: NOT ATTEMPTED  -> 0 / 4")
        return 0
    points = 0
    for key, expected in QUIZ_ANSWER_KEY.items():
        given = str(answers.get(key, "")).strip().lower()
        if given == expected:
            points += 1
    print(f"quiz: {points} / 4 correct")
    return points


def diagnostic_verdict(probe_1, probe_2, quiz):
    """Combine the three scores into the line the room reads out.

    Returns {"total", "verdict"} where verdict is "READY" or
    "FUNDAMENTALS". The probes carry 4 of the 8 points on purpose:
    someone who cannot do either probe cannot reach READY however well
    they guess the quiz.
    """
    total = probe_1 + probe_2 + quiz
    verdict = "READY" if total >= DIAGNOSTIC_READY_AT else "FUNDAMENTALS"
    banner(f"DIAGNOSTIC RESULT:  {verdict}   ({total} / {DIAGNOSTIC_MAX})")
    print(f"  probe 1  conversation history   {probe_1} / 2")
    print(f"  probe 2  structured output       {probe_2} / 2")
    print(f"  quiz     concepts                {quiz} / 4")
    print()
    print("  Hands up if your line says READY. The facilitator counts:")
    print("    READY hands >= two thirds of the room  -> COMPRESSED path (jump to Part C)")
    print("    otherwise                              -> FULL path (continue to Part B)")
    return {"total": total, "verdict": verdict,
            "probe_1": probe_1, "probe_2": probe_2, "quiz": quiz}


# ---------------------------------------------------------------------------
# Part B: the raw REST call that config/endpoints.py wraps
# ---------------------------------------------------------------------------


def raw_chat_completion(llm, messages, temperature=0.0, max_tokens=200):
    """One POST to {base_url}/chat/completions. Returns the WHOLE reply
    body as a dict, not just the text, so `usage` and `finish_reason`
    can be looked at. The key comes from the environment and is never
    printed.
    """
    url = llm.base_url + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + os.environ.get("OPENAI_API_KEY", ""),
    }
    payload = {
        "model": llm.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def reply_text(body):
    """The assistant text inside a raw chat-completion body."""
    return body["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Part C: JSON parsing and schema validation
# ---------------------------------------------------------------------------


def try_parse_json(raw):
    """(True, dict) if the reply is JSON, else (False, reason).

    Strict on purpose: a fenced or prose-wrapped reply is NOT JSON.
    That is the lesson. (`strip_fence` below shows the repair.)
    """
    try:
        return True, json.loads(raw)
    except json.JSONDecodeError as err:
        return False, f"not JSON: {err.msg} at char {err.pos}"


def strip_fence(raw):
    """Remove a ```json ... ``` wrapper if there is one."""
    cleaned = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if fence:
        return fence.group(1)
    return cleaned


def load_schema(repo_root):
    """The locked ticket schema (BUILD_SPEC section 8B)."""
    return du.load_schema(Path(repo_root) / "data" / "finetune" / "ticket_schema.json")


def schema_errors(record, validator):
    """Human-readable schema errors for one record. Empty list = valid."""
    messages = []
    for error in du.record_schema_errors(record, validator):
        messages.append(f"{error['field']}: {error['message']}")
    return messages


# ---------------------------------------------------------------------------
# Part C: five held-out tickets with their expected records
# ---------------------------------------------------------------------------


def load_sample_tickets(repo_root, count=5):
    """The first `count` held-out tickets as
    {"ticket_id", "text", "expected"}. Held-out: never in train or val,
    so nothing a model saw on Day 2 leaks in here either.
    """
    path = Path(repo_root) / "data" / "eval" / "heldout_20.jsonl"
    samples = []
    for pair in du.load_jsonl(path)[:count]:
        samples.append({
            "ticket_id": pair["ticket_id"],
            "text": du.pair_user_text(pair),
            "expected": du.parse_completion(pair),
        })
    return samples


# The six exact-match fields; requested_action is generative and is
# compared by word overlap, the same rule as scripts/eval_scoring.py.
EXACT_FIELDS = [f for f in du.RECORD_FIELDS if f != "requested_action"]
ACTION_MATCH_AT = 0.5


def compare_records(predicted, expected):
    """Per-field verdicts: {field: True/False} for all seven fields."""
    verdicts = {}
    for field in EXACT_FIELDS:
        verdicts[field] = predicted.get(field) == expected.get(field)
    similarity = du.text_similarity(
        str(predicted.get("requested_action", "")),
        str(expected.get("requested_action", "")),
    )
    verdicts["requested_action"] = similarity >= ACTION_MATCH_AT
    return verdicts


def print_comparison_table(rows):
    """rows: [{"ticket_id", "attempts", "verdicts"}] -> one ASCII table."""
    short = {
        "category": "cat", "affected_system": "sys", "asset_tag": "tag",
        "urgency": "urg", "impact": "imp", "requested_action": "act",
        "routing_queue": "queue",
    }
    header = f"{'ticket':<11} {'tries':>5}  " + " ".join(f"{short[f]:>5}" for f in du.RECORD_FIELDS) + "  whole"
    print(header)
    print("-" * len(header))
    for row in rows:
        marks = " ".join(f"{'ok' if row['verdicts'][f] else '--':>5}" for f in du.RECORD_FIELDS)
        whole = all(row["verdicts"][f] for f in EXACT_FIELDS)
        print(f"{row['ticket_id']:<11} {row['attempts']:>5}  {marks}  {'ok' if whole else '--'}")


# ---------------------------------------------------------------------------
# Part C: the agent's tools (synthetic data only)
# ---------------------------------------------------------------------------

# A tiny invented asset register. Tags follow the repo convention
# (prefix, dash, five digits); people are first names only.
ASSET_REGISTER = {
    "LAP-04391": {"asset_tag": "LAP-04391", "model": "ThinkPad T14 Gen 4", "site": "HBT",
                  "assigned_to": "Maryam", "purchased": "2024-11-03",
                  "warranty_until": "2027-11-02", "status": "in_service"},
    "LAP-04672": {"asset_tag": "LAP-04672", "model": "Latitude 5440", "site": "MRB",
                  "assigned_to": "Fatma", "purchased": "2022-06-14",
                  "warranty_until": "2025-06-13", "status": "in_service"},
    "LAP-06858": {"asset_tag": "LAP-06858", "model": "EliteBook 840 G10", "site": "SHZ",
                  "assigned_to": "Joseph", "purchased": "2025-02-20",
                  "warranty_until": "2028-02-19", "status": "in_service"},
    "DSK-05683": {"asset_tag": "DSK-05683", "model": "OptiPlex 7010", "site": "MRB",
                  "assigned_to": "shared", "purchased": "2021-09-01",
                  "warranty_until": "2024-08-31", "status": "in_service"},
}

TODAY_FOR_THE_LAB = "2026-09-27"   # fixed, so the answer is repeatable


def get_ticket(repo_root, ticket_id):
    """Tool: the raw ticket text for one ticket id, or an error string."""
    path = Path(repo_root) / "corpus" / "tickets" / "tickets_raw.jsonl"
    for ticket in du.load_jsonl(path):
        if ticket["ticket_id"] == ticket_id:
            return {"ticket_id": ticket_id, "site": ticket["site"],
                    "created": ticket["created"],
                    "text": du.format_ticket_text(ticket)}
    return {"error": f"no ticket with id {ticket_id}"}


def get_asset(asset_tag):
    """Tool: the asset register row for one tag, or an error string."""
    record = ASSET_REGISTER.get(str(asset_tag).upper())
    if record is None:
        return {"error": f"no asset with tag {asset_tag}"}
    return dict(record, today=TODAY_FOR_THE_LAB)


AGENT_SYSTEM_PROMPT = """You are an IT service desk agent. You can call tools.
Reply with ONE JSON object and nothing else, in one of these two shapes:

  {"tool": "<tool name>", "args": {<arguments>}}      to call a tool
  {"final": "<your answer to the user>"}               when you are done

Tools:
  get_ticket(ticket_id)   the text of a service desk ticket, e.g. "INC-004549"
  get_asset(asset_tag)    the asset register row for an IT asset, e.g. "LAP-04391"

Call one tool at a time. Use only what the tools return; do not invent
warranty dates or asset details. Give a final answer as soon as you have
enough information."""


def parse_action(raw):
    """The model's JSON action as a dict. Tolerates a code fence."""
    ok, value = try_parse_json(strip_fence(raw))
    if not ok or not isinstance(value, dict):
        return {"error": f"reply was not a JSON object: {raw[:120]!r}"}
    return value
