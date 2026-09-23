"""Shape tests for docs/failure_playbook.md.

The playbook is read while a room of 15 people waits, so its layout is a
requirement, not a style choice: an index on the first screen, 15 entries
with the same six fields in the same order, a trust level on every entry,
and paths that exist. These tests hold that shape; they do not judge the
advice itself.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK = REPO_ROOT / "docs" / "failure_playbook.md"
TEXT = PLAYBOOK.read_text(encoding="utf-8")
LINES = TEXT.splitlines()

FIELDS = ["They say", "Radius", "Diagnose", "Fix", "Fallback after 60 s", "Tested"]
INDEX_MUST_END_BY_LINE = 40  # one screen: the facilitator must not scroll to find the index


def github_anchor(heading):
    """The anchor GitHub (and VS Code's preview) makes from a heading."""
    text = heading.strip().lower()
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    return text.replace(" ", "-")


def part(title_start, next_title_start=None):
    start = TEXT.index(title_start)
    end = TEXT.index(next_title_start) if next_title_start else len(TEXT)
    return TEXT[start:end]


PART_1 = part("# Part 1:", "# Part 2:")
PART_2 = part("# Part 2:", "# Part 3:")
PART_3 = part("# Part 3:")


def room_entries():
    """{number: text} for the '## N. title' entries of Part 1."""
    pieces = re.split(r"^## (\d+)\. .*$", PART_1, flags=re.M)
    return {int(pieces[i]): pieces[i + 1] for i in range(1, len(pieces), 2)}


def test_part_1_has_exactly_entries_1_to_15_in_order():
    numbers = [int(n) for n in re.findall(r"^## (\d+)\. ", PART_1, flags=re.M)]
    assert numbers == list(range(1, 16))


def test_every_entry_has_the_six_fields_in_order():
    for number, body in room_entries().items():
        positions = []
        for field in FIELDS:
            match = re.search(r"^- \*\*" + re.escape(field) + r"[^*]*:\*\*", body, flags=re.M)
            assert match, f"entry {number} has no '{field}' field"
            positions.append(match.start())
        assert positions == sorted(positions), f"entry {number}: fields out of order"


def test_every_radius_says_room_laptop_or_group():
    for number, body in room_entries().items():
        radius = re.search(r"^- \*\*Radius:\*\*(.*)$", body, flags=re.M).group(1)
        assert re.search(r"\b(ROOM|LAPTOP|GROUP)\b", radius), f"entry {number}: {radius}"


def test_every_entry_says_how_far_its_fix_can_be_trusted():
    # REPRODUCED / SIMULATED / NOT REPRODUCED - an untested fix must say so,
    # so nobody trusts it under pressure.
    for number, body in room_entries().items():
        tested = body[body.index("**Tested:**"):]
        assert re.search(r"REPRODUCED|SIMULATED", tested), f"entry {number} has no trust level"


def test_the_index_is_on_the_first_screen_and_every_link_lands():
    index_rows = [i for i, line in enumerate(LINES) if re.match(r"^\| \[\d+\]\(#", line)]
    assert len(index_rows) == 15
    assert max(index_rows) < INDEX_MUST_END_BY_LINE

    anchors = {github_anchor(h) for h in re.findall(r"^#{1,3} (.+)$", TEXT, flags=re.M)}
    linked_numbers = []
    for row in index_rows:
        number, anchor = re.match(r"^\| \[(\d+)\]\(#([^)]+)\)", LINES[row]).groups()
        linked_numbers.append(int(number))
        assert anchor in anchors, f"index link #{anchor} matches no heading"
        assert anchor.startswith(f"{number}-")
    assert linked_numbers == list(range(1, 16))

    for anchor in re.findall(r"\]\(#([^)]+)\)", TEXT):
        assert anchor in anchors, f"link #{anchor} matches no heading"


def test_the_ladder_has_three_steps_each_saying_what_breaks_and_what_to_say():
    steps = re.split(r"^## Step \d: ", PART_2, flags=re.M)[1:]
    assert len(steps) == 3
    for step in steps[1:]:  # step 1 is the plan itself
        assert "**How to switch" in step
    for step in steps:
        assert "**What breaks" in step
        assert "**Say:**" in step


def test_the_sat_26_check_is_a_table_of_at_least_eight_checks():
    sat = PART_2[PART_2.index("## Sat 26"):]
    rows = re.findall(r"^\| \d+ \|", sat, flags=re.M)
    assert len(rows) >= 8
    assert "setup_check.py --network" in sat


def test_part_3_keeps_e1_to_e18_so_old_references_still_resolve():
    numbers = [int(n) for n in re.findall(r"^### E(\d+)\. ", PART_3, flags=re.M)]
    assert numbers == list(range(1, len(numbers) + 1))
    assert len(numbers) >= 18


def test_paths_the_playbook_names_exist():
    top_dirs = ("docs/", "setup/", "scripts/", "notebooks/", "solutions/", "facilitator/",
                "checkpoints/", "tests/", "services/", "config/", "data/")
    for path in set(re.findall(r"`([A-Za-z0-9_./-]+)`", TEXT)):
        if not path.startswith(top_dirs) or "<" in path:
            continue
        # checkpoints/local/ is created by the first run and git-ignored:
        # a fresh clone does not have it yet.
        if path.startswith("checkpoints/local"):
            continue
        assert (REPO_ROOT / path.rstrip("/")).exists(), f"missing: {path}"


def test_references_from_other_files_resolve():
    """'playbook entry 4' means room entry 4; 'playbook E10' means Part 3's E10.
    A plain number above 15 is an older reference and means E<number>."""
    room = set(room_entries())
    reference = {int(n) for n in re.findall(r"^### E(\d+)\. ", PART_3, flags=re.M)}
    pattern = re.compile(r"(?:failure_playbook\.md`?|[Pp]laybook)\s+(?:entry\s+|entries\s+)?(E?)(\d+)")
    checked = 0
    for path in REPO_ROOT.rglob("*"):
        if path.suffix not in (".md", ".py", ".ipynb") or path == PLAYBOOK:
            continue
        if any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(REPO_ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for prefix, number in pattern.findall(text):
            number = int(number)
            checked += 1
            if prefix == "E" or number > 15:
                assert number in reference, f"{path.name}: playbook E{number} does not exist"
            else:
                assert number in room, f"{path.name}: playbook entry {number} does not exist"
    assert checked >= 10
