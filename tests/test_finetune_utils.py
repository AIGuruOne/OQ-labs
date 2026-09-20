"""Tests for notebooks/finetune_utils.py - the fine-tune lab's plumbing.

    python -m pytest tests/test_finetune_utils.py -v

No GPU, no network, no model download. Tests that need torch,
safetensors or jinja2 skip themselves when the package is missing, so
this file also passes in the base environment (requirements.txt only).
"""

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import dataset_utils  # noqa: E402
import finetune_utils  # noqa: E402


# ---------------------------------------------------------------------------
# The dataset
# ---------------------------------------------------------------------------


def test_cleaning_the_committed_files_gives_the_notebook_04_numbers():
    train_clean, val_clean = finetune_utils.clean_committed_dataset(REPO_ROOT)
    assert len(train_clean) == 373
    assert len(val_clean) == 72


def test_cleaned_dataset_never_contains_a_heldout_ticket():
    train_clean, val_clean = finetune_utils.clean_committed_dataset(REPO_ROOT)
    heldout = dataset_utils.load_jsonl(REPO_ROOT / "data" / "eval" / "heldout_20.jsonl")
    heldout_ids = {pair["ticket_id"] for pair in heldout}
    clean_ids = {pair["ticket_id"] for pair in train_clean + val_clean}
    assert heldout_ids & clean_ids == set()


def test_load_clean_pairs_prefers_the_notebook_04_output(tmp_path):
    dataset_dir = tmp_path / "04_dataset"
    pair = {"ticket_id": "INC-000001", "messages": []}
    dataset_utils.write_jsonl(dataset_dir / "train_clean.jsonl", [pair, pair])
    dataset_utils.write_jsonl(dataset_dir / "val_clean.jsonl", [pair])
    train_pairs, val_pairs, source = finetune_utils.load_clean_pairs(REPO_ROOT, tmp_path)
    assert (len(train_pairs), len(val_pairs)) == (2, 1)
    assert "notebook 04" in source


def test_load_clean_pairs_falls_back_to_the_committed_files(tmp_path):
    train_pairs, val_pairs, source = finetune_utils.load_clean_pairs(REPO_ROOT, tmp_path)
    assert (len(train_pairs), len(val_pairs)) == (373, 72)
    assert "data/finetune" in source


# ---------------------------------------------------------------------------
# The serving template
# ---------------------------------------------------------------------------

MESSAGES = [
    {"role": "system", "content": "SYSTEM TEXT"},
    {"role": "user", "content": "Subject: x\n\nbody"},
    {"role": "assistant", "content": '{"category": "access"}'},
]

# What Ollama's llama3.2 template renders (`ollama show llama3.2:3b --template`),
# written out by hand. The training text has to be exactly this.
OLLAMA_PROMPT = (
    "<BOS><|start_header_id|>system<|end_header_id|>\n\n"
    "Cutting Knowledge Date: December 2023\n\n"
    "SYSTEM TEXT<|eot_id|>"
    "<|start_header_id|>user<|end_header_id|>\n\n"
    "Subject: x\n\nbody<|eot_id|>"
    "<|start_header_id|>assistant<|end_header_id|>\n\n"
)


def render(messages, add_generation_prompt):
    jinja2 = pytest.importorskip("jinja2")
    from jinja2.sandbox import ImmutableSandboxedEnvironment

    # The same environment settings transformers uses for chat templates.
    environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
    template = environment.from_string(finetune_utils.LLAMA3_SERVING_TEMPLATE)
    return template.render(messages=messages, bos_token="<BOS>", add_generation_prompt=add_generation_prompt)


def test_serving_template_prompt_is_exactly_what_ollama_sends():
    assert render(MESSAGES[:2], add_generation_prompt=True) == OLLAMA_PROMPT


def test_serving_template_full_row_is_the_prompt_plus_the_answer():
    full_row = render(MESSAGES, add_generation_prompt=False)
    assert full_row == OLLAMA_PROMPT + '{"category": "access"}<|eot_id|>'
    assert "Today Date" not in full_row


def test_use_serving_template_only_touches_llama3_tokenizers():
    llama_tokenizer = SimpleNamespace(chat_template="...<|start_header_id|>...Today Date...")
    other_tokenizer = SimpleNamespace(chat_template="<|im_start|>...")
    finetune_utils.use_serving_template(llama_tokenizer)
    finetune_utils.use_serving_template(other_tokenizer)
    assert llama_tokenizer.chat_template == finetune_utils.LLAMA3_SERVING_TEMPLATE
    assert other_tokenizer.chat_template == "<|im_start|>..."


# ---------------------------------------------------------------------------
# Tokenising and the loss mask
# ---------------------------------------------------------------------------


class FakeTokenizer:
    """One token per character, with a recognisable template - enough to
    test the masking arithmetic without downloading a real tokenizer."""

    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False, return_dict=True):
        text = "".join(f"[{message['role']}]{message['content']}" for message in messages)
        if add_generation_prompt:
            text += "[assistant]"
        return {"input_ids": [ord(character) for character in text]}


def test_only_the_answer_is_graded():
    pair = {"ticket_id": "INC-000001", "messages": MESSAGES}
    row = finetune_utils.tokenize_pair(pair, FakeTokenizer(), max_length=500)
    graded = [token for token, label in zip(row["input_ids"], row["labels"]) if label != finetune_utils.IGNORE_LABEL]
    assert "".join(chr(token) for token in graded) == MESSAGES[2]["content"]
    assert len(row["input_ids"]) == len(row["labels"]) == len(row["attention_mask"])


def test_a_row_that_is_too_long_is_refused_not_truncated():
    pair = {"ticket_id": "INC-000001", "messages": MESSAGES}
    with pytest.raises(ValueError, match="INC-000001"):
        finetune_utils.tokenize_pair(pair, FakeTokenizer(), max_length=10)


def test_count_tokens():
    pair = {"ticket_id": "INC-000001", "messages": MESSAGES}
    dataset = finetune_utils.build_token_dataset([pair, pair], FakeTokenizer(), max_length=500)
    all_tokens, graded_tokens = finetune_utils.count_tokens(dataset)
    assert graded_tokens == 2 * len(MESSAGES[2]["content"])
    assert all_tokens > graded_tokens


def test_pad_collator_pads_right_and_never_grades_padding():
    pytest.importorskip("torch")
    rows = [
        {"input_ids": [5, 6, 7], "attention_mask": [1, 1, 1], "labels": [-100, 6, 7]},
        {"input_ids": [5], "attention_mask": [1], "labels": [5]},
    ]
    batch = finetune_utils.PadCollator(pad_token_id=0)(rows)
    assert batch["input_ids"].tolist() == [[5, 6, 7], [5, 0, 0]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [1, 0, 0]]
    assert batch["labels"].tolist() == [[-100, 6, 7], [5, -100, -100]]


# ---------------------------------------------------------------------------
# The run folder
# ---------------------------------------------------------------------------

SETTINGS = {"model": "m", "lora_rank": 16, "target_modules": ["q_proj", "v_proj"], "learning_rate": 2e-4}


def test_run_folder_new_then_resume_then_finished(tmp_path):
    run_dir = tmp_path / "run1"
    assert finetune_utils.check_run_folder(run_dir, SETTINGS) == "new"
    assert finetune_utils.check_run_folder(run_dir, SETTINGS) == "resume"
    final_dir = run_dir / finetune_utils.FINAL_ADAPTER_FOLDER
    final_dir.mkdir()
    (final_dir / "adapter_model.safetensors").write_bytes(b"x")
    assert finetune_utils.check_run_folder(run_dir, SETTINGS) == "finished"


def test_run_folder_refuses_different_settings_and_names_them(tmp_path):
    run_dir = tmp_path / "run1"
    finetune_utils.check_run_folder(run_dir, SETTINGS)
    changed = dict(SETTINGS, lora_rank=8)
    with pytest.raises(RuntimeError, match="lora_rank"):
        finetune_utils.check_run_folder(run_dir, changed)


def test_last_checkpoint_skips_a_half_written_folder(tmp_path):
    for step in (10, 20, 30):
        (tmp_path / f"checkpoint-{step}").mkdir()
    (tmp_path / "checkpoint-10" / "trainer_state.json").write_text("{}")
    (tmp_path / "checkpoint-20" / "trainer_state.json").write_text("{}")
    # checkpoint-30 has no trainer_state.json: the runtime died mid-save.
    assert finetune_utils.find_last_checkpoint(tmp_path).name == "checkpoint-20"


def test_last_checkpoint_is_none_in_an_empty_folder(tmp_path):
    assert finetune_utils.find_last_checkpoint(tmp_path) is None


def test_last_checkpoint_sorts_by_number_not_by_text(tmp_path):
    for step in (9, 10):
        (tmp_path / f"checkpoint-{step}").mkdir()
        (tmp_path / f"checkpoint-{step}" / "trainer_state.json").write_text("{}")
    assert finetune_utils.find_last_checkpoint(tmp_path).name == "checkpoint-10"


# ---------------------------------------------------------------------------
# The progress callback: logging, resume bookkeeping, the time budget
# ---------------------------------------------------------------------------


def fake_trainer_objects(global_step, max_steps=72):
    state = SimpleNamespace(global_step=global_step, max_steps=max_steps)
    control = SimpleNamespace(should_save=False, should_training_stop=False)
    return state, control


def test_callback_logs_loss_and_validation_loss(tmp_path, capsys):
    callback = finetune_utils.ProgressCallback(tmp_path, budget_minutes=25)
    state, control = fake_trainer_objects(global_step=0)
    callback.on_train_begin(None, state, control)
    state.global_step = 2
    callback.on_log(None, state, control, logs={"loss": 0.51234, "learning_rate": 1e-4, "epoch": 0.08})
    callback.on_log(None, state, control, logs={"eval_loss": 0.4, "epoch": 1.0})
    callback.on_log(None, state, control, logs={"train_runtime": 12.0})     # the end-of-run summary: ignored
    log = finetune_utils.load_loss_log(tmp_path)
    assert [sorted(entry) for entry in log] == [
        ["epoch", "learning_rate", "loss", "minutes", "step"],
        ["epoch", "eval_loss", "minutes", "step"],
    ]
    assert log[0]["loss"] == 0.5123
    assert "step    2/72" in capsys.readouterr().out


def test_callback_resume_drops_lost_steps_and_keeps_the_clock(tmp_path):
    first_session = finetune_utils.ProgressCallback(tmp_path, budget_minutes=25)
    state, control = fake_trainer_objects(global_step=0)
    first_session.on_train_begin(None, state, control)
    for step in (2, 4, 6):
        state.global_step = step
        first_session.on_log(None, state, control, logs={"loss": 1.0 / step, "epoch": step / 24})
        if step == 4:
            first_session.session_start -= 300          # pretend 5 minutes passed
            first_session.on_save(None, state, control)  # checkpoint-4 is the last one written
    # The runtime dies after step 6 was logged but before it was checkpointed.

    second_session = finetune_utils.ProgressCallback(tmp_path, budget_minutes=25)
    state, control = fake_trainer_objects(global_step=4)
    second_session.on_train_begin(None, state, control)
    assert [entry["step"] for entry in finetune_utils.load_loss_log(tmp_path)] == [2, 4]
    assert second_session.training_seconds() >= 300


def test_callback_stops_at_the_budget_and_asks_for_a_save(tmp_path):
    callback = finetune_utils.ProgressCallback(tmp_path, budget_minutes=25)
    state, control = fake_trainer_objects(global_step=0)
    callback.on_train_begin(None, state, control)

    state.global_step = 10
    callback.on_step_end(None, state, control)
    assert not control.should_training_stop

    reserve = finetune_utils.BUDGET_RESERVE_MINUTES
    callback.session_start = time.time() - (25 - reserve) * 60 - 1
    callback.on_step_end(None, state, control)
    assert control.should_training_stop and control.should_save
    assert callback.stopped_by_budget


def test_callback_does_not_report_a_budget_stop_on_the_last_step(tmp_path):
    callback = finetune_utils.ProgressCallback(tmp_path, budget_minutes=25)
    state, control = fake_trainer_objects(global_step=72)
    callback.on_train_begin(None, state, control)
    callback.session_start = time.time() - 3600
    callback.on_step_end(None, state, control)
    assert not callback.stopped_by_budget


# ---------------------------------------------------------------------------
# Checking a reply
# ---------------------------------------------------------------------------

GOOD_RECORD = {
    "category": "access", "affected_system": None, "asset_tag": None, "urgency": "low",
    "impact": "single_user", "requested_action": "Reset the password", "routing_queue": "identity_access",
}


@pytest.fixture(scope="module")
def schema():
    return dataset_utils.load_schema(REPO_ROOT / "data" / "finetune" / "ticket_schema.json")


def test_a_clean_record_is_valid(schema):
    verdict = finetune_utils.check_reply(json.dumps(GOOD_RECORD), schema)
    assert verdict["valid"] and verdict["problems"] == []


def test_fenced_json_is_not_valid(schema):
    fenced = "```json\n" + json.dumps(GOOD_RECORD) + "\n```"
    assert not finetune_utils.check_reply(fenced, schema)["valid"]


def test_a_value_outside_an_enum_is_not_valid_and_the_field_is_named(schema):
    # routing_queue is a free string in the locked schema, so an invented
    # queue is the eval harness's job ("invented values"), not this check's.
    record = dict(GOOD_RECORD, urgency="urgent")
    verdict = finetune_utils.check_reply(json.dumps(record), schema)
    assert not verdict["valid"]
    assert any("urgency" in problem for problem in verdict["problems"])


def test_json_that_is_not_an_object_is_not_valid(schema):
    assert not finetune_utils.check_reply("[1, 2]", schema)["valid"]


# ---------------------------------------------------------------------------
# MLX adapter -> PEFT adapter
# ---------------------------------------------------------------------------


def test_converted_adapter_computes_the_same_numbers(tmp_path):
    numpy = pytest.importorskip("numpy")
    safetensors_numpy = pytest.importorskip("safetensors.numpy")

    rank, scale, inputs, outputs = 4, 2.0, 12, 6
    generator = numpy.random.default_rng(0)
    lora_a = generator.normal(size=(inputs, rank)).astype("float32")
    lora_b = generator.normal(size=(rank, outputs)).astype("float32")
    layer = "model.layers.0.self_attn.q_proj"

    mlx_dir = tmp_path / "mlx_adapter"
    mlx_dir.mkdir()
    safetensors_numpy.save_file({f"{layer}.lora_a": lora_a, f"{layer}.lora_b": lora_b},
                                str(mlx_dir / "adapters.safetensors"))
    mlx_config = {"lora_parameters": {"rank": rank, "scale": scale, "dropout": 0.05}}
    (mlx_dir / "adapter_config.json").write_text(json.dumps(mlx_config))

    peft_dir = tmp_path / "peft_adapter"
    info = finetune_utils.convert_mlx_adapter_to_peft(mlx_dir, peft_dir, "unsloth/Llama-3.2-1B-Instruct")

    peft_config = json.loads((peft_dir / "adapter_config.json").read_text())
    peft_weights = safetensors_numpy.load_file(str(peft_dir / "adapter_model.safetensors"))
    matrix_a = peft_weights[f"base_model.model.{layer}.lora_A.weight"].astype("float32")
    matrix_b = peft_weights[f"base_model.model.{layer}.lora_B.weight"].astype("float32")
    assert matrix_a.shape == (rank, inputs) and matrix_b.shape == (outputs, rank)

    x = generator.normal(size=(3, inputs)).astype("float32")
    mlx_output = scale * (x @ lora_a) @ lora_b
    peft_scaling = peft_config["lora_alpha"] / peft_config["r"]
    peft_output = peft_scaling * (x @ matrix_a.T) @ matrix_b.T
    assert numpy.allclose(mlx_output, peft_output, rtol=1e-2, atol=1e-2)      # float16 storage

    assert peft_config["target_modules"] == ["q_proj"]
    assert peft_config["base_model_name_or_path"] == "unsloth/Llama-3.2-1B-Instruct"
    assert info["tensors"] == 2


# ---------------------------------------------------------------------------
# Model choices stay consistent with the rest of the repo
# ---------------------------------------------------------------------------


def test_every_servable_model_choice_is_complete():
    for name, choice in finetune_utils.MODEL_CHOICES.items():
        assert set(choice) == {"hf_repo", "ollama_base", "mlx_repo"}, name
    assert finetune_utils.MODEL_CHOICES["smoke-test"]["ollama_base"] is None
