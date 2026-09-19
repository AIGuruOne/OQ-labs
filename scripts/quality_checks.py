"""Data-quality checks for a fine-tuning dataset. Run BEFORE any GPU time.

    python scripts/quality_checks.py --dataset data/finetune
    python scripts/quality_checks.py --dataset my_train.jsonl --val my_val.jsonl
    python scripts/quality_checks.py --dataset my_train.jsonl

--dataset is a folder holding train.jsonl + val.jsonl, or one pairs
file. With one file and no --val, the leakage check is skipped (it
needs two splits) and everything else still runs.

Five checks. The first three are hard failures, the last two warnings:

    1. near-duplicates     reworded copies inside one split        FAIL
    2. train/val leakage   the same ticket in train AND val        FAIL
    3. schema violations   completions that break the schema       FAIL
    4. coverage gaps       enum values absent or nearly absent     WARN
    5. class imbalance     REPORTED, never auto-corrected          WARN

Exit code: 0 = clean or warnings only, 1 = at least one hard failure,
2 = the input could not be read at all. That is what lets a pipeline
stop before training on a bad file.

No API calls, no GPU: 600 rows take about a second on a laptop CPU.

USE FROM A NOTEBOOK (one check at a time):

    import quality_checks as qc
    dataset = qc.load_dataset("data/finetune")
    result = qc.check_schema(dataset)
    qc.print_result(result)
    result["findings"]        # the same findings as a list of dicts

EVERY CHECK HAS THE SAME SHAPE: check(dataset, options) -> result.
No check calls another, and the report only reads the result dict. So
any one check can be deleted - or emptied into a TODO that raises
NotImplementedError - and the other four keep working.
"""

import argparse
import json
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

try:
    import dataset_utils as du  # noqa: E402
except ImportError as error:
    print(f"Cannot start: {error}")
    print("Install the pinned requirements first:  pip install -r requirements.txt")
    sys.exit(2)


DEFAULT_OPTIONS = {
    # Two tickets at or above this word similarity are near-duplicates.
    "threshold": du.NEAR_DUPLICATE_THRESHOLD,
    # An enum value with fewer rows than this in a file is "thin".
    "min_rows": 10,
    # Most common value / rarest value at or above this is "imbalanced".
    "max_ratio": 3.0,
}

# How many findings a section lists before it says "... N more".
LISTED_BY_DEFAULT = 5

# All-pairs comparison is fine for thousands of rows, not for millions.
MAX_ROWS_FOR_ALL_PAIRS = 5000


class DatasetError(Exception):
    """The input cannot be checked at all. main() prints the message
    and exits 2 - the user sees a sentence, never a stack trace."""


# ---------------------------------------------------------------------
# Loading. A row remembers its file and line, so every finding can
# point at the exact place:  train.jsonl:137
# ---------------------------------------------------------------------


def pair_format_problem(pair):
    """Why this parsed line is not a usable pair, or None if it is."""
    if not isinstance(pair, dict):
        return "line is not a JSON object"
    if not isinstance(pair.get("ticket_id"), str):
        return 'no "ticket_id" string'
    messages = pair.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return '"messages" is not a list of three (system, user, assistant)'
    for message, role in zip(messages, ["system", "user", "assistant"]):
        if not isinstance(message, dict) or message.get("role") != role:
            return f'"messages" does not have a {role} message in its usual place'
        if not isinstance(message.get("content"), str):
            return f'the {role} message has no text "content"'
    return None


def load_rows(path):
    """Read one pairs file. Returns (rows, file_problems).

    rows           [{"file": "train.jsonl", "line": 17, "pair": {...}}, ...]
    file_problems  lines that could not be used, with the reason

    One broken line does not stop the run: it is reported and the
    other lines are still checked. A file with NO usable line raises
    DatasetError.
    """
    path = Path(path)
    if not path.is_file():
        raise DatasetError(f"{path} does not exist (or is not a file).")

    try:
        # utf-8-sig also accepts the invisible BOM some Windows editors add.
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise DatasetError(f"{path} is not a UTF-8 text file. Is it really a .jsonl file?")

    rows = []
    file_problems = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            continue
        try:
            pair = json.loads(line)
            problem = pair_format_problem(pair)
        except json.JSONDecodeError as error:
            problem = f"not valid JSON ({error.msg}, column {error.colno}) - is the file truncated?"
        if problem is None:
            rows.append({"file": path.name, "line": line_number, "pair": pair})
        else:
            file_problems.append({"file": path.name, "line": line_number, "problem": problem})

    if rows == [] and file_problems == []:
        raise DatasetError(f"{path} is empty.")
    if rows == []:
        raise DatasetError(
            f"{path} has no usable rows: none of its {len(file_problems)} lines is a fine-tuning pair.\n"
            f"  Line {file_problems[0]['line']}: {file_problems[0]['problem']}.\n"
            '  Each line must look like {"ticket_id": "INC-004412", "messages": [system, user, assistant]}.\n'
            "  Raw tickets are not pairs yet: build pairs with scripts/build_dataset.py."
        )
    return rows, file_problems


def load_dataset(dataset_path, val_path=None, schema_path=None):
    """Load what the checks need into one dict:

        {"label", "train": rows, "val": rows or None, "schema", "file_problems"}

    dataset_path is a folder (train.jsonl + val.jsonl inside) or one
    pairs file. The single file, or train.jsonl, is always "train".
    """
    dataset_path = Path(dataset_path)
    if dataset_path.is_dir():
        train_path = dataset_path / "train.jsonl"
        if not train_path.is_file():
            raise DatasetError(f"{dataset_path} is a folder, but there is no train.jsonl in it.")
        if val_path is None and (dataset_path / "val.jsonl").is_file():
            val_path = dataset_path / "val.jsonl"
    elif dataset_path.exists():
        train_path = dataset_path
    else:
        raise DatasetError(f"{dataset_path} does not exist.")

    if schema_path is None:
        schema_path = train_path.parent / "ticket_schema.json"
        if not schema_path.is_file():
            schema_path = REPO_ROOT / "data" / "finetune" / "ticket_schema.json"
    try:
        schema = du.load_schema(schema_path)
    except (OSError, ValueError) as error:
        raise DatasetError(f"Cannot read the schema {schema_path}: {error}")

    train_rows, file_problems = load_rows(train_path)
    val_rows = None
    if val_path is not None:
        val_rows, val_file_problems = load_rows(val_path)
        file_problems = file_problems + val_file_problems

    return {
        "label": str(dataset_path),
        "train": train_rows,
        "val": val_rows,
        "schema": schema,
        "file_problems": file_problems,
    }


# ---------------------------------------------------------------------
# Small helpers shared by the checks
# ---------------------------------------------------------------------


def splits_of(dataset):
    """The loaded splits as a list: [train_rows] or [train_rows, val_rows]."""
    if dataset["val"] is None:
        return [dataset["train"]]
    return [dataset["train"], dataset["val"]]


def pairs_of(rows):
    return [row["pair"] for row in rows]


def where(row):
    """'train.jsonl:137' - file and line, the way an editor shows it."""
    return f"{row['file']}:{row['line']}"


def one_line(text, width=88):
    """Text squeezed onto one line and cut to `width` characters."""
    flat = " ".join(text.split())
    if len(flat) > width:
        flat = flat[:width - 3] + "..."
    return flat


def make_result(check, title, severity, headline, why, fix, findings, lines, example=None):
    """The one shape every check returns. status is PASS when nothing
    was found, otherwise the check's severity (FAIL or WARN).
    `headline` is the few words shown next to the status: "20 pairs"."""
    return {
        "check": check,
        "title": title,
        "status": severity if findings else "PASS",
        "headline": headline if findings else "",
        "why": why,
        "fix": fix,
        "findings": findings,   # list of dicts, for code
        "lines": lines,         # the same findings, for people
        "example": example or [],
    }


def make_unavailable(check, title, status, reason):
    """A check that did not run: SKIP (cannot run on this input) or
    TODO (not written yet). Never counts as a failure."""
    result = make_result(check, title, status, "", reason, "", [], [])
    result["status"] = status
    return result


def plural(count, word):
    """'1 row', '5 rows'."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


# ---------------------------------------------------------------------
# Check 1: near-duplicates (inside one split)
# ---------------------------------------------------------------------


def check_near_duplicates(dataset, options=DEFAULT_OPTIONS):
    """Reworded copies of a ticket inside the same split.

    An exact-match check cannot see these: the resubmitted ticket has
    a new greeting, a few words swapped and a NEW ticket_id. So we
    compare words, not ids (du.find_near_duplicates: shared words /
    all words, flagged at or above the threshold).
    """
    title = "NEAR-DUPLICATES"
    threshold = options["threshold"]

    findings = []
    for rows in splits_of(dataset):
        if len(rows) > MAX_ROWS_FOR_ALL_PAIRS:
            reason = (f"{rows[0]['file']} has {len(rows)} rows; comparing every row with every "
                      f"other is too slow above {MAX_ROWS_FOR_ALL_PAIRS}. Check a sample instead.")
            return make_unavailable("near_duplicates", title, "SKIP", reason)

        for item in du.find_near_duplicates(pairs_of(rows), threshold):
            first_row = rows[item["first_row"]]
            second_row = rows[item["second_row"]]
            findings.append({
                "file": first_row["file"],
                "first_line": first_row["line"],
                "second_line": second_row["line"],
                "first_id": item["first"],
                "second_id": item["second"],
                "similarity": item["similarity"],
                "rows": (first_row, second_row),
            })
    findings.sort(key=lambda finding: -finding["similarity"])

    lines = []
    for finding in findings:
        first_row, second_row = finding["rows"]
        lines.append(f"{finding['similarity']:.2f}   {where(first_row):<16} {finding['first_id']}"
                     f"   ~   {where(second_row):<16} {finding['second_id']}")

    example = []
    if findings:
        # Which pair to show? The top one often differs only by its
        # greeting, which is too easy. Of the pairs always listed above
        # (so the eye can find it), take the one whose wording differs
        # most: that is the pair an exact-match check has no hope with.
        def words_that_differ(finding):
            first_words = du.text_words(du.pair_user_text(finding["rows"][0]["pair"]))
            second_words = du.text_words(du.pair_user_text(finding["rows"][1]["pair"]))
            return len(first_words ^ second_words)

        always_listed = findings[:LISTED_BY_DEFAULT]
        hardest = max(always_listed, key=words_that_differ)

        first_row, second_row = hardest["rows"]
        first_text = du.pair_user_text(first_row["pair"])
        second_text = du.pair_user_text(second_row["pair"])
        only_first = sorted(du.text_words(first_text) - du.text_words(second_text))
        only_second = sorted(du.text_words(second_text) - du.text_words(first_text))
        example = [
            f"{where(first_row):<16} {one_line(first_text, 72)}",
            f"{where(second_row):<16} {one_line(second_text, 72)}",
            f"words only in the first : {', '.join(only_first) or '(none)'}",
            f"words only in the second: {', '.join(only_second) or '(none)'}",
        ]

    for finding in findings:
        del finding["rows"]  # findings stay plain data: strings and numbers

    return make_result(
        "near_duplicates", title, "FAIL", plural(len(findings), "pair"),
        why=f"Rows sharing {threshold:.0%}+ of their words are one ticket, resubmitted under a new "
            "ticket_id. The model over-weights whatever is repeated.",
        fix="Keep one row of each pair, drop the other.",
        findings=findings, lines=lines, example=example,
    )


# ---------------------------------------------------------------------
# Check 2: train/validation leakage
# ---------------------------------------------------------------------


def check_leakage(dataset, options=DEFAULT_OPTIONS):
    """The same ticket in train AND in validation.

    Two ways to leak: the same ticket_id in both files, or the same
    text under a different ticket_id (a reworded copy that crossed the
    split). Both make the validation score lie.
    """
    title = "TRAIN/VAL LEAKAGE"
    if dataset["val"] is None:
        return make_unavailable("leakage", title, "SKIP",
                                "Needs two splits: pass a folder, or add --val <file>.")

    train_rows = dataset["train"]
    val_rows = dataset["val"]
    findings = []

    # 2a. Same ticket_id in both files.
    leaked_ids = du.find_leakage(pairs_of(train_rows), pairs_of(val_rows))
    for ticket_id in leaked_ids:
        findings.append({
            "ticket_id": ticket_id,
            "how": "same ticket_id",
            "train_lines": [row["line"] for row in train_rows if row["pair"]["ticket_id"] == ticket_id],
            "val_lines": [row["line"] for row in val_rows if row["pair"]["ticket_id"] == ticket_id],
        })

    # 2b. Same text, different ticket_id.
    train_words = [du.text_words(du.pair_user_text(row["pair"])) for row in train_rows]
    for val_row in val_rows:
        val_words = du.text_words(du.pair_user_text(val_row["pair"]))
        for train_row, words in zip(train_rows, train_words):
            if train_row["pair"]["ticket_id"] == val_row["pair"]["ticket_id"]:
                continue  # already reported in 2a
            total = len(words | val_words)
            similarity = len(words & val_words) / total if total else 0.0
            if similarity >= options["threshold"]:
                findings.append({
                    "ticket_id": val_row["pair"]["ticket_id"],
                    "how": f"same text as {train_row['pair']['ticket_id']} ({similarity:.2f})",
                    "train_lines": [train_row["line"]],
                    "val_lines": [val_row["line"]],
                })

    train_file = train_rows[0]["file"]
    val_file = val_rows[0]["file"]
    lines = []
    for finding in findings:
        train_places = ",".join(str(line) for line in finding["train_lines"])
        val_places = ",".join(str(line) for line in finding["val_lines"])
        lines.append(f"{finding['ticket_id']}   {train_file}:{train_places:<6} and   "
                     f"{val_file}:{val_places:<6} {finding['how']}")

    return make_result(
        "leakage", title, "FAIL", plural(len(findings), "row"),
        why="The model is graded on an answer it has already been shown. The validation "
            "score goes up, and it is a lie.",
        fix="Drop these rows from VALIDATION. Training data is the scarcer resource.",
        findings=findings, lines=lines,
    )


# ---------------------------------------------------------------------
# Check 3: schema violations
# ---------------------------------------------------------------------


def violation_kind(error):
    """Name a schema error the way a person would describe it.

    `error` is one item of du.find_schema_violations(...)["errors"]:
    {"field", "rule", "value", "message"}. `rule` is the JSON Schema
    keyword that failed: enum, required, pattern, maxLength, type, ...
    """
    rule = error["rule"]
    field = error["field"]
    value = error["value"]

    if rule == "json":
        return "completion_not_json"
    if rule == "required":
        return "missing_field"
    if rule == "additionalProperties":
        return "unexpected_field"
    if rule in ("enum", "type") and value is None:
        return "null_not_allowed"
    if rule == "type" or (rule == "enum" and not isinstance(value, str)):
        return "wrong_type"
    if rule == "enum" and " " in value:
        return "stray_prose"            # "high - the user sounded stressed"
    if rule == "enum":
        return "invalid_enum_value"     # "urgent"
    if field == "asset_tag":
        return "malformed_asset_tag"    # "lap-09134", "LAP01682"
    if field == "requested_action" and rule in ("pattern", "maxLength"):
        return "stray_prose"            # a sentence or two after the clause
    if rule == "minLength":
        return "empty_value"
    return "other_schema_rule"


def check_schema(dataset, options=DEFAULT_OPTIONS):
    """Completions that are not a valid record.

    The fine-tune exists to produce strict JSON that matches the
    schema. A training row that breaks the schema teaches the model to
    break the schema.
    """
    findings = []
    for rows in splits_of(dataset):
        for violation in du.find_schema_violations(pairs_of(rows), dataset["schema"]):
            row = rows[violation["row"]]
            seen = set()
            for error in violation["errors"]:
                kind = violation_kind(error)
                if (kind, error["field"]) in seen:
                    continue  # one long prose value breaks two rules; report it once
                seen.add((kind, error["field"]))
                findings.append({
                    "file": row["file"],
                    "line": row["line"],
                    "ticket_id": violation["ticket_id"],
                    "kind": kind,
                    "field": error["field"],
                    "value": error["value"],
                    "message": error["message"],
                })
    findings.sort(key=lambda finding: (finding["kind"], finding["file"], finding["line"]))

    # One report line per KIND: how many, where, and one real value.
    lines = []
    kinds = sorted({finding["kind"] for finding in findings})
    for kind in kinds:
        of_this_kind = [finding for finding in findings if finding["kind"] == kind]
        places = ", ".join(where(finding) for finding in of_this_kind)
        sample = of_this_kind[0]
        if kind in ("missing_field", "unexpected_field", "completion_not_json"):
            shown = one_line(sample["message"], 50)
        else:
            shown = f"{sample['field']} = {one_line(json.dumps(sample['value']), 38)}"
        lines.append(f"{kind:<20} {len(of_this_kind):>2}   {shown}")
        lines.append(f"{'':<20}      at {places}")

    bad_rows = {where(finding) for finding in findings}
    result = make_result(
        "schema", "SCHEMA VIOLATIONS", "FAIL", plural(len(bad_rows), "row"),
        why="A completion that breaks the schema teaches the model to break the schema.",
        fix="Drop the row, or fix the label from the source. Never repair a label by guesswork.",
        findings=findings, lines=lines,
    )
    result["lines_per_finding"] = 2  # each kind prints two lines; see print_result
    return result


# ---------------------------------------------------------------------
# Check 4: coverage gaps
# ---------------------------------------------------------------------


def valid_values(rows, field):
    """The field's value in every row whose completion can be read.
    Unreadable completions are check 3's business, not ours."""
    values = []
    for row in rows:
        try:
            record = du.parse_completion(row["pair"])
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and field in record:
            values.append(record[field])
    return values


def check_coverage(dataset, options=DEFAULT_OPTIONS):
    """Values the model will hardly ever see - or that validation will
    hardly ever test.

    For every enum field in the schema: which allowed values are
    absent, or have fewer than `min_rows` rows? For every field that
    may be null: are there enough nulls AND enough real values to
    learn both?
    """
    min_rows = options["min_rows"]
    properties = dataset["schema"]["properties"]

    findings = []
    for rows in splits_of(dataset):
        file_name = rows[0]["file"]
        for field, spec in properties.items():
            values = valid_values(rows, field)

            if "enum" in spec:
                counts = {}
                for allowed in spec["enum"]:
                    counts[allowed] = values.count(allowed)
            elif "null" in spec.get("type", []):
                null_count = sum(1 for value in values if value is None)
                counts = {"null": null_count, "not null": len(values) - null_count}
            else:
                continue

            for value, count in counts.items():
                if count < min_rows:
                    findings.append({
                        "file": file_name,
                        "field": field,
                        "value": value,
                        "rows": count,
                        "kind": "absent" if count == 0 else "thin",
                    })

    # One report line per file + field, rarest value first.
    lines = []
    seen = []
    for finding in findings:
        key = (finding["file"], finding["field"])
        if key not in seen:
            seen.append(key)
    file_width = max([len(file_name) for file_name, field in seen], default=0)
    for file_name, field in seen:
        group = [f for f in findings if f["file"] == file_name and f["field"] == field]
        group.sort(key=lambda finding: finding["rows"])
        parts = []
        for finding in group:
            label = "ABSENT" if finding["rows"] == 0 else f"{finding['rows']} rows"
            parts.append(f"{finding['value']} ({label})")
        lines.append(f"{file_name:<{file_width}}  {field:<16} {', '.join(parts)}")

    result = make_result(
        "coverage", "COVERAGE GAPS", "WARN", f"{plural(len(findings), 'value')} under {min_rows} rows",
        why=f"Under {min_rows} rows of a value: in train the model barely sees it; in validation "
            "its score rests on a handful of tickets.",
        fix="Your call: label more of the rare cases, or accept the gap and say so in the "
            "eval report. Never invent rows.",
        findings=findings, lines=lines,
    )
    result["always_list_all"] = True  # the lines are already one per field
    return result


# ---------------------------------------------------------------------
# Check 5: class imbalance - REPORTED, NEVER CORRECTED
# ---------------------------------------------------------------------


def check_imbalance(dataset, options=DEFAULT_OPTIONS):
    """How lopsided each enum field is.

    This check only ever reports. The imbalance is real: password and
    access tickets dominate a service desk, ERP and telecom are rare.
    Rebalancing would flatter the tuned model and hide the rare-class
    problem, so there is deliberately NO fix function in this file.
    What to do about it is a decision for the people in the room.
    """
    max_ratio = options["max_ratio"]
    properties = dataset["schema"]["properties"]
    enum_fields = [field for field, spec in properties.items() if "enum" in spec]

    findings = []
    for rows in splits_of(dataset):
        for field in enum_fields:
            allowed = properties[field]["enum"]
            values = [value for value in valid_values(rows, field)
                      if isinstance(value, str) and value in allowed]
            counts = du.count_values(values)      # most common first
            if len(counts) < 2:
                continue
            most_common, rarest = list(counts)[0], list(counts)[-1]
            ratio = counts[most_common] / counts[rarest]
            if ratio >= max_ratio:
                findings.append({
                    "file": rows[0]["file"],
                    "field": field,
                    "ratio": round(ratio, 1),
                    "most_common": most_common,
                    "rarest": rarest,
                    "counts": counts,
                    "total": len(values),
                })

    # Bars for the training split - that is what the model learns
    # from. Any other split gets one line.
    train_file = dataset["train"][0]["file"]
    lines = []
    other_splits = {}
    for finding in findings:
        if finding["file"] != train_file:
            other_splits.setdefault(finding["file"], []).append(f"{finding['field']} {finding['ratio']}x")
            continue
        lines.append(f"{finding['file']}  {finding['field']}: "
                     f"{finding['most_common']} is {finding['ratio']}x {finding['rarest']}")
        biggest = max(finding["counts"].values())
        for value, count in finding["counts"].items():
            share = 100 * count / finding["total"]
            bar = "#" * max(1, round(30 * count / biggest))
            lines.append(f"    {value:<12} {count:>4} {share:5.1f}%  {bar}")
    for file_name, ratios in other_splits.items():
        lines.append(f"{file_name}  {', '.join(ratios)}")

    train_ratios = [f"{f['field']} {f['ratio']}x" for f in findings if f["file"] == train_file]
    result = make_result(
        "imbalance", "CLASS IMBALANCE", "WARN", ", ".join(train_ratios) or plural(len(findings), "field"),
        why="REPORTED, NEVER AUTO-CORRECTED. This is the mix a real service desk sees. A model "
            "can score well on average while failing every rare class.",
        fix="Your call, and no option is free: keep the mix and report PER-CLASS scores, "
            "collect more rare tickets, or re-weight. Decide, and write down why.",
        findings=findings, lines=lines,
    )
    result["always_list_all"] = True
    return result


# ---------------------------------------------------------------------
# Running the checks. To leave one as a TODO: make its body
# `raise NotImplementedError`, or remove it from this list.
# ---------------------------------------------------------------------

CHECKS = [
    check_near_duplicates,
    check_leakage,
    check_schema,
    check_coverage,
    check_imbalance,
]


def run_checks(dataset, options=DEFAULT_OPTIONS, checks=None):
    """Run every check in `checks` (default: all five). Returns the results."""
    if checks is None:
        checks = CHECKS
    results = []
    for check in checks:
        try:
            result = check(dataset, options)
        except NotImplementedError:
            name = check.__name__.replace("check_", "")
            result = make_unavailable(name, name.upper().replace("_", " "), "TODO",
                                      f"{check.__name__} is not written yet.")
        results.append(result)
    return results


def has_hard_failures(dataset, results):
    """True if a pipeline should stop: a FAIL, or lines that could not be read."""
    any_fail = any(result["status"] == "FAIL" for result in results)
    return any_fail or dataset["file_problems"] != []


# ---------------------------------------------------------------------
# The report. It only reads result dicts - it knows nothing about any
# individual check.
# ---------------------------------------------------------------------


def print_result(result, number=None, show_all=False):
    """Print one check's section of the report."""
    prefix = f"[{number}] " if number is not None else ""
    print(f"{prefix}{result['title']:<22} {result['status']:<5} {result['headline']}".rstrip())

    if result["status"] == "PASS":
        return
    print_wrapped("Why : ", result["why"])
    if result["status"] in ("SKIP", "TODO"):
        return

    lines = result["lines"]
    if show_all or result.get("always_list_all"):
        listed = lines
    else:
        listed = lines[:LISTED_BY_DEFAULT * result.get("lines_per_finding", 1)]
    for line in listed:
        print(f"      {line}")
    if len(listed) < len(lines):
        hidden = (len(lines) - len(listed)) // result.get("lines_per_finding", 1)
        print(f"      ... {hidden} more - add --all to list every one")

    if result["example"]:
        print("    Look at one:")
        for line in result["example"]:
            print(f"      {line}")
    print_wrapped("Fix : ", result["fix"])


def print_wrapped(label, text):
    """Print a sentence or two, wrapped so it fits a laptop terminal."""
    print(textwrap.fill(text, width=90, initial_indent="    " + label,
                        subsequent_indent=" " * (4 + len(label))))


def print_report(dataset, results, show_all=False):
    """The whole report: a summary you can read in ten seconds, then
    one section per check."""
    sizes = ", ".join(f"{rows[0]['file']} {len(rows)} rows" for rows in splits_of(dataset))
    print(f"QUALITY REPORT  {dataset['label']}")
    print(f"                {sizes}")
    print("=" * 78)
    for number, result in enumerate(results, start=1):
        print(f"  {result['status']:<5} {number}. {result['title']:<22} {result['headline']}".rstrip())
    if dataset["file_problems"]:
        print(f"  FAIL  -  {'UNREADABLE LINES':<22} {plural(len(dataset['file_problems']), 'line')}")
    print("=" * 78)

    if dataset["file_problems"]:
        print()
        print(f"UNREADABLE LINES           FAIL  {plural(len(dataset['file_problems']), 'line')}"
              "  (skipped; every other line was still checked)")
        for problem in dataset["file_problems"][:LISTED_BY_DEFAULT]:
            print(f"      {problem['file']}:{problem['line']}  {problem['problem']}")
        if len(dataset["file_problems"]) > LISTED_BY_DEFAULT:
            print(f"      ... {len(dataset['file_problems']) - LISTED_BY_DEFAULT} more")

    for number, result in enumerate(results, start=1):
        if result["status"] == "PASS":
            continue
        print()
        print_result(result, number, show_all)

    print()
    if has_hard_failures(dataset, results):
        print("RESULT: FAIL - fix the hard failures before training. Warnings are decisions, not bugs.")
    else:
        print("RESULT: OK - no hard failures. Warnings are decisions, not bugs: read them once.")


# ---------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Data-quality checks for a fine-tuning pairs dataset.",
        epilog="Exit code: 0 clean or warnings only, 1 hard failures, 2 input unreadable.",
    )
    parser.add_argument("--dataset", type=Path, required=True,
                        help="a folder with train.jsonl + val.jsonl, or one pairs .jsonl file")
    parser.add_argument("--val", type=Path, default=None,
                        help="validation file, when --dataset is a single file")
    parser.add_argument("--schema", type=Path, default=None,
                        help="record schema (default: ticket_schema.json next to the data, "
                             "else data/finetune/ticket_schema.json)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_OPTIONS["threshold"],
                        help="near-duplicate word similarity, 0-1 (default %(default)s)")
    parser.add_argument("--min-rows", type=int, default=DEFAULT_OPTIONS["min_rows"],
                        help="fewer rows than this of an enum value is a coverage gap (default %(default)s)")
    parser.add_argument("--max-ratio", type=float, default=DEFAULT_OPTIONS["max_ratio"],
                        help="most common / rarest at or above this is imbalance (default %(default)s)")
    parser.add_argument("--all", action="store_true", help="list every finding, not just the first five")
    args = parser.parse_args()

    # A ticket can hold a character this console cannot print. Show it
    # as an escape code instead of crashing the report half way.
    sys.stdout.reconfigure(errors="backslashreplace")

    options = {"threshold": args.threshold, "min_rows": args.min_rows, "max_ratio": args.max_ratio}
    try:
        dataset = load_dataset(args.dataset, args.val, args.schema)
    except DatasetError as error:
        print(f"CANNOT CHECK THIS DATASET\n  {error}")
        sys.exit(2)

    results = run_checks(dataset, options)
    print_report(dataset, results, show_all=args.all)
    sys.exit(1 if has_hard_failures(dataset, results) else 0)


if __name__ == "__main__":
    main()
