"""Hygiene checks for notebooks/04_dataset_builder.ipynb and its solution.

    python -m pytest tests/test_notebook_04.py -v

These read the .ipynb files; they do not execute them. Executing is
done with:

    jupyter nbconvert --to notebook --execute --inplace solutions/04_dataset_builder.ipynb
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "04_dataset_builder.ipynb"
TODO_CELL_IDS = {"pair-todo", "leak-todo", "schema-todo"}


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


def test_solution_outputs_are_retained_and_error_free(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] != [], f"solution cell {cell['id']} has no output"
            for output in cell["outputs"]:
                assert output["output_type"] != "error", f"solution cell {cell['id']} ended in an error"


def test_solution_prints_the_declared_result(solution_cells):
    final_cell = solution_cells[-1]
    printed = "".join("".join(output.get("text", "")) for output in final_cell["outputs"])
    assert "DATASET READY" in printed
    assert "differs" not in printed


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
    assert len(todo_cells) == 3
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "Hint:" in source
        assert f'"TODO {number} is not filled in yet"' in source
        for line in source.splitlines():
            code = line.split("#")[0]
            assert "= ..." not in code and ": ...," not in code, f"gap left in {cell['id']}: {line}"

def test_first_code_cell_is_the_environment_detection_cell(participant_cells):
    template = json.loads((REPO_ROOT / "notebooks" / "_template.ipynb").read_text(encoding="utf-8"))
    template_first_code = next(cell for cell in template["cells"] if cell["cell_type"] == "code")
    first_code = next(cell for cell in participant_cells if cell["cell_type"] == "code")
    assert source_of(first_code) == source_of(template_first_code)


def test_every_code_cell_has_a_markdown_cell_before_it(participant_cells):
    for position, cell in enumerate(participant_cells):
        if cell["cell_type"] == "code":
            assert participant_cells[position - 1]["cell_type"] == "markdown", f"cell {cell['id']}"


def test_no_version_touches_the_facilitator_answer_key(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        assert "planted_problems" not in source_of(cell)
        assert "plant_problems" not in source_of(cell)


def test_installs_are_exactly_pinned_and_match_requirements(participant_cells):
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    for cell in participant_cells:
        for line in source_of(cell).splitlines():
            if "%pip install" not in line:
                continue
            assert "-U" not in line.split() and "--upgrade" not in line
            packages = [word for word in line.split() if "==" in word]
            assert packages, f"unpinned install: {line}"
            for package in packages:
                assert package in requirements, f"{package} is not pinned in requirements.txt"
