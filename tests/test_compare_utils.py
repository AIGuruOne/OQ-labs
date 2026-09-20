"""Tests for notebooks/compare_utils.py and notebooks/ollama_utils.py (notebook 06).

    python -m pytest tests/test_compare_utils.py -v

No model and no Ollama server is needed: the adapter lookup works on
folders, and the example picker works on run files (contract 4).
"""

import json
import re
import shutil
import struct
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import compare_utils  # noqa: E402
import ollama_utils  # noqa: E402

PREBAKED_DIR = REPO_ROOT / "checkpoints" / "adapter_prebaked"
PREBAKED_EVAL = REPO_ROOT / "facilitator" / "prebaked_outputs" / "eval"
LLAMA_1B = "unsloth/Llama-3.2-1B-Instruct"


# ---------------------------------------------------------------------------
# Building small fake adapters
# ---------------------------------------------------------------------------


def write_safetensors(path, data_bytes=64):
    """A minimal, valid safetensors file: 8-byte header length, JSON header, data."""
    header = {"layer.weight": {"dtype": "U8", "shape": [data_bytes], "data_offsets": [0, data_bytes]}}
    header_bytes = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(header_bytes)) + header_bytes + bytes(data_bytes))


def make_adapter(folder, base_model=LLAMA_1B, data_bytes=64):
    folder.mkdir(parents=True)
    (folder / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": base_model}), encoding="utf-8")
    write_safetensors(folder / "adapter_model.safetensors", data_bytes)
    return folder


@pytest.fixture
def lab(tmp_path):
    """A fake repo with a pre-baked adapter, and an empty checkpoint folder."""
    repo_root = tmp_path / "repo"
    checkpoint_dir = tmp_path / "drive"
    checkpoint_dir.mkdir()
    make_adapter(repo_root / "checkpoints" / "adapter_prebaked", data_bytes=32)
    own_dir = checkpoint_dir / "05_finetune" / "llama3.2-1b_run1" / "adapter_final"
    return {"repo_root": repo_root, "checkpoint_dir": checkpoint_dir, "own_dir": own_dir}


def find(lab, **options):
    return compare_utils.find_adapter(lab["checkpoint_dir"], lab["repo_root"], "llama3.2-1b", "run1", **options)


# ---------------------------------------------------------------------------
# Which adapter: yours first, the pre-baked one as a VISIBLE fallback
# ---------------------------------------------------------------------------


def test_your_own_adapter_is_used_when_it_is_usable(lab):
    make_adapter(lab["own_dir"])
    found = find(lab)
    assert found["source"] == "yours"
    assert Path(found["path"]) == lab["own_dir"]
    assert found["checked"] == [{"path": str(lab["own_dir"]), "verdict": "usable"}]
    assert found["ollama_base"] == "llama3.2:1b"
    assert found["model_key"] == "llama3.2-1b"


def test_no_adapter_of_yours_falls_back_to_prebaked_and_says_where_it_looked(lab):
    found = find(lab)
    assert found["source"] == "prebaked"
    assert Path(found["path"]) == lab["repo_root"] / "checkpoints" / "adapter_prebaked"
    verdicts = [entry["verdict"] for entry in found["checked"]]
    assert verdicts == ["folder does not exist", "folder does not exist", "usable"]


def test_deleting_your_adapter_switches_to_prebaked(lab):
    make_adapter(lab["own_dir"])
    assert find(lab)["source"] == "yours"
    shutil.rmtree(lab["own_dir"])
    assert find(lab)["source"] == "prebaked"


def test_the_copy_in_the_repo_checkpoints_folder_counts_as_yours(lab):
    repo_copy = make_adapter(lab["repo_root"] / "checkpoints" / "adapter_llama3.2-1b_run1")
    found = find(lab)
    assert found["source"] == "yours"
    assert Path(found["path"]) == repo_copy


def test_a_weights_file_cut_off_by_a_disconnect_is_rejected(lab):
    make_adapter(lab["own_dir"], data_bytes=4096)
    weights = lab["own_dir"] / "adapter_model.safetensors"
    weights.write_bytes(weights.read_bytes()[:1000])
    found = find(lab)
    assert found["source"] == "prebaked"
    assert "cut off" in found["checked"][0]["verdict"]


def test_training_that_never_reached_the_save_step_is_rejected(lab):
    make_adapter(lab["own_dir"])
    (lab["own_dir"] / "adapter_model.safetensors").unlink()
    found = find(lab)
    assert found["source"] == "prebaked"
    assert "training did not reach the save step" in found["checked"][0]["verdict"]


def test_a_half_written_config_is_rejected(lab):
    make_adapter(lab["own_dir"])
    (lab["own_dir"] / "adapter_config.json").write_text('{"base_model_name', encoding="utf-8")
    found = find(lab)
    assert found["source"] == "prebaked"
    assert "not valid JSON" in found["checked"][0]["verdict"]


def test_a_smoke_test_adapter_is_rejected_because_ollama_has_no_such_model(lab):
    make_adapter(lab["own_dir"], base_model="HuggingFaceTB/SmolLM2-135M-Instruct")
    found = find(lab)
    assert found["source"] == "prebaked"
    assert "no twin in Ollama" in found["checked"][0]["verdict"]


def test_use_prebaked_skips_your_adapter_and_says_so(lab):
    make_adapter(lab["own_dir"])
    found = find(lab, use_prebaked=True)
    assert found["source"] == "prebaked"
    assert "USE_PREBAKED" in found["checked"][0]["verdict"]


def test_the_base_model_follows_the_adapter_in_use_not_the_setting(lab):
    """MODEL_NAME says 3B, but the fallback adapter sits on 1B: compare with 1B."""
    found = compare_utils.find_adapter(lab["checkpoint_dir"], lab["repo_root"], "llama3.2-3b", "run1")
    assert found["source"] == "prebaked"
    assert found["ollama_base"] == "llama3.2:1b"


def test_no_adapter_anywhere_is_a_sentence_not_a_silent_pass(lab):
    shutil.rmtree(lab["repo_root"] / "checkpoints" / "adapter_prebaked")
    with pytest.raises(FileNotFoundError, match="not even the pre-baked one"):
        find(lab)


def test_training_summary_travels_with_your_adapter(lab):
    make_adapter(lab["own_dir"])
    summary = {"steps_done": 40, "steps_planned": 72, "training_minutes": 23.0}
    (lab["own_dir"].parent / "05_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    assert find(lab)["training"] == summary


def test_fingerprint_identifies_the_weights_not_the_folder(lab):
    make_adapter(lab["own_dir"], data_bytes=32)      # same bytes as the fake pre-baked one
    assert find(lab)["fingerprint"] == find(lab, use_prebaked=True)["fingerprint"]
    assert re.fullmatch(r"[0-9a-f]{8}", find(lab)["fingerprint"])


def test_the_committed_prebaked_adapter_passes_every_check():
    assert compare_utils.adapter_problem(PREBAKED_DIR) is None
    readme = (PREBAKED_DIR / "README.md").read_text(encoding="utf-8")
    assert compare_utils.adapter_fingerprint(PREBAKED_DIR) in readme     # the README quotes the sha256


# ---------------------------------------------------------------------------
# Picking the tickets to read: by rule, never by hand
# ---------------------------------------------------------------------------

EXACT_FIELDS = ["category", "affected_system", "asset_tag", "urgency", "impact", "routing_queue"]


def fake_run(right_counts, schema_valid=None, unreadable=()):
    """right_counts: {item_id: exact fields right}. Builds the load_run() shape."""
    tickets = {}
    for item_id, right in right_counts.items():
        fields = {"(schema)": {"correct": (schema_valid or {}).get(item_id, True), "score_type": "schema",
                               "expected": "valid", "predicted": "valid", "score": 1.0}}
        for position, field in enumerate(EXACT_FIELDS):
            fields[field] = {"correct": position < right, "score_type": "exact",
                             "expected": "x", "predicted": "x", "score": 1.0}
        fields["requested_action"] = {"correct": False, "score_type": "similarity",
                                      "expected": "Do it", "predicted": "Do that", "score": 0.33}
        parse = "failed" if item_id in unreadable else "clean"
        tickets[item_id] = {"fields": fields, "reply": "{}", "parse": parse}
    return {"summary": {}, "tickets": tickets}


def test_each_rule_picks_its_ticket():
    base = fake_run({"A": 0, "B": 1, "C": 5, "D": 2, "E": 6},
                    schema_valid={"A": False}, unreadable={"A"})
    tuned = fake_run({"A": 5, "B": 5, "C": 3, "D": 2, "E": 6})
    picks = compare_utils.pick_examples(base, tuned)
    assert [(pick["rule"], pick["item_id"]) for pick in picks] == [
        ("format fixed", "A"), ("biggest gain", "B"), ("tuned worse", "C"), ("still wrong", "D")]


def test_biggest_gain_ignores_format_rescues():
    """A went 0 -> 6 only because the base reply was unreadable. The content gain is B."""
    base = fake_run({"A": 0, "X": 0, "B": 2}, schema_valid={"A": False, "X": False}, unreadable={"A", "X"})
    tuned = fake_run({"A": 6, "X": 6, "B": 4})
    picks = {pick["rule"]: pick["item_id"] for pick in compare_utils.pick_examples(base, tuned)}
    assert picks["format fixed"] == "A"
    assert picks["biggest gain"] == "B"


def test_a_rule_with_nothing_to_show_says_so():
    base = fake_run({"A": 3, "B": 3})
    tuned = fake_run({"A": 6, "B": 6})
    picks = {pick["rule"]: pick for pick in compare_utils.pick_examples(base, tuned)}
    assert picks["tuned worse"]["item_id"] is None
    assert "no ticket" in picks["tuned worse"]["why"]
    assert picks["still wrong"]["item_id"] is None
    text = compare_utils.render_example(picks["tuned worse"], "", base, tuned)
    assert "nothing to show" in text


def test_a_ticket_where_tuned_is_worse_is_always_shown_when_one_exists():
    base = fake_run({"A": 1, "B": 6, "C": 2})
    tuned = fake_run({"A": 6, "B": 5, "C": 6})
    picks = {pick["rule"]: pick["item_id"] for pick in compare_utils.pick_examples(base, tuned)}
    assert picks["tuned worse"] == "B"


def test_on_the_reference_runs_the_picks_include_a_loss_and_a_failure():
    base = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_base-1b_heldout_20")
    tuned = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_tuned_heldout_20")
    picks = compare_utils.pick_examples(base, tuned)
    assert len(picks) == 4
    by_rule = {pick["rule"]: pick["item_id"] for pick in picks}
    assert by_rule["tuned worse"] is not None, "the reference tuned model is NOT better on every ticket"
    assert by_rule["still wrong"] is not None
    assert len({item_id for item_id in by_rule.values()}) == 4, "four different tickets"


def test_rendered_examples_are_ascii_and_fit_100_columns():
    sys.path.insert(0, str(REPO_ROOT / "notebooks"))
    import dataset_utils

    base = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_base-1b_heldout_20")
    tuned = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_tuned_heldout_20")
    pairs = dataset_utils.load_jsonl(REPO_ROOT / "data" / "eval" / "heldout_20.jsonl")
    texts = {pair["ticket_id"]: dataset_utils.pair_user_text(pair) for pair in pairs}
    for item_id in base["tickets"]:
        pick = {"rule": "test", "item_id": item_id, "why": "every ticket must render"}
        text = compare_utils.render_example(pick, texts[item_id], base, tuned)
        text.encode("ascii")
        for line in text.splitlines():
            assert len(line) <= compare_utils.REPORT_WIDTH, line
            assert line == line.rstrip()


def test_an_unreadable_reply_is_shown_as_no_record_not_as_null():
    base = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_base-1b_heldout_20")
    tuned = compare_utils.load_run(PREBAKED_EVAL, "2026-09-20_tuned_heldout_20")
    unreadable = next(item_id for item_id, ticket in base["tickets"].items() if ticket["parse"] == "failed")
    pick = {"rule": "test", "item_id": unreadable, "why": "w"}
    text = compare_utils.render_example(pick, "ticket", base, tuned)
    assert "(no record)" in text
    assert "the raw reply ends" in text


def test_headline_counts_and_names_the_tickets_where_tuned_lost():
    comparison = json.loads((PREBAKED_EVAL / "comparison_base1b_vs_tuned.json").read_text(encoding="utf-8"))
    lines = compare_utils.headline(comparison)
    text = "\n".join(lines)
    assert "12/20" in text and "20/20" in text
    assert "%" not in text, "counts, not percentages"
    assert "on 2 of 20 tickets: INC-005370, INC-005480" in lines[-1]


def test_shown_command_quotes_paths_with_spaces():
    shown = compare_utils.shown_command(["python", Path("C:/Users/First Last/run_eval.py"), "--resume"])
    assert shown.startswith('python "') and shown.endswith('" --resume')


def test_run_command_streams_output_and_returns_the_exit_code(capsys):
    exit_code = compare_utils.run_command([sys.executable, "-c", "print('hello'); raise SystemExit(3)"])
    assert exit_code == 3
    assert "hello" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# ollama_utils: the pin, and the address
# ---------------------------------------------------------------------------


def test_ollama_is_pinned_to_one_exact_release():
    assert re.fullmatch(r"\d+\.\d+\.\d+", ollama_utils.OLLAMA_VERSION)
    assert ollama_utils.OLLAMA_LINUX_URL.endswith(f"?version={ollama_utils.OLLAMA_VERSION}")
    source = (REPO_ROOT / "notebooks" / "ollama_utils.py").read_text(encoding="utf-8")
    assert "install.sh" not in source.replace("install script", ""), "never pipe the moving install.sh into a shell"


def test_the_pinned_release_is_the_one_the_reference_scores_were_measured_on():
    readme = (PREBAKED_DIR / "README.md").read_text(encoding="utf-8")
    assert f"Ollama {ollama_utils.OLLAMA_VERSION}" in readme


def test_command_line_and_notebook_talk_to_the_same_server(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "restored-after-the-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11999/")
    assert ollama_utils.server_url() == "http://localhost:11999"
    assert ollama_utils.point_command_line_at_server(ollama_utils.server_url()) == "localhost:11999"


def test_no_server_is_none_not_an_exception(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")      # nothing listens on port 9
    assert ollama_utils.server_version() is None


def test_a_laptop_without_ollama_gets_a_sentence_pointing_at_the_guide(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_HOST", "restored-after-the-test")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(ollama_utils.shutil, "which", lambda name: None)
    with pytest.raises(ollama_utils.OllamaError, match="setup/ollama_setup.md"):
        ollama_utils.ensure_server(in_colab=False, log_dir=tmp_path)
