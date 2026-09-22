"""Unit tests for notebooks/fundamentals_utils.py and utils.ensure_api_key.

    python -m pytest tests/test_fundamentals_utils.py -v

No network: the one helper that calls a model (score_probe_1) is given
a fake endpoint.
"""

import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import fundamentals_utils as fu  # noqa: E402
import utils  # noqa: E402


class FakeLLM:
    """Replies with the tag only if the earlier user turn was sent."""

    name = "fake"
    model = "fake-model"
    base_url = "http://fake/v1"

    def __init__(self, reject=False):
        self.reject = reject
        self.calls = []

    def chat(self, prompt=None, *, messages=None, **kwargs):
        self.calls.append(messages)
        if self.reject:
            raise RuntimeError("HTTP 400")
        history = " ".join(m["content"] for m in messages)
        return "LAP-04412" if "LAP-04412" in history else "I do not have that information."


# ---------------------------------------------------------------------------
# Diagnostic scoring: never raises, scores what was asked
# ---------------------------------------------------------------------------


def test_probe_1_not_attempted_scores_zero_without_a_model_call(capsys):
    llm = FakeLLM()
    assert fu.score_probe_1(llm, ...) == 0
    assert llm.calls == []
    assert "NOT ATTEMPTED" in capsys.readouterr().out


def test_probe_1_malformed_messages_score_zero():
    llm = FakeLLM()
    assert fu.score_probe_1(llm, "not a list") == 0
    assert fu.score_probe_1(llm, [{"role": "user"}]) == 0
    assert fu.score_probe_1(llm, []) == 0
    assert llm.calls == []


def test_probe_1_passes_only_when_the_history_is_resent():
    with_history = [
        {"role": "user", "content": fu.PROBE_1_EARLIER_USER},
        {"role": "assistant", "content": fu.PROBE_1_EARLIER_ASSISTANT},
        {"role": "user", "content": fu.PROBE_1_FOLLOW_UP},
    ]
    without_history = [{"role": "user", "content": fu.PROBE_1_FOLLOW_UP}]
    assert fu.score_probe_1(FakeLLM(), with_history) == 2
    assert fu.score_probe_1(FakeLLM(), without_history) == 0


def test_probe_1_survives_an_api_rejection():
    assert fu.score_probe_1(FakeLLM(reject=True), [{"role": "usr", "content": "x"}]) == 0


def test_probe_2_scoring_ladder():
    assert fu.score_probe_2(...) == 0
    assert fu.score_probe_2("{}") == 0
    assert fu.score_probe_2({"category": "hardware"}) == 0
    right_keys_wrong_values = {"category": "software", "urgency": "low", "asset_tag": None}
    assert fu.score_probe_2(right_keys_wrong_values) == 1
    assert fu.score_probe_2({"category": "hardware", "urgency": "high", "asset_tag": "LAP-07731"}) == 2
    assert fu.score_probe_2({"category": "hardware", "urgency": "critical", "asset_tag": "LAP-07731"}) == 2


def test_quiz_scoring_tolerates_case_and_missing_keys():
    assert fu.score_quiz(...) == 0
    assert fu.score_quiz({"q1": "C", "q2": " a "}) == 2
    assert fu.score_quiz(dict(fu.QUIZ_ANSWER_KEY)) == 4
    assert fu.score_quiz({"q1": "a", "q2": "b", "q3": "c", "q4": "d"}) == 0


def test_quiz_answer_key_points_at_real_options():
    for key, question, options in fu.QUIZ:
        assert fu.QUIZ_ANSWER_KEY[key] in options
    assert len(set(fu.QUIZ_ANSWER_KEY.values())) > 1, "all answers the same letter is a tell"


def test_verdict_threshold_and_that_probes_dominate(capsys):
    assert fu.diagnostic_verdict(2, 2, 2)["verdict"] == "READY"
    assert fu.diagnostic_verdict(2, 2, 1)["verdict"] == "FUNDAMENTALS"
    # Perfect quiz, both probes failed: cannot reach READY.
    assert fu.diagnostic_verdict(0, 0, 4)["verdict"] == "FUNDAMENTALS"
    out = capsys.readouterr().out
    assert "DIAGNOSTIC RESULT:" in out and "two thirds" in out


# ---------------------------------------------------------------------------
# JSON handling and the schema
# ---------------------------------------------------------------------------


def test_try_parse_json_is_strict_and_strip_fence_repairs():
    fenced = '```json\n{"a": 1}\n```'
    ok, value = fu.try_parse_json(fenced)
    assert not ok and value.startswith("not JSON")
    assert fu.try_parse_json(fu.strip_fence(fenced)) == (True, {"a": 1})
    assert fu.strip_fence('{"a": 1}') == '{"a": 1}'


def test_schema_errors_use_the_locked_schema():
    schema = fu.load_schema(REPO_ROOT)
    validator = jsonschema.Draft202012Validator(schema)
    good = fu.load_sample_tickets(REPO_ROOT, count=1)[0]["expected"]
    assert fu.schema_errors(good, validator) == []
    bad = dict(good, category="printer", asset_tag="LAPTOP-1")
    messages = fu.schema_errors(bad, validator)
    assert any(m.startswith("category:") for m in messages)
    assert any(m.startswith("asset_tag:") for m in messages)


def test_sample_tickets_come_from_the_held_out_set():
    samples = fu.load_sample_tickets(REPO_ROOT, count=5)
    assert len(samples) == 5
    assert samples[0]["ticket_id"] == "INC-004183"
    assert set(samples[0]["expected"]) == set(fu.EXACT_FIELDS) | {"requested_action"}
    assert samples[0]["text"].startswith("Subject:")


def test_compare_records_uses_exact_match_and_word_overlap():
    expected = fu.load_sample_tickets(REPO_ROOT, count=1)[0]["expected"]
    same = fu.compare_records(dict(expected), expected)
    assert all(same.values())
    changed = dict(expected, urgency="low", requested_action="Reboot the printer in the lobby")
    verdicts = fu.compare_records(changed, expected)
    assert verdicts["urgency"] is False
    assert verdicts["requested_action"] is False
    assert verdicts["category"] is True


def test_comparison_table_prints_one_row_per_ticket(capsys):
    expected = fu.load_sample_tickets(REPO_ROOT, count=1)[0]["expected"]
    rows = [{"ticket_id": "INC-000001", "attempts": 1, "verdicts": fu.compare_records(expected, expected)}]
    fu.print_comparison_table(rows)
    out = capsys.readouterr().out
    assert "INC-000001" in out and out.count("\n") == 3
    assert all(ord(ch) < 128 for ch in out)


# ---------------------------------------------------------------------------
# The agent's tools and action parsing
# ---------------------------------------------------------------------------


def test_tools_return_dicts_and_errors_never_raise():
    ticket = fu.get_ticket(REPO_ROOT, "INC-004549")
    assert ticket["ticket_id"] == "INC-004549" and "LAP-04391".lower() in ticket["text"].lower()
    assert "error" in fu.get_ticket(REPO_ROOT, "INC-999999")
    asset = fu.get_asset("lap-04391")
    assert asset["asset_tag"] == "LAP-04391" and asset["today"] == fu.TODAY_FOR_THE_LAB
    assert asset["site"] == ticket["site"], "the register must agree with the ticket"
    assert "error" in fu.get_asset("LAP-00000")


def test_asset_register_follows_the_naming_conventions():
    import re
    for tag, row in fu.ASSET_REGISTER.items():
        assert re.fullmatch(r"[A-Z]{3}-[0-9]{5}", tag)
        assert re.fullmatch(r"[A-Z]{3}", row["site"])
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["warranty_until"])
        assert " " not in row["assigned_to"], "first names only (or shared)"


def test_parse_action_handles_fences_and_garbage():
    assert fu.parse_action('{"tool": "get_asset", "args": {"asset_tag": "LAP-04391"}}') == {
        "tool": "get_asset", "args": {"asset_tag": "LAP-04391"}}
    assert fu.parse_action('```json\n{"final": "done"}\n```') == {"final": "done"}
    assert "error" in fu.parse_action("I would call get_asset now.")
    assert "error" in fu.parse_action("[1, 2]")


def test_agent_prompt_names_exactly_the_two_tools():
    assert "get_ticket(ticket_id)" in fu.AGENT_SYSTEM_PROMPT
    assert "get_asset(asset_tag)" in fu.AGENT_SYSTEM_PROMPT
    assert '"final"' in fu.AGENT_SYSTEM_PROMPT and '"tool"' in fu.AGENT_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# utils.ensure_api_key
# ---------------------------------------------------------------------------


def test_ensure_api_key_uses_the_environment_and_never_prints_it(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key-123456")
    assert utils.ensure_api_key(in_colab=False) is True
    out = capsys.readouterr().out
    assert "found" in out and "sk-test" not in out


def test_ensure_api_key_reports_a_missing_key_locally(monkeypatch, capsys, tmp_path):
    import config.endpoints as endpoints  # importing loads the real .env once; then remove the key

    monkeypatch.setattr(endpoints, "REPO_ROOT", tmp_path)  # no .env there
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert utils.ensure_api_key(in_colab=False) is False
    out = capsys.readouterr().out
    assert "NOT SET" in out and ".env.example" in out


def test_ensure_api_key_sees_a_env_file_fixed_after_the_kernel_started(
    monkeypatch, capsys, tmp_path
):
    """The NOT SET message says "re-run this cell". That must be true: a
    participant who creates .env mid-session must not need a kernel
    restart (reproduced as a bug 2026-09-22, failure playbook entry 4)."""
    import config.endpoints as endpoints

    monkeypatch.setattr(endpoints, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert utils.ensure_api_key(in_colab=False) is False

    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-fixed-later\n", encoding="utf-8")
    assert utils.ensure_api_key(in_colab=False) is True
    out = capsys.readouterr().out
    assert "found in .env" in out and "sk-test" not in out
