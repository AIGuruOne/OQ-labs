"""The OQ Agent demo: the two engines, and the claims its README makes.

No model is called - the engines are exercised with the tool layer only, and the
model-facing paths are checked structurally.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from apps.oq_agent import agent  # noqa: E402


@pytest.fixture(autouse=True)
def clean_world():
    agent.SENT.clear()
    yield
    agent.SENT.clear()


def test_exactly_one_tool_changes_the_world():
    assert agent.WRITES == {"send_invite"}
    assert [t["name"] for t in agent.TOOLS] == ["get_forecast", "check_calendar", "send_invite"]


def test_the_read_tools_never_touch_the_world():
    agent.run_tool("get_forecast", {"city": "Harbor City", "date": "2026-10-10"})
    agent.run_tool("check_calendar", {"date": "2026-10-10"})
    assert agent.SENT == []


def test_a_broken_forecast_is_an_error_not_a_guess():
    out = agent.run_tool("get_forecast", {"city": "Harbor City", "date": "2026-10-10"}, broken=True)
    assert "error" in out and "condition" not in out


def test_the_gated_run_sends_nothing_until_a_person_says_yes():
    run = agent.run_gated.__wrapped__ if hasattr(agent.run_gated, "__wrapped__") else None
    # exercise the gate without a model call by driving approve/reject directly
    held = agent.Run(engine="gated")
    held.waiting = {"tool": "send_invite",
                    "args": {"date": "2026-10-10", "place": "Harbor Park lawn", "to": ["Sara"]}}
    assert agent.SENT == [], "nothing may be sent while a run is waiting"
    agent.approve(held)
    assert len(agent.SENT) == 1
    assert held.waiting is None


def test_reject_sends_nothing():
    held = agent.Run(engine="gated")
    held.waiting = {"tool": "send_invite", "args": {"date": "2026-10-10", "place": "x", "to": ["Sara"]}}
    agent.reject(held)
    assert agent.SENT == []
    assert held.waiting is None


def test_the_plain_loop_stays_readable():
    """The README calls it 26 lines. A loop nobody can read teaches nothing."""
    source = (REPO_ROOT / "apps" / "oq_agent" / "agent.py").read_text(encoding="utf-8")
    body = source.split("def run_plain")[1].split("def run_gated")[0]
    lines = [l for l in body.splitlines() if l.strip()]
    assert len(lines) <= 35, f"the plain loop has grown to {len(lines)} lines"


def test_the_demo_needs_no_local_model():
    source = (REPO_ROOT / "apps" / "oq_agent" / "agent.py").read_text(encoding="utf-8")
    for banned in ("ollama", "localhost:11434", "torch", "transformers"):
        assert banned not in source.lower()


def test_the_readme_does_not_claim_the_plain_loop_spins():
    """Measured 2026-09-30: it does not. The README must not say otherwise."""
    readme = (REPO_ROOT / "apps" / "oq_agent" / "README.md").read_text(encoding="utf-8")
    assert "did NOT spin" in readme
    assert "behaved perfectly and you had no way to know it would" in readme
