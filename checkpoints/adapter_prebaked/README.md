# Pre-baked adapter: service desk ticket -> structured record

The insurance adapter. Day 2 S12 (base vs tuned) and Day 4 S19
(three-way) both work from this folder even if nobody's training run
in the room completes. It is a real output of `05_finetune`, not a
specially prepared one: the same notebook, the same default settings,
the same free-tier T4 a participant gets.

All training data is synthetic. No real OQ material anywhere.

## What it is

| | |
|---|---|
| Kind | LoRA adapter (PEFT format, float16), **22.6 MB**. Not a model on its own |
| Sits on | Llama 3.2 **1B** Instruct. Hugging Face: `unsloth/Llama-3.2-1B-Instruct` (ungated mirror of Meta's weights). Ollama: `llama3.2:1b` |
| Task | Free-text IT service desk ticket in, one strict JSON record out (schema: `data/finetune/ticket_schema.json`, BUILD_SPEC 8B) |
| Prompt | `dataset_utils.SYSTEM_PROMPT`, in every training row and sent again at inference |
| Chat template | `finetune_utils.LLAMA3_SERVING_TEMPLATE` - the text Ollama sends, not Hugging Face's (which adds a `Today Date:` line). Saved here as `chat_template.jinja` |

An adapter only means something on the model it was trained on. On
any other base model it is noise. `scripts/register_adapter.py` reads
`adapter_config.json` and picks the matching Ollama model for you.

## How it was trained

| | |
|---|---|
| Notebook | `notebooks/05_finetune.ipynb`, TODOs filled with the hinted values (identical to `solutions/`). The retained output of that exact run is `solutions/05_finetune.ipynb` |
| When, where | 2026-09-20, Google Colab **free tier, Tesla T4**, run by Utkarsh |
| Data | 373 training rows, 72 validation rows: `data/finetune/train.jsonl` and `val.jsonl` (built by `scripts/build_dataset.py --seed 42`) cleaned with the notebook 04 rules (20 near-duplicates, 10 schema violations, 5 leaked rows removed). The 20 held-out tickets were never seen |
| Tokens | 150,340 per epoch; 21,289 of them graded (the JSON answers - loss is masked everywhere else) |
| Method | QLoRA: base weights frozen in 4-bit NF4 with double quantisation (bitsandbytes), float16 compute |
| LoRA | rank 16, alpha 32 (scale 2.0), dropout 0.05, on all seven linear layers: `q_proj k_proj v_proj o_proj gate_proj up_proj down_proj`. 11,272,192 trainable parameters (1.48%) |
| Training | 3 epochs, 72 update steps, learning rate 2e-4, cosine schedule, 10% warm-up, batch 4 x gradient accumulation 4 (effective 16), AdamW, max grad norm 1.0, gradient checkpointing, rows grouped by length, max length 1024 (longest row: 789) |
| Seed | 42 |
| Time | **7.1 minutes** of training (budget: 25), including 7 checkpoints to Drive and 3 validation passes |
| Loss | training 0.742 -> 0.020. Validation 0.136, 0.055, 0.047 after epochs 1, 2, 3 - still falling, so no sign of memorising |
| Versions | torch 2.11.0+cu128, transformers 5.16.1, peft 0.20.0, accelerate 1.14.0, bitsandbytes 0.50.2 (`requirements-finetune.txt`) |

GPU training is not bit-reproducible. A re-run with the same seed
gives an adapter that scores about the same, not the same bytes.

## How it scores (P4 harness, 2026-09-20)

`python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint tuned`,
served by Ollama 0.12.10 on a CPU, temperature 0, JSON mode off. Run
twice: identical scores both times. Files:
`facilitator/prebaked_outputs/eval/`.

The fair comparison is the **same model before and after**:

| Held-out 20 | untuned `llama3.2:1b` | **this adapter** |
|---|---|---|
| Format: schema-valid replies | 12/20 | **20/20** |
| category | 8/20 | **16/20** |
| affected_system | 11/20 | **14/20** |
| asset_tag | 15/20 | **20/20** |
| urgency | 4/20 | **7/20** |
| impact | 14/20 | **19/20** |
| routing_queue | 7/20 | **16/20** |
| requested_action, similarity >= 0.50 (mean) | 1/20 (0.14) | **16/20 (0.81)** |
| Whole record: all six exact fields | 2/20 | **4/20** |
| Invented values (a count) | 3 | **0** |
| Median seconds per ticket | 3.5 | 2.1 |

For context, the other two reference runs on the same 20 tickets:
untuned `llama3.2:3b` gets routing 8/20, requested_action 2/20,
urgency 13/20, whole record 2/20; `gpt-4o-mini` gets routing 17/20,
requested_action 6/20, urgency 8/20, whole record 6/20
(`comparison_four_way.txt`).

**Twenty tickets: one ticket is 5 points.** Read
`data/eval/rubric.md` before quoting any of this.

### Urgency: read this before presenting the table

Urgency is the one field where this adapter does NOT beat the untuned
3B model (7/20 against 13/20). What is behind that number:

- **The held-out 20 is built to be hard on urgency.** Half of it is
  `low` (19 to 30 percent elsewhere) and the harness itself marks 12 of
  the 20 as arguable (rubric H1). On the **72 validation tickets** - a
  natural sample, also never trained on - the adapter gets urgency
  right on **55/72 (76%)**, whole record 30/72, schema-valid 72/72
  (`2026-09-20_tuned-val72_val_clean_report.txt`).
- **The miss has one shape: it escalates by one level.** 10 of 13
  misses on the held-out set, 14 of 17 on validation. `gpt-4o-mini`
  has the same bias: all 12 of its held-out misses are escalations.
- **The 3B's 13/20 is mostly one habit:** it answers `low` nearly every
  time (9/10 on `low` tickets, 0/4 on `medium`). That scores well on a
  set that is half `low`. It is not evidence of understanding urgency.
- **It is the model, not the serving.** The same adapter scored through
  PyTorch/PEFT also gets 7/20, agreeing with Ollama on 19 of 20 tickets
  (`2026-09-20_tuned-pytorch_heldout_20_report.txt`).

This was deliberately NOT "fixed" by retraining until the held-out
number improved: that is tuning to the exam, and the held-out set would
stop meaning anything. The open question in `data/eval/rubric.md` (the
system prompt never defines the urgency levels) applies here too.

### Serving costs a little

Through PyTorch the same adapter scores slightly higher on three
fields (affected_system 17 vs 14, routing_queue 17 vs 16,
requested_action 18 vs 16); 12 of 20 replies are byte-identical.
Ollama applies the adapter on its own 8-bit copy of the base model,
not the float16 weights the adapter was trained against. The numbers
in the table above are the Ollama ones, because that is what the labs
and the capstone actually call.

## How to use it

Register it with Ollama (once per machine or Colab runtime):

```
python scripts/register_adapter.py --adapter checkpoints/adapter_prebaked
```

That writes a three-line Modelfile (`FROM llama3.2:1b`, `ADAPTER
<this folder>`, `PARAMETER num_ctx 4096`) and runs `ollama create
oq-ticket-tuned`. From then on it is the `tuned` endpoint:

```python
from config.endpoints import get_endpoint
llm = get_endpoint("tuned")
```

In Python without Ollama:

```python
import finetune_utils
model, tokenizer = finetune_utils.load_adapter(
    "unsloth/Llama-3.2-1B-Instruct", "checkpoints/adapter_prebaked", use_gpu=False)
reply = finetune_utils.generate_reply(model, tokenizer, messages)   # [system, user]
```

For a like-for-like "base" column next to it, score `llama3.2:1b`
(`OLLAMA_MODEL=llama3.2:1b ... --endpoint local --label base-1b`), not
the repo's default local model `llama3.2:3b`.

## Files

| File | |
|---|---|
| `adapter_model.safetensors` | the weights. 224 tensors, float16. sha256 `b1c0e3d40bb3b38a8b77b0c481843e4d57a496b317b977b568ca580cd3c1786d` |
| `adapter_config.json` | PEFT config: base model, rank, alpha, target layers |
| `chat_template.jinja`, `tokenizer.json`, `tokenizer_config.json` | the tokenizer as used in training, with the serving template. Needed by `load_adapter`; ignored by Ollama |

## Re-baking it

Run `solutions/05_finetune.ipynb` on a free-tier T4 (about 7 minutes
of training), copy `adapter_final/` from the run folder on Drive over
this folder, then: register, run the eval twice, refresh
`facilitator/prebaked_outputs/eval/`, and update the numbers and the
sha256 in this file. Anything that changes the dataset or
`SYSTEM_PROMPT` makes this adapter stale.

## Licence

The adapter is a derivative of Llama 3.2 and is covered by the Llama
3.2 Community License (shown by `ollama show llama3.2:1b --license`).
Check its redistribution terms before this repo is shared outside the
program.
