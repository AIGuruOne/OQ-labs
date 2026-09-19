"""Scoring for the ticket task. Pure functions: no network, no files.

    reply text  ->  parse_reply  ->  score_item  ->  summarise

scripts/run_eval.py does the talking to a model and the writing of
files; everything that decides whether an answer is RIGHT lives here,
so it can be read, tested and argued with in one place. The rules are
written up for humans in data/eval/rubric.md.

FOUR THINGS ARE MEASURED, AND NEVER FOLDED INTO ONE NUMBER:

    1. format      did the reply parse, and does it pass the schema?
    2. fields      is each field right?            (six exact, one similarity)
    3. record      are all six exact fields right at once?
    4. invented    values that exist nowhere: outside the allowed
                   list, keys not in the schema, asset tags that are
                   not in the ticket

Use from a notebook:

    import eval_scoring as es
    item = es.score_item(expected_record, reply_text, ticket_text, validator)
    item["fields"]["urgency"]      # {"expected", "predicted", "score", "correct", ...}
"""

import json
import re
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_utils as du  # noqa: E402
from quality_checks import violation_kind  # noqa: E402  (same words as the Day 2 S10 report)

# ---------------------------------------------------------------------
# What is scored how. The seven fields are BUILD_SPEC.md section 8B.
# ---------------------------------------------------------------------

# Right or wrong, no judgement needed.
EXACT_FIELDS = [
    "category",
    "affected_system",
    "asset_tag",
    "urgency",
    "impact",
    "routing_queue",
]

# The one field a model writes in its own words.
SIMILARITY_FIELD = "requested_action"

# Fields with a closed list of allowed values. A value outside the
# list is INVENTED - the model made up a class that does not exist.
ALLOWED_VALUES = {
    "category": ["access", "hardware", "software", "network", "erp", "telecom", "other"],
    "urgency": ["low", "medium", "high", "critical"],
    "impact": ["single_user", "team", "site", "enterprise"],
    "routing_queue": [
        "identity_access", "end_user_computing", "network_ops", "erp_support",
        "apps_support", "telecom_voice", "security_ops", "service_desk_l1",
    ],
}

# Per-class tables are printed for these fields.
CLASS_FIELDS = ["category", "urgency", "impact"]

# urgency is ordered, so a miss has a direction and a size.
URGENCY_ORDER = ["low", "medium", "high", "critical"]

# requested_action counts as a match at or above this similarity.
# Calibrated on 40 real replies (llama3.2:3b and gpt-4o-mini on the
# held-out 20, 2026-09-20): every pair at 0.5 or above named the same
# action on the same object - no false matches. BELOW 0.5 is a mix of
# wrong actions and right actions in other words. So the match rate is
# a FLOOR, and rubric H2 has people read a sample of what is below it.
ACTION_MATCH_THRESHOLD = 0.5

ACTION_MEASURE = (
    "word-set Jaccard similarity (shared words / all words, case and "
    "punctuation ignored) - the same measure as the near-duplicate check"
)
ACTION_LIMITS = (
    "It compares WORDS, not meaning, and the expected clauses are written in one house "
    "style. 'Reset password' vs 'Reset the user's MyPortal password' scores 0.33 though a "
    "desk agent would do the same thing; 'Reset the password' vs 'Do not reset the "
    "password' scores 0.60. Treat the match rate as a floor - it rewards house wording - "
    "and read the sample below the threshold (rubric H2)."
)

# A class with fewer tickets than this gets a "thin" flag in the report.
THIN_CLASS_SIZE = 5

# How many tickets the human reviewers read (data/eval/rubric.md).
# Small on purpose: the target is 15 minutes of reading, not 40 of debate.
URGENCY_REVIEW_SIZE = 3      # H1
REVIEW_SAMPLE_SIZE = 5       # H2, requested_action

# H1: if at least this share of the urgency misses point the same way
# (and there are at least 3), it is ONE disagreement about the
# convention, not many disagreements about tickets.
ONE_DIRECTION_SHARE = 2 / 3

# Any IT asset tag written inside a reply, e.g. LAP-04412.
ASSET_TAG_PATTERN = re.compile(r"\b([A-Za-z]{3})[- ]?([0-9]{5})\b")


# ---------------------------------------------------------------------
# Step 1: reply text -> record
# ---------------------------------------------------------------------


def parse_reply(reply_text):
    """Turn a model's reply into a record. Never raises.

    Returns {"record": dict or None, "parse": ..., "problem": str or None}.

    parse is one of:
      "clean"      json.loads(reply) gave an object. What the prompt asked for.
      "recovered"  an object was found only after stripping a code fence
                   or surrounding prose. The CONTENT gets scored, but the
                   reply is not schema-valid: your integration's
                   json.loads() would have crashed on it.
      "failed"     no JSON object could be found.
    """
    if not isinstance(reply_text, str) or reply_text.strip() == "":
        return {"record": None, "parse": "failed", "problem": "empty reply"}

    text = reply_text.strip()

    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return {"record": value, "parse": "clean", "problem": None}
        kind = type(value).__name__
        return {"record": None, "parse": "failed", "problem": f"JSON, but a {kind} instead of an object"}
    except json.JSONDecodeError:
        pass

    # Second chance: the outermost {...} in the reply.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start:end + 1])
            if isinstance(value, dict):
                return {"record": value, "parse": "recovered",
                        "problem": "extra text around the JSON object"}
        except json.JSONDecodeError:
            pass

    return {"record": None, "parse": "failed", "problem": "not valid JSON"}


# ---------------------------------------------------------------------
# Step 2: compare one field
# ---------------------------------------------------------------------


def normalise_name(value):
    """'Auto Cad', 'AUTOCAD' and 'AutoCAD' are the same system name.
    Lowercase, letters and digits only. Non-strings are left alone."""
    if not isinstance(value, str):
        return value
    return re.sub(r"[^a-z0-9]", "", value.lower())


def exact_match(field, expected, predicted):
    """True if the predicted value counts as the expected one.

    Exact means exact: "High" is not "high". The one allowance is
    affected_system, a NAME, where spacing, case and punctuation are
    ignored ("Auto Cad" = "AutoCAD"). "Tavrona" is still not
    "Tavrona ERP".
    """
    if field == "affected_system":
        expected = normalise_name(expected)
        predicted = normalise_name(predicted)
    # type() check: in Python True == 1, and neither is a valid value.
    return type(expected) == type(predicted) and expected == predicted


def action_similarity(expected, predicted):
    """0.0 to 1.0. See ACTION_MEASURE and ACTION_LIMITS."""
    if not isinstance(predicted, str) or not isinstance(expected, str):
        return 0.0
    return round(du.text_similarity(expected, predicted), 3)


# ---------------------------------------------------------------------
# Step 3: what did the model make up?
# ---------------------------------------------------------------------


def find_invented(record, ticket_text):
    """Values in a reply that exist nowhere. Returns a list of
    {"field", "value", "kind"}; kind is one of:

      not_in_allowed_list      urgency "urgent", routing_queue "helpdesk"
      unexpected_field         a key the schema does not have ("notes")
      asset_tag_not_in_ticket  a tag whose five digits appear nowhere in
                               the ticket - copied from the prompt's
                               example, or from nowhere

    A plain WRONG answer ("high" instead of "medium") is not invented:
    it is a real class, badly chosen. That is counted under accuracy.
    Nor is null: that is the model declining to answer, and it shows
    up as a schema problem (null_not_allowed) instead.
    """
    invented = []

    for field, allowed in ALLOWED_VALUES.items():
        if record.get(field) is not None and record[field] not in allowed:
            invented.append({"field": field, "value": record[field],
                             "kind": "not_in_allowed_list"})

    for key in record:
        if key not in du.RECORD_FIELDS:
            invented.append({"field": key, "value": record[key],
                             "kind": "unexpected_field"})

    ticket_digits = re.sub(r"[^0-9]", " ", ticket_text)
    for field in du.RECORD_FIELDS:
        value = record.get(field)
        if not isinstance(value, str):
            continue
        for prefix, digits in ASSET_TAG_PATTERN.findall(value):
            if digits not in ticket_digits.split():
                invented.append({"field": field, "value": f"{prefix.upper()}-{digits}",
                                 "kind": "asset_tag_not_in_ticket"})
    return invented


# ---------------------------------------------------------------------
# Step 4: score one ticket
# ---------------------------------------------------------------------


def schema_problems(record, validator):
    """Why a parsed record fails data/finetune/ticket_schema.json, as
    short strings like "impact: null_not_allowed". Empty = valid.
    Same vocabulary as scripts/quality_checks.py."""
    problems = []
    for error in du.record_schema_errors(record, validator):
        problems.append(f"{error['field']}: {violation_kind(error)}")
    return sorted(problems)


def score_item(expected, reply_text, ticket_text, validator, reply_error=None):
    """Score one model reply against the expected record.

    expected      the seven-field dict from the dataset
    reply_text    whatever the model sent back (may be garbage, or None)
    ticket_text   the ticket the model saw (to check asset tags against)
    validator     jsonschema validator for ticket_schema.json
    reply_error   set when the endpoint failed and there IS no reply

    A reply that cannot be parsed scores wrong on every field. That is
    deliberate: it is what the integration downstream would experience.
    """
    if reply_error is not None:
        parsed = {"record": None, "parse": "no_reply", "problem": reply_error}
    else:
        parsed = parse_reply(reply_text)
    record = parsed["record"]

    if record is None:
        problems = [f"(record): {parsed['problem']}"]
        invented = []
    else:
        problems = schema_problems(record, validator)
        invented = find_invented(record, ticket_text)

    # Schema-valid = usable as it arrived: clean parse AND passes the schema.
    schema_valid = parsed["parse"] == "clean" and problems == []

    fields = {}
    for field in du.RECORD_FIELDS:
        has_value = record is not None and field in record
        predicted = record[field] if has_value else None
        if field == SIMILARITY_FIELD:
            score = action_similarity(expected[field], predicted)
            correct = score >= ACTION_MATCH_THRESHOLD
            score_type = "similarity"
        else:
            correct = has_value and exact_match(field, expected[field], predicted)
            score = 1.0 if correct else 0.0
            score_type = "exact"
        fields[field] = {
            "expected": expected[field],
            "predicted": predicted,
            "present": has_value,
            "score": score,
            "correct": correct,
            "score_type": score_type,
        }

    exact_fields_correct = sum(1 for field in EXACT_FIELDS if fields[field]["correct"])

    return {
        "parse": parsed["parse"],
        "parse_problem": parsed["problem"],
        "schema_valid": schema_valid,
        "schema_problems": problems,
        "predicted_record": record,
        "fields": fields,
        "invented": invented,
        "exact_fields_correct": exact_fields_correct,
        "record_exact": exact_fields_correct == len(EXACT_FIELDS),
    }


# ---------------------------------------------------------------------
# Step 5: many tickets -> the numbers in the summary
# ---------------------------------------------------------------------


def rate(count, total):
    """count / total as a float rounded to 4 places; 0.0 if total is 0."""
    if total == 0:
        return 0.0
    return round(count / total, 4)


def urgency_step(expected, predicted):
    """How many steps the predicted urgency is ABOVE the expected one.
    +1 = over-escalated by one level, -2 = under by two. None if the
    predicted value is not a real urgency level."""
    if predicted not in URGENCY_ORDER:
        return None
    return URGENCY_ORDER.index(predicted) - URGENCY_ORDER.index(expected)


def summarise_urgency(scored):
    """The shape of the urgency misses: which way, and how far."""
    shape = {"over_by_1": 0, "over_by_2_or_more": 0, "under_by_1": 0,
             "under_by_2_or_more": 0, "not_a_level": 0, "no_usable_reply": 0}
    misses = []
    for entry in scored:
        field = entry["item"]["fields"]["urgency"]
        if field["correct"]:
            continue
        step = urgency_step(field["expected"], field["predicted"])
        if entry["item"]["predicted_record"] is None:
            shape["no_usable_reply"] += 1
        elif step is None:
            shape["not_a_level"] += 1
        elif step > 0:
            shape["over_by_1" if step == 1 else "over_by_2_or_more"] += 1
        else:
            shape["under_by_1" if step == -1 else "under_by_2_or_more"] += 1
        misses.append({"item_id": entry["item_id"], "expected": field["expected"],
                       "predicted": field["predicted"], "step": step})
    return shape, misses


def urgency_direction(misses):
    """Which way do the arguable urgency misses lean?

    "over-escalates" / "under-escalates" when at least two thirds of
    them (and at least 3) go one way, else "mixed"; "none" if there
    are no arguable misses at all.
    """
    steps = [miss["step"] for miss in misses if miss["step"] is not None]
    if not steps:
        return "none"
    over = sum(1 for step in steps if step > 0)
    under = len(steps) - over
    if len(steps) >= 3 and over / len(steps) >= ONE_DIRECTION_SHARE:
        return "over-escalates"
    if len(steps) >= 3 and under / len(steps) >= ONE_DIRECTION_SHARE:
        return "under-escalates"
    return "mixed"


def pick_urgency_review(misses, size=URGENCY_REVIEW_SIZE):
    """The urgency misses worth a human's time: furthest from the
    label first, then by ticket id. Always the same ones for the same
    run, so every group reads the same tickets."""
    arguable = [miss for miss in misses if miss["step"] is not None]
    arguable.sort(key=lambda miss: (-abs(miss["step"]), miss["item_id"]))
    return [miss["item_id"] for miss in arguable[:size]]


def summarise_classes(scored):
    """Per-class COUNTS for category, urgency and impact.

    {"category": {"erp": {"n": 2, "field_correct": 1, "record_exact": 0,
                          "thin": True}, ...}, ...}

    Counts, not percentages: with n = 2, "50%" would look like a
    measurement. It is one ticket.

    A class with NO tickets in the dataset is still listed, with
    n = 0: a class the run never tested must be visible, not missing.
    """
    per_class = {}
    for class_field in CLASS_FIELDS:
        table = {}
        for value in ALLOWED_VALUES[class_field]:
            members = [e for e in scored if e["expected"][class_field] == value]
            field_correct = sum(1 for e in members if e["item"]["fields"][class_field]["correct"])
            record_exact = sum(1 for e in members if e["item"]["record_exact"])
            table[value] = {
                "n": len(members),
                "field_correct": field_correct,
                "record_exact": record_exact,
                "thin": len(members) < THIN_CLASS_SIZE,
            }
        per_class[class_field] = table
    return per_class


def pick_review_sample(item_ids, size=REVIEW_SAMPLE_SIZE):
    """At most `size` ids, spread evenly across the list, always the
    same ones for the same list - so two groups review the same tickets."""
    if len(item_ids) <= size:
        return list(item_ids)
    step = len(item_ids) / size
    return [item_ids[int(index * step)] for index in range(size)]


def summarise_invented(scored):
    by_kind = {"not_in_allowed_list": 0, "unexpected_field": 0, "asset_tag_not_in_ticket": 0}
    examples = []
    for entry in scored:
        for found in entry["item"]["invented"]:
            by_kind[found["kind"]] += 1
            examples.append({"item_id": entry["item_id"], **found})
    return {"total": len(examples), "by_kind": by_kind, "examples": examples}


def limitations(n_items, per_class):
    """Plain sentences about what these numbers can NOT support. They
    go into the summary file AND the printed report, so nobody has to
    discover them."""
    notes = []
    if n_items > 0:
        points = 100 / n_items
        notes.append(
            f"{n_items} tickets: one ticket is {points:.0f} percentage points. A gap of "
            f"{2 * points:.0f} points between two runs is two tickets - do not read it as a trend."
        )
    thin = []
    untested = []
    for class_field, table in per_class.items():
        for value, cell in table.items():
            if cell["n"] == 0:
                untested.append(f"{class_field}={value}")
            elif cell["thin"]:
                thin.append(f"{class_field}={value} (n={cell['n']})")
    if untested:
        notes.append(
            "NOT TESTED AT ALL, no ticket of this class in the dataset: " + ", ".join(untested)
            + ". This run says nothing about them - a perfect score here is silent on these classes."
        )
    if thin:
        notes.append(
            f"Thin classes, fewer than {THIN_CLASS_SIZE} tickets each: " + ", ".join(thin) + ". "
            "Their per-class scores are anecdotes, not measurements. No file in this repo has "
            "enough rare-class tickets to prove rare-class quality - val.jsonl included."
        )
    notes.append("requested_action: " + ACTION_LIMITS)
    notes.append(
        "Labels follow written rules (corpus/README.md, 'Labelling rules'). Where a rule is "
        "arguable - mostly urgency - a 'miss' may be a defensible answer. Rubric H1 handles that."
    )
    notes.append(
        "One run at temperature 0. Local models can still vary slightly between runs and "
        "machines; hosted models change under you. Re-run before quoting a number."
    )
    return notes


def summarise(scored):
    """All the run-level numbers, from a list of scored tickets.

    scored = [{"item_id", "expected", "item": score_item(...), "seconds"}, ...]

    Every rate is over ALL tickets - an unusable reply is wrong on
    every field. `per_field_accuracy_when_parsed` is the same thing
    over only the tickets where a record could be read, so format
    failures and understanding failures can be told apart.
    """
    n_items = len(scored)
    parsed = [e for e in scored if e["item"]["predicted_record"] is not None]

    parse_counts = {"clean": 0, "recovered": 0, "failed": 0, "no_reply": 0}
    for entry in scored:
        parse_counts[entry["item"]["parse"]] += 1

    per_field_accuracy = {}
    per_field_when_parsed = {}
    for field in du.RECORD_FIELDS:
        correct_all = sum(1 for e in scored if e["item"]["fields"][field]["correct"])
        correct_parsed = sum(1 for e in parsed if e["item"]["fields"][field]["correct"])
        per_field_accuracy[field] = rate(correct_all, n_items)
        per_field_when_parsed[field] = rate(correct_parsed, len(parsed))

    action_scores = [e["item"]["fields"][SIMILARITY_FIELD]["score"] for e in scored]
    action_below = [e["item_id"] for e in scored
                    if not e["item"]["fields"][SIMILARITY_FIELD]["correct"]
                    and e["item"]["predicted_record"] is not None]

    urgency_shape, urgency_misses = summarise_urgency(scored)
    per_class = summarise_classes(scored)

    items = []
    for entry in scored:
        item = entry["item"]
        wrong = [f for f in du.RECORD_FIELDS if not item["fields"][f]["correct"]]
        items.append({
            "item_id": entry["item_id"],
            "parse": item["parse"],
            "schema_valid": item["schema_valid"],
            "exact_fields_correct": item["exact_fields_correct"],
            "record_exact": item["record_exact"],
            "action_similarity": item["fields"][SIMILARITY_FIELD]["score"],
            "wrong_fields": wrong,
        })

    seconds = [e["seconds"] for e in scored if e.get("seconds") is not None]

    return {
        "n_items": n_items,
        "n_parsed": len(parsed),
        "parse": parse_counts,
        "schema_valid_rate": rate(sum(1 for e in scored if e["item"]["schema_valid"]), n_items),
        "per_field_accuracy": per_field_accuracy,
        "per_field_accuracy_when_parsed": per_field_when_parsed,
        "requested_action": {
            "measure": ACTION_MEASURE,
            "match_threshold": ACTION_MATCH_THRESHOLD,
            "mean_similarity": round(statistics.mean(action_scores), 3) if action_scores else 0.0,
            "limits": ACTION_LIMITS,
        },
        "overall_exact_match": rate(sum(1 for e in scored if e["item"]["record_exact"]), n_items),
        "overall_exact_match_fields": list(EXACT_FIELDS),
        "invented": summarise_invented(scored),
        "per_class": per_class,
        "urgency_errors": {"shape": urgency_shape, "misses": urgency_misses},
        "review": {
            "H1_urgency": pick_urgency_review(urgency_misses),
            "H1_arguable_total": sum(1 for miss in urgency_misses if miss["step"] is not None),
            "H1_direction": urgency_direction(urgency_misses),
            "H2_requested_action": pick_review_sample(action_below),
            "H2_below_threshold_total": len(action_below),
        },
        "seconds_total": round(sum(seconds), 1),
        "seconds_per_item_median": round(statistics.median(seconds), 2) if seconds else None,
        "items": items,
        "limitations": limitations(n_items, per_class),
    }
