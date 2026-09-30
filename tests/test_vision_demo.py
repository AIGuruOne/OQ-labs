"""The simple vision ladder: notebooks 08a and 09a, and the OQ Vision app.

No model is called here - these check structure, and that the app, the helper module
and the two notebooks stay in step with each other.
"""
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "apps" / "oq_vision"
LADDER = ["08a_vision_basics", "09a_vision_review_rule"]
sys.path.insert(0, str(REPO_ROOT / "notebooks"))


def cells(stem):
    return json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))["cells"]


def code_of(stem):
    return "\n".join("".join(c["source"]) for c in cells(stem) if c["cell_type"] == "code")


@pytest.mark.parametrize("stem", LADDER)
def test_the_header_says_what_it_costs_and_what_it_teaches(stem):
    header = "".join(cells(stem)[0]["source"])
    assert "## What you will be able to do after this" in header       # Contract 2
    assert "A correct result looks like:" in header
    assert "All data in this lab is synthetic" in header
    assert f"{stem}.ipynb" in header                                    # the Colab badge
    for promise in ("No GPU", "no Ollama"):
        assert promise.lower() in header.lower(), promise


@pytest.mark.parametrize("stem", LADDER)
def test_no_self_hosted_model_anywhere_on_the_ladder(stem):
    """Day 3 lost a session to Ollama on CPU. Neither of these can repeat it."""
    code = code_of(stem)
    for banned in ("ollama", "localhost:11434", "qwen", "torch", "transformers"):
        assert banned not in code.lower(), f"{stem} must not reference {banned}"


@pytest.mark.parametrize("stem", LADDER)
def test_the_machinery_is_in_the_helper_not_the_notebook(stem):
    """KISS: one idea per cell. A renderer inlined in a lab is a coding exercise."""
    code_cells = [c for c in cells(stem) if c["cell_type"] == "code"]
    for cell in code_cells:
        lines = [l for l in "".join(cell["source"]).splitlines() if l.strip()]
        assert len(lines) <= 12, f"{stem} has a {len(lines)}-line cell; move it into vision_lab.py"
    code = code_of(stem)
    assert "import vision_lab as lab" in code
    for inlined in ("ImageDraw", "ImageFont", "def draw_", "OpenAI("):
        assert inlined not in code, f"{stem} inlines {inlined}; it belongs in vision_lab.py"


def test_08a_shows_all_three_prompts_in_order():
    """plain fails, soft changes nothing, careful works - that is the whole arc."""
    code = code_of("08a_vision_basics")
    order = [code.index(f'"{p}"') for p in ("plain", "soft", "careful")]
    assert order == sorted(order), "the prompts must appear plain -> soft -> careful"
    assert code.count('read_form(forms[0], "careful")') == 1, \
        "the careful prompt must also be run on the CLEAN scan, or it looks like refuse-everything"


def test_09a_ends_with_the_capstone_sentence():
    code = code_of("09a_vision_review_rule")
    assert "CHECKED_BY_A_PERSON" in code, "the learner must choose the rule themselves"
    assert "capstone_sentence" in code
    md = "\n".join("".join(c["source"]) for c in cells("09a_vision_review_rule")
                   if c["cell_type"] == "markdown")
    assert "S27" in md and "S29" in md, "09a must say where its output is used"


def test_09a_default_rule_leaves_something_uncovered():
    """If the starting rule catches everything, the residual-risk lesson never fires."""
    code = code_of("09a_vision_review_rule")
    chosen = re.search(r"CHECKED_BY_A_PERSON = \[(.*?)\]", code).group(1)
    picked = [p.strip().strip('"\'') for p in chosen.split(",") if p.strip()]
    import vision_lab as lab
    assert 0 < len(picked) < len(lab.FIELD_KEYS), \
        "start with a partial rule so section 7 shows values getting through"


def test_the_app_and_the_helper_use_the_same_strict_prompt():
    """The app and the notebook teach one lesson; two wordings would be two lessons."""
    from apps.oq_vision.main import PROMPTS as app_prompts
    import vision_lab as lab
    assert " ".join(app_prompts["strict"].split()) == " ".join(lab.PROMPTS["careful"].split())


def test_the_app_ships_its_three_photographs_and_needs_no_pillow():
    sizes = []
    for level in (0, 1, 2):
        path = APP / "static" / f"level_{level}.jpg"
        assert path.exists(), path
        sizes.append(path.stat().st_size)
    assert sizes[0] > sizes[1] > sizes[2], f"quality should fall with level: {sizes}"
    main = (APP / "main.py").read_text(encoding="utf-8")
    assert "from PIL" not in main and "import PIL" not in main


def test_vision_lab_records_the_measurement_its_default_rests_on():
    source = (REPO_ROOT / "notebooks" / "vision_lab.py").read_text(encoding="utf-8")
    assert "2026-09-30" in source
    assert "11 of 60" in source, "the 'decent' default was chosen from a measurement; keep it written down"
