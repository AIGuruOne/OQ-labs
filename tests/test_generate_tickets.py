"""Tests for scripts/generate_tickets.py.

    python -m pytest tests/test_generate_tickets.py -v

The one that matters most is test_committed_corpus_matches_generator:
every downstream artifact (dataset, adapter, eval tables) is built from
the committed seed-42 corpus, so editing a phrase bank without
regenerating must fail loudly here, not silently on Day 2.
"""

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_tickets as gen  # noqa: E402
import ticket_scenarios as bank  # noqa: E402

SCHEMA = json.loads((REPO_ROOT / "data" / "finetune" / "ticket_schema.json").read_text(encoding="utf-8"))
COMMITTED_SEED = 42
COMMITTED_COUNT = 600


@pytest.fixture(scope="module")
def corpus():
    return gen.generate_corpus(COMMITTED_COUNT, COMMITTED_SEED)


def test_same_seed_gives_identical_output():
    first = gen.generate_corpus(150, 7)
    second = gen.generate_corpus(150, 7)
    assert first == second


def test_different_seed_gives_different_output():
    tickets_a, _ = gen.generate_corpus(50, 1)
    tickets_b, _ = gen.generate_corpus(50, 2)
    assert tickets_a != tickets_b


def test_count_is_honoured():
    tickets, labels = gen.generate_corpus(37, 5)
    assert len(tickets) == 37
    assert len(labels) == 37


def test_committed_corpus_matches_generator(tmp_path):
    tickets, labels = gen.generate_corpus(COMMITTED_COUNT, COMMITTED_SEED)
    gen.write_jsonl(tmp_path / "tickets.jsonl", tickets)
    gen.write_jsonl(tmp_path / "labels.jsonl", labels)

    committed_tickets = (REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl").read_bytes()
    committed_labels = (REPO_ROOT / "data" / "finetune" / "ticket_labels.jsonl").read_bytes()
    message = "phrase bank or generator changed - rerun scripts/generate_tickets.py and rebuild downstream"
    assert (tmp_path / "tickets.jsonl").read_bytes() == committed_tickets, message
    assert (tmp_path / "labels.jsonl").read_bytes() == committed_labels, message


@pytest.mark.parametrize("seed", [42, 1, 2026])
def test_every_record_validates_against_schema(seed):
    _, labels = gen.generate_corpus(600, seed)
    validator = Draft202012Validator(SCHEMA)
    for label in labels:
        errors = [error.message for error in validator.iter_errors(label["record"])]
        assert errors == [], f"{label['ticket_id']}: {errors}"
        assert label["record"]["routing_queue"] in bank.ROUTING_QUEUES


def test_raw_tickets_follow_contract_1(corpus):
    tickets, _ = corpus
    for ticket in tickets:
        assert list(ticket.keys()) == ["ticket_id", "created", "site", "channel", "subject", "body"]
        assert re.fullmatch(r"INC-\d{6}", ticket["ticket_id"])
        assert re.fullmatch(r"[A-Z]{3}", ticket["site"])
        assert ticket["channel"] in ("portal", "email", "phone", "walk_in")
        assert ticket["body"].strip() != ""
        assert "{" + "system" + "}" not in ticket["body"], "unfilled slot"
    assert not re.search(r"\{[a-z_]+2?\}", "\n".join(t["subject"] + t["body"] for t in tickets)), "unfilled slot"


def test_ids_and_bodies_are_unique(corpus):
    tickets, _ = corpus
    assert len({ticket["ticket_id"] for ticket in tickets}) == len(tickets)
    assert len({ticket["body"] for ticket in tickets}) == len(tickets)


def test_labels_are_derivable_from_text(corpus):
    tickets, labels = corpus
    for ticket, label in zip(tickets, labels):
        text = ticket["subject"] + "\n" + ticket["body"]
        system = label["record"]["affected_system"]
        if system is not None:
            aliases = bank.SYSTEM_ALIASES[system]
            assert any(alias.lower() in text.lower() for alias in aliases), ticket["ticket_id"]
        asset = label["record"]["asset_tag"]
        if asset is not None:
            squeezed = re.sub(r"[\s-]", "", text).upper()
            assert asset.replace("-", "") in squeezed, ticket["ticket_id"]


def test_class_mix_is_imbalanced(corpus):
    _, labels = corpus
    counts = {}
    for label in labels:
        category = label["record"]["category"]
        counts[category] = counts.get(category, 0) + 1
    ranked = sorted(counts, key=lambda name: -counts[name])
    assert len(counts) == 7
    assert ranked[0] == "access"
    assert set(ranked[-2:]) == {"erp", "telecom"}
    assert counts[ranked[0]] >= 4 * counts[ranked[-1]]


def test_every_messiness_feature_occurs(corpus):
    _, labels = corpus
    seen = {feature for label in labels for feature in label["meta"]["features"]}
    expected = {"two_problems", "error_string", "multiline_paste", "screenshot_ref", "system_unnamed",
                "asset_nonstandard", "plant_tag_distractor", "tone_urgent", "non_native", "agent_note",
                "forwarded", "very_short", "very_long"}
    assert expected <= seen, expected - seen


def test_urgency_rule():
    # (kind, impact, deadline, relaxed, needed_by, fixed) -> urgency
    assert gen.decide_urgency("blocked", "single_user", False, False, False, None) == "high"
    assert gen.decide_urgency("blocked", "site", False, False, False, None) == "critical"
    assert gen.decide_urgency("degraded", "single_user", False, False, False, None) == "medium"
    assert gen.decide_urgency("degraded", "single_user", True, False, False, None) == "high"
    assert gen.decide_urgency("degraded", "single_user", False, True, False, None) == "low"
    assert gen.decide_urgency("degraded", "enterprise", False, False, False, None) == "high"
    assert gen.decide_urgency("request", "single_user", False, False, False, None) == "low"
    assert gen.decide_urgency("request", "team", False, False, True, None) == "medium"
    assert gen.decide_urgency("request", "single_user", True, False, False, None) == "high"
    assert gen.decide_urgency("request", "single_user", False, False, False, "medium") == "medium"


def test_scenario_bank_is_well_formed():
    ids = [scenario["id"] for scenario in bank.SCENARIOS]
    assert len(ids) == len(set(ids))
    for scenario in bank.SCENARIOS:
        assert scenario["category"] in bank.CATEGORY_WEIGHTS
        assert scenario["id"].startswith(scenario["category"] + ".")
        assert scenario["queue"] in bank.ROUTING_QUEUES
        assert scenario["kind"] in ("blocked", "degraded", "request")
        for system in scenario["systems"]:
            assert system in bank.SYSTEM_ALIASES
        for key in ("problems", "problems_nn", "notes"):
            assert len(scenario[key]) >= 1, f"{scenario['id']} has no {key}"
        # no system -> the texts must not use the {system} slot
        if not scenario["systems"]:
            texts = scenario["problems"] + scenario["problems_nn"] + scenario["notes"]
            assert not any("{system}" in text for text in texts), scenario["id"]
