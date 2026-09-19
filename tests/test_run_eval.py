"""Tests for scripts/run_eval.py and scripts/eval_scoring.py.

    python -m pytest tests/test_run_eval.py -v

No test here calls a model: every "model" is a Python function that
returns a canned reply. Five groups:

  * a perfect model scores perfectly (the harness itself adds no noise);
  * BROKEN model output - malformed JSON, fences, prose, missing
    fields, invented values, wrong types, empty replies, a dead
    endpoint - is scored without crashing and reported under the
    right heading;
  * the four measurements stay separate (format / fields / record /
    invented);
  * the output files follow contract #4, and three runs compose into
    one comparison table - which refuses runs on different questions;
  * the report is ASCII, at most 100 columns, and states its limits.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_utils as du  # noqa: E402
import eval_scoring as es  # noqa: E402
import run_eval  # noqa: E402
import ticket_scenarios as bank  # noqa: E402

HELDOUT = REPO_ROOT / "data" / "eval" / "heldout_20.jsonl"
VAL = REPO_ROOT / "data" / "finetune" / "val.jsonl"
SCHEMA = REPO_ROOT / "data" / "finetune" / "ticket_schema.json"
SCRIPT = REPO_ROOT / "scripts" / "run_eval.py"

TICKET_TEXT = "Subject: laptop dead\n\nmy laptop lap 04412 will not start, whole team blocked"
EXPECTED = {
    "category": "hardware",
    "affected_system": None,
    "asset_tag": "LAP-04412",
    "urgency": "high",
    "impact": "team",
    "requested_action": "Repair or replace the laptop that will not power on",
    "routing_queue": "end_user_computing",
}


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(du.load_schema(SCHEMA))


@pytest.fixture(scope="module")
def heldout_answers():
    """{the user message: the expected completion text}"""
    answers = {}
    for pair in du.load_jsonl(HELDOUT):
        answers[du.pair_user_text(pair)] = du.pair_completion_text(pair)
    return answers


def score(reply, validator, **kwargs):
    return es.score_item(EXPECTED, reply, TICKET_TEXT, validator, **kwargs)


def reply_with(**changes):
    record = dict(EXPECTED)
    record.update(changes)
    return json.dumps(record)


def run_cli(*args):
    command = [sys.executable, str(SCRIPT), *[str(arg) for arg in args]]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")


def run_with(ask, tmp_path, label, **kwargs):
    return run_eval.run_evaluation(HELDOUT, ask, endpoint_name="fake", model="fake-model",
                                   label=label, out_dir=tmp_path, show_progress=False, **kwargs)


# ---------------------------------------------------------------------
# The constants agree with the rest of the repo
# ---------------------------------------------------------------------


def test_allowed_values_match_schema_generator_and_prompt():
    schema = du.load_schema(SCHEMA)
    for field in ["category", "urgency", "impact"]:
        assert es.ALLOWED_VALUES[field] == schema["properties"][field]["enum"]
    assert es.ALLOWED_VALUES["routing_queue"] == bank.ROUTING_QUEUES
    for values in es.ALLOWED_VALUES.values():
        for value in values:
            assert f'"{value}"' in du.SYSTEM_PROMPT


def test_every_field_is_scored_exactly_once():
    assert sorted(es.EXACT_FIELDS + [es.SIMILARITY_FIELD]) == sorted(du.RECORD_FIELDS)


def test_the_limits_text_quotes_true_numbers():
    assert es.action_similarity("Reset the user's MyPortal password", "Reset password") == 0.333
    assert es.action_similarity("Reset the password", "Do not reset the password") == 0.6


# ---------------------------------------------------------------------
# A perfect model
# ---------------------------------------------------------------------


def test_perfect_reply_scores_perfectly(validator):
    item = score(json.dumps(EXPECTED), validator)
    assert item["parse"] == "clean"
    assert item["schema_valid"] is True
    assert item["record_exact"] is True
    assert item["invented"] == []
    assert all(field["correct"] for field in item["fields"].values())


def test_perfect_model_on_the_real_heldout_file(tmp_path, heldout_answers):
    summary = run_with(lambda messages: heldout_answers[messages[1]["content"]], tmp_path, "perfect")
    assert summary["n_items"] == 20
    assert summary["schema_valid_rate"] == 1.0
    assert summary["overall_exact_match"] == 1.0
    assert set(summary["per_field_accuracy"].values()) == {1.0}
    assert summary["invented"]["total"] == 0
    assert summary["review"]["H1_urgency"] == []


# ---------------------------------------------------------------------
# Broken model output. None of it may crash; all of it must be
# reported under the right heading.
# ---------------------------------------------------------------------


@pytest.mark.parametrize("reply, problem", [
    ("", "empty reply"),
    ("   \n ", "empty reply"),
    (None, "empty reply"),
    ("I think this is a hardware ticket.", "not valid JSON"),
    ('{"category": "hardware", "urgency": "hi', "not valid JSON"),          # truncated
    ("{'category': 'hardware'}", "not valid JSON"),                          # Python dict, not JSON
    ('["hardware", "high"]', "JSON, but a list instead of an object"),
    ('"hardware"', "JSON, but a str instead of an object"),
    ("42", "JSON, but a int instead of an object"),
    ("null", "JSON, but a NoneType instead of an object"),
])
def test_unparseable_replies_fail_cleanly(reply, problem, validator):
    item = score(reply, validator)
    assert item["parse"] == "failed"
    assert item["parse_problem"] == problem
    assert item["schema_valid"] is False
    assert item["record_exact"] is False
    assert not any(field["correct"] for field in item["fields"].values())
    assert item["invented"] == []        # nothing was read, so nothing was invented


@pytest.mark.parametrize("wrapper", [
    "```json\n{}\n```",
    "```\n{}\n```",
    "Here is the record:\n{}\nLet me know if you need anything else.",
    "{}\n\nNote: urgency is high because the team is blocked.",
])
def test_json_inside_fences_or_prose_is_recovered_but_not_schema_valid(wrapper, validator):
    item = score(wrapper.replace("{}", json.dumps(EXPECTED)), validator)
    assert item["parse"] == "recovered"
    assert item["schema_valid"] is False      # json.loads(reply) would have crashed
    assert item["record_exact"] is True       # ... but the content was right, and says so


def test_missing_fields(validator):
    record = dict(EXPECTED)
    del record["urgency"]
    del record["impact"]
    item = score(json.dumps(record), validator)
    assert item["parse"] == "clean"
    assert item["schema_valid"] is False
    assert item["schema_problems"] == ["impact: missing_field", "urgency: missing_field"]
    assert item["fields"]["urgency"]["correct"] is False
    assert item["fields"]["urgency"]["present"] is False
    assert item["fields"]["category"]["correct"] is True
    assert item["exact_fields_correct"] == 4
    assert item["invented"] == []             # absent is not invented


def test_empty_object(validator):
    item = score("{}", validator)
    assert item["parse"] == "clean"
    assert item["schema_valid"] is False
    assert len(item["schema_problems"]) == 7
    assert item["exact_fields_correct"] == 0


def test_invented_enum_values_are_counted_apart_from_wrong_ones(validator):
    item = score(reply_with(urgency="urgent", routing_queue="helpdesk", category="software"), validator)
    invented = {(found["field"], found["value"]) for found in item["invented"]}
    assert invented == {("urgency", "urgent"), ("routing_queue", "helpdesk")}
    # "software" is wrong but REAL: it is an accuracy miss, not an invention.
    assert item["fields"]["category"]["correct"] is False
    assert "urgency: invalid_enum_value" in item["schema_problems"]
    # routing_queue is a free string in the frozen schema, so an unknown
    # queue passes the schema - which is exactly why it is counted here.
    assert not any(problem.startswith("routing_queue") for problem in item["schema_problems"])


def test_null_is_a_schema_problem_not_an_invention(validator):
    item = score(reply_with(impact=None), validator)      # seen from llama3.2:3b
    assert item["invented"] == []
    assert item["schema_problems"] == ["impact: null_not_allowed"]
    assert item["fields"]["impact"]["correct"] is False


def test_unexpected_keys_are_invented_fields(validator):
    record = dict(EXPECTED)
    record["confidence"] = 0.9
    record["notes"] = "user sounded stressed"
    item = score(json.dumps(record), validator)
    kinds = [(found["field"], found["kind"]) for found in item["invented"]]
    assert kinds == [("confidence", "unexpected_field"), ("notes", "unexpected_field")]
    assert item["schema_valid"] is False
    assert item["record_exact"] is True


def test_asset_tag_that_is_not_in_the_ticket_is_invented(validator):
    item = score(reply_with(asset_tag="LAP-99999"), validator)
    assert item["invented"] == [{"field": "asset_tag", "value": "LAP-99999",
                                 "kind": "asset_tag_not_in_ticket"}]
    # A tag smuggled into another field is caught too (seen from llama3.2:3b).
    item = score(reply_with(requested_action="Reboot DSK-12345 now"), validator)
    assert item["invented"] == [{"field": "requested_action", "value": "DSK-12345",
                                 "kind": "asset_tag_not_in_ticket"}]
    # The real tag, written the user's way in the ticket ("lap 04412"), is fine.
    assert score(json.dumps(EXPECTED), validator)["invented"] == []


@pytest.mark.parametrize("changes", [
    {"urgency": 3},
    {"urgency": None},
    {"urgency": ["high"]},
    {"urgency": {"level": "high"}},
    {"impact": True},
    {"asset_tag": 4412},
    {"requested_action": None},
    {"requested_action": ["Repair", "the", "laptop"]},
    {"affected_system": {"name": "Teams"}},
])
def test_wrong_types_never_crash_and_never_count_as_right(changes, validator):
    item = score(reply_with(**changes), validator)
    assert item["schema_valid"] is False
    for field in changes:
        assert item["fields"][field]["correct"] is False


def test_case_matters_for_enums_but_not_for_system_names(validator):
    assert score(reply_with(urgency="High"), validator)["fields"]["urgency"]["correct"] is False
    assert es.exact_match("affected_system", "AutoCAD", "Auto Cad") is True
    assert es.exact_match("affected_system", "Tavrona ERP", "TAVRONA") is False
    assert es.exact_match("affected_system", None, "null") is False
    assert es.exact_match("affected_system", None, None) is True
    assert es.exact_match("asset_tag", "LAP-04412", "lap-04412") is False


def test_non_ascii_model_output_survives_the_report(tmp_path, heldout_answers):
    def ask(messages):
        record = json.loads(heldout_answers[messages[1]["content"]])
        record["requested_action"] = "R\u00e9initialiser \u0627\u0644\u0645\u0631\u0648\u0631 \u2013 now"
        record["urgency"] = "\u0639\u0627\u062c\u0644"
        return json.dumps(record, ensure_ascii=False)

    summary = run_with(ask, tmp_path, "unicode", show_all=True)
    report = (tmp_path / f"{summary['run_id']}_report.txt").read_text(encoding="utf-8")
    assert report.isascii()
    assert summary["invented"]["by_kind"]["not_in_allowed_list"] == 20


def test_a_mixed_bag_of_broken_replies_end_to_end(tmp_path, heldout_answers):
    """Twenty tickets, seven kinds of damage, one run. The counts in
    the summary must be exactly the damage that was done."""
    damage = ["ok", "fence", "garbage", "missing", "invented", "empty", "extra_key", "error"]
    # Tickets 0-15 get each kind of damage twice; tickets 16-19 are fine.
    position = {text: index for index, text in enumerate(heldout_answers)}

    def ask(messages):
        index = position[messages[1]["content"]]
        kind = damage[index % len(damage)] if index < 16 else "ok"
        good = heldout_answers[messages[1]["content"]]
        record = json.loads(good)
        if kind == "fence":
            return "```json\n" + good + "\n```"
        if kind == "garbage":
            return "Sure! The category is " + record["category"]
        if kind == "missing":
            del record["impact"]
        if kind == "invented":
            record["urgency"] = "asap"
        if kind == "empty":
            return ""
        if kind == "extra_key":
            record["reasoning"] = "because"
        if kind == "error":
            raise TimeoutError("read timed out")
        return json.dumps(record)

    summary = run_with(ask, tmp_path, "broken")

    assert summary["parse"] == {"clean": 12, "recovered": 2, "failed": 4, "no_reply": 2}
    assert summary["n_parsed"] == 14
    assert summary["invented"]["by_kind"] == {"not_in_allowed_list": 2, "unexpected_field": 2,
                                              "asset_tag_not_in_ticket": 0}
    # schema-valid = clean AND valid: not the fences, the missing, the invented, the extra keys.
    assert summary["schema_valid_rate"] == round(6 / 20, 4)
    # Unusable replies are wrong on every field - over ALL tickets ...
    assert summary["per_field_accuracy"]["category"] == round(14 / 20, 4)
    # ... but the readable ones all had the right category.
    assert summary["per_field_accuracy_when_parsed"]["category"] == 1.0
    assert summary["urgency_errors"]["shape"]["not_a_level"] == 2
    assert summary["urgency_errors"]["shape"]["no_usable_reply"] == 6
    # Only a real-but-different level is worth a human's time.
    assert summary["review"]["H1_urgency"] == []
    assert summary["review"]["H1_direction"] == "none"

    rows = du.load_jsonl(tmp_path / f"{summary['run_id']}_rows.jsonl")
    assert len(rows) == 20 * 8                # 7 fields + the (schema) line, per ticket


def test_a_dead_endpoint_stops_the_run_with_a_sentence(tmp_path):
    def ask(messages):
        raise ConnectionError("connection refused")

    with pytest.raises(run_eval.EvalError) as caught:
        run_with(ask, tmp_path, "dead")
    assert "not answering" in str(caught.value)
    assert "--resume" in str(caught.value)


def test_resume_reuses_saved_replies_and_calls_only_what_is_missing(tmp_path, heldout_answers):
    calls = {"n": 0}

    def flaky(messages):
        calls["n"] += 1
        if calls["n"] > 8:
            raise ConnectionError("runtime disconnected")
        return heldout_answers[messages[1]["content"]]

    with pytest.raises(run_eval.EvalError):
        run_with(flaky, tmp_path, "resumed", run_id="resume_test")

    calls["n"] = 0

    def healthy(messages):
        calls["n"] += 1
        return heldout_answers[messages[1]["content"]]

    summary = run_with(healthy, tmp_path, "resumed", run_id="resume_test", resume=True)
    assert calls["n"] == 12                   # 8 were saved before the disconnect
    assert summary["overall_exact_match"] == 1.0
    assert summary["parse"]["no_reply"] == 0


def test_saved_replies_can_be_scored_with_no_model(tmp_path, heldout_answers):
    first = run_with(lambda messages: heldout_answers[messages[1]["content"]], tmp_path, "live",
                     run_id="live")
    second = run_with(None, tmp_path, "offline", run_id="offline",
                      replies_file=tmp_path / "live_replies.jsonl")
    assert second["per_field_accuracy"] == first["per_field_accuracy"]
    assert second["dataset_sha256"] == first["dataset_sha256"]
    assert second["model"] == "fake-model"        # remembered from the replies file


def test_urgency_review_is_a_pattern_plus_three_tickets_not_a_debate(tmp_path, heldout_answers):
    """A model that over-escalates everything: 18 urgency misses must
    become one pattern and three tickets to read, not 18 arguments."""
    def ask(messages):
        record = json.loads(heldout_answers[messages[1]["content"]])
        record["urgency"] = "critical"
        return json.dumps(record)

    summary = run_with(ask, tmp_path, "alarmist")
    review = summary["review"]
    assert review["H1_arguable_total"] == 18          # 2 of the 20 really are critical
    assert review["H1_direction"] == "over-escalates"
    assert len(review["H1_urgency"]) == 3
    steps = {miss["item_id"]: miss["step"] for miss in summary["urgency_errors"]["misses"]}
    assert all(steps[item_id] == 3 for item_id in review["H1_urgency"])   # furthest first
    report = (tmp_path / f"{summary['run_id']}_report.txt").read_text(encoding="utf-8")
    assert "PATTERN: the model over-escalates" in report


def test_urgency_direction_needs_three_misses_and_two_thirds():
    def misses(*steps):
        return [{"item_id": f"INC-{n:06d}", "step": step} for n, step in enumerate(steps)]
    assert es.urgency_direction(misses()) == "none"
    assert es.urgency_direction(misses(None, None)) == "none"
    assert es.urgency_direction(misses(1, 1)) == "mixed"              # too few to call a pattern
    assert es.urgency_direction(misses(1, 2, -1)) == "over-escalates"
    assert es.urgency_direction(misses(-1, -1, -2, 1)) == "under-escalates"
    assert es.urgency_direction(misses(1, 1, -1, -1)) == "mixed"


# ---------------------------------------------------------------------
# The dataset side
# ---------------------------------------------------------------------


def test_lines_with_a_broken_expected_answer_are_skipped_not_scored(validator):
    """val.jsonl carries planted schema violations. A model must never
    be marked against a broken answer key."""
    planted = json.loads((REPO_ROOT / "data/finetune/planted_problems.json").read_text(encoding="utf-8"))
    planted_in_val = [p for p in planted["schema_violations"] if p["split"] == "val"]
    rows, skipped = run_eval.load_eval_rows(VAL, validator)
    assert len(rows) + len(skipped) == 80
    assert sorted(item["line"] for item in skipped) == sorted(p["line"] for p in planted_in_val)


def test_a_class_with_no_tickets_is_shouted_not_hidden(tmp_path):
    """Cleaned val.jsonl has no usable critical or enterprise ticket
    (the only one carries a planted schema violation). The harness
    must say so itself."""
    answers = {}
    for pair in du.load_jsonl(VAL):
        answers[du.pair_user_text(pair)] = du.pair_completion_text(pair)
    summary = run_eval.run_evaluation(VAL, lambda messages: answers[messages[1]["content"]],
                                      endpoint_name="fake", model="fake-model", out_dir=tmp_path,
                                      show_progress=False)
    assert summary["per_class"]["urgency"]["critical"]["n"] == 0
    assert summary["per_class"]["impact"]["enterprise"]["n"] == 0
    untested = [note for note in summary["limitations"] if note.startswith("NOT TESTED AT ALL")]
    assert len(untested) == 1
    assert "urgency=critical" in untested[0] and "impact=enterprise" in untested[0]

    report = (tmp_path / f"{summary['run_id']}_report.txt").read_text(encoding="utf-8")
    assert "NOT TESTED: none in this dataset" in report
    assert "3 dataset lines were skipped" in report
    assert report.isascii()
    assert max(len(line) for line in report.splitlines()) <= 100

    comparison = run_eval.compare_summaries([summary, dict(summary, label="again", run_id="again")])
    table = run_eval.render_comparison(comparison)
    assert "urgency=critical (n=0) NONE" in table
    assert any(note.startswith("NOT TESTED AT ALL") for note in comparison["limitations"])
    assert max(len(line) for line in table.splitlines()) <= 100


@pytest.mark.parametrize("content, expected_text", [
    (None, "does not exist"),
    ("", "no usable questions"),
    ("not json at all\n", "no usable questions"),
    ('{"ticket_id": "INC-000001"}\n', "no usable questions"),
])
def test_unusable_dataset_exits_2_with_a_sentence(tmp_path, content, expected_text):
    path = tmp_path / "bad.jsonl"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    result = run_cli("--dataset", path, "--endpoint", "local", "--replies", path)
    assert result.returncode == 2
    assert expected_text in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_a_dataset_built_with_another_prompt_is_flagged(tmp_path, heldout_answers):
    pairs = du.load_jsonl(HELDOUT)
    for pair in pairs:
        pair["messages"][0]["content"] = "You are a helpful assistant."
    stale = du.write_jsonl(tmp_path / "stale.jsonl", pairs)
    summary = run_eval.run_evaluation(stale, lambda messages: heldout_answers[messages[1]["content"]],
                                      endpoint_name="fake", model="fake-model", out_dir=tmp_path,
                                      show_progress=False)
    assert summary["system_prompt_matches"] is False
    report = (tmp_path / f"{summary['run_id']}_report.txt").read_text(encoding="utf-8")
    assert "NOT dataset_utils.SYSTEM_PROMPT" in report


def test_the_committed_heldout_file_uses_the_current_prompt(tmp_path, heldout_answers):
    summary = run_with(lambda messages: heldout_answers[messages[1]["content"]], tmp_path, "prompt")
    assert summary["system_prompt_matches"] is True


def test_unknown_endpoint_exits_2_with_a_sentence(tmp_path):
    result = run_cli("--dataset", HELDOUT, "--endpoint", "gpt9", "--out", tmp_path)
    assert result.returncode == 2
    assert "Unknown endpoint" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


# ---------------------------------------------------------------------
# Contract #4: the files, and three runs composing into one table
# ---------------------------------------------------------------------


def make_fake_model(heldout_answers, wrong_urgency_every, fence_every):
    """A model that is right except: every Nth ticket gets urgency
    'critical', and every Mth reply is wrapped in a code fence."""
    calls = {"n": 0}

    def ask(messages):
        calls["n"] += 1
        record = json.loads(heldout_answers[messages[1]["content"]])
        if wrong_urgency_every and calls["n"] % wrong_urgency_every == 0:
            record["urgency"] = "critical" if record["urgency"] != "critical" else "low"
        reply = json.dumps(record)
        if fence_every and calls["n"] % fence_every == 0:
            reply = "```json\n" + reply + "\n```"
        return reply

    return ask


@pytest.fixture()
def three_runs(tmp_path, heldout_answers):
    base = run_with(make_fake_model(heldout_answers, 2, 2), tmp_path, "base")
    tuned = run_with(make_fake_model(heldout_answers, 5, 0), tmp_path, "tuned")
    retrieval = run_with(make_fake_model(heldout_answers, 4, 10), tmp_path, "base+retrieval")
    return tmp_path, [base, tuned, retrieval]


def test_summary_file_has_the_contract_keys(three_runs):
    out_dir, summaries = three_runs
    on_disk = json.loads((out_dir / f"{summaries[0]['run_id']}_summary.json").read_text(encoding="utf-8"))
    for key in ["contract", "run_id", "label", "endpoint", "model", "dataset", "dataset_sha256",
                "system_prompt_matches",
                "created", "settings", "n_items", "item_ids", "n_parsed", "parse",
                "schema_valid_rate", "per_field_accuracy", "per_field_accuracy_when_parsed",
                "requested_action", "overall_exact_match", "overall_exact_match_fields",
                "invented", "per_class", "urgency_errors", "review", "seconds_total",
                "seconds_per_item_median", "items", "limitations", "skipped_dataset_lines"]:
        assert key in on_disk, key
    assert on_disk["contract"] == "eval-summary/1"
    assert list(on_disk["per_field_accuracy"]) == du.RECORD_FIELDS
    assert len(on_disk["items"]) == 20


def test_rows_file_is_one_line_per_ticket_and_field(three_runs):
    out_dir, summaries = three_runs
    rows = du.load_jsonl(out_dir / f"{summaries[0]['run_id']}_rows.jsonl")
    assert {row["score_type"] for row in rows} == {"exact", "similarity", "schema"}
    for row in rows:
        assert list(row) == ["run_id", "label", "endpoint", "model", "item_id", "field",
                             "expected", "predicted", "score", "correct", "score_type"]
    # The summary can be rebuilt from the rows: they say the same thing.
    urgency = [row for row in rows if row["field"] == "urgency"]
    assert sum(row["correct"] for row in urgency) / 20 == summaries[0]["per_field_accuracy"]["urgency"]
    schema = [row for row in rows if row["field"] == "(schema)"]
    assert sum(row["correct"] for row in schema) / 20 == summaries[0]["schema_valid_rate"]


def test_three_runs_compose_into_one_table(three_runs):
    out_dir, summaries = three_runs
    comparison = run_eval.compare_summaries(summaries)
    assert [run["name"] for run in comparison["runs"]] == ["base", "tuned", "base+retrieval"]

    by_metric = {entry["metric"]: entry["values"] for entry in comparison["metrics"]}
    assert by_metric["schema_valid_rate"] == {"base": 0.5, "tuned": 1.0, "base+retrieval": 0.9}
    assert by_metric["urgency"] == {"base": 0.5, "tuned": 0.8, "base+retrieval": 0.75}
    assert by_metric["category"] == {"base": 1.0, "tuned": 1.0, "base+retrieval": 1.0}
    assert len(comparison["per_item"]) == 20
    for line in comparison["per_item"]:
        assert set(line["exact_fields_correct"]) == {"base", "tuned", "base+retrieval"}

    # per-class counts add back up to the per-field totals
    for run in ["base", "tuned", "base+retrieval"]:
        right = sum(line["field_correct"][run] for line in comparison["per_class"]["urgency"])
        assert right == round(by_metric["urgency"][run] * 20)

    table = run_eval.render_comparison(comparison)
    assert table.isascii()
    assert max(len(line) for line in table.splitlines()) <= 100
    assert "thin" in table


def test_compare_cli_writes_json_and_table(three_runs):
    out_dir, summaries = three_runs
    paths = [out_dir / f"{summary['run_id']}_summary.json" for summary in summaries]
    result = run_cli("--compare", *paths, "--out", out_dir / "cmp")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "COMPARISON" in result.stdout
    written = json.loads((out_dir / "cmp" / "comparison.json").read_text(encoding="utf-8"))
    assert written["contract"] == "eval-comparison/1"


def test_compare_refuses_runs_on_different_questions(tmp_path, heldout_answers):
    full = run_with(make_fake_model(heldout_answers, 0, 0), tmp_path, "full")
    short = run_with(make_fake_model(heldout_answers, 0, 0), tmp_path, "short", limit=5)
    with pytest.raises(run_eval.EvalError) as caught:
        run_eval.compare_summaries([full, short])
    assert "same questions" in str(caught.value)


def test_compare_rejects_files_that_are_not_summaries(three_runs):
    out_dir, summaries = three_runs
    rows_file = out_dir / f"{summaries[0]['run_id']}_rows.jsonl"
    summary_file = out_dir / f"{summaries[0]['run_id']}_summary.json"
    result = run_cli("--compare", summary_file, rows_file)
    assert result.returncode == 2
    assert "Traceback" not in result.stdout + result.stderr


# ---------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------


def test_report_is_ascii_100_columns_and_states_its_limits(three_runs):
    out_dir, summaries = three_runs
    report = (out_dir / f"{summaries[0]['run_id']}_report.txt").read_text(encoding="utf-8")
    assert report.isascii()
    assert max(len(line) for line in report.splitlines()) <= 100
    assert "READ THIS BEFORE QUOTING A NUMBER" in report
    assert "one ticket is 5 percentage points" in report
    assert "Thin classes" in report
    assert "floor" in report
    # the four measurements each have their own heading
    for heading in ["1. FORMAT", "2. FIELDS", "3. WHOLE RECORD", "4. INVENTED", "5. PER CLASS"]:
        assert heading in report


def test_everything_printed_is_plain_ascii():
    assert run_eval.ascii_safe("pull it \u2014 or \u201cregister\u201d it\u2026") == 'pull it - or "register" it...'
    assert run_eval.ascii_safe("\u0639\u0627\u062c\u0644").isascii()
    assert run_eval.one_line("a\n  b \u2013 c", 40) == "a b - c"


def test_thin_classes_are_named_in_the_summary(three_runs):
    _, summaries = three_runs
    per_class = summaries[0]["per_class"]
    assert per_class["category"]["erp"]["n"] == 2
    assert per_class["category"]["erp"]["thin"] is True
    assert per_class["category"]["access"]["thin"] is False
    thin_note = [note for note in summaries[0]["limitations"] if note.startswith("Thin classes")]
    assert len(thin_note) == 1
    assert "category=erp (n=2)" in thin_note[0]
    assert "impact=enterprise (n=1)" in thin_note[0]
