"""Score a model on the ticket task. One command, one table.

    python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local
    python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint hosted
    python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint tuned --label tuned

    python scripts/run_eval.py --compare eval_runs/A_summary.json eval_runs/B_summary.json

--endpoint is a name from config/endpoints.py: local (Ollama), hosted
(API) or tuned (your adapter in Ollama). Switching model is switching
that one word - the harness has no model-specific code at all.

WHAT A RUN WRITES (into --out, default eval_runs/). This is interface
contract #4, docs/contracts.md:

    <run_id>_summary.json   every number in the report, one object
    <run_id>_rows.jsonl     one line per (ticket, field): expected, predicted, correct
    <run_id>_replies.jsonl  the raw model replies, saved as each one arrives
    <run_id>_report.txt     the table you see on screen

--compare merges two or more summary files into one table. It refuses
runs that did not answer the same questions.

Other switches:
    --label NAME     column name in a comparison (default: the endpoint name)
    --json-mode      ask the server to force JSON output. OFF by default, so
                     the score shows what the model does on its own
    --resume         reuse replies already saved for this run_id (after a
                     disconnect). Without it the model is always called again
    --replies FILE   score a saved replies file; no model is called
    --limit N        first N tickets only (a smoke test, not a result)
    --all            list every wrong field, not just the summary

Exit code: 0 = the run completed (whatever the scores), 2 = it could
not run. The scoring rules are in scripts/eval_scoring.py; the rubric
for humans is data/eval/rubric.md.

FROM A NOTEBOOK - including a run that adds retrieval in front of the model:

    import run_eval
    def ask(messages):                      # messages = [system, user]
        return llm.chat(messages=messages, temperature=0.0)
    summary = run_eval.run_evaluation(dataset_path, ask, endpoint_name="local",
                                      model=llm.model, label="base+retrieval",
                                      out_dir=CHECKPOINT_DIR / "eval")
"""

import argparse
import datetime
import hashlib
import json
import sys
import textwrap
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    from jsonschema import Draft202012Validator  # noqa: E402

    import dataset_utils as du  # noqa: E402
    import eval_scoring as es  # noqa: E402
    from quality_checks import pair_format_problem  # noqa: E402
except ImportError as error:
    print(f"Cannot start: {error}")
    print("Install the pinned requirements first:  pip install -r requirements.txt")
    sys.exit(2)

SUMMARY_CONTRACT = "eval-summary/1"
COMPARISON_CONTRACT = "eval-comparison/1"

DEFAULT_OUT_DIR = "eval_runs"
DEFAULT_SCHEMA = REPO_ROOT / "data" / "finetune" / "ticket_schema.json"

# Sent with every request. Temperature 0 so two runs are comparable;
# 512 tokens is about five times the length of a correct record.
TEMPERATURE = 0.0
MAX_TOKENS = 512

# Stop the run after this many endpoint errors in a row.
MAX_ERRORS_IN_A_ROW = 3

REPORT_WIDTH = 100
MAX_COMPARED_RUNS = 4


class EvalError(Exception):
    """The run cannot continue. main() prints the message and exits 2 -
    the user sees a sentence, never a stack trace."""


# ---------------------------------------------------------------------
# Loading the questions
# ---------------------------------------------------------------------


def load_eval_rows(dataset_path, validator, limit=None):
    """Read a pairs file (Contract 1). Returns (rows, skipped).

    rows     [{"item_id", "messages" (system + user only), "ticket_text",
               "expected" (the seven-field dict)}, ...]
    skipped  lines that cannot be used as a question, with the reason.

    A line is skipped - never scored - when its EXPECTED answer is
    broken: a model cannot be marked against a wrong answer key.
    val.jsonl has such lines on purpose (the Day 2 planted problems).
    """
    path = Path(dataset_path)
    if not path.is_file():
        raise EvalError(f"{path} does not exist (or is not a file).")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise EvalError(f"{path} is not a UTF-8 text file. Is it really a .jsonl file?")

    rows = []
    skipped = []
    seen_ids = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            continue
        item_id = None
        try:
            pair = json.loads(line)
            reason = pair_format_problem(pair)
        except json.JSONDecodeError:
            reason = "line is not valid JSON"

        if reason is None:
            item_id = pair["ticket_id"]
            try:
                expected = du.parse_completion(pair)
                errors = du.record_schema_errors(expected, validator)
            except json.JSONDecodeError:
                errors = None
            if errors is None:
                reason = "expected answer is not JSON"
            elif errors:
                reason = "expected answer breaks the schema (" + errors[0]["field"] + ")"
            elif item_id in seen_ids:
                reason = "ticket_id already used by an earlier line"

        if reason is not None:
            skipped.append({"line": line_number, "item_id": item_id, "reason": reason})
            continue

        seen_ids.add(item_id)
        rows.append({
            "item_id": item_id,
            "messages": pair["messages"][:2],
            "ticket_text": du.pair_user_text(pair),
            "expected": expected,
        })

    if rows == []:
        raise EvalError(f"{path} has no usable questions. Expected the fine-tuning pair format: "
                        '{"ticket_id": ..., "messages": [system, user, assistant]} per line.')
    if limit is not None:
        rows = rows[:limit]
    return rows, skipped


def questions_fingerprint(rows):
    """A short hash of the questions AND expected answers actually used.
    Two runs with the same fingerprint answered the same exam."""
    material = [[row["item_id"], row["messages"], row["expected"]] for row in rows]
    encoded = json.dumps(material, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def messages_fingerprint(messages):
    encoded = json.dumps(messages, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


# ---------------------------------------------------------------------
# Asking the model. Every reply is saved the moment it arrives.
# ---------------------------------------------------------------------


def load_saved_replies(replies_path):
    """Replies from an earlier, interrupted run: {item_id: reply_row}."""
    saved = {}
    path = Path(replies_path)
    if not path.is_file():
        return saved
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            reply_row = json.loads(line)
            saved[reply_row["item_id"]] = reply_row
        except (json.JSONDecodeError, KeyError, TypeError):
            continue    # a half-written last line after a crash
    return saved


def ask_with_one_retry(ask, messages):
    """Returns (reply_text, error_text, seconds). Exactly one is None."""
    error_text = None
    for attempt in range(2):
        started = time.time()
        try:
            reply_text = ask(messages)
            return reply_text, None, round(time.time() - started, 2)
        except Exception as error:      # noqa: BLE001 - any failure is "no reply"
            error_text = f"{type(error).__name__}: {error}"
    return None, error_text, round(time.time() - started, 2)


def collect_replies(rows, ask, model, replies_path, saved=None, show_progress=True):
    """Ask the model every question. Returns one reply_row per question:

        {"item_id", "model", "messages_sha", "reply", "error", "seconds"}

    `ask(messages) -> str` is the only thing that knows about a model.
    A saved reply is reused only if it is for the same question text
    and the same model name. With saved replies the file is appended
    to, never rewritten, so a second disconnect loses nothing; if a
    ticket ends up with two lines, the later one wins when loading.
    """
    saved = saved or {}
    replies_path = Path(replies_path)
    replies_path.parent.mkdir(parents=True, exist_ok=True)

    reply_rows = []
    errors_in_a_row = 0
    any_success = False
    with open(replies_path, "w", encoding="utf-8", newline="\n") as handle:
        for number, row in enumerate(rows, start=1):
            sha = messages_fingerprint(row["messages"])
            old = saved.get(row["item_id"])
            reusable = (old is not None and old.get("error") is None
                        and old.get("model") == model and old.get("messages_sha") == sha)
            if reusable:
                reply_row = old
                note = "saved reply reused"
            else:
                reply_text, error_text, seconds = ask_with_one_retry(ask, row["messages"])
                reply_row = {"item_id": row["item_id"], "model": model, "messages_sha": sha,
                             "reply": reply_text, "error": error_text, "seconds": seconds}
                note = "NO REPLY - " + one_line(error_text, 50) if error_text else ""

            handle.write(json.dumps(reply_row, ensure_ascii=False) + "\n")
            handle.flush()
            reply_rows.append(reply_row)
            if show_progress:
                print(f"  [{number:>3}/{len(rows)}] {row['item_id']}  {reply_row['seconds']:>6.1f} s  {note}")

            if reply_row["error"] is None:
                any_success = True
                errors_in_a_row = 0
                continue
            errors_in_a_row += 1
            if not any_success or errors_in_a_row >= MAX_ERRORS_IN_A_ROW:
                raise EvalError(
                    "The endpoint is not answering, so the run was stopped.\n"
                    f"  Last error: {reply_row['error']}\n"
                    f"  Replies so far are in {replies_path}. Fix the endpoint, then run the "
                    "same command with --resume."
                )
    return reply_rows


def load_replies_file(replies_path, rows):
    """--replies: score a saved file instead of calling a model. A
    question with no line in the file counts as 'no reply'."""
    path = Path(replies_path)
    if not path.is_file():
        raise EvalError(f"{path} does not exist (or is not a file).")
    saved = load_saved_replies(path)
    if saved == {}:
        raise EvalError(f'{path} has no usable lines. Expected {{"item_id": ..., "reply": ...}} per line.')
    reply_rows = []
    for row in rows:
        reply_row = saved.get(row["item_id"])
        if reply_row is None:
            reply_row = {"item_id": row["item_id"], "reply": None, "seconds": None,
                         "error": "no line for this ticket in the replies file"}
        reply_rows.append(reply_row)
    return reply_rows


# ---------------------------------------------------------------------
# Scoring and the two contract files
# ---------------------------------------------------------------------


def score_replies(rows, reply_rows, validator):
    """[{"item_id", "expected", "item": es.score_item(...), "seconds"}, ...]"""
    scored = []
    for row, reply_row in zip(rows, reply_rows):
        item = es.score_item(row["expected"], reply_row.get("reply"), row["ticket_text"],
                             validator, reply_error=reply_row.get("error"))
        scored.append({"item_id": row["item_id"], "expected": row["expected"],
                       "item": item, "seconds": reply_row.get("seconds")})
    return scored


def build_field_rows(scored, run_info):
    """<run_id>_rows.jsonl: one line per (ticket, field), plus one
    "(schema)" line per ticket, so format is a column like any other."""
    field_rows = []
    for entry in scored:
        item = entry["item"]
        base = {"run_id": run_info["run_id"], "label": run_info["label"],
                "endpoint": run_info["endpoint"], "model": run_info["model"],
                "item_id": entry["item_id"]}
        if item["schema_valid"]:
            predicted_schema = "valid"
        else:
            predicted_schema = "; ".join(item["schema_problems"]) or f"parse {item['parse']}"
        field_rows.append({**base, "field": "(schema)", "expected": "valid",
                           "predicted": predicted_schema, "score": 1.0 if item["schema_valid"] else 0.0,
                           "correct": item["schema_valid"], "score_type": "schema"})
        for field in du.RECORD_FIELDS:
            result = item["fields"][field]
            field_rows.append({**base, "field": field, "expected": result["expected"],
                               "predicted": result["predicted"], "score": result["score"],
                               "correct": result["correct"], "score_type": result["score_type"]})
    return field_rows


def build_summary(scored, run_info, skipped):
    summary = {"contract": SUMMARY_CONTRACT}
    summary.update(run_info)
    summary["item_ids"] = [entry["item_id"] for entry in scored]
    summary["skipped_dataset_lines"] = skipped
    summary.update(es.summarise(scored))
    return summary


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_outputs(out_dir, summary, field_rows, report_text):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = summary["run_id"]
    paths = {
        "summary": out_dir / f"{run_id}_summary.json",
        "rows": out_dir / f"{run_id}_rows.jsonl",
        "report": out_dir / f"{run_id}_report.txt",
    }
    write_json(paths["summary"], summary)
    du.write_jsonl(paths["rows"], field_rows)
    paths["report"].write_text(report_text + "\n", encoding="utf-8", newline="\n")
    return paths


# ---------------------------------------------------------------------
# The rendered report. ASCII only, 100 columns: it has to survive a
# Windows console and a projector.
# ---------------------------------------------------------------------


# Typographic characters that have a plain twin.
PLAIN_TWINS = str.maketrans({"\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
                             "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00a0": " "})


def ascii_safe(value):
    """Model output and error messages can contain anything. Print
    them without crashing (or garbling) a cp1252 console: dashes and
    curly quotes become plain ones, anything else non-ASCII becomes a
    \\u escape."""
    plain = str(value).translate(PLAIN_TWINS)
    return plain.encode("ascii", "backslashreplace").decode("ascii")


def one_line(text, width):
    flat = " ".join(ascii_safe(text).split())
    if len(flat) <= width:
        return flat
    return flat[: width - 3] + "..."


def shown(value):
    """A value as it appears in JSON: null, "high", 3."""
    return ascii_safe(json.dumps(value, ensure_ascii=True))


def percent(value):
    return f"{round(value * 100):>3}%"


def count_of(value, total):
    return f"{round(value * total):>3} / {total}"


def wrapped(text, indent):
    return textwrap.fill(ascii_safe(text), width=REPORT_WIDTH,
                         initial_indent=indent, subsequent_indent=indent + "  ")


def render_report(summary, scored, show_all=False):
    n = summary["n_items"]
    parse = summary["parse"]
    lines = []
    add = lines.append
    rule = "=" * REPORT_WIDTH

    add(rule)
    add(f"EVAL  {summary['run_id']}")
    add(f"  label     {summary['label']}")
    add(f"  endpoint  {one_line(summary['endpoint'], 20)}  ->  {one_line(summary['model'], 60)}")
    add(f"  dataset   {one_line(summary['dataset'], 50)}   {n} tickets   "
        f"questions {summary['dataset_sha256']}")
    settings = summary["settings"]
    add(f"  settings  temperature {settings['temperature']}, max_tokens {settings['max_tokens']}, "
        f"json_mode {'on' if settings['json_mode'] else 'off'}")
    if summary["seconds_per_item_median"] is not None:
        add(f"  time      {summary['seconds_total']} s in model calls, "
            f"median {summary['seconds_per_item_median']} s per ticket")
    add(rule)
    if summary["skipped_dataset_lines"]:
        add(f"  NOTE: {len(summary['skipped_dataset_lines'])} dataset lines were skipped because "
            "their EXPECTED answer is broken")
        first = summary["skipped_dataset_lines"][0]
        add(f"        (first: line {first['line']}, {one_line(first['reason'], 70)}).")
        add("        Run scripts/quality_checks.py on the file to see them all.")
    if n < 20:
        add("  NOTE: fewer than 20 tickets - this is a smoke test, not a result.")
    if not summary["system_prompt_matches"]:
        add("  NOTE: the system prompt inside this dataset is NOT dataset_utils.SYSTEM_PROMPT.")
        add("        The model is being tested on a different prompt than it is trained on. Rebuild")
        add("        the dataset:  python scripts/build_dataset.py --seed 42")

    add("")
    add("1. FORMAT - did a usable record arrive?        (says nothing about the content being right)")
    add(f"     schema-valid            {count_of(summary['schema_valid_rate'], n)}  "
        f"{percent(summary['schema_valid_rate'])}   json.loads(reply) works AND passes ticket_schema.json")
    add(f"     clean JSON              {parse['clean']:>3} / {n}")
    add(f"     JSON only after repair  {parse['recovered']:>3} / {n}         fence or prose stripped: "
        "content scored, format failed")
    add(f"     no JSON at all          {parse['failed']:>3} / {n}         wrong on every field below")
    add(f"     endpoint gave no reply  {parse['no_reply']:>3} / {n}         wrong on every field below")
    problem_counts = {}
    for entry in scored:
        if entry["item"]["predicted_record"] is not None:
            for problem in entry["item"]["schema_problems"]:
                problem_counts[problem] = problem_counts.get(problem, 0) + 1
    for problem, count in sorted(problem_counts.items(), key=lambda pair: (-pair[1], pair[0])):
        add(f"       schema problem x{count}: {ascii_safe(problem)}")

    add("")
    add(f"2. FIELDS - is each field right?               ('readable' = the "
        f"{summary['n_parsed']} replies with a record in them)")
    add("     field               right     of all     of readable")
    for field in es.EXACT_FIELDS:
        accuracy = summary["per_field_accuracy"][field]
        readable = summary["per_field_accuracy_when_parsed"][field]
        add(f"     {field:<17} {count_of(accuracy, n)}     {percent(accuracy)}        {percent(readable)}")
    action = summary["requested_action"]
    accuracy = summary["per_field_accuracy"][es.SIMILARITY_FIELD]
    readable = summary["per_field_accuracy_when_parsed"][es.SIMILARITY_FIELD]
    add(f"     {es.SIMILARITY_FIELD:<17} {count_of(accuracy, n)}     {percent(accuracy)}        "
        f"{percent(readable)}     NOT exact match - see below")
    add(f"       a match = similarity >= {action['match_threshold']:.2f}; "
        f"mean similarity {action['mean_similarity']:.2f}")
    add(wrapped("measure: " + action["measure"], "       "))

    add("")
    add("3. WHOLE RECORD - all six exact-match fields right at once   (requested_action not included)")
    add(f"     {count_of(summary['overall_exact_match'], n)}   {percent(summary['overall_exact_match'])}")

    add("")
    add("4. INVENTED - values that exist nowhere        (a separate count, never part of accuracy)")
    invented = summary["invented"]
    add(f"     outside the allowed list   {invented['by_kind']['not_in_allowed_list']:>3}")
    add(f"     keys not in the schema     {invented['by_kind']['unexpected_field']:>3}")
    add(f"     asset tags not in ticket   {invented['by_kind']['asset_tag_not_in_ticket']:>3}")
    listed = invented["examples"] if show_all else invented["examples"][:5]
    for example in listed:
        add(f"       {example['item_id']}  {example['field']} = {one_line(shown(example['value']), 40)}"
            f"   ({example['kind']})")
    if len(invented["examples"]) > len(listed):
        add(f"       ... {len(invented['examples']) - len(listed)} more (--all lists them)")

    add("")
    add("5. PER CLASS - counts, not percentages         ('thin' = fewer than "
        f"{es.THIN_CLASS_SIZE} tickets: an anecdote)")
    for class_field, table in summary["per_class"].items():
        add(f"     {class_field:<14}   n   {class_field + ' right':<16} whole record right")
        for value, cell in table.items():
            flag = "thin" if cell["thin"] else ""
            if cell["n"] == 0:
                flag = "NOT TESTED: none in this dataset"
            add(f"       {value:<12} {cell['n']:>3}   {cell['field_correct']:>8}         "
                f"{cell['record_exact']:>8}           {flag}")

    add("")
    add("6. URGENCY MISSES - for rubric H1              (+ = the model escalated higher than the label)")
    shape = summary["urgency_errors"]["shape"]
    add(f"     over by 1: {shape['over_by_1']}   over by 2+: {shape['over_by_2_or_more']}   "
        f"under by 1: {shape['under_by_1']}   under by 2+: {shape['under_by_2_or_more']}")
    add(f"     not a real level: {shape['not_a_level']}   no usable reply: {shape['no_usable_reply']}"
        "     (neither goes to H1: nothing to argue about)")
    review = summary["review"]
    if review["H1_direction"] in ("over-escalates", "under-escalates"):
        add(f"     PATTERN: the model {review['H1_direction']}. That is ONE disagreement about the "
            "convention -")
        add("     settle it once (rubric H1, step 1), then read only the tickets marked *.")
    for miss in summary["urgency_errors"]["misses"]:
        step = "" if miss["step"] is None else f"{miss['step']:+d}"
        mark = "*" if miss["item_id"] in review["H1_urgency"] else " "
        add(f"     {mark} {miss['item_id']}  label {shown(miss['expected']):<10}  model "
            f"{one_line(shown(miss['predicted']), 30):<12} {step}")

    add("")
    add(f"7. REQUESTED_ACTION BELOW {action['match_threshold']:.2f} - for rubric H2       "
        f"({review['H2_below_threshold_total']} below; read these {len(review['H2_requested_action'])})")
    by_id = {entry["item_id"]: entry for entry in scored}
    action_ids = review["H2_requested_action"]
    if show_all:
        action_ids = [entry["item_id"] for entry in scored
                      if not entry["item"]["fields"][es.SIMILARITY_FIELD]["correct"]
                      and entry["item"]["predicted_record"] is not None]
    for item_id in action_ids:
        result = by_id[item_id]["item"]["fields"][es.SIMILARITY_FIELD]
        add(f"       {item_id}  {result['score']:.2f}  label: {one_line(result['expected'], 70)}")
        add(f"                         model: {one_line(shown(result['predicted']), 70)}")

    if show_all:
        add("")
        add("8. EVERY WRONG EXACT-MATCH FIELD")
        for entry in scored:
            for field in es.EXACT_FIELDS:
                result = entry["item"]["fields"][field]
                if not result["correct"]:
                    add(f"       {entry['item_id']}  {field:<16} label {one_line(shown(result['expected']), 24):<24}"
                        f"  model {one_line(shown(result['predicted']), 28)}")

    add("")
    add("READ THIS BEFORE QUOTING A NUMBER")
    for note in summary["limitations"]:
        add(wrapped("- " + note, "  "))
    add(rule)
    return "\n".join(lines)


# ---------------------------------------------------------------------
# One call that does a whole run. The CLI and the notebooks share it.
# ---------------------------------------------------------------------


def run_evaluation(dataset_path, ask, endpoint_name, model, label=None, out_dir=DEFAULT_OUT_DIR,
                   run_id=None, schema_path=DEFAULT_SCHEMA, limit=None, resume=False,
                   json_mode=False, replies_file=None, show_all=False, show_progress=True):
    """Ask, score, write the contract files, print the report.
    Returns the summary dict. `ask` may be None when replies_file is given."""
    label = label or endpoint_name
    validator = Draft202012Validator(du.load_schema(schema_path))
    rows, skipped = load_eval_rows(dataset_path, validator, limit=limit)

    today = datetime.date.today().isoformat()
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)
    run_id = run_id or f"{today}_{safe_label}_{Path(dataset_path).stem}"

    out_dir = Path(out_dir)
    replies_path = out_dir / f"{run_id}_replies.jsonl"

    if show_progress:
        print(f"Run {run_id}: {len(rows)} tickets -> {endpoint_name} ({model or 'saved replies'})")
    if replies_file is not None:
        reply_rows = load_replies_file(replies_file, rows)
        # Re-scoring an old run: keep the model name it was recorded with.
        recorded = [row["model"] for row in reply_rows if row.get("model")]
        model = model or (recorded[0] if recorded else "(saved replies)")
        if show_progress:
            print(f"  scoring saved replies from {replies_file}; no model was called")
    else:
        saved = load_saved_replies(replies_path) if resume else {}
        if resume and show_progress:
            print(f"  --resume: {len(saved)} saved replies found in {replies_path.name}")
        reply_rows = collect_replies(rows, ask, model, replies_path, saved, show_progress)

    scored = score_replies(rows, reply_rows, validator)

    try:
        dataset_shown = Path(dataset_path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        dataset_shown = Path(dataset_path).name
    run_info = {
        "run_id": run_id,
        "label": label,
        "endpoint": endpoint_name,
        "model": model,
        "dataset": dataset_shown,
        "dataset_sha256": questions_fingerprint(rows),
        # False = the file was built with an older prompt than training uses now.
        "system_prompt_matches": all(row["messages"][0]["content"] == du.SYSTEM_PROMPT
                                     for row in rows),
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "settings": {"temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "json_mode": json_mode},
    }
    summary = build_summary(scored, run_info, skipped)
    field_rows = build_field_rows(scored, run_info)
    report_text = render_report(summary, scored, show_all=show_all)
    paths = write_outputs(out_dir, summary, field_rows, report_text)

    print(report_text)
    print(f"Wrote {paths['summary']}")
    print(f"      {paths['rows']}  ({len(field_rows)} lines)")
    print(f"      {paths['report']}")
    return summary


# ---------------------------------------------------------------------
# Comparison: summaries in, one table out. Never reads a rows file.
# ---------------------------------------------------------------------


def load_summary(path):
    path = Path(path)
    if not path.is_file():
        raise EvalError(f"{path} does not exist (or is not a file).")
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise EvalError(f"{path} is not valid JSON. Pass the *_summary.json files, not rows or replies.")
    if not isinstance(summary, dict) or summary.get("contract") != SUMMARY_CONTRACT:
        raise EvalError(f'{path} is not an eval summary (no "contract": "{SUMMARY_CONTRACT}"). '
                        "Pass the *_summary.json files.")
    return summary


def compare_summaries(summaries):
    """Merge run summaries into one comparison dict (contract #4).

    Refuses runs that answered different questions: a table that
    compares different exams is worse than no table.
    """
    if len(summaries) < 2:
        raise EvalError("A comparison needs at least two summary files.")
    if len(summaries) > MAX_COMPARED_RUNS:
        raise EvalError(f"At most {MAX_COMPARED_RUNS} runs fit in one table.")

    first = summaries[0]
    for other in summaries[1:]:
        if other["dataset_sha256"] != first["dataset_sha256"]:
            raise EvalError(
                "These runs did not answer the same questions, so they cannot share a table.\n"
                f"  {first['run_id']}: {first['n_items']} tickets, questions {first['dataset_sha256']}\n"
                f"  {other['run_id']}: {other['n_items']} tickets, questions {other['dataset_sha256']}\n"
                "  Re-run them on the same --dataset (and the same --limit, if any)."
            )

    names = [summary["label"] for summary in summaries]
    if len(set(names)) < len(names):
        names = [summary["run_id"] for summary in summaries]
    if len(set(names)) < len(names):
        raise EvalError("Two of these runs have the same run_id. Re-run one with --label.")

    def metric(name, getter, kind):
        values = {run: getter(summary) for run, summary in zip(names, summaries)}
        return {"metric": name, "kind": kind, "values": values}

    metrics = [metric("schema_valid_rate", lambda s: s["schema_valid_rate"], "rate")]
    for field in du.RECORD_FIELDS:
        metrics.append(metric(field, lambda s, f=field: s["per_field_accuracy"][f], "rate"))
    metrics.append(metric("requested_action_mean_similarity",
                          lambda s: s["requested_action"]["mean_similarity"], "score"))
    metrics.append(metric("overall_exact_match", lambda s: s["overall_exact_match"], "rate"))
    metrics.append(metric("invented_values", lambda s: s["invented"]["total"], "count"))
    metrics.append(metric("seconds_per_item_median", lambda s: s["seconds_per_item_median"], "seconds"))

    per_class = {}
    for class_field, table in first["per_class"].items():
        per_class[class_field] = []
        for value, cell in table.items():
            line = {"class": value, "n": cell["n"], "thin": cell["thin"], "field_correct": {}}
            for run, summary in zip(names, summaries):
                line["field_correct"][run] = summary["per_class"][class_field][value]["field_correct"]
            per_class[class_field].append(line)

    per_item = []
    for position, item_id in enumerate(first["item_ids"]):
        line = {"item_id": item_id, "exact_fields_correct": {}}
        for run, summary in zip(names, summaries):
            item = summary["items"][position]
            readable = item["parse"] in ("clean", "recovered")
            line["exact_fields_correct"][run] = item["exact_fields_correct"] if readable else None
        per_item.append(line)

    return {
        "contract": COMPARISON_CONTRACT,
        "dataset": first["dataset"],
        "dataset_sha256": first["dataset_sha256"],
        "n_items": first["n_items"],
        "runs": [{"name": run, "run_id": s["run_id"], "endpoint": s["endpoint"], "model": s["model"],
                  "json_mode": s["settings"]["json_mode"]} for run, s in zip(names, summaries)],
        "metrics": metrics,
        "per_class": per_class,
        "per_item": per_item,
        # everything about sample size; the per-run notes stay in the run reports
        "limitations": [note for note in first["limitations"]
                        if note.startswith(("NOT TESTED", "Thin classes")) or "percentage points" in note],
    }


METRIC_TITLES = {
    "schema_valid_rate": "FORMAT  schema-valid replies",
    "requested_action": "FIELD   requested_action (>= %.2f)" % es.ACTION_MATCH_THRESHOLD,
    "requested_action_mean_similarity": "requested_action mean similarity",
    "overall_exact_match": "RECORD  all six exact fields right",
    "invented_values": "INVENTED values (a count)",
    "seconds_per_item_median": "median seconds per ticket",
}


def render_comparison(comparison):
    names = [run["name"] for run in comparison["runs"]]
    n = comparison["n_items"]
    column = 16
    lines = []
    add = lines.append
    rule = "=" * REPORT_WIDTH

    def cells(values):
        return "".join(f"{one_line(value, column - 2):>{column}}" for value in values)

    add(rule)
    add(f"COMPARISON  the same {n} tickets for every run")
    add(f"  dataset   {one_line(comparison['dataset'], 60)}   questions {comparison['dataset_sha256']}")
    add(rule)
    add(f"{'':<36}" + cells(names))
    add(f"{'  model':<36}" + cells([run["model"] for run in comparison["runs"]]))
    add(f"{'  endpoint':<36}" + cells([run["endpoint"] for run in comparison["runs"]]))
    add("")
    for entry in comparison["metrics"]:
        title = METRIC_TITLES.get(entry["metric"], "FIELD   " + entry["metric"])
        values = []
        for run in names:
            value = entry["values"][run]
            if value is None:
                values.append("-")
            elif entry["kind"] == "rate":
                values.append(f"{round(value * n)}/{n} {percent(value)}")
            elif entry["kind"] == "count":
                values.append(str(value))
            else:
                values.append(f"{value:.2f}")
        add(f"  {title:<34}" + cells(values))

    add("")
    add("PER CLASS - tickets where that field was right, out of n   ('thin' = fewer than "
        f"{es.THIN_CLASS_SIZE}: an anecdote)")
    for class_field, table in comparison["per_class"].items():
        for line in table:
            flag = " thin" if line["thin"] else ""
            if line["n"] == 0:
                flag = " NONE"
            title = f"  {class_field}={line['class']} (n={line['n']}){flag}"
            values = [f"{line['field_correct'][run]}/{line['n']}" for run in names]
            add(f"{title:<36}" + cells(values))
        add("")

    add("PER TICKET - exact-match fields right, out of 6               ('-' = no readable reply)")
    for line in comparison["per_item"]:
        values = []
        for run in names:
            value = line["exact_fields_correct"][run]
            values.append("-" if value is None else str(value))
        add(f"  {line['item_id']:<34}" + cells(values))

    add("")
    add("READ THIS BEFORE QUOTING A NUMBER")
    for note in comparison["limitations"]:
        add(wrapped("- " + note, "  "))
    add(rule)
    return "\n".join(lines)


def run_comparison(summary_paths, out_dir=None):
    summaries = [load_summary(path) for path in summary_paths]
    comparison = compare_summaries(summaries)
    table_text = render_comparison(comparison)
    print(table_text)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "comparison.json", comparison)
        (out_dir / "comparison.txt").write_text(table_text + "\n", encoding="utf-8", newline="\n")
        print(f"Wrote {out_dir / 'comparison.json'}")
        print(f"      {out_dir / 'comparison.txt'}")
    return comparison


# ---------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        description="Score a model endpoint on the ticket task, or compare scored runs.")
    parser.add_argument("--dataset", help="pairs file, e.g. data/eval/heldout_20.jsonl")
    parser.add_argument("--endpoint", help="local | hosted | tuned (config/endpoints.py)")
    parser.add_argument("--label", help="column name for this run in a comparison (default: the endpoint)")
    parser.add_argument("--out", help=f"output folder (default: {DEFAULT_OUT_DIR}/ for a run; "
                                      "for --compare, nothing is written unless --out is given)")
    parser.add_argument("--run-id", help="override the generated run id (date_label_dataset)")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="ticket schema file")
    parser.add_argument("--json-mode", action="store_true",
                        help="ask the server to force JSON output (off by default)")
    parser.add_argument("--resume", action="store_true",
                        help="reuse replies already saved for this run id")
    parser.add_argument("--replies", help="score this saved replies file; no model is called")
    parser.add_argument("--limit", type=int, help="first N tickets only (smoke test)")
    parser.add_argument("--all", action="store_true", help="list every wrong field")
    parser.add_argument("--compare", nargs="+", metavar="SUMMARY_JSON",
                        help="merge these *_summary.json files into one table")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.compare:
            run_comparison(args.compare, out_dir=args.out)
            return 0

        if not args.dataset or not args.endpoint:
            parser.error("give --dataset and --endpoint (or --compare)")
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be 1 or more")

        if args.replies:
            ask = None
            model = None        # taken from the replies file
        else:
            # Imported here so --compare and --replies work with no endpoint set up.
            from config.endpoints import EndpointError, get_endpoint
            try:
                endpoint = get_endpoint(args.endpoint)
            except (ValueError, EndpointError) as error:
                raise EvalError(str(error))
            model = endpoint.model

            def ask(messages):
                return endpoint.chat(messages=messages, temperature=TEMPERATURE,
                                     max_tokens=MAX_TOKENS, json_mode=args.json_mode)

        run_evaluation(
            args.dataset, ask, endpoint_name=args.endpoint, model=model, label=args.label,
            out_dir=args.out or DEFAULT_OUT_DIR, run_id=args.run_id, schema_path=args.schema,
            limit=args.limit, resume=args.resume, json_mode=args.json_mode,
            replies_file=args.replies, show_all=args.all,
        )
        return 0
    except EvalError as error:
        print(f"Cannot run the eval: {ascii_safe(error)}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
