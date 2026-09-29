"""The simple vision lab: notebook 08a and the OQ Vision app.

No model is called anywhere here - these check structure and the shared answer key.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NB = REPO_ROOT / "notebooks" / "08a_vision_basics.ipynb"
APP = REPO_ROOT / "apps" / "oq_vision"


def nb_cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def nb_code():
    return "\n".join("".join(c["source"]) for c in nb_cells() if c["cell_type"] == "code")


def test_the_notebook_header_promises_what_it_delivers():
    header = "".join(nb_cells()[0]["source"])
    assert "A correct result looks like:" in header
    assert "All data in this lab is synthetic" in header
    assert "08a_vision_basics.ipynb" in header
    for promise in ("No GPU", "no Ollama", "no local model"):
        assert promise.lower() in header.lower(), promise


def test_the_notebook_needs_no_self_hosted_model():
    """Day 3 lost a session to Ollama on CPU. This lab must not be able to."""
    code = nb_code()
    for banned in ("ollama", "localhost:11434", "qwen", "torch", "transformers"):
        assert banned not in code.lower(), f"08a must not reference {banned}"


def test_the_notebook_runs_all_three_prompts_and_both_images():
    code = nb_code()
    for name in ("NAIVE", "SOFT", "STRICT"):
        assert f"{name} = " in code or f"{name} =(" in code, name
    # the soft prompt must be shown to FAIL, and strict must be checked on a good image
    assert 'Did asking politely help?' in code
    assert code.count('compare(read_form(SHOTS["clean scan"], STRICT)') == 1, \
        "the strict prompt must also be run on the clean scan, or it looks like refuse-everything"


def test_the_app_and_the_notebook_share_one_answer_key():
    """If the form changes in one and not the other, the demo teaches two things."""
    import sys
    sys.path.insert(0, str(REPO_ROOT))
    from apps.oq_vision.forms import TRUTH as APP_TRUTH

    match = re.search(r"TRUTH = \{(.*?)\}", nb_code(), re.S)
    assert match, "notebook TRUTH not found"
    nb_truth = dict(re.findall(r'"(\w+)":\s*"([^"]+)"', match.group(1)))
    assert nb_truth == APP_TRUTH, (nb_truth, APP_TRUTH)


def test_the_app_ships_its_three_photographs():
    """They are committed so the demo cannot change under the facilitator."""
    for level in (0, 1, 2):
        path = APP / "static" / f"level_{level}.jpg"
        assert path.exists(), path
        assert path.stat().st_size > 1500, f"{path.name} looks truncated"
    sizes = [(APP / "static" / f"level_{i}.jpg").stat().st_size for i in range(3)]
    assert sizes[0] > sizes[1] > sizes[2], f"quality should fall with level: {sizes}"


def test_the_app_imports_without_pillow():
    """main.py must serve pre-rendered images; Pillow is not pinned."""
    main = (APP / "main.py").read_text(encoding="utf-8")
    assert "from PIL" not in main and "import PIL" not in main
    forms = (APP / "forms.py").read_text(encoding="utf-8")
    top = forms.split("def ")[0]
    assert "from PIL" not in top, "forms.py must import Pillow lazily, inside its functions"


def test_the_three_prompts_differ_in_the_way_the_readme_claims():
    from apps.oq_vision.main import PROMPTS
    assert set(PROMPTS) == {"naive", "soft", "strict"}
    assert "NOT_LEGIBLE" not in PROMPTS["naive"]
    assert "NOT_LEGIBLE" in PROMPTS["soft"]
    assert "Assume you CANNOT" in PROMPTS["strict"]
    assert len(PROMPTS["strict"]) > len(PROMPTS["soft"]) > len(PROMPTS["naive"])
