"""Helpers for notebook 06: base model versus tuned model.

Import after the environment-detection cell has run:

    import compare_utils

What lives here is PLUMBING:

    find_adapter     your own adapter from notebook 05 - or, if it is missing or
                     broken, the pre-baked one. Never a silent swap: every folder
                     it looked at comes back with a verdict, and the notebook prints it
    run_command      run a command line and show its output as it arrives
    load_run         read the files one run_eval.py run wrote (contract 4)
    pick_examples    choose tickets to read side by side, by fixed rules
    render_example   one ticket: the label, the base answer, the tuned answer

What does NOT live here: scoring. Every number comes from
scripts/run_eval.py, so the table in this lab is the same table any
other lab - or your own project - gets from the same command.

Standard library only (plus the repo's own finetune_utils for one lookup).
"""

import hashlib
import json
import os
import struct
import subprocess
import textwrap
from pathlib import Path

PREBAKED_FOLDER = "adapter_prebaked"
ADAPTER_WEIGHTS_FILE = "adapter_model.safetensors"
ADAPTER_CONFIG_FILE = "adapter_config.json"

REPORT_WIDTH = 100


# ---------------------------------------------------------------------------
# Which adapter
# ---------------------------------------------------------------------------


def weights_file_problem(weights_path):
    """None if the safetensors file is complete, else a sentence.

    A safetensors file starts with 8 bytes giving the length of a JSON
    header; the header lists where every tensor ends. If the file is
    shorter than the header says, the copy was cut off - typically a
    runtime that disconnected while saving to Drive.
    """
    file_size = weights_path.stat().st_size
    with open(weights_path, "rb") as handle:
        first_bytes = handle.read(8)
        if len(first_bytes) < 8:
            return "the weights file is empty"
        header_length = struct.unpack("<Q", first_bytes)[0]
        if header_length > file_size:
            return "the weights file is cut off (its header is incomplete)"
        try:
            header = json.loads(handle.read(header_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return "the weights file is not a safetensors file"

    tensor_ends = [entry["data_offsets"][1] for name, entry in header.items() if name != "__metadata__"]
    if tensor_ends == []:
        return "the weights file holds no tensors"
    expected_size = 8 + header_length + max(tensor_ends)
    if file_size < expected_size:
        return f"the weights file is cut off ({file_size:,} bytes, should be {expected_size:,})"
    return None


def adapter_problem(adapter_dir):
    """None if adapter_dir holds a usable adapter, else a sentence saying why not."""
    adapter_dir = Path(adapter_dir)
    if not adapter_dir.is_dir():
        return "folder does not exist"
    config_path = adapter_dir / ADAPTER_CONFIG_FILE
    weights_path = adapter_dir / ADAPTER_WEIGHTS_FILE
    if not config_path.is_file():
        return f"no {ADAPTER_CONFIG_FILE}"
    if not weights_path.is_file():
        return f"no {ADAPTER_WEIGHTS_FILE} (training did not reach the save step)"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return f"{ADAPTER_CONFIG_FILE} is not valid JSON (cut off while saving?)"
    if find_model_key(config.get("base_model_name_or_path")) is None:
        return (f"trained on '{config.get('base_model_name_or_path')}', which has no twin in Ollama "
                "(a smoke-test adapter?)")
    return weights_file_problem(weights_path)


def find_model_key(hf_repo):
    """'unsloth/Llama-3.2-1B-Instruct' -> 'llama3.2-1b' (a key of
    finetune_utils.MODEL_CHOICES), or None if Ollama has no such model."""
    import finetune_utils

    for model_key, choice in finetune_utils.MODEL_CHOICES.items():
        if choice["hf_repo"] == hf_repo and choice["ollama_base"]:
            return model_key
    return None


def adapter_fingerprint(adapter_dir):
    """First 8 hex digits of the sha256 of the weights. Two adapters with
    the same fingerprint are the same adapter, whatever their folder is called."""
    digest = hashlib.sha256()
    with open(Path(adapter_dir) / ADAPTER_WEIGHTS_FILE, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:8]


def find_adapter(checkpoint_dir, repo_root, model_name, run_name, use_prebaked=False):
    """Choose the adapter notebook 06 scores. Returns:

        {"source"       "yours" | "prebaked"
         "path"         the adapter folder
         "checked"      [{"path", "verdict"}, ...] every folder looked at, in order
         "fingerprint"  8 hex digits identifying the weights
         "model_key"    e.g. "llama3.2-1b"   (finetune_utils.MODEL_CHOICES)
         "ollama_base"  e.g. "llama3.2:1b"   the untuned model to compare against
         "training"     notebook 05's summary for this run, or None}

    Order: your run folder under CHECKPOINT_DIR (Google Drive on Colab -
    it survives a disconnect), then the copy notebook 05 put in the
    repo's checkpoints/ folder, then checkpoints/adapter_prebaked/.
    """
    import finetune_utils

    checkpoint_dir = Path(checkpoint_dir)
    repo_root = Path(repo_root)
    run_dir = checkpoint_dir / "05_finetune" / f"{model_name}_{run_name}"
    own_candidates = [
        run_dir / finetune_utils.FINAL_ADAPTER_FOLDER,
        repo_root / "checkpoints" / f"adapter_{model_name}_{run_name}",
    ]
    prebaked_dir = repo_root / "checkpoints" / PREBAKED_FOLDER

    checked = []
    chosen = None
    source = None
    if use_prebaked:
        checked.append({"path": str(own_candidates[0]), "verdict": "skipped: USE_PREBAKED is True"})
    else:
        for candidate in own_candidates:
            problem = adapter_problem(candidate)
            checked.append({"path": str(candidate), "verdict": "usable" if problem is None else problem})
            if problem is None:
                chosen = candidate
                source = "yours"
                break

    if chosen is None:
        problem = adapter_problem(prebaked_dir)
        checked.append({"path": str(prebaked_dir), "verdict": "usable" if problem is None else problem})
        if problem is not None:
            raise FileNotFoundError(
                f"No usable adapter anywhere - not even the pre-baked one ({prebaked_dir}: {problem}). "
                "Is the repo clone complete? In Colab: delete /content/oq-advanced-ai and run the first cell again."
            )
        chosen = prebaked_dir
        source = "prebaked"

    config = json.loads((chosen / ADAPTER_CONFIG_FILE).read_text(encoding="utf-8"))
    model_key = find_model_key(config["base_model_name_or_path"])

    training = None
    training_summary_path = run_dir / "05_summary.json"
    if source == "yours" and training_summary_path.is_file():
        training = json.loads(training_summary_path.read_text(encoding="utf-8"))

    return {
        "source": source,
        "path": str(chosen),
        "checked": checked,
        "fingerprint": adapter_fingerprint(chosen),
        "model_key": model_key,
        "ollama_base": finetune_utils.MODEL_CHOICES[model_key]["ollama_base"],
        "training": training,
    }


# ---------------------------------------------------------------------------
# Running a command line from a cell
# ---------------------------------------------------------------------------


def shown_command(command):
    """The command as one line you could paste into a terminal."""
    words = []
    for word in command:
        word = str(word)
        words.append(f'"{word}"' if " " in word else word)
    return " ".join(words)


def run_command(command, extra_env=None):
    """Run a command, print its output line by line as it arrives, and
    return its exit code. extra_env adds environment variables for this
    one command."""
    environment = dict(os.environ)
    environment["PYTHONUNBUFFERED"] = "1"       # progress lines appear as they happen
    environment["PYTHONIOENCODING"] = "utf-8"
    environment.update(extra_env or {})

    print("$ " + shown_command(command))
    process = subprocess.Popen([str(word) for word in command], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                               errors="replace", env=environment)
    for line in process.stdout:
        print(line, end="")
    return process.wait()


# ---------------------------------------------------------------------------
# Reading what run_eval.py wrote (contract 4)
# ---------------------------------------------------------------------------


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_run(eval_dir, run_id):
    """One scored run, regrouped by ticket:

        {"summary": {...},
         "tickets": {item_id: {"fields": {field: row}, "reply": raw text or None, "parse": ...}}}

    `row` is a line of <run_id>_rows.jsonl: expected, predicted, correct, score.
    """
    eval_dir = Path(eval_dir)
    summary = json.loads((eval_dir / f"{run_id}_summary.json").read_text(encoding="utf-8"))

    tickets = {}
    for row in read_jsonl(eval_dir / f"{run_id}_rows.jsonl"):
        ticket = tickets.setdefault(row["item_id"], {"fields": {}, "reply": None})
        ticket["fields"][row["field"]] = row
    for reply_row in read_jsonl(eval_dir / f"{run_id}_replies.jsonl"):
        if reply_row["item_id"] in tickets:
            tickets[reply_row["item_id"]]["reply"] = reply_row.get("reply")
    # "clean" | "recovered" | "failed" | "no_reply": could a record be read out of the reply at all?
    for item in summary["items"]:
        tickets[item["item_id"]]["parse"] = item["parse"]
    return {"summary": summary, "tickets": tickets}


def exact_fields_right(ticket):
    """How many of the six exact-match fields this run got right on this ticket."""
    return sum(1 for row in ticket["fields"].values()
               if row["score_type"] == "exact" and row["correct"])


# ---------------------------------------------------------------------------
# Choosing the tickets to read. Fixed rules, so nobody - including the
# person who built this lab - gets to pick the flattering ones.
# ---------------------------------------------------------------------------


def pick_examples(base_run, tuned_run):
    """Up to four tickets, each chosen by a rule, in this order:

      1. format fixed   the first ticket where the base reply FAILED the
                        format check and the tuned reply passed
      2. biggest gain   the largest rise in exact-match fields right, among
                        tickets where both replies held a readable record
      3. tuned worse    the largest FALL - shown whenever one exists
      4. still wrong    the tuned model's worst remaining ticket

    Ties go to the earlier ticket in the file. A rule with no ticket to
    show is reported as such, not skipped quietly.
    Returns [{"rule", "item_id" (or None), "why"}, ...].
    """
    item_ids = list(base_run["tickets"])
    base_right = {item_id: exact_fields_right(base_run["tickets"][item_id]) for item_id in item_ids}
    tuned_right = {item_id: exact_fields_right(tuned_run["tickets"][item_id]) for item_id in item_ids}
    change = {item_id: tuned_right[item_id] - base_right[item_id] for item_id in item_ids}

    picks = []
    used = set()

    def add(rule, item_id, why):
        picks.append({"rule": rule, "item_id": item_id, "why": why})
        if item_id is not None:
            used.add(item_id)

    # 1. format fixed
    format_fixed = [item_id for item_id in item_ids
                    if not base_run["tickets"][item_id]["fields"]["(schema)"]["correct"]
                    and tuned_run["tickets"][item_id]["fields"]["(schema)"]["correct"]]
    if format_fixed:
        add("format fixed", format_fixed[0],
            f"the base reply failed the format check, the tuned reply passed "
            f"({len(format_fixed)} tickets like this; this is the first)")
    else:
        add("format fixed", None, "no ticket where tuning turned a format failure into a pass")

    # 2. biggest gain
    # Only tickets where BOTH replies held a record: a gain in content, not another format rescue.
    remaining = [item_id for item_id in item_ids if item_id not in used
                 and base_run["tickets"][item_id]["parse"] in ("clean", "recovered")
                 and tuned_run["tickets"][item_id]["parse"] in ("clean", "recovered")]
    best = max(remaining, key=lambda item_id: change[item_id], default=None)
    if best is not None and change[best] > 0:
        add("biggest gain", best,
            f"largest rise in exact-match fields right where both replies were readable: "
            f"{base_right[best]} -> {tuned_right[best]} of 6")
    else:
        add("biggest gain", None, "no readable ticket where the tuned model got more fields right")

    # 3. tuned worse
    remaining = [item_id for item_id in item_ids if item_id not in used]
    worst = min(remaining, key=lambda item_id: change[item_id], default=None)
    if worst is not None and change[worst] < 0:
        worse_count = sum(1 for item_id in item_ids if change[item_id] < 0)
        add("tuned worse", worst,
            f"the tuned model did WORSE than the base model: {base_right[worst]} -> {tuned_right[worst]} of 6 "
            f"({worse_count} tickets like this)")
    else:
        add("tuned worse", None, "no ticket where the tuned model got fewer fields right than the base model")

    # 4. still wrong
    remaining = [item_id for item_id in item_ids if item_id not in used and tuned_right[item_id] < 6]
    lowest = min(remaining, key=lambda item_id: tuned_right[item_id], default=None)
    if lowest is not None:
        add("still wrong", lowest,
            f"the tuned model's worst remaining ticket: {tuned_right[lowest]} of 6 fields right "
            f"(base: {base_right[lowest]})")
    else:
        add("still wrong", None, "no remaining ticket where the tuned model has a wrong field")
    return picks


# ---------------------------------------------------------------------------
# Showing one ticket. ASCII only, 100 columns (a projector, a Windows console).
# ---------------------------------------------------------------------------


def plain(text, width):
    """Text on one line, cut to width, ASCII only."""
    text = " ".join(str(text).split())
    text = text.encode("ascii", "backslashreplace").decode("ascii")
    if len(text) > width:
        text = text[: width - 3] + "..."
    return text


def wrapped(text):
    """Text folded to the report width, indented two spaces."""
    return textwrap.fill(text, width=REPORT_WIDTH, initial_indent="  ", subsequent_indent="    ")


def shown(value, width):
    """A value as it appears in JSON - null, "high" - so a missing value
    and the string "null" cannot be mistaken for each other."""
    return plain(json.dumps(value), width)


def render_example(pick, ticket_text, base_run, tuned_run, ticket_characters=420):
    """The text block for one picked ticket."""
    lines = ["-" * REPORT_WIDTH]
    if pick["item_id"] is None:
        lines.append(f"[{pick['rule']}]  nothing to show: {pick['why']}")
        return "\n".join(lines)

    base_ticket = base_run["tickets"][pick["item_id"]]
    tuned_ticket = tuned_run["tickets"][pick["item_id"]]

    lines.append(f"{pick['item_id']}   [{pick['rule']}]")
    lines.append(wrapped(f"why this one: {pick['why']}"))
    lines.append(wrapped(f"ticket: {plain(ticket_text, ticket_characters)}"))
    lines.append("")
    lines.append(f"  {'field':<17}{'label':<24}{'base':<28}tuned")

    for field, label_row in base_ticket["fields"].items():
        if field == "requested_action":
            continue
        cells = []
        for ticket in [base_ticket, tuned_ticket]:
            row = ticket["fields"][field]
            if field == "(schema)":
                cell = "valid" if row["correct"] else "FAILED"
            elif ticket["parse"] in ("failed", "no_reply"):
                cell = "(no record)"
            else:
                cell = shown(row["predicted"], 20)
            cells.append(cell + ("" if row["correct"] else "  <-- X"))
        name = "(format)" if field == "(schema)" else field
        label = "valid" if field == "(schema)" else shown(label_row["expected"], 22)
        lines.append(f"  {name:<17}{label:<24}{cells[0]:<28}{cells[1]:<28}".rstrip())

    lines.append("  requested_action   (a match = word similarity >= 0.50 with the label)")
    lines.append(f"    label : {plain(base_ticket['fields']['requested_action']['expected'], 86)}")
    for name, ticket in [("base ", base_ticket), ("tuned", tuned_ticket)]:
        row = ticket["fields"]["requested_action"]
        verdict = "match" if row["correct"] else "no match"
        clause = "(no record)" if ticket["parse"] in ("failed", "no_reply") else plain(row["predicted"], 66)
        lines.append(f"    {name} : {clause}   ({row['score']:.2f}, {verdict})")

    for name, ticket in [("base", base_ticket), ("tuned", tuned_ticket)]:
        format_row = ticket["fields"]["(schema)"]
        if format_row["correct"]:
            continue
        lines.append(wrapped(f"why the {name} reply FAILED format: {plain(format_row['predicted'], 250)}"))
        if ticket["parse"] != "clean":
            raw_reply = plain(ticket["reply"] or "(no reply)", 100_000)
            lines.append(f"    the raw reply ends:  ...{raw_reply[-70:]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The final cell: a few rows of the comparison, as counts
# ---------------------------------------------------------------------------

HEADLINE_METRICS = [
    ("schema_valid_rate", "FORMAT  schema-valid"),
    ("routing_queue", "FIELD   routing_queue"),
    ("requested_action", "FIELD   requested_action"),
    ("urgency", "FIELD   urgency"),
    ("overall_exact_match", "RECORD  all six exact fields"),
    ("invented_values", "INVENTED values (a count)"),
]


def headline(comparison):
    """A few rows of a comparison.json (contract 4) as text lines, plus
    how many tickets the LAST run did worse on than the FIRST run."""
    names = [run["name"] for run in comparison["runs"]]
    n_items = comparison["n_items"]
    metrics = {entry["metric"]: entry for entry in comparison["metrics"]}

    lines = [f"  {'':<32}" + "".join(f"{name:>12}" for name in names)]
    for metric_name, title in HEADLINE_METRICS:
        entry = metrics[metric_name]
        cells = []
        for name in names:
            value = entry["values"][name]
            if entry["kind"] == "rate":
                cells.append(f"{round(value * n_items)}/{n_items}")
            else:
                cells.append(str(value))
        lines.append(f"  {title:<32}" + "".join(f"{cell:>12}" for cell in cells))

    first_name, last_name = names[0], names[-1]
    worse_ids = []
    for item in comparison["per_item"]:
        first_right = item["exact_fields_correct"][first_name] or 0
        last_right = item["exact_fields_correct"][last_name] or 0
        if last_right < first_right:
            worse_ids.append(item["item_id"])
    lines.append(f"  '{last_name}' got FEWER fields right than '{first_name}' on {len(worse_ids)} of {n_items} tickets"
                 + (f": {', '.join(worse_ids)}" if worse_ids else ""))
    return lines
