"""Tests for notebooks/inference_utils.py and the notebook-02 additions to
notebooks/ollama_utils.py. No network, no Ollama: the HTTP layer is stubbed.

    python -m pytest tests/test_inference_utils.py -v
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import inference_utils  # noqa: E402
import ollama_utils  # noqa: E402


class FakeResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code
        self.text = str(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


# ---------------------------------------------------------------------------
# chat_timed: the server's nanoseconds become seconds and tokens per second
# ---------------------------------------------------------------------------


def test_chat_timed_turns_nanoseconds_into_seconds_and_a_speed(monkeypatch):
    body = {"message": {"role": "assistant", "content": "hello"}, "done_reason": "stop",
            "total_duration": 1_000_000_000, "load_duration": 100_000_000,
            "prompt_eval_count": 30, "prompt_eval_duration": 50_000_000,
            "eval_count": 40, "eval_duration": 800_000_000}
    monkeypatch.setattr(inference_utils.requests, "post", lambda *args, **kwargs: FakeResponse(body))
    timing = inference_utils.chat_timed("m", [{"role": "user", "content": "hi"}], base_url="http://x")
    assert timing["reply"] == "hello"
    assert timing["load_seconds"] == 0.1
    assert timing["generate_seconds"] == 0.8
    assert timing["total_seconds"] == 1.0
    assert timing["reply_tokens"] == 40 and timing["prompt_tokens"] == 30
    assert timing["tokens_per_second"] == 50.0


def test_chat_timed_with_no_generation_reports_zero_not_a_crash(monkeypatch):
    body = {"message": {"role": "assistant", "content": ""}, "done_reason": "stop"}
    monkeypatch.setattr(inference_utils.requests, "post", lambda *args, **kwargs: FakeResponse(body))
    timing = inference_utils.chat_timed("m", [], base_url="http://x")
    assert timing["tokens_per_second"] == 0.0


def test_a_missing_model_says_run_the_pull_cell(monkeypatch):
    monkeypatch.setattr(inference_utils.requests, "post",
                        lambda *args, **kwargs: FakeResponse({"error": "model 'm' not found"}, 404))
    with pytest.raises(ollama_utils.OllamaError, match="pull cell"):
        inference_utils.chat_timed("m", [], base_url="http://x")
    with pytest.raises(ollama_utils.OllamaError, match="pull cell"):
        inference_utils.model_card("m", base_url="http://x")


# ---------------------------------------------------------------------------
# run_experiments: identical or not, per setting
# ---------------------------------------------------------------------------


def test_run_experiments_reports_identical_and_different(monkeypatch):
    replies = iter(["same", "same", "one", "two"])

    def fake_post(url, json, timeout):
        text = next(replies)
        return FakeResponse({"choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                             "usage": {"completion_tokens": len(text)}})

    monkeypatch.setattr(inference_utils.requests, "post", fake_post)
    results = inference_utils.run_experiments("m", [], {"a": {"temperature": 0.0}, "b": {"temperature": 1.0}},
                                              repeats=2, base_url="http://x")
    assert results["a"]["identical"] is True
    assert results["b"]["identical"] is False
    assert results["b"]["replies"] == ["one", "two"]
    assert results["a"]["reply_tokens"] == [4, 4]


def test_common_prefix_length():
    assert inference_utils.common_prefix_length(["abcd", "abxy"]) == 2
    assert inference_utils.common_prefix_length(["same", "same"]) == 4
    assert inference_utils.common_prefix_length([]) == 0


def test_print_experiments_is_ascii_and_explains_temperature_zero_differences(capsys):
    results = {"repeatable": {"settings": {"temperature": 0.0, "seed": 1}, "replies": ["café A", "café B"],
                              "finish_reasons": ["stop", "stop"], "reply_tokens": [3, 3],
                              "identical": False, "seconds": [1.0, 1.0]}}
    inference_utils.print_experiments(results)
    printed = capsys.readouterr().out
    printed.encode("ascii")                                     # a Windows console can show it
    assert "DIFFERENT (identical for the first 5 characters)" in printed
    assert "at temperature 0" in printed


# ---------------------------------------------------------------------------
# Reading replies
# ---------------------------------------------------------------------------


def test_parse_json_reply_distinguishes_clean_fenced_and_prose():
    assert inference_utils.parse_json_reply('{"a": 1}') == ({"a": 1}, "valid JSON object")
    assert inference_utils.parse_json_reply('```json\n{"a": 1}\n```') == ({"a": 1}, "JSON inside a code fence")
    assert inference_utils.parse_json_reply("Sure! Here you go") == (None, "not JSON")
    assert inference_utils.parse_json_reply("[1, 2]") == (None, "not JSON")


def test_compare_records_counts_right_wrong_and_missing():
    expected = {"category": "software", "urgency": "high", "impact": "single_user"}
    marks = inference_utils.compare_records({"category": "software", "urgency": "low"}, expected)
    assert marks == {"right": ["category"], "wrong": ["urgency"], "missing": ["impact"]}
    assert inference_utils.compare_records(None, expected)["missing"] == list(expected)


def test_side_by_side_stays_under_100_columns_and_ascii():
    rows = [("label", "x" * 200, "café " * 30), ("short", 1.5, None)]
    table = inference_utils.side_by_side(rows, "left", "right")
    for line in table.splitlines():
        assert len(line) <= 100
        line.encode("ascii")
    assert "..." in table


# ---------------------------------------------------------------------------
# ollama_utils: a server that dies at once explains itself
# ---------------------------------------------------------------------------


def test_a_port_clash_is_named_with_a_free_port_to_try(tmp_path):
    log = tmp_path / "ollama_server.log"
    log.write_text("time=... level=INFO msg=starting\n"
                   "Error: listen tcp 127.0.0.1:11434: bind: address already in use\n", encoding="utf-8")
    message = ollama_utils.explain_server_exit("http://localhost:11434", log)
    assert "Port 11434 is held by another program" in message
    assert "OLLAMA_BASE_URL=http://localhost:11435" in message


def test_the_windows_wording_of_a_port_clash_is_recognised(tmp_path):
    log = tmp_path / "ollama_server.log"
    log.write_text("Error: listen tcp 127.0.0.1:11437: bind: Only one usage of each socket address "
                   "(protocol/network address/port) is normally permitted.\n", encoding="utf-8")
    message = ollama_utils.explain_server_exit("http://localhost:11437", log)
    assert "Port 11437 is held" in message and "localhost:11438" in message


def test_any_other_exit_points_at_the_full_log(tmp_path):
    log = tmp_path / "ollama_server.log"
    log.write_text("Error: something else\n", encoding="utf-8")
    message = ollama_utils.explain_server_exit("http://localhost:11434", log)
    assert "something else" in message and "Full log" in message
    assert "(empty log)" in ollama_utils.explain_server_exit("http://localhost:11434", tmp_path / "missing.log")


def test_a_server_that_exits_at_once_raises_within_seconds_not_a_minute(monkeypatch, tmp_path):
    class DeadProcess:
        def poll(self):
            return 1

    log = tmp_path / "ollama_server.log"

    def fake_popen(*args, **kwargs):
        log.write_text("Error: listen tcp 127.0.0.1:11434: bind: address already in use\n", encoding="utf-8")
        return DeadProcess()

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(ollama_utils.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(ollama_utils.time, "sleep", lambda seconds: None)
    with pytest.raises(ollama_utils.OllamaError, match="held by another program"):
        ollama_utils.start_server(log)
