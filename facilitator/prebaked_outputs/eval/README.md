# Pre-baked eval runs

Real runs of `scripts/run_eval.py` on `data/eval/heldout_20.jsonl`,
kept so Day 2 S12 and Day 4 S19 have a table to show if a live run
dies. File formats: Contract 4 in `docs/contracts.md`. How to read
them: `data/eval/rubric.md`.

| Run | Model | How it was run |
|---|---|---|
| `2026-09-20_base_heldout_20_*` | llama3.2:3b, Ollama 0.12.10, 4096-token context, CPU | `python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local --label base` |
| `2026-09-20_hosted_heldout_20_*` | gpt-4o-mini | `python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint hosted` |
| `comparison_base_vs_hosted.*` | both | `python scripts/run_eval.py --compare <the two summary files>` |
| `2026-09-20_tuned_heldout_20_*` | `oq-ticket-tuned` = `llama3.2:1b` + `checkpoints/adapter_prebaked`, Ollama 0.12.10, 4096-token context, CPU | `python scripts/register_adapter.py --adapter checkpoints/adapter_prebaked` then `python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint tuned --label tuned`. Run twice, identical scores |
| `2026-09-20_base-1b_heldout_20_*` | llama3.2:1b untuned - the SAME model the adapter sits on, so this is the fair "before" column | `OLLAMA_MODEL=llama3.2:1b python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local --label base-1b` |
| `comparison_base1b_vs_tuned.*` | the Day 2 S12 table: same model, before and after | `--compare` on those two summaries |
| `06_base_llama3.2-1b_*`, `06_tuned_prebaked_b1c0e3d4_*`, `06_base_vs_tuned/comparison.*` | **the pre-baked output of notebook 06** (Day 2 S12): exactly the files the notebook leaves in `CHECKPOINT_DIR/eval`, from the run whose output is retained in `solutions/06_compare_base_tuned.ipynb`. Same models as the two rows above | run the solution notebook with no adapter of your own, so it falls back to `checkpoints/adapter_prebaked` |
| `comparison_four_way.*` | untuned 1B, tuned 1B, untuned 3B, gpt-4o-mini | `--compare` on all four summaries |
| `2026-09-20_tuned-val72_val_clean_*` (summary + report only) | the tuned model on the 72 cleaned validation tickets - a natural sample, where urgency is 55/72. Dataset file is notebook 04's `val_clean.jsonl` (git-ignored checkpoint; rebuild it with notebook 04) | `--dataset <val_clean.jsonl> --endpoint tuned --label tuned-val72` |
| `2026-09-20_tuned-pytorch_heldout_20_*` (summary + report only) | DIAGNOSTIC: the same adapter through PyTorch/PEFT (bfloat16, CPU) instead of Ollama, via `run_eval.run_evaluation(ask=...)`. Shows the urgency score is the model's, not a serving artefact | not a CLI run |

Show a saved table without calling any model:

```
python scripts/run_eval.py --compare facilitator/prebaked_outputs/eval/2026-09-20_base_heldout_20_summary.json facilitator/prebaked_outputs/eval/2026-09-20_hosted_heldout_20_summary.json
```

After any change to the scoring rules, refresh these from the saved
replies (no model is called, the recorded model name is kept):

```
python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local --label base --replies facilitator/prebaked_outputs/eval/2026-09-20_base_heldout_20_replies.jsonl --out facilitator/prebaked_outputs/eval
```

**Before showing the tuned table, read "Urgency" in
`checkpoints/adapter_prebaked/README.md`.** The tuned 1B beats its own
base on every field, but on urgency it does not beat the untuned 3B
(7/20 against 13/20), and the reason is worth two minutes of the
S12 discussion rather than a surprise in it.

**Why the two base-1B runs differ.** `2026-09-20_base-1b_*` (P5) and
`06_base_llama3.2-1b_*` (P6) are the same model, prompt, tickets and
temperature 0, run a few hours apart: 9 of the 20 replies differ
(schema-valid 12/20 and 13/20, category 8 and 9, urgency 4 and 5). In a
Linux container it was 9/20. The untuned 1B is not stable; the tuned
model's replies were identical across all of those runs bar one reply.
Both files are real. For S12 show the `06_` table - it is what the
room's own notebook prints. Playbook entry 10 has the detail.

If a live notebook 06 dies, show the table with no model at all:

```
python scripts/run_eval.py --compare facilitator/prebaked_outputs/eval/06_base_llama3.2-1b_summary.json facilitator/prebaked_outputs/eval/06_tuned_prebaked_b1c0e3d4_summary.json
```

Still to add once it exists: the `base+retrieval` run (Day 4).
