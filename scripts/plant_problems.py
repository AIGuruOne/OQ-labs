"""Plant the data-quality problems the Day 2 S10 lab is built to find.

FACILITATOR CODE. Participants never call this; they meet its effects
in data/finetune/train.jsonl and val.jsonl and find them with the
quality checks. Called by scripts/build_dataset.py, which writes the
answer key to data/finetune/planted_problems.json.

Three kinds of problem (BUILD_SPEC.md section 8B):

    near-duplicates     20 reworded resubmissions of tickets already in
                        train. New ticket_id, same underlying ticket,
                        same record. An id check cannot see them; a
                        text-similarity check can.
    leakage              5 train rows copied, unchanged, into val.
    schema violations   10 completions broken the way hand-edited
                        labels break: a value outside the enum, a
                        dropped field, prose inside a field, a
                        malformed asset tag. 7 in train, 3 in val.

No row carries two planted problems, so the answer key is unambiguous.
Everything is driven by the seeded `rng` passed in: same seed, same
plants.
"""

import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "notebooks"))

import dataset_utils as du  # noqa: E402

NEAR_DUPLICATE_COUNT = 20
LEAKAGE_COUNT = 5

# A planted near-duplicate must clear the detector's threshold with
# room to spare, and must not be an exact copy.
PLANT_MIN_SIMILARITY = du.NEAR_DUPLICATE_THRESHOLD + 0.03
PLANT_MAX_SIMILARITY = 0.97


# ---------------------------------------------------------------------
# 1. Near-duplicates: reword a ticket the way a user resubmits it
# ---------------------------------------------------------------------

# Meaning-preserving swaps. None of these words decides a label.
WORD_SWAPS = [
    ("please", "kindly"),
    ("kindly", "please"),
    ("pls", "please"),
    ("cannot", "am unable to"),
    ("issue", "problem"),
    ("problem", "issue"),
    ("help", "assist"),
    ("need", "require"),
    ("getting", "receiving"),
    ("showing", "displaying"),
    ("tried", "attempted"),
    ("but", "however"),
    ("colleague", "coworker"),
    ("again", "once more"),
    ("also", "additionally"),
]

NEW_GREETINGS = ["Hello team,", "Good day,", "Dear IT support,", "Hello,"]
NEW_CLOSINGS = ["Thanks in advance.", "Appreciate the support.", "Many thanks."]

GREETING_AT_START = re.compile(
    r"^(hi|hello|hey|dear|good morning|good afternoon|good day|greetings)\b[^,\n]*[,\n]\s*",
    re.IGNORECASE,
)

# Tickets that are awkward to reword believably: pasted traces,
# forwarded email trails, desk-agent phone notes.
SKIP_FEATURES = {"multiline_paste", "forwarded", "agent_note"}


def reword_body(body, rng):
    """Return (new_body, number_of_word_swaps)."""
    new_body = body

    # Swap up to three words that occur in the text.
    swaps_done = 0
    swaps = list(WORD_SWAPS)
    rng.shuffle(swaps)
    for old_word, new_word in swaps:
        if swaps_done == 3:
            break
        pattern = re.compile(rf"\b{re.escape(old_word)}\b", re.IGNORECASE)
        if pattern.search(new_body):
            new_body = pattern.sub(new_word, new_body)
            swaps_done += 1

    # Replace the greeting, or add one. Keep the line break if the
    # original greeting sat on its own line.
    greeting = rng.choice(NEW_GREETINGS)
    match = GREETING_AT_START.match(new_body)
    if match is None:
        new_body = f"{greeting} {new_body}"
    else:
        separator = "\n\n" if "\n" in match.group(0) else " "
        new_body = greeting + separator + new_body[match.end():]

    # Add a closing line, unless the ticket already ends with a
    # sign-off block (a closing after "Regards, Maryam" reads wrong).
    has_signoff_block = "\n" in new_body.rstrip()[-60:]
    if not has_signoff_block:
        closing = rng.choice(NEW_CLOSINGS)
        new_body = f"{new_body.rstrip()} {closing}"
    return new_body, swaps_done


def next_free_ticket_id(source_ticket_id, used_ids):
    """The first unused INC number after the source ticket's number."""
    number = int(source_ticket_id.split("-")[1]) + 1
    while f"INC-{number:06d}" in used_ids:
        number += 1
    return f"INC-{number:06d}"


def plant_near_duplicates(train_examples, used_ids, protected_ids, rng):
    """Build 20 reworded copies of train tickets.

    Returns (new_pairs, answer_key_entries). `used_ids` gains every new
    ticket_id; `protected_ids` gains every source, so no other plant
    touches the same row.
    """
    candidates = []
    for example in train_examples:
        word_count = example["meta"]["word_count"]
        features = set(example["meta"]["features"])
        if 25 <= word_count <= 120 and not (features & SKIP_FEATURES):
            candidates.append(example)
    rng.shuffle(candidates)

    new_pairs = []
    entries = []
    for example in candidates:
        if len(new_pairs) == NEAR_DUPLICATE_COUNT:
            break
        source_ticket = example["ticket"]
        new_body, swaps_done = reword_body(source_ticket["body"], rng)
        if swaps_done == 0:
            continue  # a new greeting alone is not a rewording

        new_ticket = dict(source_ticket)
        new_ticket["body"] = new_body
        new_ticket["subject"] = source_ticket["subject"].lower()

        similarity = du.text_similarity(
            du.format_ticket_text(source_ticket), du.format_ticket_text(new_ticket)
        )
        if not PLANT_MIN_SIMILARITY <= similarity <= PLANT_MAX_SIMILARITY:
            continue

        new_ticket["ticket_id"] = next_free_ticket_id(source_ticket["ticket_id"], used_ids)
        used_ids.add(new_ticket["ticket_id"])
        protected_ids.add(source_ticket["ticket_id"])
        protected_ids.add(new_ticket["ticket_id"])

        new_pairs.append(du.build_pair(new_ticket, example["record"]))
        entries.append({
            "split": "train",
            "ticket_id": new_ticket["ticket_id"],
            "duplicate_of": source_ticket["ticket_id"],
            "similarity": round(similarity, 3),
        })

    if len(new_pairs) < NEAR_DUPLICATE_COUNT:
        raise ValueError(f"Only {len(new_pairs)} near-duplicates could be planted")
    return new_pairs, entries


# ---------------------------------------------------------------------
# 2. Leakage: train rows copied into val
# ---------------------------------------------------------------------


def plant_leakage(train_pairs, protected_ids, rng):
    """Pick 5 untouched train rows to copy into val, unchanged."""
    candidates = [pair for pair in train_pairs if pair["ticket_id"] not in protected_ids]
    rng.shuffle(candidates)
    leaked = candidates[:LEAKAGE_COUNT]

    entries = []
    for pair in leaked:
        protected_ids.add(pair["ticket_id"])
        entries.append({"ticket_id": pair["ticket_id"], "in_splits": ["train", "val"]})
    return [copy.deepcopy(pair) for pair in leaked], entries


# ---------------------------------------------------------------------
# 3. Schema violations: break a completion the way hand edits do
# ---------------------------------------------------------------------


def break_asset_no_dash(record):
    record["asset_tag"] = record["asset_tag"].replace("-", "")


def break_asset_lowercase(record):
    record["asset_tag"] = record["asset_tag"].lower()


def break_asset_short(record):
    record["asset_tag"] = record["asset_tag"][:-1]


def break_urgency_word(record):
    record["urgency"] = "urgent"


def break_category_word(record):
    record["category"] = "password"


def break_impact_word(record):
    record["impact"] = "department"


def break_drop_impact(record):
    del record["impact"]


def break_action_prose(record):
    record["requested_action"] = (
        record["requested_action"]
        + ". The user has raised this before, so please check the earlier ticket as well."
    )


def break_action_note(record):
    record["requested_action"] = (
        "Not sure, maybe this one: " + record["requested_action"] + ". Someone please confirm."
    )


def break_urgency_prose(record):
    record["urgency"] = record["urgency"] + " - the user sounded quite stressed on the phone"


# (split, kind, field, needs an asset tag?, the edit)
VIOLATION_PLAN = [
    ("train", "invalid_enum_value", "urgency", False, break_urgency_word),
    ("train", "invalid_enum_value", "category", False, break_category_word),
    ("val", "invalid_enum_value", "impact", False, break_impact_word),
    ("train", "missing_field", "impact", False, break_drop_impact),
    ("train", "stray_prose", "requested_action", False, break_action_prose),
    ("train", "stray_prose", "urgency", False, break_urgency_prose),
    ("val", "stray_prose", "requested_action", False, break_action_note),
    ("train", "malformed_asset_tag", "asset_tag", True, break_asset_no_dash),
    ("train", "malformed_asset_tag", "asset_tag", True, break_asset_lowercase),
    ("val", "malformed_asset_tag", "asset_tag", True, break_asset_short),
]


def plant_schema_violations(train_pairs, val_pairs, protected_ids, rng):
    """Edit 10 completions in place. Returns the answer-key entries."""
    shuffled = {"train": list(train_pairs), "val": list(val_pairs)}
    rng.shuffle(shuffled["train"])
    rng.shuffle(shuffled["val"])

    entries = []
    for split, kind, field, needs_asset, edit in VIOLATION_PLAN:
        for pair in shuffled[split]:
            if pair["ticket_id"] in protected_ids:
                continue
            record = du.parse_completion(pair)
            if needs_asset and record["asset_tag"] is None:
                continue

            original_value = record.get(field)
            edit(record)
            pair["messages"][2]["content"] = json.dumps(record, ensure_ascii=False)
            protected_ids.add(pair["ticket_id"])
            entries.append({
                "split": split,
                "ticket_id": pair["ticket_id"],
                "kind": kind,
                "field": field,
                "original": original_value,
                "planted": record.get(field, "<field removed>"),
            })
            break
        else:
            raise ValueError(f"No untouched {split} row available for {kind}")
    return entries
