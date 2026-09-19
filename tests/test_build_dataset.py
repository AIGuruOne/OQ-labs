"""Tests for scripts/build_dataset.py and notebooks/dataset_utils.py.

    python -m pytest tests/test_build_dataset.py -v

Two groups:

  * the COMMITTED files keep their promises - held-out never in
    train/val, every planted problem present and findable, nothing
    extra found;
  * the builder still REPRODUCES the committed files byte for byte, so
    an edit to the builder, the prompt or the corpus without a rebuild
    fails here, not on Day 2.

The checks here are written independently of the builder's own verify
step where it is cheap to do so (they read the files, not the
builder's variables).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import dataset_utils as du  # noqa: E402

FINETUNE_DIR = REPO_ROOT / "data" / "finetune"
EVAL_DIR = REPO_ROOT / "data" / "eval"
COMMITTED_SEED = 42

BUILT_FILES = [
    (FINETUNE_DIR, "train.jsonl"),
    (FINETUNE_DIR, "val.jsonl"),
    (FINETUNE_DIR, "split_manifest.json"),
    (FINETUNE_DIR, "planted_problems.json"),
    (EVAL_DIR, "heldout_20.jsonl"),
]


@pytest.fixture(scope="module")
def train():
    return du.load_jsonl(FINETUNE_DIR / "train.jsonl")


@pytest.fixture(scope="module")
def val():
    return du.load_jsonl(FINETUNE_DIR / "val.jsonl")


@pytest.fixture(scope="module")
def heldout():
    return du.load_jsonl(EVAL_DIR / "heldout_20.jsonl")


@pytest.fixture(scope="module")
def planted():
    return json.loads((FINETUNE_DIR / "planted_problems.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return du.load_schema(FINETUNE_DIR / "ticket_schema.json")


@pytest.fixture(scope="module")
def labels_by_id():
    labels = du.load_jsonl(FINETUNE_DIR / "ticket_labels.jsonl")
    return {label["ticket_id"]: label for label in labels}


# ---------------------------------------------------------------------
# Sizes and format
# ---------------------------------------------------------------------


def test_split_sizes(train, val, heldout):
    assert len(train) == 400
    assert len(val) == 80
    assert len(heldout) == 20


def test_every_row_has_the_pair_format(train, val, heldout):
    for pair in train + val + heldout:
        assert sorted(pair) == ["messages", "ticket_id"]
        roles = [message["role"] for message in pair["messages"]]
        assert roles == ["system", "user", "assistant"]
        assert pair["messages"][0]["content"] == du.SYSTEM_PROMPT
        assert pair["messages"][1]["content"].startswith("Subject: ")


def test_completion_is_json_and_nothing_else(train, val, heldout):
    for pair in train + val + heldout:
        text = du.pair_completion_text(pair)
        assert text.startswith("{") and text.endswith("}")
        assert "\n" not in text
        json.loads(text)


def test_system_prompt_names_every_enum_value(schema):
    for field in ["category", "urgency", "impact"]:
        for value in schema["properties"][field]["enum"]:
            assert f'"{value}"' in du.SYSTEM_PROMPT, f"{field} value {value} missing from the prompt"


def test_system_prompt_names_every_routing_queue(labels_by_id):
    queues = {label["record"]["routing_queue"] for label in labels_by_id.values()}
    for queue in queues:
        assert f'"{queue}"' in du.SYSTEM_PROMPT


# ---------------------------------------------------------------------
# The held-out 20
# ---------------------------------------------------------------------


def test_heldout_never_appears_in_train_or_val(train, val, heldout):
    heldout_ids = {pair["ticket_id"] for pair in heldout}
    other_ids = {pair["ticket_id"] for pair in train + val}
    assert heldout_ids & other_ids == set()

    heldout_texts = {du.pair_user_text(pair) for pair in heldout}
    other_texts = {du.pair_user_text(pair) for pair in train + val}
    assert heldout_texts & other_texts == set()


def test_heldout_has_no_lookalike_in_train_or_val(train, val, heldout):
    for held in heldout:
        for other in train + val:
            similarity = du.text_similarity(du.pair_user_text(held), du.pair_user_text(other))
            assert similarity < 0.6, f"{held['ticket_id']} ~ {other['ticket_id']} = {similarity:.2f}"


def test_heldout_is_stratified(heldout, labels_by_id):
    records = [du.parse_completion(pair) for pair in heldout]
    assert {record["category"] for record in records} == {
        "access", "hardware", "software", "network", "erp", "telecom", "other"}
    assert sum(record["urgency"] == "critical" for record in records) >= 1
    assert sum(record["impact"] == "enterprise" for record in records) >= 1
    assert {record["urgency"] for record in records} == {"low", "medium", "high", "critical"}

    arguable = 0
    for pair in heldout:
        features = labels_by_id[pair["ticket_id"]]["meta"]["features"]
        if "tone_urgent" in features or "two_problems" in features:
            arguable += 1
    assert arguable >= 4, "too few tickets where urgency is arguable"


def test_heldout_is_clean_and_matches_ground_truth(heldout, schema, labels_by_id):
    validator = Draft202012Validator(schema)
    for pair in heldout:
        record = du.parse_completion(pair)
        assert list(validator.iter_errors(record)) == []
        assert record == labels_by_id[pair["ticket_id"]]["record"]
        assert list(record) == du.RECORD_FIELDS


# ---------------------------------------------------------------------
# The planted problems: present, findable, and nothing else found
# ---------------------------------------------------------------------


def test_planted_counts(planted):
    assert len(planted["near_duplicates"]) == 20
    assert len(planted["leakage"]) == 5
    assert len(planted["schema_violations"]) == 10
    kinds = {entry["kind"] for entry in planted["schema_violations"]}
    assert kinds == {"invalid_enum_value", "missing_field", "stray_prose", "malformed_asset_tag"}


def test_no_row_carries_two_planted_problems(planted):
    touched = []
    for entry in planted["near_duplicates"]:
        touched.extend([entry["ticket_id"], entry["duplicate_of"]])
    touched.extend(entry["ticket_id"] for entry in planted["leakage"])
    touched.extend(entry["ticket_id"] for entry in planted["schema_violations"])
    assert len(touched) == len(set(touched))


def test_near_duplicates_are_reworded_not_copied(train, planted, labels_by_id):
    by_id = {pair["ticket_id"]: pair for pair in train}
    for entry in planted["near_duplicates"]:
        copy_pair = by_id[entry["ticket_id"]]
        source_pair = by_id[entry["duplicate_of"]]
        assert entry["ticket_id"] not in labels_by_id, "a planted id collides with a corpus ticket"
        assert du.pair_user_text(copy_pair) != du.pair_user_text(source_pair)
        assert du.pair_completion_text(copy_pair) == du.pair_completion_text(source_pair)
        similarity = du.text_similarity(du.pair_user_text(copy_pair), du.pair_user_text(source_pair))
        assert du.NEAR_DUPLICATE_THRESHOLD <= similarity < 1.0


def test_near_duplicate_check_finds_exactly_the_planted_pairs(train, val, planted):
    found = du.find_near_duplicates(train + val)
    found_keys = {frozenset([item["first"], item["second"]]) for item in found}
    found_keys = {key for key in found_keys if len(key) == 2}  # drop leaked self-pairs
    planted_keys = {frozenset([e["ticket_id"], e["duplicate_of"]]) for e in planted["near_duplicates"]}
    assert found_keys == planted_keys


def test_leakage_check_finds_exactly_the_planted_rows(train, val, planted):
    assert du.find_leakage(train, val) == sorted(e["ticket_id"] for e in planted["leakage"])


def test_leaked_rows_are_identical_in_both_splits(train, val, planted):
    train_by_id = {pair["ticket_id"]: pair for pair in train}
    val_by_id = {pair["ticket_id"]: pair for pair in val}
    for entry in planted["leakage"]:
        assert train_by_id[entry["ticket_id"]] == val_by_id[entry["ticket_id"]]


def test_schema_check_finds_exactly_the_planted_rows(train, val, planted, schema):
    for split_name, pairs in [("train", train), ("val", val)]:
        found_ids = sorted(item["ticket_id"] for item in du.find_schema_violations(pairs, schema))
        planted_ids = sorted(e["ticket_id"] for e in planted["schema_violations"] if e["split"] == split_name)
        assert found_ids == planted_ids


def test_planted_violation_is_on_the_recorded_line_and_field(train, val, planted):
    rows = {"train": train, "val": val}
    for entry in planted["schema_violations"]:
        pair = rows[entry["split"]][entry["line"] - 1]
        assert pair["ticket_id"] == entry["ticket_id"]
        record = du.parse_completion(pair)
        if entry["kind"] == "missing_field":
            assert entry["field"] not in record
        else:
            assert record[entry["field"]] == entry["planted"]
            assert record[entry["field"]] != entry["original"]


def test_unplanted_rows_match_ground_truth(train, val, planted, labels_by_id):
    skip = {e["ticket_id"] for e in planted["schema_violations"]}
    skip |= {e["ticket_id"] for e in planted["near_duplicates"]}
    for pair in train + val:
        if pair["ticket_id"] in skip:
            continue
        assert du.parse_completion(pair) == labels_by_id[pair["ticket_id"]]["record"]


def test_class_mix_is_left_imbalanced(train):
    counts = du.count_record_field(train, "category")
    assert counts["access"] >= 5 * counts["erp"], "the category mix must stay realistically imbalanced"


# ---------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------


def run_builder(tmp_path, *extra_args):
    command = [
        sys.executable, str(REPO_ROOT / "scripts" / "build_dataset.py"),
        "--finetune-dir", str(tmp_path / "finetune"),
        "--eval-dir", str(tmp_path / "eval"),
        "--seed", str(COMMITTED_SEED), *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8")


def test_committed_files_match_the_builder(tmp_path):
    result = run_builder(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    message = "builder, prompt or corpus changed - rerun scripts/build_dataset.py and rebuild downstream"
    for committed_dir, name in BUILT_FILES:
        rebuilt_dir = tmp_path / ("eval" if committed_dir == EVAL_DIR else "finetune")
        assert (rebuilt_dir / name).read_bytes() == (committed_dir / name).read_bytes(), f"{name}: {message}"


def test_builder_refuses_sizes_the_corpus_cannot_supply(tmp_path):
    # 580 tickets are left after the held-out 20, so 500 + 100 cannot be
    # supplied. The builder must say so, not write a short val.jsonl.
    result = run_builder(tmp_path, "--no-plant", "--train-size", "500", "--val-size", "100")
    assert result.returncode != 0
    assert "Not enough tickets" in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    assert not (tmp_path / "finetune" / "train.jsonl").exists(), "a short dataset was written anyway"


def test_no_plant_build_is_clean_and_keeps_the_same_heldout(tmp_path, schema):
    result = run_builder(tmp_path, "--no-plant")
    assert result.returncode == 0, result.stdout + result.stderr

    clean_train = du.load_jsonl(tmp_path / "finetune" / "train.jsonl")
    clean_val = du.load_jsonl(tmp_path / "finetune" / "val.jsonl")
    assert len(clean_train) == 400 and len(clean_val) == 80
    assert du.find_near_duplicates(clean_train + clean_val) == []
    assert du.find_leakage(clean_train, clean_val) == []
    assert du.find_schema_violations(clean_train + clean_val, schema) == []
    assert not (tmp_path / "finetune" / "planted_problems.json").exists()

    # The held-out 20 must not depend on whether problems were planted.
    rebuilt = (tmp_path / "eval" / "heldout_20.jsonl").read_bytes()
    assert rebuilt == (EVAL_DIR / "heldout_20.jsonl").read_bytes()
