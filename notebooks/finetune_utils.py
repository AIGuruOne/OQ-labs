"""Helpers for the fine-tuning notebooks: 05 (Colab T4 / CPU) and 05b (Apple Silicon).

Import after the environment-detection cell has run:

    import finetune_utils

What lives here is PLUMBING - the parts a participant should not have
to write during a 90-minute lab:

    load_clean_pairs        the cleaned dataset from notebook 04 (or rebuilt)
    use_serving_template    make training text match what Ollama sends
    tokenize_pair           one row -> token ids + a loss mask
    TokenDataset, PadCollator   what transformers.Trainer needs
    load_base_model         4-bit on a GPU, plain fp32 on a CPU
    ProgressCallback        prints the loss, logs it, enforces the time budget
    check_run_folder        refuses to resume a run with different settings
    find_last_checkpoint    where to resume from after a disconnect
    save_adapter, load_adapter, generate_reply, check_reply
    convert_mlx_adapter_to_peft     05b only: MLX adapter -> the same format

What does NOT live here: the LoRA settings and the training settings.
Those are the decisions of the lab, so they stay in the notebook.
"""

import copy
import json
import time
from pathlib import Path

import dataset_utils

try:
    import torch
    from transformers import TrainerCallback
except ImportError:
    # Notebook 05b runs on Apple Silicon with MLX and has no torch.
    # The shared helpers (dataset, template, converter) still work.
    torch = None
    TrainerCallback = object


# ---------------------------------------------------------------------------
# Which model
# ---------------------------------------------------------------------------

# hf_repo     : where the weights come from. The unsloth/ repos are
#               ungated mirrors of Meta's weights - no Hugging Face
#               account or licence click needed in the room.
# ollama_base : the SAME model inside Ollama. The adapter is applied on
#               top of it when the tuned model is registered.
# mlx_repo    : the same model converted for Apple Silicon (05b).
MODEL_CHOICES = {
    "llama3.2-1b": {
        "hf_repo": "unsloth/Llama-3.2-1B-Instruct",
        "ollama_base": "llama3.2:1b",
        "mlx_repo": "mlx-community/Llama-3.2-1B-Instruct-bf16",
    },
    "llama3.2-3b": {
        "hf_repo": "unsloth/Llama-3.2-3B-Instruct",
        "ollama_base": "llama3.2:3b",
        "mlx_repo": "mlx-community/Llama-3.2-3B-Instruct-bf16",
    },
    # Smoke test only: a 135M model with the same (Llama) layer names.
    # It proves the plumbing on a CPU in minutes. It does not learn the task.
    "smoke-test": {
        "hf_repo": "HuggingFaceTB/SmolLM2-135M-Instruct",
        "ollama_base": None,
        "mlx_repo": "HuggingFaceTB/SmolLM2-135M-Instruct",
    },
}

SMOKE_TEST_TRAIN_ROWS = 20
SMOKE_TEST_VAL_ROWS = 8


# ---------------------------------------------------------------------------
# The dataset
# ---------------------------------------------------------------------------


def clean_committed_dataset(repo_root):
    """Rebuild the cleaned train/val sets from the committed files.

    Same three rules as notebook 04: drop the second row of every
    near-duplicate pair, drop rows whose answer breaks the schema, and
    drop validation rows that also sit in train. For a group that did
    not finish notebook 04 - nobody is locked out of the fine-tune lab.
    """
    finetune_dir = Path(repo_root) / "data" / "finetune"
    train_pairs = dataset_utils.load_jsonl(finetune_dir / "train.jsonl")
    val_pairs = dataset_utils.load_jsonl(finetune_dir / "val.jsonl")
    schema = dataset_utils.load_schema(finetune_dir / "ticket_schema.json")

    near_duplicates = dataset_utils.find_near_duplicates(train_pairs)
    duplicate_ids = {item["second"] for item in near_duplicates}
    leaked_ids = set(dataset_utils.find_leakage(train_pairs, val_pairs))
    violations = dataset_utils.find_schema_violations(train_pairs + val_pairs, schema)
    bad_record_ids = {item["ticket_id"] for item in violations}

    train_clean = []
    for pair in train_pairs:
        if pair["ticket_id"] in duplicate_ids or pair["ticket_id"] in bad_record_ids:
            continue
        train_clean.append(pair)

    val_clean = []
    for pair in val_pairs:
        if pair["ticket_id"] in leaked_ids or pair["ticket_id"] in bad_record_ids:
            continue
        val_clean.append(pair)

    return train_clean, val_clean


def load_clean_pairs(repo_root, checkpoint_dir):
    """The cleaned dataset: yours from notebook 04 if it is on Drive,
    otherwise rebuilt from the committed files.

    Returns (train_pairs, val_pairs, where_it_came_from).
    """
    dataset_dir = Path(checkpoint_dir) / "04_dataset"
    train_path = dataset_dir / "train_clean.jsonl"
    val_path = dataset_dir / "val_clean.jsonl"

    if train_path.exists() and val_path.exists():
        train_pairs = dataset_utils.load_jsonl(train_path)
        val_pairs = dataset_utils.load_jsonl(val_path)
        return train_pairs, val_pairs, f"your notebook 04 output in {dataset_dir}"

    train_pairs, val_pairs = clean_committed_dataset(repo_root)
    return train_pairs, val_pairs, "data/finetune, cleaned here with the notebook 04 rules"


# ---------------------------------------------------------------------------
# The chat template: train on EXACTLY the text the model will be served
# ---------------------------------------------------------------------------

# Why this exists. The tuned model is served by Ollama, and Ollama wraps
# every request in its own Llama 3 template. The Hugging Face template
# for the same model is NOT identical: it also writes "Today Date: <the
# day you happen to train>" into the system block. Train with that and
# the model learns a header it never sees again. So we train with the
# text Ollama sends - checked against `ollama show llama3.2:3b --template`.
LLAMA3_SERVING_TEMPLATE = (
    "{{- bos_token }}"
    "{%- if messages[0]['role'] == 'system' %}"
    "{%- set system_text = messages[0]['content'] %}"
    "{%- set messages = messages[1:] %}"
    "{%- else %}"
    "{%- set system_text = '' %}"
    "{%- endif %}"
    "{{- '<|start_header_id|>system<|end_header_id|>\n\n' }}"
    "{{- 'Cutting Knowledge Date: December 2023\n\n' }}"
    "{{- system_text + '<|eot_id|>' }}"
    "{%- for message in messages %}"
    "{{- '<|start_header_id|>' + message['role'] + '<|end_header_id|>\n\n' }}"
    "{{- message['content'] + '<|eot_id|>' }}"
    "{%- endfor %}"
    "{%- if add_generation_prompt %}"
    "{{- '<|start_header_id|>assistant<|end_header_id|>\n\n' }}"
    "{%- endif %}"
)


def use_serving_template(tokenizer):
    """Switch a Llama 3 tokenizer to the template Ollama serves with.

    Other model families keep their own template (the smoke-test model
    is never served, so there is nothing to match). Returns a sentence
    saying what happened, for the notebook to print.
    """
    current_template = tokenizer.chat_template or ""
    if "<|start_header_id|>" in current_template:
        tokenizer.chat_template = LLAMA3_SERVING_TEMPLATE
        return "Llama 3 tokenizer: now using the template Ollama serves with (no 'Today Date' line)."
    return "Not a Llama 3 tokenizer: keeping the model's own chat template."


# ---------------------------------------------------------------------------
# Tokenising: one row -> token ids and a loss mask
# ---------------------------------------------------------------------------

# Label value that tells the loss function "do not score this position".
IGNORE_LABEL = -100


def tokenize_pair(pair, tokenizer, max_length):
    """Turn one dataset row into what the trainer needs.

    The model reads [system, ticket, answer] but is only GRADED on the
    answer: every label before the answer is IGNORE_LABEL. Without that
    mask, most of the training signal would be spent learning to
    recite the system prompt (250 of roughly 410 tokens per row).
    """
    messages = pair["messages"]
    prompt_ids = tokenizer.apply_chat_template(
        messages[:2], tokenize=True, add_generation_prompt=True, return_dict=True
    )["input_ids"]
    full_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, return_dict=True
    )["input_ids"]

    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(
            f"{pair['ticket_id']}: the prompt tokens are not the start of the full "
            "row. This chat template cannot be used for answer-only loss."
        )

    # Too long: truncating would cut off the answer, which sits at the
    # end. Say so instead of training on a row with no answer in it.
    if len(full_ids) > max_length:
        raise ValueError(
            f"{pair['ticket_id']} is {len(full_ids)} tokens, over max_length={max_length}. "
            "Raise MAX_LENGTH or drop the row."
        )

    labels = [IGNORE_LABEL] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return {
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": labels,
    }


class TokenDataset:
    """A list of tokenised rows, in the shape transformers.Trainer accepts."""

    def __init__(self, rows):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, position):
        return self.rows[position]


def build_token_dataset(pairs, tokenizer, max_length):
    """Tokenise every pair. Returns a TokenDataset."""
    rows = [tokenize_pair(pair, tokenizer, max_length) for pair in pairs]
    return TokenDataset(rows)


def count_tokens(token_dataset):
    """(all tokens, graded answer tokens) in a TokenDataset."""
    all_tokens = 0
    graded_tokens = 0
    for row in token_dataset.rows:
        all_tokens += len(row["input_ids"])
        graded_tokens += sum(1 for label in row["labels"] if label != IGNORE_LABEL)
    return all_tokens, graded_tokens


class PadCollator:
    """Pad the rows of one batch to the same length.

    Padding goes on the right, is hidden from attention (mask 0) and is
    never graded (IGNORE_LABEL).
    """

    def __init__(self, pad_token_id):
        self.pad_token_id = pad_token_id

    def __call__(self, rows):
        longest = max(len(row["input_ids"]) for row in rows)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for row in rows:
            padding = longest - len(row["input_ids"])
            batch["input_ids"].append(row["input_ids"] + [self.pad_token_id] * padding)
            batch["attention_mask"].append(row["attention_mask"] + [0] * padding)
            batch["labels"].append(row["labels"] + [IGNORE_LABEL] * padding)
        return {name: torch.tensor(values) for name, values in batch.items()}


# ---------------------------------------------------------------------------
# Loading the base model
# ---------------------------------------------------------------------------


def load_tokenizer(hf_repo):
    """The tokenizer, with a pad token guaranteed."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(hf_repo)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def load_base_model(hf_repo, use_gpu):
    """Load the base model, frozen.

    GPU: 4-bit NF4 weights via bitsandbytes - this is the "Q" in QLoRA.
         A 3B model drops from about 6.4 GB to about 2.2 GB, which is
         what leaves room for training on a 15 GB T4. Compute is
         float16 because the T4 has no bfloat16.
    CPU: plain float32. bitsandbytes 4-bit needs a GPU; the adapter
         that comes out has exactly the same format either way.
    """
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    if use_gpu:
        four_bit = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )
        model = AutoModelForCausalLM.from_pretrained(
            hf_repo,
            quantization_config=four_bit,
            dtype=torch.float16,
            device_map={"": 0},
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(hf_repo, dtype=torch.float32)

    model.config.use_cache = False   # the cache is for generating, not training
    return model


def count_parameters(model):
    """(trainable, total) parameter counts."""
    trainable = 0
    total = 0
    for parameter in model.parameters():
        total += parameter.numel()
        if parameter.requires_grad:
            trainable += parameter.numel()
    return trainable, total


# ---------------------------------------------------------------------------
# The run folder: resume safely, never silently mix two runs
# ---------------------------------------------------------------------------

RUN_SETTINGS_FILE = "run_settings.json"
RUN_STATE_FILE = "run_state.json"
LOSS_LOG_FILE = "loss_log.jsonl"
FINAL_ADAPTER_FOLDER = "adapter_final"


def check_run_folder(run_dir, settings):
    """Create the run folder, or confirm it belongs to THESE settings.

    Checkpoints from a run with a different rank or learning rate must
    not be resumed as if they were this run - the result would be a
    model nobody can describe. So the settings are written down once
    and compared on every later visit.

    Returns "new", "resume" or "finished".
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    settings_path = run_dir / RUN_SETTINGS_FILE
    settings_as_saved = json.loads(json.dumps(settings))   # tuples -> lists, like the file

    if not settings_path.exists():
        settings_path.write_text(json.dumps(settings_as_saved, indent=2), encoding="utf-8")
        return "new"

    previous = json.loads(settings_path.read_text(encoding="utf-8"))
    if previous != settings_as_saved:
        changed = sorted(
            name for name in set(previous) | set(settings_as_saved)
            if previous.get(name) != settings_as_saved.get(name)
        )
        raise RuntimeError(
            f"The run folder {run_dir} was started with different settings "
            f"(changed: {', '.join(changed)}). Give this run a new RUN_NAME, "
            "or put the old settings back to resume the old run."
        )

    if (run_dir / FINAL_ADAPTER_FOLDER / "adapter_model.safetensors").exists():
        return "finished"
    return "resume"


def find_last_checkpoint(run_dir):
    """The newest COMPLETE checkpoint folder in run_dir, or None.

    A disconnect can land in the middle of a save. A checkpoint counts
    only if trainer_state.json is there, because the trainer writes it
    last; a half-written folder is skipped and the one before is used.
    """
    candidates = []
    for folder in Path(run_dir).glob("checkpoint-*"):
        step_text = folder.name.split("-")[-1]
        if step_text.isdigit() and (folder / "trainer_state.json").exists():
            candidates.append((int(step_text), folder))
    if not candidates:
        return None
    candidates.sort()
    return candidates[-1][1]


def load_loss_log(run_dir):
    """Every logged training step so far: [{"step", "epoch", "loss", ...}]."""
    log_path = Path(run_dir) / LOSS_LOG_FILE
    if not log_path.exists():
        return []
    return dataset_utils.load_jsonl(log_path)


# Minutes of the budget kept back for the last checkpoint and the adapter save.
BUDGET_RESERVE_MINUTES = 2


class ProgressCallback(TrainerCallback):
    """Prints the loss as it happens, keeps it on Drive, and enforces the budget.

    - Every logged step is printed AND appended to loss_log.jsonl in the
      run folder, so the loss curve survives a disconnect.
    - Training time is counted across sessions (run_state.json), so a
      resumed run still honours one overall budget.
    - When the budget is reached the run stops cleanly and saves. A
      slightly under-trained adapter you have beats a better one you
      do not.
    """

    def __init__(self, run_dir, budget_minutes):
        self.run_dir = Path(run_dir)
        # Stop a little early, so the final save lands INSIDE the budget.
        self.budget_seconds = (budget_minutes - BUDGET_RESERVE_MINUTES) * 60
        self.seconds_before_this_session = 0.0
        self.session_start = None
        self.stopped_by_budget = False

    def training_seconds(self):
        return self.seconds_before_this_session + (time.time() - self.session_start)

    def on_train_begin(self, args, state, control, **kwargs):
        self.session_start = time.time()
        state_path = self.run_dir / RUN_STATE_FILE
        if state.global_step > 0 and state_path.exists():
            saved = json.loads(state_path.read_text(encoding="utf-8"))
            self.seconds_before_this_session = saved["training_seconds"]

        # Steps logged after the last checkpoint were lost with the
        # runtime and are about to be redone: drop them from the log.
        kept = [entry for entry in load_loss_log(self.run_dir) if entry["step"] <= state.global_step]
        dataset_utils.write_jsonl(self.run_dir / LOSS_LOG_FILE, kept)

        if state.global_step > 0:
            minutes = self.seconds_before_this_session / 60
            print(f"Resuming at step {state.global_step} of {state.max_steps} "
                  f"({minutes:.1f} min of training already done).")
        else:
            print(f"Starting at step 0 of {state.max_steps}.")

    def on_log(self, args, state, control, logs=None, **kwargs):
        logs = logs or {}
        minutes = round(self.training_seconds() / 60, 2)

        if "eval_loss" in logs:
            entry = {"step": state.global_step, "epoch": round(logs.get("epoch", 0.0), 3),
                     "eval_loss": round(logs["eval_loss"], 4), "minutes": minutes}
            self.append_to_log(entry)
            print(f"   validation loss after epoch {entry['epoch']:.0f}: {entry['eval_loss']:.4f}")
            return

        if "loss" not in logs:
            return
        entry = {"step": state.global_step, "epoch": round(logs.get("epoch", 0.0), 3),
                 "loss": round(logs["loss"], 4), "learning_rate": logs.get("learning_rate"),
                 "minutes": minutes}
        self.append_to_log(entry)

        # Projection: minutes per step so far, times all the steps.
        projected = minutes / state.global_step * state.max_steps
        print(f"step {state.global_step:>4}/{state.max_steps}   epoch {entry['epoch']:>5.2f}   "
              f"loss {entry['loss']:.4f}   {minutes:>5.1f} min so far   "
              f"~{projected:.0f} min for the whole run")

    def append_to_log(self, entry):
        with open(self.run_dir / LOSS_LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def on_save(self, args, state, control, **kwargs):
        run_state = {"global_step": state.global_step, "training_seconds": round(self.training_seconds(), 1)}
        (self.run_dir / RUN_STATE_FILE).write_text(json.dumps(run_state), encoding="utf-8")

    def on_step_end(self, args, state, control, **kwargs):
        if self.training_seconds() >= self.budget_seconds and state.global_step < state.max_steps:
            print(f"TIME BUDGET reached at step {state.global_step} of {state.max_steps}: "
                  "stopping cleanly and saving what has been learned so far.")
            self.stopped_by_budget = True
            control.should_save = True
            control.should_training_stop = True
        return control


# ---------------------------------------------------------------------------
# Saving, loading back, generating
# ---------------------------------------------------------------------------


def save_adapter(model, tokenizer, adapter_dir):
    """Save ONLY the adapter (a few tens of MB), as float16, plus the tokenizer.

    The base model is not saved: anyone can download it again. The
    adapter is the part that is yours. float16 halves the file and is
    what the serving side uses anyway.
    """
    from safetensors.torch import load_file, save_file

    adapter_dir = Path(adapter_dir)
    model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)

    weights_path = adapter_dir / "adapter_model.safetensors"
    weights = load_file(weights_path)
    half_weights = {name: tensor.to(torch.float16).contiguous() for name, tensor in weights.items()}
    save_file(half_weights, weights_path, metadata={"format": "pt"})
    return weights_path


def load_adapter(hf_repo, adapter_dir, use_gpu):
    """Fresh base model + saved adapter, ready to generate.

    This is the load-back test: it proves the files on disk are enough
    to rebuild the tuned model, with nothing left over in memory.
    """
    from peft import PeftModel
    from transformers import AutoTokenizer

    base_model = load_base_model(hf_repo, use_gpu)
    tuned_model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    tuned_model.eval()
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_dir))
    return tuned_model, tokenizer


def generate_reply(model, tokenizer, messages, max_new_tokens=160):
    """Greedy reply to [system, user] messages. Returns the reply text.

    Greedy (no sampling) so the same ticket gives the same answer every
    time - the eval harness asks the same way (temperature 0).
    """
    was_training = model.training
    model.eval()
    model.config.use_cache = True

    inputs = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, return_tensors="pt", return_dict=True
    )
    inputs = {name: tensor.to(model.device) for name, tensor in inputs.items()}
    prompt_length = inputs["input_ids"].shape[1]

    # Greedy, with a hard length cap. Start from the model's own settings
    # (they hold its stop tokens) and switch sampling OFF in that copy.
    # Llama ships do_sample=True, temperature 0.6, top_p 0.9; the neutral
    # values 1.0 / 1.0 are what "off" looks like to transformers 5.x -
    # None would be refilled from the model's defaults, with a warning.
    generation_config = copy.deepcopy(model.generation_config)
    generation_config.do_sample = False
    generation_config.temperature = 1.0
    generation_config.top_p = 1.0
    generation_config.max_new_tokens = None
    generation_config.max_length = prompt_length + max_new_tokens
    generation_config.pad_token_id = tokenizer.pad_token_id
    with torch.no_grad():
        output_ids = model.generate(**inputs, generation_config=generation_config)

    model.config.use_cache = False
    if was_training:
        model.train()
    reply_ids = output_ids[0][prompt_length:]
    return tokenizer.decode(reply_ids, skip_special_tokens=True).strip()


def check_reply(reply_text, schema):
    """Is a reply strict JSON that passes the ticket schema?

    Returns {"valid": bool, "record": dict or None, "problems": [str]}.
    Strict on purpose, the same rule as the eval harness: a fenced or
    prose-wrapped answer is NOT valid, because a program downstream
    would choke on it.
    """
    from jsonschema import Draft202012Validator

    try:
        record = json.loads(reply_text)
    except json.JSONDecodeError as error:
        return {"valid": False, "record": None, "problems": [f"not JSON: {error.msg}"]}
    if not isinstance(record, dict):
        return {"valid": False, "record": None, "problems": ["JSON, but not an object"]}

    validator = Draft202012Validator(schema)
    errors = dataset_utils.record_schema_errors(record, validator)
    problems = [f"{error['field']}: {error['message']}" for error in errors]
    return {"valid": not problems, "record": record, "problems": problems}


# ---------------------------------------------------------------------------
# 05b only: MLX adapter -> the same adapter format notebook 05 produces
# ---------------------------------------------------------------------------


def convert_mlx_adapter_to_peft(mlx_adapter_dir, peft_adapter_dir, hf_repo):
    """Rewrite an mlx-lm LoRA adapter as a Hugging Face PEFT adapter.

    Same numbers, different packaging:

      mlx-lm   layer.lora_a  shape (in, rank)     y = Wx + scale * (x @ lora_a) @ lora_b
               layer.lora_b  shape (rank, out)
      PEFT     lora_A.weight shape (rank, in)     y = Wx + (alpha / rank) * B(A(x))
               lora_B.weight shape (out, rank)

    So: transpose both matrices, and choose alpha = scale * rank so the
    two formulas give the same output. Needs numpy + safetensors only.
    """
    from safetensors.numpy import load_file, save_file

    mlx_adapter_dir = Path(mlx_adapter_dir)
    peft_adapter_dir = Path(peft_adapter_dir)
    peft_adapter_dir.mkdir(parents=True, exist_ok=True)

    mlx_config = json.loads((mlx_adapter_dir / "adapter_config.json").read_text(encoding="utf-8"))
    lora_parameters = mlx_config["lora_parameters"]
    rank = lora_parameters["rank"]
    scale = lora_parameters["scale"]

    mlx_weights = load_file(str(mlx_adapter_dir / "adapters.safetensors"))
    peft_weights = {}
    target_modules = set()
    for mlx_name, matrix in mlx_weights.items():
        # e.g. "model.layers.0.self_attn.q_proj.lora_a"
        layer_path, _, which = mlx_name.rpartition(".")
        if which not in ("lora_a", "lora_b"):
            raise ValueError(f"Unexpected tensor in MLX adapter: {mlx_name}")
        peft_letter = "A" if which == "lora_a" else "B"
        peft_name = f"base_model.model.{layer_path}.lora_{peft_letter}.weight"
        peft_weights[peft_name] = matrix.T.astype("float16").copy()
        target_modules.add(layer_path.split(".")[-1])

    save_file(peft_weights, str(peft_adapter_dir / "adapter_model.safetensors"), metadata={"format": "pt"})

    peft_config = {
        "peft_type": "LORA",
        "task_type": "CAUSAL_LM",
        "base_model_name_or_path": hf_repo,
        "r": rank,
        "lora_alpha": scale * rank,
        "lora_dropout": lora_parameters.get("dropout", 0.0),
        "target_modules": sorted(target_modules),
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "modules_to_save": None,
        "use_rslora": False,
        "use_dora": False,
    }
    (peft_adapter_dir / "adapter_config.json").write_text(json.dumps(peft_config, indent=2), encoding="utf-8")
    return {"tensors": len(peft_weights), "rank": rank, "lora_alpha": scale * rank,
            "target_modules": sorted(target_modules)}
