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

Show a saved table without calling any model:

```
python scripts/run_eval.py --compare facilitator/prebaked_outputs/eval/2026-09-20_base_heldout_20_summary.json facilitator/prebaked_outputs/eval/2026-09-20_hosted_heldout_20_summary.json
```

After any change to the scoring rules, refresh these from the saved
replies (no model is called, the recorded model name is kept):

```
python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local --label base --replies facilitator/prebaked_outputs/eval/2026-09-20_base_heldout_20_replies.jsonl --out facilitator/prebaked_outputs/eval
```

Still to add once they exist: the `tuned` run (after notebook 05
produces the adapter) and the `base+retrieval` run (Day 4).
