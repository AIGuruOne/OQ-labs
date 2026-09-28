"""Hygiene checks for notebooks/05_finetune.ipynb and its solution.

    python -m pytest tests/test_notebook_05.py -v

These read the .ipynb files; they do not execute them. A full run needs
a GPU (or hours of CPU). The plumbing-only run that works anywhere is:

    OQ_SMOKE_TEST=1 python -m nbconvert --to notebook --execute --output /tmp/smoke.ipynb solutions/05_finetune.ipynb
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "05_finetune.ipynb"
TODO_CELL_IDS = ["lora-todo", "train-todo"]


def load_cells(folder):
    notebook = json.loads((REPO_ROOT / folder / NAME).read_text(encoding="utf-8"))
    return notebook["cells"]


def source_of(cell):
    return "".join(cell["source"])


@pytest.fixture(scope="module")
def participant_cells():
    return load_cells("notebooks")


@pytest.fixture(scope="module")
def solution_cells():
    return load_cells("solutions")


def test_participant_outputs_are_cleared(participant_cells):
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [], f"cell {cell['id']} has outputs"
            assert cell["execution_count"] is None, f"cell {cell['id']} has an execution count"


def test_the_two_versions_match_outside_the_todo_cells(participant_cells, solution_cells):
    """The TODO values were pre-filled in place on 2026-09-28, for the three-person
    delivery: a blocking assert mid-session cost more room time than the gap bought.

    The TODO cells may still differ between the two copies, because the participant
    copy keeps its hint comment (the facilitator talks through it) where the solution
    replaced the hint with its answer. Everything outside a TODO cell must match.
    The gapped originals are kept under the git tag `labs-with-todo-gaps`.
    """
    assert [cell["id"] for cell in participant_cells] == [cell["id"] for cell in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            continue
        assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs between the two versions"

def test_todo_cells_keep_their_marker_hint_and_loud_failure(participant_cells):
    """Pre-filled, but every TODO cell keeps its marker, its hint and its assert.

    The hint is what the facilitator discusses instead of having people type it, and
    the assert still fires if a value is edited back into an unusable state.
    """
    todo_cells = [cell for cell in participant_cells if cell["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 2
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "Hint:" in source
        assert f'"TODO {number} is not filled in yet"' in source
        for line in source.splitlines():
            code = line.split("#")[0]
            assert "= ..." not in code and ": ...," not in code, f"gap left in {cell['id']}: {line}"

def test_the_todos_are_the_decisions_not_the_plumbing(participant_cells):
    """The participant's eight choices - rank / alpha / dropout / target modules, and
    epochs / lr / batch / accumulation - are still the only values the TODO cells
    surface. They are pre-filled now rather than blank, so this checks the set of
    decisions has not grown or moved, not that they are empty.
    """
    decisions = []
    for cell in participant_cells:
        if cell["id"] not in TODO_CELL_IDS:
            continue
        for line in source_of(cell).splitlines():
            name = line.split("=")[0].strip()
            if "=" in line and name.isupper() and not line.startswith((" ", "\t")):
                decisions.append(name)
    assert decisions == ["LORA_RANK", "LORA_ALPHA", "LORA_DROPOUT", "TARGET_MODULES",
                         "NUM_EPOCHS", "LEARNING_RATE", "BATCH_SIZE", "GRADIENT_ACCUMULATION"]

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
    for phrase in ["**Expected runtime:**", "**Needs:**", "**A correct result looks like:**", "25 minutes", "T4"]:
        assert phrase in header, phrase
    assert "TBD" not in header and "__" not in header, "header still has a placeholder"


def test_installs_are_exactly_pinned_and_match_requirements_finetune(participant_cells):
    requirements = (REPO_ROOT / "requirements-finetune.txt").read_text(encoding="utf-8")
    install_lines = [line for cell in participant_cells for line in source_of(cell).splitlines()
                     if "%pip install" in line]
    assert install_lines, "no install cell"
    for line in install_lines:
        assert "-U" not in line.split() and "--upgrade" not in line
        packages = [word for word in line.split() if "==" in word]
        assert packages, f"unpinned install: {line}"
        for package in packages:
            assert package in requirements, f"{package} is not pinned in requirements-finetune.txt"


def test_colab_never_reinstalls_what_it_already_ships(participant_cells):
    """Reinstalling torch or transformers on a cold runtime costs minutes
    and can force a restart. Only bitsandbytes is missing on Colab."""
    for cell in participant_cells:
        for line in source_of(cell).splitlines():
            if "%pip install" in line:
                for package in ["torch", "transformers", "peft", "accelerate", "unsloth"]:
                    assert f"{package}==" not in line, f"{package} must not be installed on Colab"


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


def test_training_is_resumable_and_budgeted(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    assert "resume_from_checkpoint" in sources
    assert "find_last_checkpoint" in sources
    assert "check_run_folder" in sources
    assert "TRAINING_BUDGET_MINUTES = 25" in sources
    assert "output_dir=str(run_dir)" in sources          # checkpoints go under CHECKPOINT_DIR (Drive on Colab)


def solution_has_outputs(solution_cells):
    return any(cell["cell_type"] == "code" and cell["outputs"] for cell in solution_cells)


def test_solution_outputs_are_retained_and_error_free(solution_cells):
    if not solution_has_outputs(solution_cells):
        pytest.skip("solutions/05_finetune.ipynb has not been executed yet (needs a T4, or hours of CPU)")
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] != [], f"solution cell {cell['id']} has no output"
            for output in cell["outputs"]:
                assert output["output_type"] != "error", f"solution cell {cell['id']} ended in an error"


def test_solution_prints_the_declared_result(solution_cells):
    if not solution_has_outputs(solution_cells):
        pytest.skip("solutions/05_finetune.ipynb has not been executed yet (needs a T4, or hours of CPU)")
    final_cell = solution_cells[-1]
    printed = "".join("".join(output.get("text", "")) for output in final_cell["outputs"])
    assert "ADAPTER READY" in printed
    assert "SMOKE TEST" not in printed, "the reference output must be a real run, not the smoke test"
