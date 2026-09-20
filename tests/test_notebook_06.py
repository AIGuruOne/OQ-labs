"""Hygiene checks for notebooks/06_compare_base_tuned.ipynb and its solution.

    python -m pytest tests/test_notebook_06.py -v

These read the .ipynb files; they do not execute them. Executing needs
an Ollama server with llama3.2:1b (about 3 minutes on a laptop CPU):

    python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/06_compare_base_tuned.ipynb
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "06_compare_base_tuned.ipynb"
TODO_CELL_IDS = ["tuned-todo", "compare-todo", "reflect-todo"]


def load_cells(folder):
    notebook = json.loads((REPO_ROOT / folder / NAME).read_text(encoding="utf-8"))
    return notebook["cells"]


def source_of(cell):
    return "".join(cell["source"])


def printed_by(cell):
    return "".join("".join(output.get("text", "")) for output in cell["outputs"])


def cell_by_id(cells, cell_id):
    return next(cell for cell in cells if cell["id"] == cell_id)


@pytest.fixture(scope="module")
def participant_cells():
    return load_cells("notebooks")


@pytest.fixture(scope="module")
def solution_cells():
    return load_cells("solutions")


# ---------------------------------------------------------------------------
# Contract 2: the conventions every notebook follows
# ---------------------------------------------------------------------------


def test_participant_outputs_are_cleared(participant_cells):
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [], f"cell {cell['id']} has outputs"
            assert cell["execution_count"] is None, f"cell {cell['id']} has an execution count"


def test_the_two_versions_differ_only_in_the_todo_cells(participant_cells, solution_cells):
    assert [cell["id"] for cell in participant_cells] == [cell["id"] for cell in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            assert source_of(mine) != source_of(theirs)
        else:
            assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs between the two versions"


def test_todo_cells_have_a_gap_a_hint_and_a_loud_failure(participant_cells):
    todo_cells = [cell for cell in participant_cells if cell["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 3
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "..." in source
        assert "Hint:" in source
        assert f"TODO {number} is not filled in yet" in source


def test_the_solution_has_no_gap_left(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            for line in source_of(cell).splitlines():
                code = line.split("#")[0]
                assert "= ..." not in code and ": ...," not in code, f"cell {cell['id']}: {line}"


def test_first_code_cell_is_the_environment_detection_cell(participant_cells):
    template = json.loads((REPO_ROOT / "notebooks" / "_template.ipynb").read_text(encoding="utf-8"))
    template_first_code = next(cell for cell in template["cells"] if cell["cell_type"] == "code")
    first_code = next(cell for cell in participant_cells if cell["cell_type"] == "code")
    assert source_of(first_code) == source_of(template_first_code)


def test_every_code_cell_has_a_markdown_cell_before_it(participant_cells):
    for position, cell in enumerate(participant_cells):
        if cell["cell_type"] == "code":
            assert participant_cells[position - 1]["cell_type"] == "markdown", f"cell {cell['id']}"


def test_header_declares_runtime_needs_and_correct_result(participant_cells):
    header = source_of(participant_cells[0])
    for phrase in ["**Expected runtime:**", "**Needs:**", "**A correct result looks like:**",
                   "25 minutes", "COMPARISON READY", "If the runtime disconnects"]:
        assert phrase in header, phrase
    assert "TBD" not in header and "__" not in header, "header still has a placeholder"


def test_installs_are_exactly_pinned_and_match_requirements(participant_cells):
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    install_lines = [line for cell in participant_cells for line in source_of(cell).splitlines()
                     if "%pip install" in line]
    assert install_lines, "no install cell"
    for line in install_lines:
        assert "-U" not in line.split() and "--upgrade" not in line
        packages = [word for word in line.split() if "==" in word]
        assert packages, f"unpinned install: {line}"
        for package in packages:
            assert package in requirements, f"{package} is not pinned in requirements.txt"


def test_never_asks_for_a_bigger_accelerator_or_pro(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        source = source_of(cell)
        for forbidden in ["A100", "L4 GPU", "V100", "High-RAM"]:
            assert forbidden not in source
    metadata = json.loads((REPO_ROOT / "notebooks" / NAME).read_text(encoding="utf-8"))["metadata"]
    assert metadata["colab"]["gpuType"] == "T4"


def test_no_version_touches_the_facilitator_answer_key(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        assert "planted_problems" not in source_of(cell)
        assert "plant_problems" not in source_of(cell)


# ---------------------------------------------------------------------------
# What this lab promises: one command, one table, a visible fallback
# ---------------------------------------------------------------------------


def command_words(cell, list_name):
    """The lines inside `<list_name> = [ ... ]` in a cell."""
    source = source_of(cell)
    body = source.split(f"{list_name} = [", 1)[1].split("\n]", 1)[0]
    return [line.strip().rstrip(",") for line in body.splitlines() if line.strip()]


def test_base_and_tuned_are_the_same_command_with_a_different_endpoint(solution_cells):
    base_words = command_words(cell_by_id(solution_cells, "base-run"), "base_command")
    tuned_words = command_words(cell_by_id(solution_cells, "tuned-todo"), "tuned_command")
    assert len(base_words) == len(tuned_words)
    differing = [(base, tuned) for base, tuned in zip(base_words, tuned_words) if base != tuned]
    assert differing == [('"--endpoint", "local"', '"--endpoint", tuned_endpoint'),
                         ('"--label", "base"', '"--label", tuned_label'),
                         ('"--run-id", base_run_id', '"--run-id", tuned_run_id')]


def test_every_score_comes_from_run_eval_not_from_the_notebook(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    assert sources.count("sys.executable, run_eval_script") == 3       # base, tuned, compare
    assert '"--compare"' in sources
    for forbidden in ["eval_scoring", "score_item", "accuracy ="]:
        assert forbidden not in sources, "the notebook must not score anything itself"


def test_a_disconnect_costs_one_ticket_not_the_run(participant_cells):
    base_source = source_of(cell_by_id(participant_cells, "base-run"))
    tuned_source = source_of(cell_by_id(participant_cells, "tuned-todo"))
    assert '"--resume"' in base_source and '"--resume"' in tuned_source
    assert '"--out", eval_dir' in base_source and '"--out", eval_dir' in tuned_source
    settings = source_of(cell_by_id(participant_cells, "settings"))
    assert 'eval_dir = CHECKPOINT_DIR / "eval"' in settings         # Drive on Colab (contract 4)


def test_saved_replies_can_never_belong_to_another_adapter(participant_cells):
    """--resume reuses replies by run id, so the run id must name the adapter's weights."""
    tuned_source = source_of(cell_by_id(participant_cells, "tuned-todo"))
    assert "adapter['fingerprint']" in tuned_source.split("tuned_run_id =", 1)[1].splitlines()[0]


def test_the_fallback_is_announced_in_the_adapter_cell_and_again_at_the_end(participant_cells):
    adapter_source = source_of(cell_by_id(participant_cells, "adapter"))
    assert "ADAPTER IN USE: THE PRE-BAKED ONE - NOT an adapter you trained" in adapter_source
    assert "ADAPTER IN USE: YOURS" in adapter_source
    assert 'adapter["checked"]' in adapter_source                   # every folder it looked at is printed
    final_source = source_of(participant_cells[-1])
    assert "PRE-BAKED" in final_source and "YOURS" in final_source


def test_the_lab_is_colab_t4_only_and_never_recommends_a_laptop(participant_cells):
    """Decision 2026-09-21 (setup/ollama_setup.md): current Ollama releases refuse
    LoRA adapters, so the tuned endpoint is supported on Colab only."""
    header = source_of(participant_cells[0])
    assert "free T4 GPU runtime" in header
    assert "only supported place" in header
    assert "A laptop is not a supported path for the tuned model" in header

    ollama_source = source_of(cell_by_id(participant_cells, "ollama"))
    assert "LOCAL RUN - NOT A SUPPORTED PATH FOR THIS LAB" in ollama_source
    assert "Do not reinstall Ollama in the room" in ollama_source
    # The Colab-without-GPU stop must send people to a T4 or the pre-baked table, not to a laptop.
    no_gpu_message = ollama_source.split("if IN_COLAB and gpu_name is None:", 1)[1].split("raise RuntimeError", 1)[0]
    assert "T4 GPU" in no_gpu_message and "pre-baked table" in no_gpu_message
    assert "A laptop is NOT the way out" in no_gpu_message
    assert "on a laptop with Ollama" not in no_gpu_message

    setup_guide = (REPO_ROOT / "setup" / "ollama_setup.md").read_text(encoding="utf-8")
    assert "The tuned endpoint is Colab T4 only" in setup_guide
    assert "ollama --version" in setup_guide and "pre-program email" in setup_guide


def test_a_failed_registration_stops_the_notebook(participant_cells):
    """Otherwise the tuned run would score whatever older model still has the name."""
    register_source = source_of(cell_by_id(participant_cells, "register"))
    assert "assert register_exit_code == 0" in register_source


def test_the_reflection_is_the_rubric_tally_sheet(participant_cells):
    reflect_source = source_of(cell_by_id(participant_cells, "reflect-todo"))
    for key in ["schema_valid", "whole_record", "invented_values", "not_fixed", "tuned_did_worse_on",
                "h1_pattern", "h1_whose_job", "h2_adequate", "fix_first", "fix_with"]:
        assert f'"{key}": ...,' in reflect_source, key
    rubric = (REPO_ROOT / "data" / "eval" / "rubric.md").read_text(encoding="utf-8")
    for phrase in ["prompt / tuning / retrieval / validator", "over / under / mixed / none"]:
        assert phrase in rubric, "the rubric's tally sheet changed - update TODO 3 to match"


# ---------------------------------------------------------------------------
# The solution's retained output is a real run
# ---------------------------------------------------------------------------


def test_solution_outputs_are_retained_and_error_free(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] != [], f"solution cell {cell['id']} has no output"
            for output in cell["outputs"]:
                assert output["output_type"] != "error", f"solution cell {cell['id']} ended in an error"


def test_solution_prints_the_declared_result_and_names_the_adapter(solution_cells):
    printed = printed_by(solution_cells[-1])
    assert "COMPARISON READY" in printed
    assert "adapter in use : " in printed
    assert "ADAPTER IN USE:" in printed_by(cell_by_id(solution_cells, "adapter"))


def test_solution_reference_run_is_a_first_run_not_a_resumed_one(solution_cells):
    for cell_id in ["base-run", "tuned-todo"]:
        printed = printed_by(cell_by_id(solution_cells, cell_id))
        assert "--resume: 0 saved replies found" in printed, f"{cell_id}: re-execute after deleting the eval folder"
        assert "saved reply reused" not in printed


def test_solution_shows_one_table_for_the_same_20_tickets(solution_cells):
    printed = printed_by(cell_by_id(solution_cells, "compare-todo"))
    assert printed.count("COMPARISON  the same 20 tickets for every run") == 1
    assert "READ THIS BEFORE QUOTING A NUMBER" in printed


def test_solution_is_honest_the_tuned_model_does_not_win_everything(solution_cells):
    """If this fails after a re-bake, do not edit the test: find out why the tuned
    model suddenly wins every ticket (leakage? a scoring change?) and tell Utkarsh."""
    examples = printed_by(cell_by_id(solution_cells, "examples"))
    assert "[tuned worse]" in examples and "did WORSE than the base model" in examples
    assert "[still wrong]" in examples
    assert "got FEWER fields right than 'base' on 0 of" not in printed_by(solution_cells[-1])


def test_solution_reflection_quotes_the_numbers_of_its_own_retained_table(solution_cells):
    reflect_source = source_of(cell_by_id(solution_cells, "reflect-todo"))
    final_printed = printed_by(solution_cells[-1])
    for title, key in [("FORMAT  schema-valid", "schema_valid"), ("RECORD  all six exact fields", "whole_record"),
                       ("INVENTED values (a count)", "invented_values")]:
        table_line = next(line for line in final_printed.splitlines() if title in line)
        base_value, tuned_value = table_line.split()[-2:]
        reflection_line = next(line for line in reflect_source.splitlines() if f'"{key}":' in line)
        assert f'"{base_value} -> {tuned_value}' in reflection_line, (table_line, reflection_line)


def test_no_secret_in_the_retained_output(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            printed = printed_by(cell)
            assert "sk-" not in printed and "OPENAI_API_KEY=" not in printed
