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


# --- the self-hosted arm is opt-in -----------------------------------------
# Measured 2026-09-30: the self-hosted arm was ~94% of the run time in both 08 and 09
# (791s and 795s against the vendor model's 48s and 42s) and produced every call
# failure. With it off, both notebooks run in about 19 seconds.

@pytest.mark.parametrize("stem", ["08_vision_diagram", "09_vision_scanned"])
def test_the_self_hosted_arm_is_off_by_default(stem):
    code = code_of(stem)
    assert 'INCLUDE_SELF_HOSTED = os.environ.get("LAB_SELF_HOSTED", "0") == "1"' in code, \
        "the expensive arm must default to off, and be switchable without editing code"
    # and it must actually gate the Ollama call
    block = code[code.index("INCLUDE_SELF_HOSTED"):]
    assert "if INCLUDE_SELF_HOSTED:" in block
    ollama_at = block.index("ensure_ollama()")
    guard_at = block.index("if INCLUDE_SELF_HOSTED:")
    assert guard_at < ollama_at, "ensure_ollama() must sit inside the guard"


@pytest.mark.parametrize("stem", ["08_vision_diagram", "09_vision_scanned"])
def test_the_notebook_says_what_turning_it_on_costs(stem):
    code = code_of(stem)
    assert "self-hosted arm OFF" in code
    assert "INCLUDE_SELF_HOSTED = True" in code, "tell the reader how to get the second column"


def test_08_section_8_explains_itself_when_every_model_is_skipped():
    """With the default flag, nothing runs. That must read as a finding, not a gap."""
    code = code_of("08_vision_diagram")
    section = code[code.index("PROMPT_V2"):]
    assert "ran_any" in section
    assert "Nothing to run" in section and "That is the finding" in section


@pytest.mark.parametrize("stem,phrase", [
    ("08_vision_diagram", "What this buys you over lab 08a"),
    ("09_vision_scanned", "the model you can afford to self-host"),
    ("10_multimodal_retrieval", "What this buys you over labs 08a, 08 and 09"),
])
def test_each_lab_says_what_it_adds_over_the_simple_one(stem, phrase):
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    md = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
    assert phrase in md, f"{stem} does not justify its extra cost over 08a"


def test_09_no_longer_claims_vision_models_invent_values_as_a_law():
    """Measured: current vendor models do not invent on a blank field. 09's own numbers agree."""
    nb = json.loads((REPO_ROOT / "notebooks" / "09_vision_scanned.ipynb").read_text(encoding="utf-8"))
    md = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
    assert "This lab is about one failure in particular: **a model that fills in a blank field" not in md
    assert "not a law about vision models" in md
    assert "hosting decision" in md
