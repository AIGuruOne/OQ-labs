"""Regression tests for the vision labs' scoring, 08 / 09 / 10.

The bug these pin down: a live call that fails writes no file, and the scorer used to
label that row with the model's DIRECTORY name instead of its display label. The
result was a whole extra model appearing in every summary table, with a single 0.0 in
it - so lab 08 showed three models where two had run.
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LABS = ["08_vision_diagram", "09_vision_scanned", "10_multimodal_retrieval"]


def code_of(stem: str) -> str:
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")


def code_cells(stem: str) -> list[str]:
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


@pytest.mark.parametrize("stem", LABS)
def test_a_scored_row_is_never_labelled_with_a_directory_name(stem):
    code = code_of(stem)
    assert 'rec.get("label", model_dir.name)' not in code, (
        "this is the bug: a missing prediction gets labelled by its folder, "
        "which invents an extra model in every summary table")
    assert 'MODEL_LABELS.get(model_dir.name' in code


@pytest.mark.parametrize("stem", LABS)
def test_model_labels_is_declared_before_it_is_used(stem):
    cells = code_cells(stem)
    declared = next((i for i, s in enumerate(cells) if "MODEL_LABELS: dict" in s), None)
    updated = next((i for i, s in enumerate(cells) if "MODEL_LABELS.update" in s), None)
    assert declared is not None, "MODEL_LABELS is never declared"
    assert updated is not None, "MODEL_LABELS is never populated from MODELS"
    assert declared <= updated, "MODEL_LABELS is used before it exists"


@pytest.mark.parametrize("stem", LABS)
def test_a_call_failure_is_distinguishable_from_a_wrong_answer(stem):
    """Scoring a failed call 0.0 is a choice; hiding that it was a failure is not."""
    assert "failed=pred is None" in code_of(stem)


def test_08_does_not_ask_you_to_improve_a_model_that_is_already_perfect():
    """Section 8 ran the 'better prompt' exercise against a model scoring 1.0."""
    code = code_of("08_vision_diagram")
    section = code[code.index("PROMPT_V2"):]
    assert "already 1.0 on dia_10" in section, "a model with no headroom must be skipped"
    assert "nothing to improve" in section
    assert "no change" in section, "the cell must say plainly when the score does not move"


def test_08_section_8_markdown_does_not_promise_an_improvement():
    """It used to imply the prompt would help. Measured: it does not."""
    nb = json.loads((REPO_ROOT / "notebooks" / "08_vision_diagram.ipynb").read_text(encoding="utf-8"))
    md = [("".join(c["source"])) for c in nb["cells"] if c["cell_type"] == "markdown"]
    section = next(s for s in md if s.startswith("## 8. Try it"))
    assert "the answer is no" in section.lower()
    note = next(s for s in md if "What that tells you" in s)
    assert "Nothing moved" in note
    # and it must say what DOES help, or the section is just bad news
    assert "A better image" in note and "A bigger model" in note
