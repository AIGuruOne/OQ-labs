"""facilitator/skills_map.md and the notebooks' skill blocks must not drift.

Contract 2 requires a "What you will be able to do after this" block in the header of
every lab listed in the skills map. The map is the opt-in: adding a row is what brings
a notebook under these checks, so the older notebooks can be retrofitted one at a time.
"""
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MAP = REPO_ROOT / "facilitator" / "skills_map.md"
CONVENTIONS = REPO_ROOT / "docs" / "notebook_conventions.md"


def header_of(stem: str) -> str:
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    return "".join(nb["cells"][0]["source"])


def rows() -> list[dict]:
    """Every lab row in the map: | `stem` | skill | test | feeds |."""
    out = []
    for line in MAP.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`([0-9a-z_]+)`\s*\|(.+?)\|(.+?)\|(.+?)\|\s*$", line)
        if m:
            out.append({"stem": m.group(1), "skill": m.group(2).strip(),
                        "test": m.group(3).strip(), "feeds": m.group(4).strip()})
    return out


def test_the_map_lists_the_labs_on_the_ladder():
    stems = [r["stem"] for r in rows()]
    assert stems, "the skills map has no lab rows"
    assert "08a_vision_basics" in stems and "09a_vision_review_rule" in stems
    assert len(stems) == len(set(stems)), "a lab is listed twice"


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["stem"])
def test_every_mapped_lab_exists_and_has_the_skill_block(row):
    path = REPO_ROOT / "notebooks" / f"{row['stem']}.ipynb"
    assert path.exists(), path
    header = header_of(row["stem"])
    assert "## What you will be able to do after this" in header, \
        f"{row['stem']} has no skill block (Contract 2)"
    assert "**You will know it landed**" in header
    assert "**Where you use it:**" in header


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["stem"])
def test_the_skill_sentence_matches_the_notebook(row):
    """The map must quote the notebook, not paraphrase it."""
    header = " ".join(header_of(row["stem"]).split())
    skill = " ".join(row["skill"].replace("**", "").split())
    assert skill.rstrip(".") in header.replace("**", ""), (
        f"{row['stem']}: the skill in skills_map.md is not the sentence in the notebook\n"
        f"map:      {skill[:120]}\nheader:   {header[:200]}")


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["stem"])
def test_every_feeds_target_is_real(row):
    """A lab that feeds nothing is not on a ladder - it is a detour."""
    assert row["feeds"], f"{row['stem']} feeds nothing"
    for target in [t.strip() for t in row["feeds"].split(",")]:
        target = target.replace("`", "")
        if target.startswith("S"):                       # a session, e.g. S27
            assert re.match(r"^S\d+\b", target), target
            continue
        if (REPO_ROOT / "notebooks" / f"{target.split()[0]}.ipynb").exists():
            continue
        pytest.fail(f"{row['stem']} feeds '{target}', which is neither a session nor a notebook")


def test_contract_2_requires_the_block():
    text = CONVENTIONS.read_text(encoding="utf-8")
    assert "## What you will be able to do after this" in text
    assert "You will know it landed" in text
    assert "Where you use it" in text
    assert "skills_map.md" in text, "Contract 2 must point at the map it is kept in step with"


def test_the_measured_claims_table_is_present():
    """The labs' text quotes numbers. The map records them so a drift is visible."""
    text = MAP.read_text(encoding="utf-8")
    assert "2026-09-30" in text and "temperature 0" in text
    for claim in ["5 of 6 wrong", "6 of 6 refused", "8 of 60 fields wrong"]:
        assert claim in text, claim
