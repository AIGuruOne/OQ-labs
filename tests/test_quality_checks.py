"""Tests for scripts/quality_checks.py.

    python -m pytest tests/test_quality_checks.py -v

Four groups:

  * against the ANSWER KEY - on the committed dataset every planted
    problem is found, on the right line, with the right kind, and
    nothing else is flagged (precision = recall = 1.0 per check);
  * problems the planter never makes (nulls, wrong types, a reworded
    copy that crossed the split, ...) built by hand here;
  * a clean dataset reports clean; broken input fails with a sentence
    and an exit code, never a stack trace;
  * the design promises: any one check can be removed, and nothing
    ever "fixes" the class imbalance.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_utils as du  # noqa: E402
import quality_checks as qc  # noqa: E402

FINETUNE_DIR = REPO_ROOT / "data" / "finetune"
SCRIPT = REPO_ROOT / "scripts" / "quality_checks.py"


def run_cli(*args):
    command = [sys.executable, str(SCRIPT), *[str(arg) for arg in args]]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")


def results_by_check(dataset, **kwargs):
    return {result["check"]: result for result in qc.run_checks(dataset, **kwargs)}


@pytest.fixture(scope="module")
def planted():
    return json.loads((FINETUNE_DIR / "planted_problems.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def committed():
    return qc.load_dataset(FINETUNE_DIR)


@pytest.fixture(scope="module")
def committed_results(committed):
    return results_by_check(committed)


@pytest.fixture(scope="module")
def clean_dir(tmp_path_factory):
    """A dataset with nothing planted, built by the real builder."""
    folder = tmp_path_factory.mktemp("clean")
    command = [sys.executable, str(REPO_ROOT / "scripts" / "build_dataset.py"), "--seed", "42",
               "--no-plant", "--finetune-dir", str(folder / "finetune"), "--eval-dir", str(folder / "eval")]
    built = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert built.returncode == 0, built.stdout + built.stderr
    return folder / "finetune"


def good_pair(ticket_id, body, **record_changes):
    """One valid pair, for hand-made datasets. record_changes edits the record."""
    record = {
        "category": "access", "affected_system": "Myportal", "asset_tag": "LAP-04412",
        "urgency": "low", "impact": "single_user",
        "requested_action": "Reset the user's password", "routing_queue": "identity_access",
    }
    record.update(record_changes)
    ticket = {"ticket_id": ticket_id, "subject": "help", "body": body}
    return du.build_pair(ticket, record)


def write_dataset(folder, train_pairs, val_pairs=None):
    du.write_jsonl(folder / "train.jsonl", train_pairs)
    if val_pairs is not None:
        du.write_jsonl(folder / "val.jsonl", val_pairs)
    return folder


# Forty bodies with no words in common, so no two look alike by accident.
DISTINCT_BODIES = [" ".join(f"word{n}x{k}" for k in range(12)) for n in range(40)]


# ---------------------------------------------------------------------
# Against the answer key
# ---------------------------------------------------------------------


def test_near_duplicates_match_the_answer_key_exactly(committed_results, planted):
    found = {(f["file"], frozenset([f["first_line"], f["second_line"]]),
              frozenset([f["first_id"], f["second_id"]]))
             for f in committed_results["near_duplicates"]["findings"]}
    truth = {(e["split"] + ".jsonl", frozenset([e["line"], e["duplicate_of_line"]]),
              frozenset([e["ticket_id"], e["duplicate_of"]]))
             for e in planted["near_duplicates"]}
    assert len(truth) == 20
    assert found == truth


def test_leakage_matches_the_answer_key_exactly(committed_results, planted):
    found = {(f["ticket_id"], tuple(f["train_lines"]), tuple(f["val_lines"]))
             for f in committed_results["leakage"]["findings"]}
    truth = {(e["ticket_id"], (e["train_line"],), (e["val_line"],)) for e in planted["leakage"]}
    assert len(truth) == 5
    assert found == truth


def test_schema_violations_match_the_answer_key_line_field_and_kind(committed_results, planted):
    found = {(f["file"], f["line"], f["ticket_id"], f["field"], f["kind"])
             for f in committed_results["schema"]["findings"]}
    truth = {(e["split"] + ".jsonl", e["line"], e["ticket_id"], e["field"], e["kind"])
             for e in planted["schema_violations"]}
    assert len(truth) == 10
    assert found == truth


def test_hard_checks_fail_and_soft_checks_only_warn(committed, committed_results):
    statuses = {name: result["status"] for name, result in committed_results.items()}
    assert statuses == {"near_duplicates": "FAIL", "leakage": "FAIL", "schema": "FAIL",
                        "coverage": "WARN", "imbalance": "WARN"}
    assert qc.has_hard_failures(committed, list(committed_results.values()))


def test_imbalance_reports_the_real_mix(committed_results):
    by_field = {(f["file"], f["field"]): f for f in committed_results["imbalance"]["findings"]}
    category = by_field[("train.jsonl", "category")]
    assert category["most_common"] == "access"
    assert category["rarest"] == "erp"
    assert category["ratio"] >= 5


def test_coverage_flags_the_rare_values(committed_results):
    flagged = {(f["file"], f["field"], f["value"]) for f in committed_results["coverage"]["findings"]}
    assert ("train.jsonl", "impact", "enterprise") in flagged
    assert ("val.jsonl", "category", "erp") in flagged


# ---------------------------------------------------------------------
# The report itself: readable in 90 seconds
# ---------------------------------------------------------------------


def test_report_on_the_committed_dataset(committed_results):
    result = run_cli("--dataset", FINETUNE_DIR)
    assert result.returncode == 1
    assert "Traceback" not in result.stdout + result.stderr

    lines = result.stdout.splitlines()
    assert len(lines) <= 100, "the report has grown into a wall of text"
    assert max(len(line) for line in lines[1:]) <= 100, "a line no longer fits a laptop terminal"

    # Everything a participant must FIX (checks 1-3) is on the first
    # screen; the warnings, with their bar charts, come after.
    first_warning_section = next(n for n, line in enumerate(lines) if line.startswith("[4] "))
    assert first_warning_section <= 50
    assert result.stdout.isascii(), "non-ASCII output breaks on a Windows console"

    # The verdict is in the first ten lines: what was found, and how many.
    summary = "\n".join(lines[:10])
    for expected in ["NEAR-DUPLICATES        20 pairs", "TRAIN/VAL LEAKAGE      5 rows",
                     "SCHEMA VIOLATIONS      10 rows"]:
        assert expected in summary

    # Every hard finding section names a concrete row.
    assert "train.jsonl:" in result.stdout and "val.jsonl:" in result.stdout
    assert "Look at one:" in result.stdout
    assert "RESULT: FAIL" in lines[-1]


def test_near_duplicate_example_is_a_listed_pair_and_not_the_easy_one(committed_results):
    result = committed_results["near_duplicates"]
    listed = result["lines"][:qc.LISTED_BY_DEFAULT]
    example = result["example"]

    # The example is one of the pairs the report always lists...
    first_place = example[0].split()[0]          # "train.jsonl:39"
    assert any(f" {first_place} " in line for line in listed)
    # ...but not the top one, which differs only by its greeting...
    assert f" {first_place} " not in listed[0]
    # ...and the wording really differs on both sides.
    only_first = example[2].split(":", 1)[1].split(",")
    only_second = example[3].split(":", 1)[1].split(",")
    assert len(only_first) + len(only_second) >= 5


def test_all_flag_lists_every_near_duplicate():
    result = run_cli("--dataset", FINETUNE_DIR, "--all")
    assert result.stdout.count("   ~   ") == 20
    assert "more - add --all" not in result.stdout


# ---------------------------------------------------------------------
# Problems the planter never makes
# ---------------------------------------------------------------------


def test_every_kind_of_schema_violation_is_named(tmp_path):
    pairs = [
        good_pair("INC-000001", DISTINCT_BODIES[1], urgency=None),
        good_pair("INC-000002", DISTINCT_BODIES[2], requested_action=None),
        good_pair("INC-000003", DISTINCT_BODIES[3], impact=3),
        good_pair("INC-000004", DISTINCT_BODIES[4], asset_tag=4412),
        good_pair("INC-000005", DISTINCT_BODIES[5], notes="added by hand"),
        good_pair("INC-000006", DISTINCT_BODIES[6], affected_system=""),
        good_pair("INC-000007", DISTINCT_BODIES[7], category="Access"),
        good_pair("INC-000008", DISTINCT_BODIES[8], asset_tag="LAP-4412"),
        good_pair("INC-000009", DISTINCT_BODIES[9], requested_action="Reset it. Then call the user back."),
        good_pair("INC-000010", DISTINCT_BODIES[10]),
    ]
    pairs[9]["messages"][2]["content"] = 'Here is the JSON: {"category": "access"}'
    pairs.append(good_pair("INC-000011", DISTINCT_BODIES[11]))  # the only valid row

    dataset = qc.load_dataset(write_dataset(tmp_path, pairs))
    findings = qc.check_schema(dataset)["findings"]
    kind_on_line = {finding["line"]: finding["kind"] for finding in findings}
    assert kind_on_line == {
        1: "null_not_allowed", 2: "null_not_allowed", 3: "wrong_type", 4: "wrong_type",
        5: "unexpected_field", 6: "empty_value", 7: "invalid_enum_value",
        8: "malformed_asset_tag", 9: "stray_prose", 10: "completion_not_json",
    }


def test_a_reworded_copy_across_the_split_is_leakage(tmp_path):
    body = "my password for the portal expired while i was on leave please reset it today thanks"
    reworded = "hello " + body.replace("please", "kindly")
    train = [good_pair("INC-000001", body), good_pair("INC-000002", DISTINCT_BODIES[2])]
    val = [good_pair("INC-000777", reworded), good_pair("INC-000003", DISTINCT_BODIES[3])]

    dataset = qc.load_dataset(write_dataset(tmp_path, train, val))
    findings = qc.check_leakage(dataset)["findings"]
    assert len(findings) == 1
    assert findings[0]["ticket_id"] == "INC-000777"
    assert findings[0]["train_lines"] == [1] and findings[0]["val_lines"] == [1]
    assert "INC-000001" in findings[0]["how"]
    # ...and it is NOT double-reported as a near-duplicate inside a split.
    assert qc.check_near_duplicates(dataset)["findings"] == []


def test_an_exact_copy_inside_one_file_is_a_near_duplicate(tmp_path):
    pairs = [good_pair("INC-000001", DISTINCT_BODIES[1]), good_pair("INC-000002", DISTINCT_BODIES[2]),
             good_pair("INC-000001", DISTINCT_BODIES[1])]
    dataset = qc.load_dataset(write_dataset(tmp_path, pairs))
    findings = qc.check_near_duplicates(dataset)["findings"]
    assert [(f["first_line"], f["second_line"], f["similarity"]) for f in findings] == [(1, 3, 1.0)]


def test_an_absent_enum_value_is_a_coverage_gap(tmp_path):
    pairs = [good_pair(f"INC-{n:06d}", DISTINCT_BODIES[n]) for n in range(12)]
    dataset = qc.load_dataset(write_dataset(tmp_path, pairs))
    result = qc.check_coverage(dataset)
    absent = {(f["field"], f["value"]) for f in result["findings"] if f["kind"] == "absent"}
    assert ("category", "telecom") in absent
    assert ("asset_tag", "null") in absent          # no row teaches the model to say null
    assert ("category", "access") not in absent
    assert "ABSENT" in "\n".join(result["lines"])


# ---------------------------------------------------------------------
# Clean data reports clean
# ---------------------------------------------------------------------


def test_clean_dataset_reports_clean_and_exits_zero(clean_dir):
    result = run_cli("--dataset", clean_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    for title in ["NEAR-DUPLICATES", "TRAIN/VAL LEAKAGE", "SCHEMA VIOLATIONS"]:
        assert f"PASS  1. {title}" in result.stdout or f". {title}" in result.stdout
    assert result.stdout.count("  PASS  ") == 3
    assert "FAIL" not in result.stdout.replace("RESULT: OK", "")
    # The imbalance is still there, still a warning, still not "fixed".
    assert "WARN  5. CLASS IMBALANCE" in result.stdout
    assert "RESULT: OK" in result.stdout


def test_single_file_skips_leakage_and_still_runs_the_rest(clean_dir):
    result = run_cli("--dataset", clean_dir / "train.jsonl")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIP  2. TRAIN/VAL LEAKAGE" in result.stdout
    assert "add --val" in result.stdout


def test_file_plus_val_argument_checks_leakage():
    result = run_cli("--dataset", FINETUNE_DIR / "train.jsonl", "--val", FINETUNE_DIR / "val.jsonl")
    assert result.returncode == 1
    assert "FAIL  2. TRAIN/VAL LEAKAGE      5 rows" in result.stdout


# ---------------------------------------------------------------------
# Broken input: a sentence and an exit code, never a stack trace
# ---------------------------------------------------------------------


def assert_graceful(result, exit_code, *expected_words):
    output = result.stdout + result.stderr
    assert result.returncode == exit_code, output
    assert "Traceback" not in output
    for word in expected_words:
        assert word in output, output


def test_truncated_file_names_the_line_and_checks_the_rest(tmp_path, clean_dir):
    whole = (clean_dir / "train.jsonl").read_bytes()
    (tmp_path / "train.jsonl").write_bytes(whole[: len(whole) // 2 + 37])  # cut mid-line
    result = run_cli("--dataset", tmp_path / "train.jsonl")
    assert_graceful(result, 1, "UNREADABLE LINES", "not valid JSON", "truncated", "train.jsonl:2")
    assert "PASS  3. SCHEMA VIOLATIONS" in result.stdout  # the readable half was still checked


def test_empty_file(tmp_path):
    (tmp_path / "train.jsonl").write_text("", encoding="utf-8")
    assert_graceful(run_cli("--dataset", tmp_path / "train.jsonl"), 2, "CANNOT CHECK", "empty")


def test_raw_tickets_are_not_pairs():
    raw = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"
    assert_graceful(run_cli("--dataset", raw), 2, "CANNOT CHECK", "messages", "build_dataset.py")


def test_missing_path(tmp_path):
    assert_graceful(run_cli("--dataset", tmp_path / "nope.jsonl"), 2, "CANNOT CHECK", "does not exist")


def test_folder_without_train_file(tmp_path):
    assert_graceful(run_cli("--dataset", tmp_path), 2, "CANNOT CHECK", "no train.jsonl")


def test_binary_file(tmp_path):
    (tmp_path / "train.jsonl").write_bytes(bytes(range(256)) * 20)
    assert_graceful(run_cli("--dataset", tmp_path / "train.jsonl"), 2, "CANNOT CHECK", "UTF-8")


def test_not_json_at_all(tmp_path):
    (tmp_path / "train.jsonl").write_text("ticket_id,subject,body\nINC-1,hi,there\n", encoding="utf-8")
    assert_graceful(run_cli("--dataset", tmp_path / "train.jsonl"), 2, "CANNOT CHECK", "not valid JSON")


def test_broken_schema_file(tmp_path, clean_dir):
    (tmp_path / "schema.json").write_text("{ not json", encoding="utf-8")
    result = run_cli("--dataset", clean_dir, "--schema", tmp_path / "schema.json")
    assert_graceful(result, 2, "CANNOT CHECK", "schema")


def test_windows_bom_is_tolerated(tmp_path, clean_dir):
    text = (clean_dir / "train.jsonl").read_text(encoding="utf-8")
    (tmp_path / "train.jsonl").write_text(text, encoding="utf-8-sig")
    assert_graceful(run_cli("--dataset", tmp_path / "train.jsonl"), 0, "RESULT: OK")


# ---------------------------------------------------------------------
# Design promises
# ---------------------------------------------------------------------


@pytest.mark.parametrize("removed", qc.CHECKS, ids=lambda check: check.__name__)
def test_any_one_check_can_be_removed(committed, committed_results, removed):
    remaining = [check for check in qc.CHECKS if check is not removed]
    results = qc.run_checks(committed, checks=remaining)
    assert len(results) == 4
    for result in results:
        assert result["findings"] == committed_results[result["check"]]["findings"]


def test_a_check_left_as_a_todo_does_not_break_the_report(committed, capsys):
    def check_schema(dataset, options):
        raise NotImplementedError

    checks = [check_schema if check is qc.check_schema else check for check in qc.CHECKS]
    results = qc.run_checks(committed, checks=checks)
    assert [result["status"] for result in results] == ["FAIL", "FAIL", "TODO", "WARN", "WARN"]

    qc.print_report(committed, results)
    printed = capsys.readouterr().out
    assert "TODO  3. SCHEMA" in printed
    assert "check_schema is not written yet" in printed


def test_nothing_rebalances_the_data(committed):
    before = copy.deepcopy(committed)
    qc.run_checks(committed)
    assert committed == before, "a check modified the dataset it was given"

    public_names = [name for name in dir(qc) if not name.startswith("_")]
    for name in public_names:
        for word in ["rebalance", "resample", "oversample", "undersample"]:
            assert word not in name.lower(), f"{name}: imbalance is reported, never auto-corrected"
