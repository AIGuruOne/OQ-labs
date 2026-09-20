# Fine-tune lab (notebook 05): stack, timing estimate, T4 checklist

Written 2026-09-20 (P5). Everything here was checked against a primary
source on that date; the source is named next to each claim.

## 1. What was researched, and what was chosen

| Question | Finding (source) | Decision |
|---|---|---|
| Unsloth on a free T4 today | Latest is unsloth 2026.9.7 (PyPI, 2026-09-18). Its wheel metadata requires `transformers<=5.5.0`, `trl<=0.24.0`, `datasets<4.4.0` (PyPI JSON, `requires_dist`). Published speed-up over plain HF QLoRA on a T4 is 1.56x to 1.95x for 7B models (Hugging Face blog "unsloth-trl") | **Not used.** See below |
| What Colab ships | torch 2.11.0+cu128, transformers 5.16.1, peft 0.20.0, accelerate 1.14.0, safetensors 0.8.0, tokenizers 0.23.1, huggingface_hub 1.29.0. **No `trl`, no `bitsandbytes`** (googlecolab/backend-info, `pip-freeze.gpu.txt`) | Use exactly these. Install only `bitsandbytes==0.50.2` |
| bitsandbytes | 0.50.2 (2026-08-27) is one prebuilt 43 MB wheel, needs only `torch>=2.4` (PyPI) | Pinned |
| Trainer API in transformers 5.16.1 | `warmup_ratio`, `group_by_length`, `evaluation_strategy`, `save_safetensors` are **gone**. Now: `warmup_steps=0.1` (a float is a ratio), `train_sampling_strategy="group_by_length"`, `eval_strategy`, `processing_class=` (introspected from the installed package) | Notebook uses the 5.x names. Code from a 4.x tutorial will crash |
| Which model | `meta-llama/Llama-3.2-*-Instruct` is **gated** (HF API: `gated: manual`) - every participant would need an approved account. `unsloth/Llama-3.2-1B-Instruct` and `-3B-Instruct` are ungated mirrors of the same weights (HF API) | Ungated mirrors. Default **1B** - see the arithmetic |
| Serving the adapter | Ollama `ADAPTER` takes a PEFT safetensors folder for Llama-family models (docs.ollama.com/modelfile). Verified on Ollama 0.12.10 with all seven target modules | `scripts/register_adapter.py` |
| Chat template | HF's Llama 3.2 template writes `Today Date: <today>` into the system block; Ollama's does not (`ollama show llama3.2:3b --template`) | Train on Ollama's text: `finetune_utils.LLAMA3_SERVING_TEMPLATE` (tested byte for byte) |
| MLX | mlx 0.32.2 + mlx-lm 0.31.3 (PyPI). mlx-lm resumes adapter weights only, not optimizer state or step count (source of `mlx_lm.tuner.trainer.train`). LoRA scale is a raw multiplier, not alpha/rank | 05b trains one epoch per call; converter sets `alpha = scale * rank` |

### Why not Unsloth

1. **It breaks the cold-runtime rule.** Installing it on today's Colab
   downgrades transformers 5.16.1 to <=5.5.0 and datasets 4.8.5 to
   <4.4.0, then wants a runtime restart. "Runs top to bottom on a cold
   runtime with no manual intervention" does not survive that.
2. **It cannot be tested without a GPU.** Unsloth has no CPU path. The
   plain stack runs the *same* notebook cells on a CPU (only the 4-bit
   load differs), which is how every non-GPU path in notebook 05 was
   actually executed, including a killed-kernel resume.
3. **The speed is not needed** at 1B (below). It would matter at 3B.

If the T4 run shows the plain stack is too slow, the fallbacks are in
section 3 - none of them is a bigger accelerator.

## 2. T4 training-time estimate (arithmetic shown)

Measured, not guessed: the 373 clean training rows are **154,070 tokens
per epoch** under the serving template (mean 413, longest 799, so
`MAX_LENGTH = 1024` truncates nothing). 250 of those 413 are the fixed
system prompt - it is paid for in compute on every row even though the
loss ignores it.

Work per token for LoRA with gradient checkpointing is about
`6 x N` FLOPs over the non-embedding weights (forward 2N, recomputed
forward 2N, backward through activations 2N; frozen weights need no
weight gradients), plus the output head.

| | Llama 3.2 1B | Llama 3.2 3B |
|---|---|---|
| Non-embedding parameters N | 0.97 B | 2.82 B |
| FLOPs per token (6N + head) | ~7.4 G | ~19.3 G |
| Tokens, 3 epochs, +5% padding | 485,000 | 485,000 |
| Total work | 3.6e15 | 9.4e15 |
| T4 at 5 to 10 TFLOP/s effective | **6 to 12 min** | **16 to 31 min** |
| + 3 validation passes, 7 Drive checkpoints | +1 to 2 min | +2 to 3 min |
| **Estimate** | **7 to 14 min** | **18 to 34 min** |

The 5 to 10 TFLOP/s band: a T4 peaks at 65 TFLOP/s (fp16 tensor cores)
and 8.1 (fp32); QLoRA at batch 4 with 4-bit dequantisation on every
layer realistically sustains 8 to 15 percent of the fp16 peak, and
Colab T4s are power-capped at 70 W. No absolute T4 tokens-per-second
figure for this setup is published, which is why this is a band and
why section 4 measures it.

Cross-check from this build machine: the same notebook trains the 1B
at about 40 tokens/s on a 12-core CPU, roughly 0.3 TFLOP/s. A T4 at
5 to 10 TFLOP/s is 17x to 33x that; 3.5 hours / 17 to 33 = 6 to 12
minutes. The two routes agree.

**Conclusion.** 1B fits the 25-minute budget with about 2x margin even
at the slow end. **3B straddles the budget and is not the default.**
The notebook still offers it (`MODEL_NAME = "llama3.2-3b"`) for a
facilitator who has measured headroom.

**The backstop, whatever the estimate:** `ProgressCallback` stops
training at 23 minutes of accumulated training time (25 minus a
2-minute reserve for the save), writes a checkpoint, and the notebook
saves the adapter it has. The budget is enforced by the code, not
hoped for.

## 3. If the T4 run is slower than estimated

In this order. None is a bigger accelerator or Colab Pro.

1. `NUM_EPOCHS = 2` (time is linear in epochs).
2. `TARGET_MODULES` = attention only (`q_proj k_proj v_proj o_proj`).
3. Do nothing: the budget guard stops at 23 minutes and the adapter
   from that point is used. Check its eval score before accepting.
4. Already at 1B, so there is no smaller Llama 3.2 to drop to.

## 4. What to run on a real cold free-tier T4

Use a Google account that has never opened this repo. Free tier.
*Runtime > Change runtime type > T4 GPU*.

| # | Do | Time it | Passes if |
|---|---|---|---|
| 1 | Open `solutions/05_finetune.ipynb` from GitHub in Colab. Start a stopwatch. *Runtime > Run all*. Approve the Drive prompt | Stopwatch runs to step 9 | No cell asks for a restart |
| 2 | `settings` cell | | Prints `GPU : Tesla T4` |
| 3 | `install` cell | seconds | Under 60 s. `bitsandbytes` only |
| 4 | `model-load` cell | seconds | Prints `in memory : ~1.0 GB on GPU, 4-bit`. Under 3 min including the 2.5 GB download |
| 5 | `before` cell | seconds | Five replies printed |
| 6 | `train` cell: read the **first five** `step` lines | | The last column (`~N min for the whole run`) settles **under 23**. This is the number that matters |
| 7 | `train` cell finishes | **minutes, from `Starting at step 0` to `training stopped`** | `training stopped at step 72 of 72` with **no** `(time budget reached)`, in **under 25 min** |
| 8 | `loss` cell | | Training loss falls and flattens; validation loss does not rise sharply at epoch 3 |
| 9 | `final` cell. Stop the stopwatch | **total wall-clock** | `ADAPTER READY`, `schema-valid JSON : n of 5 -> 5 of 5`, total under 40 min |
| 10 | **Disconnect test.** New `RUN_NAME = "run2"`, Run all. When the train cell shows step 20 or more: *Runtime > Disconnect and delete runtime*. Reconnect, Run all | | Train cell prints `Resuming at step 20` (or 10, 30...), **not** `Starting at step 0`; the `before` cell prints no `checkpoint saved` line |
| 11 | Run all a third time on the finished run | | Train cell prints `This run already finished` |
| 12 | Record steps 7 and 9 in `docs/timing_log.md`. Repeat steps 1 to 9 once more on a fresh runtime (spec section 11: two runs within 20 percent) | | Two rows in the timing log |
| 13 | Download the executed notebook, replace `solutions/05_finetune.ipynb`, run `python -m pytest tests/test_notebook_05.py` | | All pass. This makes the T4 run the retained reference output |

If step 6 projects over 23 minutes, stop there and apply section 3
before spending more compute units.

Known unknowns this checklist exists to settle, because none of them
can be exercised without a T4: bitsandbytes 0.50.2 loading against
Colab's torch 2.11.0+cu128; fp16 mixed precision with 4-bit weights
under transformers 5.16.1; Drive write latency for a ~135 MB
checkpoint every 10 steps; peak GPU memory at batch 4.
