"""Hygiene checks for notebooks/01_fundamentals.ipynb and its solution.

    python -m pytest tests/test_notebook_01.py -v

These read the .ipynb files; they do not execute them. Executing needs
OPENAI_API_KEY and about two minutes:

    python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/01_fundamentals.ipynb

The notebook carries TWO paths (BUILD_SPEC section 2, S1). The tests
below pin the signposting a facilitator relies on: Part B cells are
tagged `full-path-only` and start with `# [FULL PATH ONLY]`, Part C
cells never depend on Part B, and the diagnostic can never stop the
notebook.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "01_fundamentals.ipynb"
TODO_CELL_IDS = ["probe-1", "probe-2", "quiz", "b-prompt", "c-feedback", "c-agent", "c-reflect"]
DIAGNOSTIC_TODO_IDS = ["probe-1", "probe-2", "quiz"]
FULL_ONLY_TAG = "full-path-only"


def load_cells(folder):
    notebook = json.loads((REPO_ROOT / folder / NAME).read_text(encoding="utf-8"))
    return notebook["cells"]


def source_of(cell):
    return "".join(cell["source"])


def printed_by(cell):
    return "".join("".join(output.get("text", "")) for output in cell["outputs"])


def cell_by_id(cells, cell_id):
    return next(cell for cell in cells if cell["id"] == cell_id)


def is_full_only(cell):
    return FULL_ONLY_TAG in cell.get("metadata", {}).get("tags", [])


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


def test_solution_outputs_are_retained_and_error_free(solution_cells):
    code_cells = [cell for cell in solution_cells if cell["cell_type"] == "code"]
    assert all(cell["execution_count"] is not None for cell in code_cells)
    for cell in code_cells:
        for output in cell["outputs"]:
            assert output["output_type"] != "error", f"cell {cell['id']} errored"


def test_solution_prints_the_declared_result(solution_cells):
    final = solution_cells[-1]
    text = printed_by(final)
    assert "01 FUNDAMENTALS OK" in text
    assert "schema-valid  : 5 / 5" in text
    assert re.search(r"final answer in [1-4] steps", text), text
    assert "diagnostic    : READY (8 / 8)" in text


def test_the_two_versions_differ_only_in_the_todo_cells(participant_cells, solution_cells):
    assert [cell["id"] for cell in participant_cells] == [cell["id"] for cell in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            assert source_of(mine) != source_of(theirs)
        else:
            assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs between the two versions"
        assert mine.get("metadata", {}).get("tags", []) == theirs.get("metadata", {}).get("tags", [])


def test_todo_cells_have_a_gap_and_a_hint(participant_cells):
    todo_cells = [cell for cell in participant_cells if cell["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 7
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} " in source, f"cell {cell['id']} is not TODO {number}"
        assert "...  # <-" in source or "...  # <- " in source
        assert "Hint:" in source


def test_lab_todos_fail_loudly_but_diagnostic_todos_never_stop_the_notebook(participant_cells):
    for cell in participant_cells:
        if cell["id"] not in TODO_CELL_IDS:
            continue
        source = source_of(cell)
        number = TODO_CELL_IDS.index(cell["id"]) + 1
        if cell["id"] in DIAGNOSTIC_TODO_IDS:
            # A probe left as ... is scored 0 by fundamentals_utils; no assert may stop the room.
            assert "assert" not in source, f"diagnostic cell {cell['id']} must not assert"
            assert "fu.score_" in source
        else:
            assert f"TODO {number} is not filled in yet" in source


def test_the_solution_has_no_gap_left(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert "...  # <-" not in source_of(cell), f"cell {cell['id']} still has a gap"


def test_first_code_cell_is_the_environment_detection_cell(participant_cells):
    template = json.loads((REPO_ROOT / "notebooks" / "_template.ipynb").read_text(encoding="utf-8"))
    template_first_code = next(cell for cell in template["cells"] if cell["cell_type"] == "code")
    first_code = next(cell for cell in participant_cells if cell["cell_type"] == "code")
    assert source_of(first_code) == source_of(template_first_code)


def test_every_code_cell_has_a_markdown_cell_before_it(participant_cells):
    for position, cell in enumerate(participant_cells):
        if cell["cell_type"] == "code":
            assert participant_cells[position - 1]["cell_type"] == "markdown", f"cell {cell['id']}"


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


def test_header_declares_runtime_needs_and_result(participant_cells):
    header = source_of(participant_cells[0])
    for field in ("**Expected runtime:**", "**Needs:**", "**A correct result looks like:**", "synthetic"):
        assert field in header
    assert "60 minutes" in header and "45 minutes" in header


def test_no_secret_in_any_retained_output(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] != "code":
            continue
        text = json.dumps(cell["outputs"])
        assert "sk-" not in text, f"cell {cell['id']} output looks like it contains a key"
        assert "Bearer" not in text
        assert "Authorization" not in text


# ---------------------------------------------------------------------------
# The two paths: the signposting a facilitator under pressure relies on
# ---------------------------------------------------------------------------


def test_part_b_cells_are_tagged_and_marked_and_contiguous(participant_cells):
    positions = [i for i, cell in enumerate(participant_cells) if is_full_only(cell)]
    assert positions, "no cell is tagged full-path-only"
    assert positions == list(range(positions[0], positions[-1] + 1)), "Part B must be one contiguous block"
    for cell in participant_cells:
        if cell["cell_type"] == "code" and is_full_only(cell):
            assert source_of(cell).startswith("# [FULL PATH ONLY]"), f"cell {cell['id']} lacks the banner comment"
        if cell["cell_type"] == "code" and not is_full_only(cell):
            assert "[FULL PATH ONLY]" not in source_of(cell), f"cell {cell['id']} carries the banner but is not tagged"
    # Part B sits between THE FORK and PART C STARTS HERE.
    fork = next(i for i, cell in enumerate(participant_cells) if "THE FORK" in source_of(cell) and cell["cell_type"] == "markdown" and source_of(cell).startswith("# "))
    part_c = next(i for i, cell in enumerate(participant_cells) if source_of(cell).startswith("# ▶ PART C STARTS HERE"))
    assert fork < positions[0] and positions[-1] < part_c


def test_the_diagnostic_and_the_fork_come_before_part_b(participant_cells):
    ids = [cell["id"] for cell in participant_cells]
    first_full_only = next(i for i, cell in enumerate(participant_cells) if is_full_only(cell))
    for cell_id in ("probe-1", "probe-2", "quiz", "score", "fork"):
        assert ids.index(cell_id) < first_full_only


def test_part_c_never_uses_a_name_defined_only_in_part_b(participant_cells):
    """Runtime -> Run after on PART C STARTS HERE must work after Part A alone."""
    part_b_sources = [source_of(cell) for cell in participant_cells if is_full_only(cell) and cell["cell_type"] == "code"]
    part_a_and_c_sources = [source_of(cell) for cell in participant_cells if not is_full_only(cell) and cell["cell_type"] == "code"]
    assigned_in_b = set()
    for source in part_b_sources:
        assigned_in_b.update(re.findall(r"^([a-z_][a-z0-9_]*)\s*=", source, flags=re.MULTILINE))
    part_c_started = False
    for cell in participant_cells:
        if source_of(cell).startswith("# ▶ PART C STARTS HERE"):
            part_c_started = True
        if not part_c_started or cell["cell_type"] != "code":
            continue
        # Look at code only: drop comments and string literals before collecting names.
        code_only = re.sub(r"#.*", "", source_of(cell))
        code_only = re.sub(r'"[^"\n]*"', "", code_only)
        code_only = re.sub(r"'[^'\n]*'", "", code_only)
        names_used = set(re.findall(r"\b([a-z_][a-z0-9_]*)\b", code_only))
        # Names Part C assigns itself are fine; only names that exist ONLY in Part B are a problem.
        for name in names_used & assigned_in_b:
            defined_in_a_or_c = any(re.search(rf"^{name}\s*=", src, flags=re.MULTILINE) for src in part_a_and_c_sources)
            assert defined_in_a_or_c, f"cell {cell['id']} uses {name!r}, which only Part B defines"


def test_header_cell_map_matches_the_tags(participant_cells):
    header = source_of(participant_cells[0])
    assert "# [FULL PATH ONLY]" in header
    assert "PART C STARTS HERE" in header
    assert "THE FORK" in header
    assert "Run after" in header


def test_solution_diagnostic_and_fork_outputs_are_the_room_instructions(solution_cells):
    score_text = printed_by(cell_by_id(solution_cells, "score"))
    assert "DIAGNOSTIC RESULT:" in score_text
    assert "two thirds" in score_text
    assert "COMPRESSED" in score_text and "FULL" in score_text


def test_no_version_touches_the_facilitator_answer_key(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        assert "planted_problems" not in source_of(cell)
        assert "plant_problems" not in source_of(cell)
