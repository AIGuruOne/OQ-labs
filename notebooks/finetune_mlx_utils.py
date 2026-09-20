"""MLX helpers for notebook 05b (Apple Silicon variant of the fine-tune lab).

    import finetune_mlx_utils

Notebook 05b does the same job as notebook 05 with Apple's MLX instead
of PyTorch: same dataset, same chat template, same LoRA idea, and - after
one conversion step - the SAME adapter format, so notebook 06 and the
`tuned` endpoint cannot tell which notebook produced the adapter.

Everything model-independent (dataset loading, the serving template,
reply checking, the run folder, the adapter converter) is shared with
notebook 05 and lives in finetune_utils.py. This file holds only what
is MLX-specific.

How resuming works here. mlx-lm can reload adapter WEIGHTS but keeps no
record of how far training got. So this lab trains ONE EPOCH PER CALL
and writes the adapter plus a small progress file after each epoch. A
crash or a closed lid costs at most the epoch in flight.
"""

import json
import time
from pathlib import Path

import mlx.core as mx
import mlx.optimizers as optimizers
from mlx.utils import tree_flatten
from mlx_lm import generate, load
from mlx_lm.tuner import trainer as mlx_trainer
from mlx_lm.tuner.callbacks import TrainingCallback
from mlx_lm.tuner.datasets import CacheDataset, ChatDataset
from mlx_lm.tuner.utils import linear_to_lora_layers

import finetune_utils

MLX_ADAPTER_FOLDER = "mlx_adapter"
MLX_ADAPTER_FILE = "adapters.safetensors"
PROGRESS_FILE = "mlx_progress.json"

# Notebook 05 names layers the Hugging Face way ("q_proj"). mlx-lm wants
# the path inside one transformer block ("self_attn.q_proj").
MLX_LAYER_PATHS = {
    "q_proj": "self_attn.q_proj",
    "k_proj": "self_attn.k_proj",
    "v_proj": "self_attn.v_proj",
    "o_proj": "self_attn.o_proj",
    "gate_proj": "mlp.gate_proj",
    "up_proj": "mlp.up_proj",
    "down_proj": "mlp.down_proj",
}


def load_model_and_tokenizer(mlx_repo):
    """Base model + tokenizer, with the chat template Ollama serves with.

    Returns (model, tokenizer, note) - the note says what happened to
    the template, for the notebook to print.
    """
    model, tokenizer = load(mlx_repo)
    note = finetune_utils.use_serving_template(tokenizer)
    return model, tokenizer, note


def build_lora_parameters(rank, alpha, dropout, target_modules):
    """Translate notebook 05's LoRA settings into mlx-lm's vocabulary.

    PEFT scales the adapter by alpha / rank. mlx-lm takes that ratio
    directly and calls it `scale`. Same number, different name.
    """
    unknown = [name for name in target_modules if name not in MLX_LAYER_PATHS]
    if unknown:
        raise ValueError(f"Unknown layer names {unknown}. Choose from {sorted(MLX_LAYER_PATHS)}.")
    return {
        "rank": rank,
        "scale": alpha / rank,
        "dropout": dropout,
        "keys": [MLX_LAYER_PATHS[name] for name in target_modules],
    }


def add_lora_layers(model, lora_parameters):
    """Freeze the base model and put a LoRA adapter on every chosen layer."""
    model.freeze()
    linear_to_lora_layers(model, len(model.layers), lora_parameters)


def count_parameters(model):
    """(trainable, total) parameter counts."""
    trainable = sum(value.size for _, value in tree_flatten(model.trainable_parameters()))
    total = sum(value.size for _, value in tree_flatten(model.parameters()))
    return trainable, total


def build_chat_dataset(pairs, tokenizer):
    """Tokenised rows with the loss masked to the answer only - the same
    rule as finetune_utils.tokenize_pair, done by mlx-lm (mask_prompt)."""
    rows = [{"messages": pair["messages"]} for pair in pairs]
    return CacheDataset(ChatDataset(rows, tokenizer, mask_prompt=True))


def count_tokens(chat_dataset):
    """(all tokens, graded answer tokens) in a dataset from build_chat_dataset."""
    all_tokens = 0
    graded_tokens = 0
    for position in range(len(chat_dataset)):
        tokens, answer_starts_at = chat_dataset[position]
        all_tokens += len(tokens)
        graded_tokens += len(tokens) - answer_starts_at
    return all_tokens, graded_tokens


# ---------------------------------------------------------------------------
# Progress: what survives a crash
# ---------------------------------------------------------------------------


def load_progress(run_dir):
    """{"epochs_done", "iterations_done", "training_seconds"} - zeros if new."""
    progress_path = Path(run_dir) / PROGRESS_FILE
    if not progress_path.exists():
        return {"epochs_done": 0, "iterations_done": 0, "training_seconds": 0.0}
    return json.loads(progress_path.read_text(encoding="utf-8"))


def save_mlx_adapter(model, run_dir, mlx_repo, lora_parameters):
    """Write the adapter the way `mlx_lm.load(adapter_path=...)` expects it:
    adapters.safetensors + adapter_config.json."""
    adapter_dir = Path(run_dir) / MLX_ADAPTER_FOLDER
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_weights = dict(tree_flatten(model.trainable_parameters()))
    mx.save_safetensors(str(adapter_dir / MLX_ADAPTER_FILE), adapter_weights)
    adapter_config = {
        "model": mlx_repo,
        "fine_tune_type": "lora",
        "num_layers": len(model.layers),
        "lora_parameters": lora_parameters,
    }
    (adapter_dir / "adapter_config.json").write_text(json.dumps(adapter_config, indent=2), encoding="utf-8")
    return adapter_dir


def restore_adapter_weights(model, run_dir):
    """After a restart: put the saved adapter weights back into the model."""
    adapter_file = Path(run_dir) / MLX_ADAPTER_FOLDER / MLX_ADAPTER_FILE
    model.load_weights(str(adapter_file), strict=False)


class LossPrinter(TrainingCallback):
    """Prints each loss report and appends it to loss_log.jsonl in the
    run folder - the same log format notebook 05 writes."""

    def __init__(self, run_dir, iterations_before, iterations_per_epoch, seconds_before):
        self.run_dir = Path(run_dir)
        self.iterations_before = iterations_before
        self.iterations_per_epoch = iterations_per_epoch
        self.seconds_before = seconds_before
        self.started = time.time()

    def on_train_loss_report(self, train_info):
        iteration = self.iterations_before + train_info["iteration"]
        minutes = (self.seconds_before + time.time() - self.started) / 60
        entry = {
            "step": iteration,
            "epoch": round(iteration / self.iterations_per_epoch, 3),
            "loss": round(train_info["train_loss"], 4),
            "minutes": round(minutes, 2),
        }
        with open(self.run_dir / finetune_utils.LOSS_LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        print(f"iteration {iteration:>4}   epoch {entry['epoch']:>5.2f}   loss {entry['loss']:.4f}   "
              f"{entry['minutes']:>5.1f} min so far   {train_info['tokens_per_second']:,.0f} tokens/s")


def make_optimizer(learning_rate):
    """Adam, the same family notebook 05 uses."""
    return optimizers.Adam(learning_rate=learning_rate)


def train_one_epoch(model, optimizer, train_set, run_dir, progress, batch_size,
                    gradient_accumulation, max_length, report_every):
    """One pass over the training rows. Returns the seconds it took.

    mlx-lm counts ITERATIONS (one batch each); an update happens every
    `gradient_accumulation` iterations. Its own printing is left on, so
    the raw mlx-lm lines appear next to ours.
    """
    iterations_per_epoch = len(train_set) // batch_size
    training_arguments = mlx_trainer.TrainingArgs(
        batch_size=batch_size,
        iters=iterations_per_epoch,
        steps_per_report=report_every,
        steps_per_eval=10**9,                 # validation is run by the notebook, once per epoch
        steps_per_save=10**9,                 # saving too: after the epoch, with the progress file
        max_seq_length=max_length,
        adapter_file=str(Path(run_dir) / "mlx_trainer_last.safetensors"),
        grad_checkpoint=True,
        grad_accumulation_steps=gradient_accumulation,
    )
    printer = LossPrinter(run_dir, progress["iterations_done"], iterations_per_epoch,
                          progress["training_seconds"])
    started = time.time()
    model.train()
    mlx_trainer.train(
        model=model,
        optimizer=optimizer,
        train_dataset=train_set,
        val_dataset=None,
        args=training_arguments,
        training_callback=printer,
    )
    return time.time() - started


def validation_loss(model, val_set, batch_size, max_length):
    """Average loss on the validation rows (answer tokens only)."""
    loss = mlx_trainer.evaluate(
        model=model,
        dataset=val_set,
        batch_size=batch_size,
        num_batches=-1,
        max_seq_length=max_length,
    )
    model.train()
    return float(loss)


def record_epoch(run_dir, progress, epoch_seconds, iterations_in_epoch, eval_loss):
    """Write the progress file and the validation entry after an epoch."""
    progress = {
        "epochs_done": progress["epochs_done"] + 1,
        "iterations_done": progress["iterations_done"] + iterations_in_epoch,
        "training_seconds": round(progress["training_seconds"] + epoch_seconds, 1),
    }
    entry = {
        "step": progress["iterations_done"],
        "epoch": float(progress["epochs_done"]),
        "eval_loss": round(eval_loss, 4),
        "minutes": round(progress["training_seconds"] / 60, 2),
    }
    with open(Path(run_dir) / finetune_utils.LOSS_LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    (Path(run_dir) / PROGRESS_FILE).write_text(json.dumps(progress), encoding="utf-8")
    return progress


def drop_unfinished_epoch_from_log(run_dir, progress):
    """After a crash mid-epoch, that epoch is redone: remove its half-written
    loss lines so the log has no duplicates."""
    import dataset_utils

    kept = [entry for entry in finetune_utils.load_loss_log(run_dir)
            if entry["step"] <= progress["iterations_done"]]
    dataset_utils.write_jsonl(Path(run_dir) / finetune_utils.LOSS_LOG_FILE, kept)


# ---------------------------------------------------------------------------
# Generating
# ---------------------------------------------------------------------------


def generate_reply(model, tokenizer, messages, max_new_tokens=160):
    """Greedy reply to [system, user] messages. Returns the reply text."""
    prompt_tokens = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_dict=False)
    model.eval()
    reply_text = generate(model, tokenizer, prompt=prompt_tokens, max_tokens=max_new_tokens, verbose=False)
    model.train()
    return reply_text.strip()


def load_tuned_model(mlx_repo, run_dir):
    """Fresh base model + the saved MLX adapter - the load-back test."""
    adapter_dir = Path(run_dir) / MLX_ADAPTER_FOLDER
    model, tokenizer = load(mlx_repo, adapter_path=str(adapter_dir))
    finetune_utils.use_serving_template(tokenizer)
    return model, tokenizer
