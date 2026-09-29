"""Lab 08b, the image-triage notebook.

It calls no model and needs no key, so unlike the other notebook tests this one
actually EXECUTES it - the whole run is about two seconds. What it checks is the
notebook's own claim: that each quality measure recovers the degradation the
renderer applied.

Pillow is not in requirements.txt (Colab preinstalls it, and labs 08/09/10 rely on
that), so the execution test skips where Pillow is absent.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NB = REPO_ROOT / "notebooks" / "08b_image_triage.ipynb"


def source_of(cell):
    return "".join(cell["source"])


@pytest.fixture(scope="module")
def cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def test_the_notebook_exists_and_declares_what_it_costs(cells):
    header = source_of(cells[0])
    assert "A correct result looks like:" in header
    assert "All data in this lab is synthetic" in header
    assert "no model" in header.lower() and "no api key" in header.lower()
    assert "colab.research.google.com" in header and "08b_image_triage.ipynb" in header


def test_it_calls_no_model_and_needs_no_network(cells):
    """The whole point is that triage is cheap. A model call here would be a bug."""
    code = "\n".join(source_of(c) for c in cells if c["cell_type"] == "code")
    for banned in ["openai", "OpenAI(", "requests.post", "requests.get", "ollama",
                   "huggingface", "from_pretrained", "pip install"]:
        assert banned not in code, f"08b must not {banned}"


def test_it_uses_only_numpy_and_pillow(cells):
    """No OpenCV, no scipy, no scikit-image: requirements.txt is frozen."""
    code = "\n".join(source_of(c) for c in cells if c["cell_type"] == "code")
    imports = set(re.findall(r"^\s*(?:import|from)\s+([A-Za-z_][\w]*)", code, re.M))
    assert imports <= {"io", "math", "sys", "numpy", "PIL", "collections", "dataclasses"}, imports
    for banned in ("cv2", "scipy", "skimage"):
        assert banned not in code


def test_every_gate_threshold_is_used(cells):
    """A threshold in GATE that nothing reads is a promise nobody checks."""
    code = "\n".join(source_of(c) for c in cells if c["cell_type"] == "code")
    gate = re.search(r"GATE = \{(.*?)\n\}", code, re.S)
    assert gate, "GATE not found"
    keys = re.findall(r'"(\w+)":', gate.group(1))
    assert len(keys) >= 5
    verdict = code[code.index("def verdict("):]
    for key in keys:
        assert f'GATE["{key}"]' in verdict, f"{key} is defined but never applied"


def test_executing_it_recovers_the_degradations(tmp_path):
    """The notebook's section 5 checks its own measurements. Run it and read the verdict."""
    pytest.importorskip("PIL", reason="Pillow is not pinned in requirements.txt")
    pytest.importorskip("nbconvert")
    target = tmp_path / NB.name
    target.write_text(NB.read_text(encoding="utf-8"), encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-m", "nbconvert", "--to", "notebook", "--execute",
         "--output", "executed.ipynb", str(target)],
        capture_output=True, text=True, timeout=600, cwd=tmp_path)
    assert done.returncode == 0, done.stderr[-2000:]

    executed = json.loads((tmp_path / "executed.ipynb").read_text(encoding="utf-8"))
    errors = [o for c in executed["cells"] for o in c.get("outputs", [])
              if o.get("output_type") == "error"]
    assert not errors, errors[:1]

    text = "\n".join("".join(o.get("text") or [])
                     for c in executed["cells"] for o in c.get("outputs", []))
    assert "every measure recovers the degradation it is named for" in text, \
        "section 5 reported a measure that does not track its degradation"
    assert "FAIL" not in text, "a ground-truth check failed"
    assert "08b IMAGE TRIAGE OK" in text
    assert "ground-truth checks: all passed" in text
