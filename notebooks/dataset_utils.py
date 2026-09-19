"""Helpers for turning raw service-desk tickets into fine-tuning pairs.

Used by three things, so the logic lives in exactly one place:

    scripts/build_dataset.py            builds data/finetune + data/eval
    notebooks/04_dataset_builder.ipynb  the Day 2 S10 lab
    later labs                          fine-tuning, eval, three-way comparison

Import after the environment-detection cell has run:

    import dataset_utils as du
    tickets = du.load_jsonl(REPO_ROOT / "corpus/tickets/tickets_raw.jsonl")

THE PAIR FORMAT (one JSON object per line in train/val/heldout files):

    {"ticket_id": "INC-004412",
     "messages": [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": "Subject: ...\\n\\n<ticket body>"},
        {"role": "assistant", "content": "{...the seven-field record...}"}]}

Why role/content messages and not a hand-written template string:
every model family has its own chat template (special tokens around
each turn). The tokenizer applies the right one at training time, and
Ollama applies the same one at inference time. If we baked one
model's tokens into the data, the data would only fit that model.
"""

import json
import random
import re
from pathlib import Path

from jsonschema import Draft202012Validator

# ---------------------------------------------------------------------------
# The prompt. Training and inference MUST use the same text, so every
# lab imports it from here. Never retype it in a notebook.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an IT service desk triage assistant. Read the ticket and reply with ONE JSON object and nothing else: no explanation, no markdown fences.

The JSON object has exactly these seven keys, in this order:
- "category": one of "access", "hardware", "software", "network", "erp", "telecom", "other"
- "affected_system": the application or service the user names, or null if none is named
- "asset_tag": the IT asset tag of the affected device in the form LAP-04412, or null if none is given
- "urgency": one of "low", "medium", "high", "critical". Judge by the stated business effect, never by the tone
- "impact": one of "single_user", "team", "site", "enterprise"
- "requested_action": one short imperative clause, starting with a capital letter, with no full stop
- "routing_queue": one of "identity_access", "end_user_computing", "network_ops", "erp_support", "apps_support", "telecom_voice", "security_ops", "service_desk_l1"

If the ticket raises two problems, describe only the first one."""

# The seven record fields, in BUILD_SPEC.md section 8B order.
RECORD_FIELDS = [
    "category",
    "affected_system",
    "asset_tag",
    "urgency",
    "impact",
    "requested_action",
    "routing_queue",
]


# ---------------------------------------------------------------------------
# Reading and writing JSONL
# ---------------------------------------------------------------------------


def load_jsonl(path):
    """Read a .jsonl file into a list of dicts, one per line."""
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path, rows):
    """Write a list of dicts as .jsonl. Returns the path written.

    newline="\\n" keeps the file byte-identical on Windows and Linux,
    so a rebuilt dataset can be compared with the committed one.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def load_schema(path):
    """Read the frozen ticket schema (data/finetune/ticket_schema.json)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Raw tickets + labels -> examples
# ---------------------------------------------------------------------------


def join_tickets_and_labels(tickets, labels):
    """Join raw tickets to their ground-truth labels on ticket_id.

    Returns a list of "examples":
        {"ticket": {...raw ticket...}, "record": {...}, "meta": {...}}
    in the same order as `tickets`.
    """
    labels_by_id = {}
    for label in labels:
        labels_by_id[label["ticket_id"]] = label

    examples = []
    for ticket in tickets:
        label = labels_by_id[ticket["ticket_id"]]
        example = {
            "ticket": ticket,
            "record": label["record"],
            "meta": label["meta"],
        }
        examples.append(example)
    return examples


def format_ticket_text(ticket):
    """The text a model sees for one ticket: subject, blank line, body.

    Contract 1: anything that feeds a model a ticket feeds it
    subject + body. Subjects are sometimes empty in the corpus.
    """
    subject = ticket["subject"].strip()
    if subject == "":
        subject = "(none)"
    return f"Subject: {subject}\n\n{ticket['body']}"


def build_pair(ticket, record):
    """One raw ticket + its record -> one instruction-tuning pair.

    The completion is the record as compact JSON and NOTHING else.
    """
    user_text = format_ticket_text(ticket)
    completion_text = json.dumps(record, ensure_ascii=False)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": completion_text},
    ]
    return {"ticket_id": ticket["ticket_id"], "messages": messages}


def pair_user_text(pair):
    """The ticket text inside a pair (the user message)."""
    return pair["messages"][1]["content"]


def pair_completion_text(pair):
    """The raw completion string inside a pair (the assistant message)."""
    return pair["messages"][2]["content"]


def parse_completion(pair):
    """The completion parsed back into a dict. Raises if it is not JSON."""
    return json.loads(pair_completion_text(pair))


# ---------------------------------------------------------------------------
# Counting, for the "inspect" steps
# ---------------------------------------------------------------------------


def count_values(values):
    """Count how often each value appears. Returns {value: count},
    most common first."""
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))
    return dict(ordered)


def count_record_field(pairs, field):
    """Distribution of one record field across a list of pairs.

    A completion that is not valid JSON, or lacks the field, is
    counted under "<unreadable>" instead of crashing the count.
    """
    values = []
    for pair in pairs:
        try:
            value = parse_completion(pair).get(field, "<unreadable>")
        except json.JSONDecodeError:
            value = "<unreadable>"
        values.append(value)
    return count_values(values)


# ---------------------------------------------------------------------------
# The held-out 20
# ---------------------------------------------------------------------------

# How many held-out tickets come from each category. Roughly follows
# the corpus mix, but every category - including the rare ones, erp and
# telecom - gets at least two, so a per-category score is never 0-of-0.
HELDOUT_CATEGORY_QUOTA = {
    "access": 5,
    "software": 3,
    "hardware": 3,
    "network": 3,
    "other": 2,
    "telecom": 2,
    "erp": 2,
}


def is_critical_enterprise(example):
    record = example["record"]
    return record["urgency"] == "critical" and record["impact"] == "enterprise"


def is_critical_site(example):
    record = example["record"]
    return record["urgency"] == "critical" and record["impact"] == "site"


def has_loud_tone(example):
    """The user shouts URGENT but states no business effect. The label
    follows the effect, not the tone - so urgency here is arguable."""
    return "tone_urgent" in example["meta"]["features"]


def has_two_problems(example):
    """Two unrelated problems in one ticket. The record describes the
    first - which a reasonable person could dispute."""
    return "two_problems" in example["meta"]["features"]


# Picked FIRST, before the category quotas are filled: (how many, test).
HELDOUT_MUST_HAVES = [
    (1, is_critical_enterprise),
    (1, is_critical_site),
    (3, has_loud_tone),
    (3, has_two_problems),
]


# A held-out candidate must be less similar than this to EVERY other
# ticket in the corpus. Well below the near-duplicate threshold on
# purpose: the eval set should not even have cousins in train.
HELDOUT_MAX_SIMILARITY = 0.6


def select_heldout(examples, seed):
    """Choose the 20 held-out examples. Stratified, never random-only.

    Step 0 drops every ticket that has a lookalike anywhere in the
    corpus. Step 1 fills the must-haves (critical urgency, enterprise
    impact, arguable urgency). Step 2 tops every category up to its
    quota, preferring kinds of ticket not already chosen.
    Same examples + same seed -> same 20, every time.
    """
    # Step 0: only tickets with no lookalike may be held out.
    all_pairs = [build_pair(example["ticket"], example["record"]) for example in examples]
    lookalike_ids = find_lookalike_ids(all_pairs, HELDOUT_MAX_SIMILARITY)
    candidates = [e for e in examples if e["ticket"]["ticket_id"] not in lookalike_ids]

    rng = random.Random(seed)
    shuffled = list(candidates)
    rng.shuffle(shuffled)

    chosen = []
    chosen_ids = set()
    remaining_quota = dict(HELDOUT_CATEGORY_QUOTA)

    def take(example):
        chosen.append(example)
        chosen_ids.add(example["ticket"]["ticket_id"])
        remaining_quota[example["record"]["category"]] -= 1

    def is_available(example):
        not_taken = example["ticket"]["ticket_id"] not in chosen_ids
        has_room = remaining_quota[example["record"]["category"]] > 0
        return not_taken and has_room

    # Step 1: the must-haves.
    for how_many, test in HELDOUT_MUST_HAVES:
        found = 0
        for example in shuffled:
            if found == how_many:
                break
            if is_available(example) and test(example):
                take(example)
                found += 1
        if found < how_many:
            raise ValueError(f"Could not find {how_many} examples for {test.__name__}")

    # Step 2: fill what is left of each category's quota. First pass
    # takes only scenarios not chosen yet, so the 20 span as many
    # kinds of ticket as possible; second pass fills any gap left.
    chosen_scenarios = {example["meta"]["scenario"] for example in chosen}
    for example in shuffled:
        if is_available(example) and example["meta"]["scenario"] not in chosen_scenarios:
            take(example)
            chosen_scenarios.add(example["meta"]["scenario"])
    for example in shuffled:
        if is_available(example):
            take(example)

    # Return in corpus order (by ticket_id), so the file reads naturally.
    chosen.sort(key=lambda example: example["ticket"]["ticket_id"])
    return chosen


# ---------------------------------------------------------------------------
# Train / validation split
# ---------------------------------------------------------------------------


def proportional_quotas(counts, total):
    """Share `total` slots across groups in proportion to `counts`.

    Largest-remainder rounding, so the quotas add up to exactly
    `total`. Example: {"a": 70, "b": 30}, total=10 -> {"a": 7, "b": 3}.
    """
    grand_total = sum(counts.values())
    exact = {}
    for group, count in counts.items():
        exact[group] = total * count / grand_total

    quotas = {}
    for group, value in exact.items():
        quotas[group] = int(value)

    slots_left = total - sum(quotas.values())
    by_remainder = sorted(exact, key=lambda group: (-(exact[group] - quotas[group]), group))
    for group in by_remainder[:slots_left]:
        quotas[group] += 1
    return quotas


def split_train_val(examples, train_size, val_size, seed):
    """Stratified split by category. Returns (train, val, unused).

    Stratified means each split keeps the corpus's category mix - the
    REAL, imbalanced mix. We do not balance it: an even mix would
    flatter the tuned model and hide the rare-class problem.
    """
    rng = random.Random(seed)

    by_category = {}
    for example in examples:
        category = example["record"]["category"]
        by_category.setdefault(category, []).append(example)

    category_counts = {}
    for category, group in by_category.items():
        category_counts[category] = len(group)

    train_quota = proportional_quotas(category_counts, train_size)
    val_quota = proportional_quotas(category_counts, val_size)

    train, val, unused = [], [], []
    for category in sorted(by_category):
        group = by_category[category]
        rng.shuffle(group)
        n_train = train_quota[category]
        n_val = val_quota[category]
        train.extend(group[:n_train])
        val.extend(group[n_train:n_train + n_val])
        unused.extend(group[n_train + n_val:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val, unused


# ---------------------------------------------------------------------------
# Quality checks. The full checker (coverage gaps, class imbalance,
# CLI) is scripts/quality_checks.py; these three are its core.
# ---------------------------------------------------------------------------

# Two tickets at or above this similarity count as near-duplicates.
# Measured on the 600 raw tickets: no two DIFFERENT tickets reach 0.8
# (the closest natural pair is 0.78), so 0.8 flags resubmissions
# without flagging tickets that merely share a template.
NEAR_DUPLICATE_THRESHOLD = 0.8


def text_words(text):
    """The set of lowercase words in a text. Punctuation and case are
    ignored, so 'Cannot LOGIN!!' and 'cannot login' look the same."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def text_similarity(first_text, second_text):
    """Jaccard similarity of the two word sets: shared / total.
    1.0 = same words, 0.0 = nothing in common."""
    first_words = text_words(first_text)
    second_words = text_words(second_text)
    if not first_words or not second_words:
        return 0.0
    shared = first_words & second_words
    total = first_words | second_words
    return len(shared) / len(total)


def find_near_duplicates(pairs, threshold=NEAR_DUPLICATE_THRESHOLD):
    """Every two rows whose ticket text is suspiciously similar.

    Returns [{"first": id, "second": id, "similarity": 0.91,
              "first_row": 12, "second_row": 388}, ...],
    most similar first. first_row / second_row are positions in
    `pairs` (0-based), so a report can point at the exact rows.
    Compares all rows with all rows - fine for a few hundred rows,
    too slow for a few hundred thousand.
    """
    word_sets = [text_words(pair_user_text(pair)) for pair in pairs]
    found = []
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            shared = len(word_sets[i] & word_sets[j])
            total = len(word_sets[i] | word_sets[j])
            similarity = shared / total if total else 0.0
            if similarity >= threshold:
                found.append({
                    "first": pairs[i]["ticket_id"],
                    "second": pairs[j]["ticket_id"],
                    "similarity": round(similarity, 3),
                    "first_row": i,
                    "second_row": j,
                })
    found.sort(key=lambda item: -item["similarity"])
    return found


def find_lookalike_ids(pairs, threshold):
    """ticket_ids of every row that has at least one lookalike.

    The builder uses this with a LOW threshold to keep lookalikes out
    of the held-out 20: a held-out ticket with a twin in train would
    be a test question the model has half seen.
    """
    lookalike_ids = set()
    for item in find_near_duplicates(pairs, threshold):
        lookalike_ids.add(item["first"])
        lookalike_ids.add(item["second"])
    return lookalike_ids


def find_leakage(train_pairs, val_pairs):
    """ticket_ids that appear in BOTH train and validation.

    A leaked row makes the validation score lie: the model is graded
    on an answer it was shown during training.
    """
    train_ids = {pair["ticket_id"] for pair in train_pairs}
    val_ids = {pair["ticket_id"] for pair in val_pairs}
    return sorted(train_ids & val_ids)


def find_schema_violations(pairs, schema):
    """Rows whose completion is not a valid record.

    Returns [{"ticket_id": ..., "row": 17, "problems": ["...", ...],
              "errors": [{"field", "rule", "value", "message"}, ...]}, ...].

    "row" is the position in `pairs` (0-based). "problems" is the
    readable version; "errors" is the same thing in pieces, for code
    that wants to group violations by field or by rule
    (scripts/quality_checks.py does).
    """
    validator = Draft202012Validator(schema)
    found = []
    for row, pair in enumerate(pairs):
        try:
            record = parse_completion(pair)
        except json.JSONDecodeError as error:
            message = f"completion is not JSON: {error}"
            found.append({
                "ticket_id": pair["ticket_id"],
                "row": row,
                "problems": [message],
                "errors": [{"field": "(record)", "rule": "json", "value": None, "message": message}],
            })
            continue

        errors = []
        for error in validator.iter_errors(record):
            if error.path:
                field = error.path[0]
                value = error.instance
            elif error.validator == "required":
                # "'impact' is a required property" -> name the field.
                field = error.message.split("'")[1]
                value = None
            else:
                field = "(record)"
                value = None
            errors.append({
                "field": field,
                "rule": error.validator,
                "value": value,
                "message": error.message,
            })

        if errors:
            problems = sorted(f"{item['field']}: {item['message']}" for item in errors)
            found.append({"ticket_id": pair["ticket_id"], "row": row,
                          "problems": problems, "errors": errors})
    return found
