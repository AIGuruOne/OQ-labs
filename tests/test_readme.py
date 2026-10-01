"""The two READMEs a participant actually opens: README.md and resources/README.md.

    python -m pytest tests/test_readme.py -v

Prose cannot be executed, but it rots. These catch the ways it rotted before:
a path that moved, a folder nobody listed, and the slides section that still
said the decks were in Google Drive a week after they landed in the repo.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
RESOURCES_README = REPO_ROOT / "resources" / "README.md"

# `like/this` in backticks. Commands and globs are not paths.
PATH_IN_BACKTICKS = re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*)`")


def read(path):
    return path.read_text(encoding="utf-8")


def named_paths(doc):
    for match in PATH_IN_BACKTICKS.findall(read(doc)):
        if "<" in match or match.startswith("http") or "*" in match:
            continue
        yield match


@pytest.mark.parametrize("doc", [README, RESOURCES_README], ids=lambda d: d.name)
def test_every_path_named_exists(doc):
    """Paths are repo-relative; resources/README.md also names its own files."""
    missing = [p for p in named_paths(doc)
               if not (REPO_ROOT / p.rstrip("/")).exists()
               and not (doc.parent / p.rstrip("/")).exists()]
    assert not missing, missing


def test_every_app_is_listed_and_runnable():
    """apps/ was invisible in the README for a week. Not again."""
    apps = sorted(d.name for d in (REPO_ROOT / "apps").iterdir()
                  if d.is_dir() and not d.name.startswith("__"))
    assert apps, "no apps found"
    text = read(README)
    for app in apps:
        assert f"apps/{app}/" in text, f"apps/{app} is not listed in README.md"
        assert (REPO_ROOT / "apps" / app / "README.md").exists(), f"{app} has no README"
        assert (REPO_ROOT / "apps" / app / "main.py").exists(), f"{app} has no main.py"
        assert f"apps.{app}.main:app" in text, f"README.md does not say how to run {app}"


def test_every_resources_file_is_indexed():
    """A file that nobody listed is a file nobody opens."""
    text = read(RESOURCES_README)
    unlisted = [str(f.relative_to(REPO_ROOT / "resources"))
                for f in (REPO_ROOT / "resources").rglob("*")
                if f.is_file() and f.name != "README.md" and f.name not in text]
    assert not unlisted, f"in resources/ but not in its README: {unlisted}"


def test_the_slides_section_matches_what_is_actually_committed():
    """It claimed the decks were in Google Drive for a week after they landed here."""
    decks = sorted(f.name for f in (REPO_ROOT / "resources").glob("*.pdf"))
    assert decks, "no slide decks in resources/"
    for section in (read(README), read(RESOURCES_README)):
        for deck in decks:
            assert deck in section, f"{deck} is committed but not named"
    assert "live in the program **Google Drive**" not in read(README)


def test_all_five_days_have_a_deck_and_every_day_folder_is_written_up():
    """The decks landed in three pushes. The README claimed the absent ones were
    absent, then they arrived - so this checks presence both ways round."""
    resources = REPO_ROOT / "resources"
    for day in range(1, 6):
        decks = list(resources.glob(f"OQ_Day{day}_*.pdf"))
        assert decks, f"no slide deck committed for day {day}"

    text = read(RESOURCES_README)
    for folder in sorted(d.name for d in resources.iterdir() if d.is_dir()):
        assert f"`{folder}/" in text, f"resources/{folder}/ has no section in its README"
        assert f"## Day {folder[-1]} " in text, f"no '## Day {folder[-1]}' heading for {folder}/"

    # The claim that bit us: never let it come back while the file is sitting there.
    for doc in (README, RESOURCES_README):
        assert "are not in this repo" not in read(doc)
        assert "are not in the repo" not in read(doc)


def test_the_refresher_table_points_at_things_that_exist():
    """The first section a returning participant reads."""
    text = read(README)
    assert "## Coming back to this after the week" in text
    section = text.split("## Coming back to this after the week")[1].split("\n## ")[0]
    for pointer in ("resources/", "facilitator/skills_map.md", "apps/", "notebooks/",
                    "solutions/", "docs/failure_playbook.md"):
        assert pointer in section, f"the refresher table does not mention {pointer}"
