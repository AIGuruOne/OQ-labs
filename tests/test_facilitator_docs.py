"""Tests for the Day 1 paper artifacts in facilitator/ (P12).

    python -m pytest tests/test_facilitator_docs.py -v

Paper cannot be executed, but it can drift: a path it names can
disappear, a number it quotes can be superseded by a re-run, a time
budget can stop adding up. These tests catch that.
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FAC = REPO_ROOT / "facilitator"
EVAL = FAC / "prebaked_outputs" / "eval"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DOCS = [
    FAC / "decision_matrix_template.md",
    FAC / "architecture_spec_template.md",
    FAC / "cost_model.md",
    FAC / "spec_review_checklist.md",
    FAC / "use_case_briefs.md",
    FAC / "README.md",
    FAC / "examples" / "architecture_spec_brief1_filled.md",
    FAC / "examples" / "spec_review_brief1_filled.md",
]

# Repo paths the briefs name that other slices deliver later in the
# build (Day 3 corpus and eval sets, Day 5 capstone). Remove an entry
# here when the thing exists.
PENDING_PATHS = {
    "data/eval/rag_adversarial.jsonl",
    "data/eval/golden_answers.jsonl",
    "data/eval/image_ground_truth/",
    "capstone/reference_index/",
    "scripts/score_extraction.py",
}


def is_present(path):
    """A folder holding only .gitkeep is a placeholder, not the thing."""
    full = REPO_ROOT / path.rstrip("/")
    if not full.exists():
        return False
    if full.is_file():
        return True
    return any(child.name != ".gitkeep" for child in full.iterdir())


def read(path):
    return path.read_text(encoding="utf-8")


def test_all_documents_exist_and_are_not_stubs():
    for doc in DOCS:
        assert doc.exists(), doc
        assert len(read(doc).split()) > 300, f"{doc.name} is too short to be the real thing"


def test_referenced_repo_paths_exist():
    """Every `path/like/this` in the documents points at something real (or is listed as pending)."""
    pattern = re.compile(r"`((?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]*)`")
    missing = []
    for doc in DOCS:
        for match in pattern.findall(read(doc)):
            candidate = match.rstrip("/")
            if match in PENDING_PATHS or match.rstrip("/") + "/" in PENDING_PATHS:
                continue
            if "<" in match or match.startswith("http"):
                continue
            # paths are repo-relative; facilitator/README.md also uses paths relative to itself
            if not (REPO_ROOT / candidate).exists() and not (doc.parent / candidate).exists():
                missing.append((doc.name, match))
    assert not missing, missing


def test_pending_paths_are_still_pending():
    """When a pending path appears, drop it from PENDING_PATHS so the test above covers it."""
    now_present = [p for p in PENDING_PATHS if is_present(p)]
    assert not now_present, f"remove from PENDING_PATHS: {now_present}"


def test_spec_template_minutes_add_to_75():
    text = read(FAC / "architecture_spec_template.md")
    minutes = [int(m) for m in re.findall(r"^## \d+\. .*?\((\d+) min", text, re.M)]
    assert len(minutes) == 11, minutes
    assert sum(minutes) == 75, minutes
    assert "75 minutes" in text


def test_checklist_shape():
    text = read(FAC / "spec_review_checklist.md")
    questions = re.findall(r"^\| ([A-J]\d+) \|", text, re.M)
    assert len(questions) >= 40
    assert len(set(questions)) == len(questions), "duplicate question ids"
    for group in "ABCDEFGHIJ":
        assert any(q.startswith(group) for q in questions), group
    for severity in ("BLOCKS", "BEFORE PILOT", "NOTE"):
        assert severity in text
    assert "| 0–7 |" in text and "| 23–25 |" in text


def test_briefs_cover_five_capabilities_and_every_brief_has_a_session_map():
    text = read(FAC / "use_case_briefs.md")
    headings = re.findall(r"^## Brief (\d) — (.*)$", text, re.M)
    assert [h[0] for h in headings] == ["1", "2", "3", "4", "5"]
    titles = " ".join(h[1].lower() for h in headings)
    for capability in ("fine-tuning", "retrieval", "vision", "agents", "integration"):
        assert capability in titles, capability
    assert "Ticket to structured record" in headings[0][1], "brief 1 must be the locked fine-tune task"
    for section in ("**The problem.**", "**Who feels it.**", "**What success looks like.**",
                    "**What data exists.**", '**What "deployment-ready" means here.**',
                    "**Which sessions give you what you need.**", "**What you show on Thursday.**"):
        assert text.count(section) == 5, section
    # the coverage table has a column per brief and marks each essential at least three days
    table = text[text.index("## Coverage"):]
    assert table.count("| **E** |") + table.count("| **E** ") > 40


def test_decision_matrix_worked_example_arithmetic():
    text = read(FAC / "decision_matrix_template.md")
    example = text[text.index("## Worked example"):]
    rows = re.findall(r"^\| \d \| .*? \| (\d+) \| (\d) \| (\d) \| (\d) \| (\d) \|", example, re.M)
    assert len(rows) == 8, rows
    weights = [int(r[0]) for r in rows]
    assert sum(weights) == 100
    totals = [sum(int(r[0]) * int(r[i]) for r in rows) for i in (1, 2, 3, 4)]
    assert totals == [380, 430, 295, 305], totals
    assert "**380** | **430** | **295** | **305**" in example


def summary(name):
    return json.loads(read(EVAL / name))


def counts(summ):
    n = summ["n_items"]
    return {field: round(rate * n) for field, rate in summ["per_field_accuracy"].items()}


def test_filled_spec_quotes_the_prebaked_numbers():
    """The quality table in the filled spec must match the reference runs it cites."""
    text = read(FAC / "examples" / "architecture_spec_brief1_filled.md")
    base = summary("06_base_llama3.2-1b_summary.json")
    tuned = summary("06_tuned_prebaked_b1c0e3d4_summary.json")
    hosted = summary("2026-09-20_hosted_heldout_20_summary.json")
    b, t, h = counts(base), counts(tuned), counts(hosted)

    def row(label):
        m = re.search(r"^\s*\| " + re.escape(label) + r" \| (\S+) \| (\S+) \| (\S+) \|", text, re.M)
        assert m, label
        return m.groups()

    assert row("Format: schema-valid") == (f"{round(base['schema_valid_rate'] * 20)}/20", f"{round(tuned['schema_valid_rate'] * 20)}/20", f"{round(hosted['schema_valid_rate'] * 20)}/20")
    for label, field in [("`routing_queue`", "routing_queue"), ("`requested_action` >= 0.5", "requested_action"),
                         ("`category`", "category"), ("`asset_tag`", "asset_tag"), ("`urgency`", "urgency")]:
        assert row(label) == (f"{b[field]}/20", f"{t[field]}/20", f"{h[field]}/20"), label
    assert row("Whole record (six exact fields)") == (f"{round(base['overall_exact_match'] * 20)}/20", f"{round(tuned['overall_exact_match'] * 20)}/20", f"{round(hosted['overall_exact_match'] * 20)}/20")
    assert row("Invented values") == (str(base["invented"]["total"]), str(tuned["invented"]["total"]), str(hosted["invented"]["total"]))

    val = summary("2026-09-20_tuned-val72_val_clean_summary.json")
    v = counts(val)
    assert f"urgency {v['urgency']}/72 and routing {v['routing_queue']}/72" in text
    shape = tuned["urgency_errors"]["shape"]
    assert f"{shape['over_by_1']} over-by-one, {shape['over_by_2_or_more']} over-by-two, {shape['under_by_1']} under-by-one" in text


def test_filled_spec_quotes_the_cost_model():
    import build_cost_model as cm

    r = cm.compute(cm.SCENARIOS["ticket"])
    text = read(FAC / "examples" / "architecture_spec_brief1_filled.md")
    assert f"| Requests per month | {r['requests_month']:,} |" in text
    assert f"${r['self_month']:,.0f}" in text
    assert f"{r['breakeven_requests_month']:,.0f}" in text
    assert f"| Peak requests per hour | {r['peak_requests_hour']:.0f} |" in text
    sonnet = next(a for a in r["api"] if a["model"] == "Claude Sonnet 5")
    assert f"${sonnet['monthly']:.2f}" in text


def test_cost_model_note_matches_the_script_output():
    import build_cost_model as cm

    text = read(FAC / "cost_model.md")
    r = cm.compute(cm.SCENARIOS["ticket"])
    assert f"Break-even against Claude Sonnet 5: {r['breakeven_requests_month']:,.0f} requests/month" in text
    for a in r["api"]:
        assert f"{a['monthly']:9.2f}" in text, a["model"]
    for source_id, *_ in cm.SOURCES:
        assert f"| {source_id} |" in text, source_id
