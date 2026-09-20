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

Measured, not guessed: the 373 clean training rows are **150,340 tokens
per epoch** under the serving template (mean 403, longest 789, so
`MAX_LENGTH = 1024` truncates nothing; the estimate below was made with
the Hugging Face template's 154,070, 2.5 percent more). About 250 of the
403 tokens in an average row are the fixed system prompt - it is paid for in compute on every row even though the
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

## 2b. Measured on a real T4 (2026-09-20)

Utkarsh ran the participant notebook on a Colab free-tier T4 with the
TODOs filled with the hinted values. The retained output is
`solutions/05_finetune.ipynb`.

| | Estimate | Measured |
|---|---|---|
| Training, 72 steps, incl. 7 Drive checkpoints + 3 validation passes | 7 to 14 min | **7.1 min** |
| Base model in GPU memory, 4-bit | about 1 GB | 1.01 GB |
| Install | one 43 MB wheel | 43.1 MB, no restart prompt |
| Trainable parameters | about 1% | 11,272,192 (1.48%) |
| Training loss | - | 0.742 -> 0.020 |
| Validation loss per epoch | - | 0.136, 0.055, 0.047 (still falling: no sign of memorising at 3 epochs) |
| Preview replies schema-valid, before -> after | - | 5 of 5 -> 5 of 5 |

That is about 1,060 tokens per second, the fast end of the band, and a
3.5x margin under the 25-minute budget. By the same arithmetic the 3B
would take about 18 minutes of training on this T4 - inside the budget,
but with 1.4x margin instead of 3.5x, and not measured.

All four "known unknowns" at the end of section 4 came back clean:
bitsandbytes 0.50.2 loads against Colab's torch, fp16 + 4-bit trains
under transformers 5.16.1, Drive checkpoints cost little, and batch 4
fits.

What the run did NOT measure: the whole-notebook wall-clock, a second
run, and the disconnect test on Colab (steps 9 to 12 below).

What the replies showed: the untuned 1B already returns valid JSON. It
fails on CONTENT - it copied the system prompt's example asset tag
`LAP-04412` into all five tickets, wrote the string `"null"` for a
null, and routed a Teams microphone fault to `erp_support`. After
tuning, three of five records match the expected record exactly and
the other two differ in one arguable field each (`impact`, `urgency`).

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

## 5. Notebook 05b (Apple Silicon / MLX): what was and was not verified

No Mac was available. MLX ships a Linux CPU backend (`mlx[cpu]`), so
05b was executed for real in a Linux container - same Python API, same
mlx-lm 0.31.3, only the device differs. (The plain Windows mlx wheel
has no backend: `ImportError: DLL load failed`.)

| Verified (2026-09-20, container, smoke mode) | Result |
|---|---|
| Whole solution notebook, top to bottom | no errors |
| Hard kill mid-epoch 3, then Run all | `status: resume`, `epochs done: 2 of 3 (adapter weights restored from disk)`; only iterations 5 and 6 trained; "before" replies loaded, not regenerated; loss log continuous |
| It learns | loss 1.318 -> 0.420; validation 0.909, 0.585, 0.457 |
| Same adapter shape as notebook 05 | 4,884,480 trainable parameters in MLX - exactly PEFT's count for the same settings on the same model |
| **Converted adapter == MLX adapter** | strong random adapter, both sides float32: PyTorch+PEFT loading the converted folder matches MLX's logits to 0.0013 (the adapter moves them by 5.7 and changes the top token); correlation of the adapter's effect 1.000000; the two base models agree to 0.0002 |
| In-notebook converter check | 1.3e-05 difference on an output of 3.0e-02 |

| NOT verified - needs a real Mac | |
|---|---|
| Speed, and therefore the 25-minute budget | The container backend is ~70 s per training row on one core; it proves nothing about Apple Silicon |
| The real model | Only the 135M smoke model ran under MLX. `mlx-community/Llama-3.2-1B-Instruct-bf16` exists and is ungated (HF API), but was not downloaded or trained here |
| Memory on an 8 GB Mac | unknown |
| `%pip install` of the pins on macOS | the pins resolve on Linux; macOS wheels exist on PyPI for all four |
| Registering an MLX-trained adapter in Ollama on a Mac | the same script and the same adapter format were verified with the notebook 05 adapter |

Design notes. mlx-lm reloads adapter WEIGHTS only - no optimizer
state, no step count - so 05b trains one epoch per call and writes the
adapter and a progress file after each: a crash costs at most one
epoch, and the 25-minute budget is checked between epochs. The
optimizer's momentum is kept across epochs in an uninterrupted run and
starts fresh after a crash. mlx-lm's LoRA `scale` is a raw multiplier;
the converter writes `lora_alpha = scale * rank` so PEFT's
`alpha / rank` gives the same number, and transposes both matrices.
