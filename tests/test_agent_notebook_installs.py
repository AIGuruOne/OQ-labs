"""The Day 4 agent notebooks must install what they need on a laptop, not only on Colab.

The bug: 12 and 13 installed their pinned packages inside `if IN_COLAB:`. On a laptop
`tabulate` was therefore never installed, and the notebook died several cells later
inside pandas' df.to_markdown() with "Import tabulate failed" - a long way from the
cause.
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_LABS = ["12_agent_graph", "13_agent_control", "14_agent_safety"]


def code_of(stem):
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")


@pytest.mark.parametrize("stem", AGENT_LABS)
def test_installs_are_not_colab_only(stem):
    code = code_of(stem)
    assert 'pip", "install"' in code, f"{stem} has no pip install line"
    # There must be a path that installs when NOT on Colab. Either an unconditional
    # install, or an explicit branch for packages that are missing locally.
    has_local_path = ("elif MISSING:" in code
                      or "missing_packages()" in code
                      or "if IN_COLAB:" not in code.split('pip", "install"')[0][-400:])
    assert has_local_path, (
        f"{stem} installs only on Colab; a laptop hits ImportError several cells later")


@pytest.mark.parametrize("stem", AGENT_LABS)
def test_every_installed_package_is_pinned(stem):
    code = code_of(stem)
    packages = re.findall(r'"([a-zA-Z][a-zA-Z0-9_.-]*(?:==[0-9][0-9a-zA-Z.]*)?)"',
                          "\n".join(re.findall(r"PACKAGES = \[(.*?)\]", code, re.S)))
    assert packages, f"{stem}: no PACKAGES list found"
    unpinned = [p for p in packages if "==" not in p]
    assert not unpinned, f"{stem} installs unpinned packages: {unpinned}"


@pytest.mark.parametrize("stem", ["12_agent_graph", "13_agent_control"])
def test_tabulate_is_installed_because_to_markdown_needs_it(stem):
    code = code_of(stem)
    if "to_markdown" not in code:
        pytest.skip("this notebook no longer renders markdown tables")
    assert "tabulate==" in code, f"{stem} calls df.to_markdown() but does not install tabulate"
    assert '"tabulate": "tabulate"' in code, \
        f"{stem} must check tabulate is importable, not just list it"
