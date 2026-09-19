"""Build the fine-tuning dataset from the raw ticket corpus.

    python scripts/build_dataset.py --seed 42

Reads:
    --tickets   corpus/tickets/tickets_raw.jsonl     raw tickets (Contract 1)
    --labels    data/finetune/ticket_labels.jsonl    ground-truth records
    --schema    data/finetune/ticket_schema.json     the frozen 8B schema

Writes:
    <finetune-dir>/train.jsonl              400 pairs
    <finetune-dir>/val.jsonl                 80 pairs
    <eval-dir>/heldout_20.jsonl              20 pairs, never in train or val
    <finetune-dir>/split_manifest.json      which ticket went where
    <finetune-dir>/planted_problems.json    FACILITATOR answer key

The steps, in order:
    1. join      raw tickets + labels -> examples
    2. hold out  the 20 eval tickets, stratified (not random)
    3. split     the rest into train / val, stratified by category
    4. pair      every example -> {"ticket_id", "messages"} (see
                 notebooks/dataset_utils.py for the format and why)
    5. plant     the quality problems the Day 2 lab finds
                 (scripts/plant_problems.py; skip with --no-plant)
    6. verify    held-out never overlaps train/val; plants are findable
    7. write

Deterministic: same inputs + same --seed -> byte-identical files.
tests/test_build_dataset.py fails if the committed files disagree.
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_utils as du  # noqa: E402
import plant_problems as plant  # noqa: E402


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ids_of(pairs):
    return [pair["ticket_id"] for pair in pairs]


def print_distribution(title, pairs, field):
    counts = du.count_record_field(pairs, field)
    total = len(pairs)
    print(f"  {title} ({total} rows) by {field}:")
    for value, count in counts.items():
        share = 100 * count / total
        print(f"    {str(value):<20} {count:>4}  {share:5.1f}%")


def build(args):
    # --- 1. join ---------------------------------------------------------
    tickets = du.load_jsonl(args.tickets)
    labels = du.load_jsonl(args.labels)
    schema = du.load_schema(args.schema)
    examples = du.join_tickets_and_labels(tickets, labels)
    print(f"Loaded {len(tickets)} tickets and {len(labels)} labels -> {len(examples)} examples")

    # --- 2. hold out the 20 ----------------------------------------------
    heldout_examples = du.select_heldout(examples, args.seed)
    heldout_ids = {example["ticket"]["ticket_id"] for example in heldout_examples}

    # --- 3. split the rest -------------------------------------------------
    pool = [e for e in examples if e["ticket"]["ticket_id"] not in heldout_ids]

    clean_train_size = args.train_size
    clean_val_size = args.val_size
    if not args.no_plant:
        # Planting ADDS rows (20 near-duplicates to train, 5 leaked rows
        # to val), so draw that many fewer and land on the target size.
        clean_train_size -= plant.NEAR_DUPLICATE_COUNT
        clean_val_size -= plant.LEAKAGE_COUNT

    train_examples, val_examples, unused_examples = du.split_train_val(
        pool, clean_train_size, clean_val_size, args.seed
    )

    # --- 4. pair -------------------------------------------------------------
    heldout_pairs = [du.build_pair(e["ticket"], e["record"]) for e in heldout_examples]
    train_pairs = [du.build_pair(e["ticket"], e["record"]) for e in train_examples]
    val_pairs = [du.build_pair(e["ticket"], e["record"]) for e in val_examples]

    # --- 5. plant ------------------------------------------------------------
    planted = None
    if not args.no_plant:
        rng = random.Random(args.seed + 1000)
        used_ids = {ticket["ticket_id"] for ticket in tickets}
        protected_ids = set()

        duplicate_pairs, duplicate_entries = plant.plant_near_duplicates(
            train_examples, used_ids, protected_ids, rng
        )
        leaked_pairs, leakage_entries = plant.plant_leakage(train_pairs, protected_ids, rng)
        violation_entries = plant.plant_schema_violations(train_pairs, val_pairs, protected_ids, rng)

        train_pairs = train_pairs + duplicate_pairs
        val_pairs = val_pairs + leaked_pairs
        # Shuffle so the plants are not sitting in a block at the end.
        rng.shuffle(train_pairs)
        rng.shuffle(val_pairs)

        planted = {
            "note": "FACILITATOR ANSWER KEY. Problems planted on purpose by "
                    "scripts/plant_problems.py for the Day 2 S10 lab. Not for participants.",
            "seed": args.seed,
            "near_duplicate_measure": "Jaccard similarity of lowercase word sets, "
                                      "subject + body (dataset_utils.text_similarity)",
            "near_duplicate_threshold": du.NEAR_DUPLICATE_THRESHOLD,
            "near_duplicates": duplicate_entries,
            "leakage": leakage_entries,
            "schema_violations": violation_entries,
        }
        add_line_numbers(planted, train_pairs, val_pairs)

    # --- 6. verify -------------------------------------------------------------
    verify(heldout_pairs, train_pairs, val_pairs, schema, planted)

    # --- 7. write ----------------------------------------------------------------
    train_path = du.write_jsonl(args.finetune_dir / "train.jsonl", train_pairs)
    val_path = du.write_jsonl(args.finetune_dir / "val.jsonl", val_pairs)
    heldout_path = du.write_jsonl(args.eval_dir / "heldout_20.jsonl", heldout_pairs)

    manifest = {
        "seed": args.seed,
        "note": "train/val list the CLEAN split. Rows added by planting "
                "are in planted_problems.json, not here.",
        "heldout": sorted(heldout_ids),
        "train": sorted(e["ticket"]["ticket_id"] for e in train_examples),
        "val": sorted(e["ticket"]["ticket_id"] for e in val_examples),
        "unused": sorted(e["ticket"]["ticket_id"] for e in unused_examples),
    }
    manifest_path = write_json(args.finetune_dir / "split_manifest.json", manifest)
    written = [train_path, val_path, heldout_path, manifest_path]
    if planted is not None:
        written.append(write_json(args.finetune_dir / "planted_problems.json", planted))

    # --- report --------------------------------------------------------------------
    print()
    print("SPLIT SIZES")
    print(f"  train      {len(train_pairs):>4}")
    print(f"  val        {len(val_pairs):>4}")
    print(f"  heldout    {len(heldout_pairs):>4}")
    print(f"  unused     {len(unused_examples):>4}   (tickets in no split; see split_manifest.json)")
    print()
    print("PER-CLASS DISTRIBUTION")
    for title, pairs in [("train", train_pairs), ("val", val_pairs), ("heldout", heldout_pairs)]:
        print_distribution(title, pairs, "category")
    for field in ["urgency", "impact"]:
        print_distribution("heldout", heldout_pairs, field)
    print()
    print("FILES")
    for path in written:
        print(f"  {sha256_of(path)}  {path}")


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    return path


def add_line_numbers(planted, train_pairs, val_pairs):
    """Record the 1-based line of every planted row in its file."""
    line_of = {"train": {}, "val": {}}
    for line_number, pair in enumerate(train_pairs, start=1):
        line_of["train"][pair["ticket_id"]] = line_number
    for line_number, pair in enumerate(val_pairs, start=1):
        line_of["val"][pair["ticket_id"]] = line_number

    for entry in planted["near_duplicates"]:
        entry["line"] = line_of["train"][entry["ticket_id"]]
        entry["duplicate_of_line"] = line_of["train"][entry["duplicate_of"]]
    for entry in planted["leakage"]:
        entry["train_line"] = line_of["train"][entry["ticket_id"]]
        entry["val_line"] = line_of["val"][entry["ticket_id"]]
    for entry in planted["schema_violations"]:
        entry["line"] = line_of[entry["split"]][entry["ticket_id"]]


def verify(heldout_pairs, train_pairs, val_pairs, schema, planted):
    """Fail loudly if the build broke a promise. Prints what it checked."""
    print()
    print("VERIFY")

    # Promise 1: exactly 20 held-out, none of them in train or val.
    heldout_ids = set(ids_of(heldout_pairs))
    overlap = heldout_ids & (set(ids_of(train_pairs)) | set(ids_of(val_pairs)))
    assert len(heldout_pairs) == 20, f"heldout has {len(heldout_pairs)} rows, not 20"
    assert overlap == set(), f"held-out tickets leaked into train/val: {sorted(overlap)}"
    print("  [PASS] heldout has exactly 20 rows; ticket_id overlap with train+val = 0")

    # Promise 2: no held-out TEXT in train or val either (a reworded
    # copy would have a new id).
    cross = du.find_near_duplicates(heldout_pairs + train_pairs + val_pairs,
                                    du.HELDOUT_MAX_SIMILARITY)
    cross = [item for item in cross if item["first"] in heldout_ids or item["second"] in heldout_ids]
    assert cross == [], f"held-out tickets have lookalikes: {cross}"
    print(f"  [PASS] no train/val row is >= {du.HELDOUT_MAX_SIMILARITY} similar to a held-out ticket")

    # Promise 3: held-out is clean and covers what the evals need.
    assert du.find_schema_violations(heldout_pairs, schema) == []
    categories = du.count_record_field(heldout_pairs, "category")
    urgencies = du.count_record_field(heldout_pairs, "urgency")
    impacts = du.count_record_field(heldout_pairs, "impact")
    assert len(categories) == 7, f"heldout covers only {sorted(categories)}"
    assert urgencies.get("critical", 0) >= 1, "heldout has no critical ticket"
    assert impacts.get("enterprise", 0) >= 1, "heldout has no enterprise ticket"
    print("  [PASS] heldout: all 7 categories, >=1 critical, >=1 enterprise, schema-valid")

    if planted is None:
        assert du.find_near_duplicates(train_pairs + val_pairs) == []
        assert du.find_leakage(train_pairs, val_pairs) == []
        assert du.find_schema_violations(train_pairs + val_pairs, schema) == []
        print("  [PASS] --no-plant build: checks find nothing in train/val")
        return

    # Promise 4: the checks find EXACTLY what was planted. Nothing
    # missed, nothing extra.
    found_duplicates = du.find_near_duplicates(train_pairs + val_pairs)
    found_duplicate_keys = {frozenset([item["first"], item["second"]]) for item in found_duplicates}
    planted_duplicate_keys = {frozenset([e["ticket_id"], e["duplicate_of"]])
                              for e in planted["near_duplicates"]}
    # A leaked row is also a perfect duplicate of itself across splits;
    # those pairs have ONE id, so they are not near-duplicate findings.
    found_duplicate_keys = {key for key in found_duplicate_keys if len(key) == 2}
    assert found_duplicate_keys == planted_duplicate_keys, (
        f"near-duplicates: planted {len(planted_duplicate_keys)}, found {len(found_duplicate_keys)}"
    )
    print(f"  [PASS] near-duplicates: planted {len(planted_duplicate_keys)}, "
          f"found {len(found_duplicate_keys)}, identical sets")

    found_leaks = du.find_leakage(train_pairs, val_pairs)
    planted_leaks = sorted(entry["ticket_id"] for entry in planted["leakage"])
    assert found_leaks == planted_leaks
    print(f"  [PASS] leakage: planted {len(planted_leaks)}, found {len(found_leaks)}, identical sets")

    found_violations = du.find_schema_violations(train_pairs + val_pairs, schema)
    found_violation_ids = sorted(item["ticket_id"] for item in found_violations)
    planted_violation_ids = sorted(entry["ticket_id"] for entry in planted["schema_violations"])
    assert found_violation_ids == planted_violation_ids
    print(f"  [PASS] schema violations: planted {len(planted_violation_ids)}, "
          f"found {len(found_violation_ids)}, identical sets")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickets", type=Path, default=REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl")
    parser.add_argument("--labels", type=Path, default=REPO_ROOT / "data" / "finetune" / "ticket_labels.jsonl")
    parser.add_argument("--schema", type=Path, default=REPO_ROOT / "data" / "finetune" / "ticket_schema.json")
    parser.add_argument("--finetune-dir", type=Path, default=REPO_ROOT / "data" / "finetune",
                        help="where train.jsonl, val.jsonl and the two .json files go")
    parser.add_argument("--eval-dir", type=Path, default=REPO_ROOT / "data" / "eval",
                        help="where heldout_20.jsonl goes")
    parser.add_argument("--train-size", type=int, default=400, help="rows in train.jsonl (default 400)")
    parser.add_argument("--val-size", type=int, default=80, help="rows in val.jsonl (default 80)")
    parser.add_argument("--seed", type=int, default=42, help="same seed -> same files (default 42)")
    parser.add_argument("--no-plant", action="store_true",
                        help="build a clean dataset, without the planted lab problems")
    args = parser.parse_args()
    build(args)


if __name__ == "__main__":
    main()
