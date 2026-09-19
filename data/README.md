# data/ - fine-tuning dataset and eval sets

All synthetic. Provenance and the labelling rules are in
`corpus/README.md`; the row format is in `docs/contracts.md`
(Contract 1, "Fine-tuning pair format").

## What is here

| File | What it is | Made by |
|---|---|---|
| `finetune/ticket_schema.json` | The frozen section 8B schema. **Never edit.** | hand, P1 |
| `finetune/ticket_labels.jsonl` | Ground-truth record for each of the 600 tickets | `scripts/generate_tickets.py` |
| `finetune/train.jsonl` | 400 training pairs, **with planted problems** | `scripts/build_dataset.py` |
| `finetune/val.jsonl` | 80 validation pairs, **with planted problems** | `scripts/build_dataset.py` |
| `eval/heldout_20.jsonl` | The 20 held-out eval pairs. Clean. Never in train or val | `scripts/build_dataset.py` |
| `finetune/split_manifest.json` | Which ticket_id went to which split (and the 125 used by none) | `scripts/build_dataset.py` |
| `finetune/planted_problems.json` | **Facilitator answer key** - see below | `scripts/build_dataset.py` |

All five built files are GENERATED. Never hand-edit them:

```
python scripts/build_dataset.py --seed 42
```

Same inputs and seed give byte-identical files (verified on Python
3.11, 3.12, 3.13 and 3.14). `tests/test_build_dataset.py` fails if the
committed files and the builder disagree. If the ticket corpus, the
system prompt (`notebooks/dataset_utils.py`) or the builder changes:
rebuild, run the tests, then rebuild everything downstream (adapter,
eval tables, the solutions notebook outputs).

## The held-out 20

Used by Day 2 S12 (base vs tuned) and Day 4 S19 (three-way), so it is
stable and reproducible. It is drawn **before** the train/val split,
and stratified rather than random:

- every one of the seven categories, the rare ones (erp, telecom)
  included, at least two each;
- two `critical` tickets: one `enterprise` impact, one `site`;
- six tickets where urgency is honestly arguable: three where the
  user shouts URGENT with no stated business effect (`tone_urgent`),
  four that raise two unrelated problems (`two_problems`; one ticket
  is both). The label follows the rules in `corpus/README.md` - these
  are the rows the S12 rubric conversation is about;
- no ticket that has a lookalike (word-set Jaccard >= 0.6) anywhere
  else in the corpus, so no near-copy of an eval ticket can sit in
  train.

## Planted problems - `finetune/planted_problems.json` is for US

`train.jsonl` and `val.jsonl` contain problems planted on purpose, so
that participants in S10 find real problems in the first 90 seconds:

| Problem | Count | Where | What it looks like |
|---|---|---|---|
| Near-duplicates | 20 | train | A reworded resubmission of a ticket already in train: new greeting, a few words swapped, a **new ticket_id**, identical record. Similarity to its source is 0.84-0.95 |
| Leakage | 5 | train + val | A train row copied unchanged into val (same ticket_id) |
| Schema violations | 10 | 7 train, 3 val | 3 values outside an enum, 1 dropped field, 3 stray prose inside a field, 3 malformed asset tags |

No row carries two problems. `planted_problems.json` records every
plant: split, line number, ticket_id, the source ticket of a
duplicate, the field, the original and the planted value.

**That file is the facilitator's answer key, and the ground truth that
`scripts/quality_checks.py` is tested against. It is not lab material:
do not point participants at it, and do not load it in a participant
notebook.** `scripts/plant_problems.py` is the code that does the
planting; same status.

The checks find exactly the planted problems and nothing else: with
the near-duplicate threshold at 0.8, no two genuinely different
tickets in the 600-ticket corpus are flagged (the closest natural
pair scores 0.78). The builder asserts this on every run.

For a dataset with no plants - for example to train the pre-baked
adapter - build to another folder:

```
python scripts/build_dataset.py --seed 42 --no-plant --finetune-dir <dir> --eval-dir <dir>
```

The held-out 20 are identical with and without `--no-plant`.

`--train-size` and `--val-size` exist, but only 580 tickets are left
after the held-out 20. Ask for more than the corpus can supply (for
example `--no-plant --train-size 500 --val-size 100`) and the builder
stops with "Not enough tickets" rather than writing a short file.

## Checking a dataset - `scripts/quality_checks.py`

```
python scripts/quality_checks.py --dataset data/finetune
python scripts/quality_checks.py --dataset <train file> --val <val file>
```

Five checks: near-duplicates, train/val leakage and schema violations
are hard failures (exit code 1); coverage gaps and class imbalance are
warnings (exit code 0). Exit code 2 means the input could not be read.
On the committed files it reports exactly the planted problems - 20
pairs, 5 rows, 10 rows, each with file:line - and
`tests/test_quality_checks.py` holds it to precision = recall = 1.0
against `planted_problems.json`, down to the line, field and kind.

**The class imbalance is reported and never corrected.** There is no
rebalancing function anywhere in the repo, on purpose (BUILD_SPEC.md
section 8B), and a test fails if one appears in `quality_checks.py`.

## Scoring a model - `scripts/run_eval.py` and `eval/rubric.md`

```
python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local
python scripts/run_eval.py --compare eval_runs/<a>_summary.json eval_runs/<b>_summary.json
```

`eval/rubric.md` says how every field is scored and what the two
human-judged steps are (draft until Ritesh signs it). The output
format is Contract 4 in `docs/contracts.md`. Reference runs against
the base model and the hosted API are in
`facilitator/prebaked_outputs/eval/`.

The harness skips any row whose EXPECTED answer is not a valid record,
so it can be pointed at `finetune/val.jsonl` as well: it reports the
planted schema violations as skipped lines instead of marking a model
against a broken answer key.

