"""Hygiene checks for notebooks/05b_finetune_mlx.ipynb and its solution.

    python -m pytest tests/test_notebook_05b.py -v

These read the .ipynb files; they do not execute them. 05b needs MLX,
which means an Apple Silicon Mac - or, for the plumbing only, MLX's
Linux CPU backend (`pip install "mlx[cpu]"` in a Linux container) with
OQ_SMOKE_TEST=1.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "05b_finetune_mlx.ipynb"
TODO_CELL_IDS = ["lora-todo", "train-todo"]


def load_cells(folder, name=NAME):
    notebook = json.loads((REPO_ROOT / folder / name).read_text(encoding="utf-8"))
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
            assert cell["execution_count"] is None


def test_the_two_versions_differ_only_in_the_todo_cells(participant_cells, solution_cells):
    assert [cell["id"] for cell in participant_cells] == [cell["id"] for cell in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            assert source_of(mine) != source_of(theirs)
        else:
            assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs between the two versions"


def test_todo_cells_have_a_gap_a_hint_and_a_loud_failure(participant_cells):
    todo_cells = [cell for cell in participant_cells if cell["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 2
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "= ...  " in source
        assert "Hint:" in source
        assert f'"TODO {number} is not filled in yet"' in source


def test_the_decisions_are_the_same_ones_as_notebook_05(participant_cells):
    """A group on a Mac and a group on Colab must be able to compare notes:
    same variable names, same hinted values."""
    def gaps(cells):
        found = []
        for cell in cells:
            if cell["cell_type"] == "code":
                found += [line.split("=")[0].strip() for line in source_of(cell).splitlines() if "= ...  " in line]
        return found

    assert gaps(participant_cells) == gaps(load_cells("notebooks", "05_finetune.ipynb"))

    def solution_values(name):
        cells = load_cells("solutions", name)
        lines = [line for cell in cells if cell["id"] in TODO_CELL_IDS for line in source_of(cell).splitlines()
                 if line.split("=")[0].strip().isupper() and "=" in line and "assert" not in line and "if " not in line
                 and not line.startswith(" ")]
        return sorted(lines)

    assert solution_values(NAME) == solution_values("05_finetune.ipynb")


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
    for phrase in ["**Expected runtime:**", "**Needs:**", "**A correct result looks like:**", "Apple Silicon"]:
        assert phrase in header, phrase


def test_header_does_not_claim_a_mac_timing_that_was_never_measured(participant_cells):
    """Remove this test the day a real Apple Silicon run is in docs/timing_log.md
    and the header carries its number."""
    header = source_of(participant_cells[0])
    timing_log = (REPO_ROOT / "docs" / "timing_log.md").read_text(encoding="utf-8")
    measured_on_a_mac = "05b_finetune_mlx" in timing_log and "Apple Silicon, measured" in timing_log
    if not measured_on_a_mac:
        assert "Not yet measured on a Mac" in header


def test_installs_are_exactly_pinned_and_match_requirements_mlx(participant_cells):
    requirements = (REPO_ROOT / "requirements-mlx.txt").read_text(encoding="utf-8")
    install_lines = [line for cell in participant_cells for line in source_of(cell).splitlines()
                     if "%pip install" in line]
    assert install_lines, "no install cell"
    for line in install_lines:
        assert "-U" not in line.split() and "--upgrade" not in line
        packages = [word for word in line.split() if "==" in word]
        assert packages, f"unpinned install: {line}"
        for package in packages:
            assert package in requirements, f"{package} is not pinned in requirements-mlx.txt"


def test_it_produces_the_same_adapter_format_as_notebook_05(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    assert "convert_mlx_adapter_to_peft" in sources
    assert "finetune_utils.FINAL_ADAPTER_FOLDER" in sources      # same folder name notebook 06 looks for
    assert "the converted adapter does not compute the same numbers" in sources   # and it checks itself


def test_training_is_resumable_and_budgeted(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    for needed in ["check_run_folder", "load_progress", "restore_adapter_weights", "record_epoch",
                   "TRAINING_BUDGET_MINUTES = 25"]:
        assert needed in sources, needed


def test_no_version_touches_the_facilitator_answer_key(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        assert "planted_problems" not in source_of(cell)
        assert "plant_problems" not in source_of(cell)


def test_solution_outputs_if_present_are_error_free(solution_cells):
    executed = [cell for cell in solution_cells if cell["cell_type"] == "code" and cell["outputs"]]
    if not executed:
        pytest.skip("solutions/05b_finetune_mlx.ipynb has no retained outputs: it has not been run on "
                    "Apple Silicon yet, and a Linux-CPU smoke run is not a reference output")
    for cell in executed:
        for output in cell["outputs"]:
            assert output["output_type"] != "error", f"solution cell {cell['id']} ended in an error"
    final_text = "".join("".join(o.get("text", "")) for o in solution_cells[-1]["outputs"])
    assert "ADAPTER READY" in final_text and "SMOKE TEST" not in final_text
