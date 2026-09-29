"""The OQ Helpdesk demo app: Contract 5, the guards, and the synthetic-data rule.

No model is called anywhere in here.
"""
import json
import re
from pathlib import Path

import pytest

from apps.oq_helpdesk.index import SCORE_FLOOR, build_index, tokens
from apps.oq_helpdesk.main import SYSTEM_PROMPT, render_context
from capstone.contract import DESCRIBE_KEYS, HIT_KEYS, check_hits

REPO_ROOT = Path(__file__).resolve().parent.parent
KB = REPO_ROOT / "apps" / "oq_helpdesk" / "kb"

# systems and queues the ticket corpus uses - the KB must not invent new ones
SYSTEMS = {"Tavrona ERP", "GateKey VPN", "DocHarbor", "S: drive", "AssetHive", "MyPortal",
           "KeyNest", "StaffGate", "VoxLine", "CORP-WIFI", "Teams", "Outlook", "Excel",
           "Power BI", "Acrobat", "Windows"}
QUEUES = {"apps_support", "end_user_computing", "erp_support", "identity_access",
          "network_ops", "security_ops", "service_desk_l1", "telecom_voice"}
CATEGORIES = {"access", "erp", "hardware", "network", "other", "software", "telecom"}


@pytest.fixture(scope="module")
def index():
    return build_index()


def test_every_article_has_the_frontmatter_the_index_reads():
    articles = sorted(KB.glob("*.md"))
    assert len(articles) >= 12, "the knowledgebase is too small to demo retrieval"
    for path in articles:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---"), path.name
        front = text.split("---")[1]
        for key in ("kb_id", "title", "category", "routing_queue", "systems", "updated"):
            assert re.search(rf"^{key}:", front, re.M), f"{path.name} has no {key}"
        assert path.name.startswith(re.search(r"^kb_id:\s*(\S+)", front, re.M).group(1))


def test_the_kb_reuses_the_ticket_corpus_vocabulary(index):
    """An invented system or queue here would teach the room the wrong words."""
    for article in index.articles():
        assert article["category"] in CATEGORIES, article
        assert article["routing_queue"] in QUEUES, article
        for system in article["systems"]:
            assert system in SYSTEMS, f"{article['kb_id']} names an unknown system: {system}"


def test_the_index_satisfies_contract_5(index):
    described = index.describe()
    for key in DESCRIBE_KEYS:
        assert key in described, key
    assert described["items"] > 0
    hits = index.search("how do I get access to Tavrona ERP", k=4)
    check_hits(hits, 4)                       # the repo's own validator
    for hit in hits:
        assert sorted(hit) == sorted(HIT_KEYS), hit


def test_search_is_ordered_and_respects_k(index):
    hits = index.search("password expired cannot sign in", k=3)
    assert 0 < len(hits) <= 3
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)


def test_filters_narrow_by_metadata(index):
    erp = index.search("access", k=10, filters={"category": "erp"})
    assert erp, "expected at least one erp hit"
    assert {h["metadata"]["category"] for h in erp} == {"erp"}
    by_system = index.search("access", k=10, filters={"systems": "Tavrona ERP"})
    assert by_system and all("Tavrona ERP" in h["metadata"]["systems"] for h in by_system)


def test_an_empty_or_stopword_query_returns_nothing(index):
    assert index.search("") == []
    assert index.search("the and of to") == []
    assert tokens("the and of to") == []


def test_covered_questions_clear_the_retrieval_floor(index):
    for question in ["how do I get access to Tavrona ERP",
                     "my password expired and I cannot sign in",
                     "nobody can hear me in Teams",
                     "I clicked a link in a suspicious email",
                     "GateKey VPN will not connect"]:
        hits = index.search(question, k=3)
        assert hits, question
        assert hits[0]["score"] >= SCORE_FLOOR, f"{question} -> {hits[0]['score']}"


def test_a_question_with_no_article_retrieves_nothing_at_all(index):
    """Not every off-corpus question falls below the floor - see the README. These do."""
    for question in ["how do I claim travel expenses", "what is the company dividend policy"]:
        assert index.search(question, k=3) == [], question


def test_the_grounding_prompt_still_says_the_four_things_it_promises():
    """The README and the demo script quote this prompt. Keep them true."""
    assert "ONLY from the knowledgebase extracts" in SYSTEM_PROMPT
    assert "NOT_IN_KB:" in SYSTEM_PROMPT
    assert "[KB-004]" in SYSTEM_PROMPT            # citation format, by example
    assert "Never invent" in SYSTEM_PROMPT


def test_the_context_handed_to_the_model_is_only_retrieved_text(index):
    hits = index.search("new phone MFA", k=3)
    context = render_context(hits)
    for hit in hits:
        assert hit["text"] in context
        assert f"[{hit['doc_id']}]" in context     # the model can cite only what it is shown
    assert len(context.split("---")) == len(hits)


def test_the_index_build_id_changes_with_the_knowledgebase(tmp_path):
    for name, body in (("KB-900_a.md", "---\nkb_id: KB-900\ntitle: A\ncategory: other\n"
                                       "routing_queue: service_desk_l1\nsystems: Teams\n"
                                       "updated: 2026-01-01\n---\n\n# A\n\n## S\none\n"),):
        (tmp_path / name).write_text(body, encoding="utf-8")
    first = build_index(tmp_path).describe()["build_id"]
    (tmp_path / "KB-900_a.md").write_text(
        (tmp_path / "KB-900_a.md").read_text(encoding="utf-8") + "\ntwo\n", encoding="utf-8")
    assert build_index(tmp_path).describe()["build_id"] != first


def test_no_real_names_or_real_oq_material_in_the_knowledgebase():
    """Same rule as the ticket corpus: invented systems, first names only, no OQ."""
    banned = re.compile(r"\b(SAP|e-Symphony|Oman|Muscat|Sohar|Duqm|OQ8|Orpic)\b", re.I)
    for path in sorted(KB.glob("*.md")):
        found = banned.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path.name} mentions {found}"
