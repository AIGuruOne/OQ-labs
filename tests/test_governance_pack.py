"""Tests for the Day 5 governance pack in facilitator/governance_pack/ (P14).

    python -m pytest tests/test_governance_pack.py -v

Paper cannot run, but it can drift: a template can lose its "why"
paragraph, the minute budgets can stop adding up, a cited source can
vanish from sources.md, a path can disappear, the worked example can
fall out of step with the templates. These tests catch that.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACK = REPO_ROOT / "facilitator" / "governance_pack"
EXAMPLE = PACK / "examples" / "brief3_vision_capture_filled.md"

TEMPLATES = [
    "01_system_register.md",
    "02_data_classification.md",
    "03_evaluation_acceptance.md",
    "04_approval_gating.md",
    "05_audit_logging.md",
    "06_incident_response.md",
    "07_change_management.md",
    "08_monitoring_drift.md",
]

# Repo paths the pack names that later build items deliver. Remove an
# entry when the thing exists (tests/test_facilitator_docs.py has the
# same list for the Day 1 documents).
PENDING_PATHS = {
    "services/mcp_server_reference/",
    "scripts/score_extraction.py",
    "data/eval/image_ground_truth/",
}


def read(path):
    return path.read_text(encoding="utf-8")


def all_docs():
    return [PACK / name for name in TEMPLATES] + [PACK / "README.md", PACK / "sources.md", EXAMPLE]


def test_every_file_exists_and_is_not_a_stub():
    for doc in all_docs():
        assert doc.exists(), doc
        assert len(read(doc).split()) > 300, f"{doc.name} is too short to be the real thing"


def test_each_template_opens_with_one_why_paragraph():
    """The task's bar: a one-paragraph 'why this exists' a sceptical engineer would accept."""
    for name in TEMPLATES:
        text = read(PACK / name)
        match = re.search(r"\*\*Why this exists\.\*\*(.*?)\n\n", text, re.S)
        assert match, f"{name}: no 'Why this exists' paragraph"
        why = match.group(1)
        assert "\n\n" not in why.strip(), f"{name}: the why is more than one paragraph"
        words = len(why.split())
        assert 60 <= words <= 260, f"{name}: why paragraph is {words} words"
        assert re.search(r"\[S\d+", why), f"{name}: the why paragraph cites nothing"
        # the why comes before any section
        assert text.index("**Why this exists.**") < text.index("\n## "), name


def test_minute_budgets_add_to_80_and_match_the_readme():
    budgets = {}
    for name in TEMPLATES:
        first_line = read(PACK / name).splitlines()[0]
        match = re.match(r"# (\d)\. .*\((\d+) min\)$", first_line)
        assert match, f"{name}: first line must be '# <n>. <title> (<m> min)': {first_line!r}"
        assert int(match.group(1)) == int(name[:2]), name
        budgets[name] = int(match.group(2))
    assert sum(budgets.values()) == 80, budgets
    assert all(m <= 15 for m in budgets.values()), "no single template may take over 15 minutes in the room"

    readme = read(PACK / "README.md")
    for name, minutes in budgets.items():
        row = re.search(r"^\| \d \| `" + re.escape(name) + r"` \| (\d+) \|", readme, re.M)
        assert row, f"README table has no row for {name}"
        assert int(row.group(1)) == minutes, f"README minutes for {name} differ from the template"
    assert "80 minutes" in readme


def test_readme_splits_the_session_into_presented_and_taken_away():
    readme = read(PACK / "README.md")
    clock = readme[readme.index("## The 30-minute session"):]
    minutes = re.findall(r"^\| (\d+)–(\d+) \|", clock, re.M)
    assert minutes and minutes[0][0] == "0" and minutes[-1][1] == "30", minutes
    for a, b in zip(minutes, minutes[1:]):
        assert a[1] == b[0], f"clock has a gap or overlap at {a} -> {b}"
    assert "Take-away rule" in readme
    assert "template 1" in clock.lower() and "template 4" in clock.lower()


def test_every_template_has_fillable_tables_and_a_signoff():
    for name in TEMPLATES:
        text = read(PACK / name)
        empty_cells = re.findall(r"^\|.*\| +\|$", text, re.M)
        assert len(empty_cells) >= 8, f"{name}: fewer than 8 fillable rows"
        assert re.search(r"^\| (Owner|Data owner) \| +\| +\|", text, re.M), f"{name}: no sign-off row"
        assert "**Paste from:**" in text and "**Done when:**" in text, name


def test_every_cited_source_exists_in_sources_md_and_is_used():
    sources = read(PACK / "sources.md")
    defined = set(re.findall(r"^\| (S\d+) \|", sources, re.M))
    assert len(defined) >= 10, defined
    used = set()
    for doc in [PACK / name for name in TEMPLATES] + [PACK / "README.md"]:
        cited = set(re.findall(r"\[(S\d+)", read(doc)))
        missing = cited - defined
        assert not missing, f"{doc.name} cites {missing}, not in sources.md"
        used |= cited
    unused = defined - used
    assert not unused, f"sources.md defines {unused} but no template cites them"


def test_every_source_has_a_link_a_date_and_a_verification_note():
    sources = read(PACK / "sources.md")
    rows = re.findall(r"^\| (S\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", sources, re.M)
    assert len(rows) >= 10
    for sid, _name, date, link, _use, verified in rows:
        assert "https://" in link, sid
        assert re.search(r"20\d\d", date), f"{sid}: no year in the date column"
        assert any(word in verified.lower() for word in ("primary", "secondary")), f"{sid}: verification note must say primary or secondary"


def test_legal_rows_are_marked_for_the_dpo():
    """The pack is not legal advice: every PDPL figure must point at the DPO."""
    for name in ("02_data_classification.md", "06_incident_response.md"):
        text = read(PACK / name)
        assert "DPO" in text, name
    incident = read(PACK / "06_incident_response.md")
    assert "VERIFY" in incident, "the 72-hour clock must be marked VERIFY"


def test_referenced_repo_paths_exist_or_are_pending():
    pattern = re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*)`")
    missing = []
    for doc in all_docs():
        for match in pattern.findall(read(doc)):
            if match in PENDING_PATHS or match.rstrip("/") + "/" in PENDING_PATHS:
                continue
            if "<" in match or match.startswith(("http", "/var/")):
                continue
            candidate = match.rstrip("/")
            if not (REPO_ROOT / candidate).exists() and not (doc.parent / candidate).exists():
                missing.append((doc.name, match))
    assert not missing, missing


def test_pending_paths_are_still_pending():
    now_present = []
    for path in PENDING_PATHS:
        full = REPO_ROOT / path.rstrip("/")
        if full.is_file() or (full.is_dir() and any(c.name != ".gitkeep" for c in full.iterdir())):
            now_present.append(path)
    assert not now_present, f"remove from PENDING_PATHS: {now_present}"


def test_the_pack_ties_to_the_day_3_demonstration_and_the_mcp_patterns():
    """The task's shaping constraint: connect to the known-bad extraction, the approval interrupt and the audit line."""
    register = read(PACK / "01_system_register.md")
    assert "stored" in register and "index" in register.lower()
    approval = read(PACK / "04_approval_gating.md")
    for needle in ("readOnlyHint", "destructiveHint", "approval interrupt", "index"):
        assert needle.lower() in approval.lower(), needle
    audit = read(PACK / "05_audit_logging.md")
    for event in ("`llm_call`", "`tool_call`", "`index_write`"):
        assert event in audit, event
    for field in ("`trace_id`", "`approval`", "`chunk_id`", "`produced_by`", "`status`"):
        assert field in audit, field
    incident = read(PACK / "06_incident_response.md")
    assert "quarantine" in incident.lower() and "knowledge base" in incident.lower()


def test_example_mirrors_the_templates_in_order_and_has_no_blank_answers():
    text = read(EXAMPLE)
    headings = re.findall(r"^# (\d)\. (.*)$", text, re.M)
    assert [h[0] for h in headings] == [str(i) for i in range(1, 9)], headings
    for name, (_, title) in zip(TEMPLATES, headings):
        template_title = re.match(r"# \d\. (.*) \(\d+ min\)$", read(PACK / name).splitlines()[0]).group(1)
        assert title == template_title, (name, title)
    # every template sub-section (## n.m) appears in the example
    for name in TEMPLATES:
        for sub in re.findall(r"^## (\d\.\d) ", read(PACK / name), re.M):
            assert re.search(r"^## " + re.escape(sub) + r" ", text, re.M), f"example lacks section {sub}"
    # no empty fill prompts and no empty table cells left behind (the header note is a quote; skip it)
    body = text[text.index("# 1. "):text.index("## Fill time")]
    assert not re.findall(r"^>\s*$", body, re.M), "the example has an empty '>' answer"
    lines = body.splitlines()
    blank_rows = []
    for line, following in zip(lines, lines[1:] + [""]):
        if not re.match(r"^\|.*\| +\|$", line):
            continue
        if following.startswith("|---"):
            continue                       # a table header with an empty column title, as in the templates
        if re.match(r"^\| [2-4] \|", line):
            continue                       # the first-month log's future weeks may be blank
        blank_rows.append(line)
    assert not blank_rows, blank_rows[:5]


def test_example_is_honest_about_what_is_not_measured():
    text = read(EXAMPLE)
    assert text.count("not measured") >= 5, "the extraction scores do not exist yet; the example must say so"
    assert "not rehearsed" in text
    assert "invented" in text.lower()
    assert "Fill time" in text and re.search(r"\| whole pack \| \d\d:\d\d:\d\d \| \d\d:\d\d:\d\d \| [\d.]+ \|", text)
    # synthetic only: none of the real site or system names the rules forbid
    for forbidden in ("e-Symphony", "SAP "):
        assert forbidden not in text, forbidden
