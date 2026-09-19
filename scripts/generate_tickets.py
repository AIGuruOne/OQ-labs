"""Generate the synthetic service desk ticket corpus.

    python scripts/generate_tickets.py --count 600 --seed 42

Writes two files:
    --out         corpus/tickets/tickets_raw.jsonl   raw tickets (Contract 1)
    --labels-out  data/finetune/ticket_labels.jsonl  ground-truth records
                                                     (BUILD_SPEC.md section 8B)

The labels are kept OUT of corpus/ on purpose: retrieval labs ingest
corpus/tickets/ and must never see the answers.

How it works, one ticket at a time:
    1. choose_facts      pick a scenario, a writer persona and the facts
                         that decide the labels (who is affected, is
                         there a deadline, is the system named ...)
    2. compose_core      turn the facts into sentences, with {slots}
    3. add_noise         typos, lowercase, missing punctuation, run-ons
    4. fill_slots        put system names, asset tags, error strings in
                         AFTER the noise, so they are never corrupted
    5. build_record      the ground-truth record, from the same facts

Deterministic: same --seed and --count -> byte-identical files, on any
OS and any Python 3.11+. Standard library only, no GPU, no API calls.
All content is invented - see corpus/README.md.
"""

import argparse
import hashlib
import json
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# The two data modules sit next to this script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticket_phrases as phrases  # noqa: E402
import ticket_scenarios as bank  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"
DEFAULT_LABELS_OUT = REPO_ROOT / "data" / "finetune" / "ticket_labels.jsonl"

# Tickets are "created" inside this window.
WINDOW_START = datetime(2026, 3, 1)
WINDOW_DAYS = 184  # up to 2026-08-31

FIRST_TICKET_NUMBER = 4100  # -> INC-004100. Older ids are free for {old_inc}.

SLOT_PATTERN = re.compile(r"(\{[a-z_0-9]+\})")


# ---------------------------------------------------------------------
# Small random helpers
# ---------------------------------------------------------------------


def weighted_choice(rng, weights):
    """Pick one key from a {key: weight} dict."""
    keys = list(weights.keys())
    values = list(weights.values())
    return rng.choices(keys, weights=values)[0]


def chance(rng, probability):
    return rng.random() < probability


# ---------------------------------------------------------------------
# Step 1 - facts. Everything that decides a label is decided here.
# ---------------------------------------------------------------------


def choose_scenario(rng, exclude_category=None):
    """Category first (the imbalanced mix), then a scenario inside it."""
    category_weights = dict(bank.CATEGORY_WEIGHTS)
    if exclude_category is not None:
        del category_weights[exclude_category]
    category = weighted_choice(rng, category_weights)

    scenario_weights = {}
    for scenario in bank.SCENARIOS:
        if scenario["category"] == category:
            scenario_weights[scenario["id"]] = scenario["weight"]
    scenario_id = weighted_choice(rng, scenario_weights)

    for scenario in bank.SCENARIOS:
        if scenario["id"] == scenario_id:
            return scenario


def choose_created(rng):
    """A timestamp in the window. The work week is Sunday-Thursday."""
    while True:
        day = WINDOW_START + timedelta(days=rng.randrange(WINDOW_DAYS))
        is_weekend = day.weekday() in (4, 5)  # Friday, Saturday
        if is_weekend and chance(rng, 0.88):
            continue
        break
    hour_weights = {6: 2, 7: 8, 8: 16, 9: 16, 10: 13, 11: 11, 12: 6, 13: 8,
                    14: 8, 15: 5, 16: 3, 17: 2, 19: 1, 21: 1}
    hour = weighted_choice(rng, hour_weights)
    minute = rng.randrange(60)
    return day.replace(hour=hour, minute=minute)


def make_asset_tag(rng, prefix):
    return f"{prefix}-{rng.randrange(1000, 10000):05d}"


def write_asset_like_a_user(rng, asset_tag):
    """LAP-04412 is the label. Users also write lap-04412, LAP 04412 ..."""
    style = weighted_choice(rng, {"exact": 70, "lower": 12, "space": 10, "nodash": 8})
    if style == "lower":
        return asset_tag.lower()
    if style == "space":
        return asset_tag.replace("-", " ")
    if style == "nodash":
        return asset_tag.replace("-", "")
    return asset_tag


def make_plant_tag(rng):
    prefix = rng.choice(phrases.PLANT_TAG_PREFIXES)
    number = rng.randrange(1001, 4600)
    suffix = rng.choice(["", "", "A", "B"])
    return f"{prefix}-{number}{suffix}"


def decide_urgency(kind, impact, has_deadline, is_relaxed, has_needed_by, fixed_urgency):
    """THE URGENCY RULE. Urgency follows the stated business effect,
    never the tone. A ticket shouting URGENT!!! with no reason stays put.

        critical  blocked work, site-wide or enterprise-wide
        high      blocked work for a user or team; a same-day deadline;
                  degraded service across a site or the enterprise
        medium    degraded but workable; a request with a needed-by date
        low       a request with no time pressure; "no rush"
    """
    if fixed_urgency is not None:
        return fixed_urgency
    is_wide = impact in ("site", "enterprise")
    if kind == "blocked":
        return "critical" if is_wide else "high"
    if kind == "degraded":
        if is_wide or has_deadline:
            return "high"
        return "low" if is_relaxed else "medium"
    # kind == "request"
    if has_deadline:
        return "high"
    return "medium" if has_needed_by else "low"


def choose_facts(rng):
    scenario = choose_scenario(rng)
    persona_weights = {name: p["weight"] for name, p in phrases.PERSONAS.items()}
    persona_name = weighted_choice(rng, persona_weights)
    persona = phrases.PERSONAS[persona_name]
    created = choose_created(rng)

    # --- affected system: which one, and does the user name it? -------
    system = rng.choice(scenario["systems"]) if scenario["systems"] else None
    system_is_named = system is not None and not chance(rng, scenario["unnamed"])

    # --- asset: what device, and does the user quote its tag? ---------
    asset_prefix = rng.choice(scenario["assets"]) if scenario["assets"] else None
    device_word = rng.choice(phrases.DEVICE_WORDS[asset_prefix]) if asset_prefix else "computer"
    asset_tag = None
    if asset_prefix is not None and chance(rng, scenario["asset_p"]):
        asset_tag = make_asset_tag(rng, asset_prefix)

    # --- impact and the urgency modifiers ------------------------------
    impact = weighted_choice(rng, scenario["scopes"])
    fixed_urgency = scenario.get("urgency")
    kind = scenario["kind"]
    is_wide = impact in ("site", "enterprise")

    has_deadline = False
    is_relaxed = False
    has_needed_by = False
    if fixed_urgency is None:
        has_deadline = scenario.get("deadline_ok", True) and chance(rng, 0.13)
        if not has_deadline and not is_wide and kind in ("degraded", "request"):
            is_relaxed = chance(rng, 0.18)
        if kind == "request" and not has_deadline and not is_relaxed:
            has_needed_by = scenario.get("needed_by_ok", True) and chance(rng, 0.35)

    # --- a second, unrelated problem in the same ticket ----------------
    second_scenario = None
    if chance(rng, 0.11):
        second_scenario = choose_scenario(rng, exclude_category=scenario["category"])

    site = weighted_choice(rng, phrases.SITE_WEIGHTS)
    other_sites = [code for code in phrases.SITE_WEIGHTS if code != site]
    rng.shuffle(other_sites)
    people = rng.sample(phrases.FIRST_NAMES, 5)

    facts = {
        "scenario": scenario,
        "persona_name": persona_name,
        "persona": persona,
        "created": created,
        "site": site,
        "channel": weighted_choice(rng, persona["channels"]),
        "system": system,
        "system_is_named": system_is_named,
        "asset_tag": asset_tag,
        "impact": impact,
        "has_deadline": has_deadline,
        "is_relaxed": is_relaxed,
        "has_needed_by": has_needed_by,
        # shouting, with no reason given. Never combined with "no rush".
        "tone_urgent": chance(rng, 0.07) and not is_relaxed and persona["wrapper"] != "agent",
        "second_scenario": second_scenario,
        "urgency": decide_urgency(kind, impact, has_deadline, is_relaxed, has_needed_by, fixed_urgency),
    }

    # Values for the {slots}. Filled in AFTER noise (step 4).
    facts["slots"] = {
        "system": system_text(rng, scenario, system, system_is_named, persona["voice"]),
        "asset": write_asset_like_a_user(rng, asset_tag) if asset_tag else "",
        "device": device_word,
        "me": people[0],
        "name": people[1],
        "name2": people[2],
        "name3": people[3],
        "author": people[4],  # who wrote the email inside a forwarded trail
        "dept": rng.choice(phrases.DEPARTMENTS),
        "site": site,
        "site2": other_sites[0],
        "site3": other_sites[1],
        "plant_tag": make_plant_tag(rng),
        "wo": f"WO-1{rng.randrange(10000, 100000)}",
        "old_inc": f"INC-{rng.randrange(2000, 4050):06d}",
        "date": (created + timedelta(days=rng.randrange(3, 22))).date().isoformat(),
        "past_date": (created - timedelta(days=rng.randrange(1, 15))).date().isoformat(),
        "ext": str(rng.randrange(2000, 7000)),
    }
    if second_scenario is not None:
        facts["slots"].update(second_problem_slots(rng, second_scenario))
    return facts


def system_text(rng, scenario, system, system_is_named, voice):
    """How the system appears in the text: an alias, or a vague word."""
    if system is None:
        return ""
    if system_is_named:
        return rng.choice(bank.SYSTEM_ALIASES[system])
    generic = scenario["generic"]
    if voice == "note":
        # telegraphic notes drop the article: "pwd reset system"
        generic = generic.removeprefix("the ").removeprefix("my ")
    return generic


def second_problem_slots(rng, second_scenario):
    """The second problem gets its own slots ({system2} ...) so its
    system and asset can never leak into the labels of the first."""
    slots = {"system2": "", "asset2": "", "device2": "computer"}
    if second_scenario["systems"]:
        second_system = rng.choice(second_scenario["systems"])
        slots["system2"] = rng.choice(bank.SYSTEM_ALIASES[second_system])
    if second_scenario["assets"]:
        prefix = rng.choice(second_scenario["assets"])
        slots["device2"] = rng.choice(phrases.DEVICE_WORDS[prefix])
        slots["asset2"] = make_asset_tag(rng, prefix)
    return slots


# ---------------------------------------------------------------------
# Step 2 - compose. Facts -> sentences with {slots}.
# ---------------------------------------------------------------------


def error_gives_system_away(error_text, system):
    hints = bank.SYSTEM_ERROR_HINTS.get(system, [])
    lowered = error_text.lower()
    return any(hint in lowered for hint in hints)


def choose_error(rng, facts, problem_text):
    """Maybe a pasted error string. Never one that names a system the
    user did not name - the affected_system label would become wrong."""
    scenario = facts["scenario"]
    if not scenario["errors"] or not chance(rng, facts["persona"]["p_error"]):
        return None
    error_text = rng.choice(scenario["errors"])
    # stack traces and log dumps are the hard ones - lean towards them
    multiline_errors = [error for error in scenario["errors"] if "\n" in error]
    if multiline_errors and chance(rng, 0.5):
        error_text = rng.choice(multiline_errors)
    user_named_system = facts["system_is_named"] and "{system}" in problem_text
    if error_gives_system_away(error_text, facts["system"]) and not user_named_system:
        return None
    return error_text


def label_bearing_fragments(rng, facts):
    """Sentences that a label depends on. ALWAYS included when they
    apply - leave one out and the ground truth stops being derivable."""
    scenario = facts["scenario"]
    register = facts["persona"]["register"]
    fragments = []

    impact = facts["impact"]
    if impact != "single_user" and not scenario.get("scope_in_text"):
        if impact == "team" and scenario["kind"] == "request":
            fragments.append(rng.choice(phrases.SCOPE_PHRASES_REQUEST_TEAM[register]))
        else:
            fragments.append(rng.choice(phrases.SCOPE_PHRASES[impact][register]))

    if facts["has_deadline"]:
        fragments.append(rng.choice(phrases.DEADLINE_PHRASES[register]))
    if facts["is_relaxed"]:
        fragments.append(rng.choice(phrases.RELAXED_PHRASES[register]))
    if facts["has_needed_by"]:
        fragments.append(rng.choice(phrases.NEEDED_BY_PHRASES[register]))
    return fragments


def colour_fragments(rng, facts):
    """Optional sentences that change NO label: details, wrong guesses,
    things already tried, a screenshot that is not attached."""
    scenario = facts["scenario"]
    persona = facts["persona"]
    register = persona["register"]
    fragments = []

    if facts["asset_tag"] is not None:
        fragments.append(rng.choice(phrases.ASSET_MENTIONS[register]))
    if scenario["details"] and chance(rng, persona["p_detail"]):
        fragments.append(rng.choice(scenario["details"]))
    can_troubleshoot = scenario["kind"] != "request" and not scenario.get("no_troubleshooting")
    if chance(rng, persona["p_tried"]) and can_troubleshoot:
        fragments.append(rng.choice(phrases.TRIED[register]))
    if chance(rng, persona["p_guess"]) and can_troubleshoot:
        # the user's diagnosis - usually wrong, and never the label
        guesses = scenario["guesses"] + phrases.GENERIC_GUESSES[register]
        fragments.append(rng.choice(guesses))
    if facts["impact"] == "single_user" and can_troubleshoot and chance(rng, 0.15):
        fragments.append(rng.choice(phrases.SCOPE_ONLY_ME[register]))
    if chance(rng, persona["p_screenshot"]) and scenario["kind"] != "request":
        fragments.append(rng.choice(phrases.SCREENSHOTS[register]))
    return fragments


def second_problem_text(rng, facts):
    """A second, unrelated problem. The record describes the FIRST
    problem only, so this whole sentence is a distractor."""
    second = facts["second_scenario"]
    persona = facts["persona"]
    if persona["voice"] == "note":
        text = rng.choice(second["notes"])
    elif persona["voice"] == "nn":
        text = rng.choice(second["problems_nn"])
    else:
        text = rng.choice(second["problems"])
    for slot_name in ("system", "device", "name"):
        text = text.replace("{" + slot_name + "}", "{" + slot_name + "2}")
    if facts["slots"]["asset2"] and chance(rng, 0.25):
        text = text + " ({asset2})"
    intro = rng.choice(phrases.SECOND_PROBLEM_INTROS[persona["register"]])
    return f"{intro} {text}"


def choose_backstory(rng, facts):
    """Rambling filler - the wall-of-text tickets. Changes no label."""
    scenario = facts["scenario"]
    bank_for_ticket = list(phrases.BACKSTORY_ANY)
    something_is_broken = scenario["kind"] != "request" and not scenario.get("no_troubleshooting")
    if something_is_broken:
        bank_for_ticket = bank_for_ticket + phrases.BACKSTORY_PROBLEM
    how_many = rng.randint(*facts["persona"]["backstory"])
    backstory = rng.sample(bank_for_ticket, how_many)
    if how_many >= 4 and chance(rng, 0.4):
        backstory.append(phrases.LONG_MESSAGE_APOLOGY)
    return backstory


def compose_core(rng, facts):
    """The main paragraph, before noise. Returns (text, error or None)."""
    scenario = facts["scenario"]
    persona = facts["persona"]
    register = persona["register"]

    voice_key = {"plain": "problems", "nn": "problems_nn", "note": "notes"}[persona["voice"]]
    problem_text = rng.choice(scenario[voice_key])
    error_text = choose_error(rng, facts, problem_text)

    # the middle of the ticket comes in no particular order
    middle = label_bearing_fragments(rng, facts) + colour_fragments(rng, facts)
    rng.shuffle(middle)

    backstory = choose_backstory(rng, facts)
    backstory_before = backstory[: len(backstory) // 2]
    backstory_after = backstory[len(backstory) // 2:]

    sentences = []
    if persona["layout"] == "line" and chance(rng, persona["p_greeting"]):
        sentences.append(rng.choice(phrases.GREETINGS[register]))
    sentences.extend(backstory_before)
    sentences.append(problem_text)
    if error_text is not None:
        sentences.append(rng.choice(phrases.ERROR_INTROS[register]) + " {error}")
    sentences.extend(middle)
    sentences.extend(backstory_after)
    if facts["second_scenario"] is not None:
        sentences.append(second_problem_text(rng, facts))
    if chance(rng, persona["p_ask"]):
        sentences.append(rng.choice(phrases.ASKS[register]))

    # telegraphic notes are strung together with whatever is to hand
    separator = rng.choice([", ", " - ", ". ", " / "]) if persona["voice"] == "note" else " "
    return separator.join(sentences), error_text


def compose_subject(rng, facts):
    """Subjects are as unreliable as bodies: empty, generic, or a note."""
    roll = rng.random()
    if roll < 0.12:
        subject = ""
    elif roll < 0.45:
        subject = rng.choice(phrases.GENERIC_SUBJECTS)
    else:
        subject = rng.choice(facts["scenario"]["notes"])
    if subject and facts["tone_urgent"] and chance(rng, 0.5):
        subject = "URGENT " + subject
    if facts["persona"]["wrapper"] == "forward":
        subject = "FW: " + (subject or "issue")
    return subject


# ---------------------------------------------------------------------
# Step 3 - noise. Only ever touches text OUTSIDE {slots}.
# ---------------------------------------------------------------------


def outside_slots(text, transform):
    """Apply transform() to the text between {slots}, leave slots alone."""
    pieces = SLOT_PATTERN.split(text)
    for index, piece in enumerate(pieces):
        if not SLOT_PATTERN.fullmatch(piece):
            pieces[index] = transform(piece)
    return "".join(pieces)


def misspell(rng, word):
    lowered = word.lower()
    if lowered in phrases.COMMON_MISSPELLINGS and chance(rng, 0.7):
        wrong = rng.choice(phrases.COMMON_MISSPELLINGS[lowered])
        return wrong.capitalize() if word[0].isupper() else wrong

    position = rng.randrange(1, len(word) - 1)
    operation = rng.choice(["swap", "drop", "double", "neighbour"])
    if operation == "swap":
        return word[:position] + word[position + 1] + word[position] + word[position + 2:]
    if operation == "drop":
        return word[:position] + word[position + 1:]
    if operation == "double":
        return word[:position] + word[position] + word[position:]
    neighbours = phrases.KEYBOARD_NEIGHBOURS.get(word[position].lower())
    if neighbours is None:
        return word
    return word[:position] + rng.choice(neighbours) + word[position + 1:]


def add_typos(rng, text, rate):
    """Misspell ordinary words. Ids, tags, slots and CAPS are left alone."""
    words = text.split(" ")
    for index, word in enumerate(words):
        letters = word.rstrip(".,!?:")
        trailing = word[len(letters):]
        is_ordinary = letters.isalpha() and len(letters) >= 4 and not letters.isupper()
        if is_ordinary and chance(rng, rate):
            words[index] = misspell(rng, letters) + trailing
    return " ".join(words)


def make_run_on(rng, text, rate):
    """Join sentences the way hurried people do: no full stop."""

    def join_sentences(match):
        if not chance(rng, rate):
            return match.group(0)
        connector = rng.choice([" ", ", ", " and ", " ", ", ", " so "])
        return connector + match.group(1).lower()

    return re.sub(r"\. ([A-Za-z])", join_sentences, text)


def add_noise(rng, text, persona):
    if chance(rng, persona["no_apos"]):
        text = text.replace("'", "")
    text = make_run_on(rng, text, persona["run_on"])
    if chance(rng, persona["lower"]):
        text = outside_slots(text, str.lower)
    text = add_typos(rng, text, persona["typo"])
    return text


# ---------------------------------------------------------------------
# Step 4 - layout and slots.
# ---------------------------------------------------------------------


def wrap_as_email(rng, core, register):
    greeting = rng.choice(phrases.GREETINGS[register])
    closing = rng.choice(phrases.CLOSINGS[register])
    extra = rng.choice(phrases.SIGNATURE_EXTRAS)
    signature = "{me}" + ("\n" + extra if extra else "")
    return f"{greeting}\n\n{core}\n\n{closing}\n{signature}"


def wrap_as_agent_note(rng, core, channel):
    opener = rng.choice(phrases.AGENT_OPENERS[channel])
    closer = rng.choice(phrases.AGENT_CLOSERS)
    return f"{opener} {core}. {closer}".strip()


def wrap_as_forward(rng, inner_email, facts):
    top = rng.choice(phrases.FORWARD_TOPS)
    sent = facts["created"] - timedelta(minutes=rng.randrange(15, 180))
    header = (
        "-----Original Message-----\n"
        "From: {author} ({dept})\n"
        f"Sent: {sent.isoformat(timespec='minutes')}\n"
        "To: {me}\n"
        "Subject: {inner_subject}"
    )
    inner_email = inner_email.replace("{me}", "{author}")
    trail = ""
    if chance(rng, 0.6):
        # an earlier exchange further down the trail - pure noise
        trail = "\n\n-----Original Message-----\n" + rng.choice(phrases.FORWARD_TRAIL)
    return f"{top}\n\n{header}\n\n{inner_email}\n\n{phrases.EMAIL_DISCLAIMER}{trail}"


def fill_slots(rng, text, slots):
    for slot_name, value in slots.items():
        text = text.replace("{" + slot_name + "}", value)
    while "{n}" in text:
        text = text.replace("{n}", str(rng.randrange(2, 10)), 1)
    return text


def compose_ticket_text(rng, facts):
    """Steps 2-4. Returns (subject, body, templates) - the templates are
    kept so build_record can see which slots the text really used."""
    persona = facts["persona"]
    core_template, error_text = compose_core(rng, facts)
    subject_template = compose_subject(rng, facts)
    facts["error_text"] = error_text

    core = add_noise(rng, core_template, persona)
    subject = add_noise(rng, subject_template, persona)

    if facts["tone_urgent"]:
        shout = rng.choice(phrases.TONE_URGENT)
        core = f"{shout} {core}" if chance(rng, 0.6) else f"{core} {shout}"

    if persona["wrapper"] == "agent":
        body = wrap_as_agent_note(rng, core, facts["channel"])
    elif persona["layout"] == "email":
        body = wrap_as_email(rng, core, persona["register"])
    else:
        body = core
    if persona["wrapper"] == "forward":
        body = wrap_as_forward(rng, body, facts)

    slots = dict(facts["slots"])
    slots["error"] = "\n" + error_text + "\n" if error_text and "\n" in error_text else (error_text or "")
    slots["inner_subject"] = subject_template.removeprefix("FW: ")

    # twice: an error string can itself contain slots ({wo}, {plant_tag})
    body = fill_slots(rng, fill_slots(rng, body, slots), slots)
    subject = fill_slots(rng, subject, slots)
    templates = subject_template + "\n" + core_template + "\n" + (error_text or "")
    return subject.strip(), body.strip(), templates


# ---------------------------------------------------------------------
# Step 5 - the ground-truth record.
# ---------------------------------------------------------------------


def build_record(facts, templates):
    """The section 8B record. Field order matches the spec."""
    scenario = facts["scenario"]

    # affected_system is the canonical name IF the text really names it.
    text_names_system = facts["system_is_named"] and "{system}" in templates
    if text_names_system:
        affected_system = facts["system"]
        requested_action = scenario["action"].replace("{system}", facts["system"])
    else:
        affected_system = None
        requested_action = scenario["action_generic"]

    return {
        "category": scenario["category"],
        "affected_system": affected_system,
        "asset_tag": facts["asset_tag"],
        "urgency": facts["urgency"],
        "impact": facts["impact"],
        "requested_action": requested_action,
        "routing_queue": scenario["queue"],
    }


def list_features(facts, templates, body):
    """Which messiness features this ticket carries. Goes into the
    labels file as metadata - handy for error analysis on Day 2."""
    word_count = len(body.split())
    checks = {
        "two_problems": facts["second_scenario"] is not None,
        "error_string": "{error}" in templates,
        "multiline_paste": "\n" in (facts["error_text"] or ""),  # stack traces, logs
        "screenshot_ref": any(p in templates for bank_ in phrases.SCREENSHOTS.values() for p in bank_),
        "system_unnamed": facts["system"] is not None and not (facts["system_is_named"] and "{system}" in templates),
        "asset_nonstandard": bool(facts["asset_tag"]) and facts["asset_tag"] not in body,
        "plant_tag_distractor": "{plant_tag}" in templates or "{wo}" in templates,
        "tone_urgent": facts["tone_urgent"],
        "non_native": facts["persona"]["voice"] == "nn",
        "agent_note": facts["persona"]["wrapper"] == "agent",
        "forwarded": facts["persona"]["wrapper"] == "forward",
        "very_short": word_count <= 8,
        "very_long": word_count >= 150,
    }
    return [name for name, is_present in checks.items() if is_present]


# ---------------------------------------------------------------------
# The whole corpus
# ---------------------------------------------------------------------


def generate_one(seed, index, seen_bodies):
    """One ticket. Its random stream depends only on (seed, index), so
    tickets do not disturb each other. Exact-duplicate bodies re-roll."""
    for attempt in range(50):
        rng = random.Random(f"{seed}:{index}:{attempt}")
        facts = choose_facts(rng)
        subject, body, templates = compose_ticket_text(rng, facts)
        if body not in seen_bodies:
            break
    seen_bodies.add(body)

    ticket = {
        "ticket_id": None,  # assigned once all tickets are sorted by time
        "created": facts["created"].isoformat(timespec="seconds"),
        "site": facts["site"],
        "channel": facts["channel"],
        "subject": subject,
        "body": body,
    }
    label = {
        "ticket_id": None,
        "record": build_record(facts, templates),
        "meta": {
            "scenario": facts["scenario"]["id"],
            "persona": facts["persona_name"],
            "features": list_features(facts, templates, body),
            "word_count": len(body.split()),
        },
    }
    return ticket, label


def generate_corpus(count, seed):
    seen_bodies = set()
    pairs = [generate_one(seed, index, seen_bodies) for index in range(count)]

    # Ticket ids rise with time, with gaps - like a real desk.
    pairs.sort(key=lambda pair: pair[0]["created"])
    id_rng = random.Random(f"{seed}:ids")
    number = FIRST_TICKET_NUMBER
    for ticket, label in pairs:
        number += id_rng.randrange(1, 8)
        ticket["ticket_id"] = f"INC-{number:06d}"
        label["ticket_id"] = ticket["ticket_id"]

    tickets = [ticket for ticket, label in pairs]
    labels = [label for ticket, label in pairs]
    return tickets, labels


def write_jsonl(path, rows):
    """UTF-8, LF line endings - identical bytes on Windows and Colab."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def print_distribution(title, values):
    print(f"\n{title}")
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    for value, count in sorted(counts.items(), key=lambda item: -item[1]):
        share = 100 * count / len(values)
        print(f"  {str(value):<14}{count:>5}  {share:5.1f}%  {'#' * round(share / 2)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--count", type=int, default=600, help="number of tickets (default 600)")
    parser.add_argument("--seed", type=int, default=42, help="same seed -> same tickets (default 42)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="raw tickets JSONL")
    parser.add_argument("--labels-out", type=Path, default=DEFAULT_LABELS_OUT, help="ground-truth JSONL")
    args = parser.parse_args()

    started = time.perf_counter()
    tickets, labels = generate_corpus(args.count, args.seed)
    tickets_hash = write_jsonl(args.out, tickets)
    labels_hash = write_jsonl(args.labels_out, labels)
    elapsed = time.perf_counter() - started

    print(f"Generated {len(tickets)} tickets with seed {args.seed} in {elapsed:.2f}s")
    print(f"  tickets -> {args.out}\n             sha256 {tickets_hash}")
    print(f"  labels  -> {args.labels_out}\n             sha256 {labels_hash}")
    records = [label["record"] for label in labels]
    print_distribution("category", [record["category"] for record in records])
    print_distribution("urgency", [record["urgency"] for record in records])
    print_distribution("impact", [record["impact"] for record in records])
    null_systems = sum(1 for record in records if record["affected_system"] is None)
    null_assets = sum(1 for record in records if record["asset_tag"] is None)
    print(f"\naffected_system is null in {null_systems}/{len(records)}, asset_tag is null in {null_assets}/{len(records)}")


if __name__ == "__main__":
    main()
