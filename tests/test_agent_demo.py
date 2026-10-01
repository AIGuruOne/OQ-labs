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


def _plain_loop_body():
    source = (REPO_ROOT / "apps" / "oq_agent" / "agent.py").read_text(encoding="utf-8")
    return source.split("def run_plain")[1].split("def run_gated")[0]


def _without_narration(body):
    """Drop the run.steps.append(Step(...)) statements.

    Those exist so the page can say who did what; they are not the mechanism. What
    is left is the loop a person actually has to read to believe it.
    """
    kept, depth, dropping = [], 0, False
    for line in body.splitlines():
        if not dropping and "run.steps.append(" in line:
            dropping, depth = True, 0
        if dropping:
            depth += line.count("(") - line.count(")")
            dropping = depth > 0
            continue
        kept.append(line)
    return [l for l in kept if l.strip()]


def test_the_plain_loop_stays_readable():
    """A loop nobody can read teaches nothing.

    The step narration roughly doubled the line count when the page gained its
    person / program / model columns. Both numbers are capped: the mechanism,
    which is what goes on a slide, and the whole function, so narration cannot
    balloon either.

    The mechanism budget was 35 and went to 40 on 2026-10-01, when `obey` added
    its branch. These are budgets, not measurements - raise one deliberately and
    say so here, never to get a commit through.
    """
    body = _plain_loop_body()
    mechanism = _without_narration(body)
    assert len(mechanism) <= 40, f"the loop itself is now {len(mechanism)} lines"
    whole = [l for l in body.splitlines() if l.strip()]
    assert len(whole) <= 65, f"run_plain is now {len(whole)} lines in total"


# ---------------------------------------------------------------------------
# The claim the whole demo exists to make: the model never runs anything.
# These drive the real engines with a stubbed _chat, so no key and no network.
# ---------------------------------------------------------------------------

ASK_READS = {"tool_calls": [
    {"id": "c1", "function": {"name": "get_forecast",
                              "arguments": '{"city": "Harbor City", "date": "2026-10-10"}'}},
    {"id": "c2", "function": {"name": "check_calendar", "arguments": '{"date": "2026-10-10"}'}}]}
ASK_WRITE = {"tool_calls": [
    {"id": "c3", "function": {"name": "send_invite",
                              "arguments": '{"date": "2026-10-10", "place": "Harbor Park lawn",'
                                           ' "to": ["Sara", "Omar"]}'}}]}
PLAIN_ANSWER = {"content": "I sent the invite."}
GATED_VERDICT = {"content": '{"go": true, "why": "sunny and free"}'}


def canned(*replies):
    it = iter(replies)
    return lambda messages, with_tools=True: next(it)


def test_every_step_is_attributed_to_one_of_three_actors(monkeypatch):
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    assert {s.actor for s in run.steps} <= {agent.PERSON, agent.PROGRAM, agent.MODEL_ACTOR}
    assert run.steps[0].actor == agent.PERSON, "a person starts every run"


def test_the_model_never_runs_a_function(monkeypatch):
    """The sentence on the page. If this test ever fails, the page is lying."""
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    ran = [s for s in run.steps if s.ran]
    assert ran, "something should have run"
    assert all(s.actor == agent.PROGRAM for s in ran), "only the program runs functions"
    assert len(agent.SENT) == 1

    agent.SENT.clear()
    monkeypatch.setattr(agent, "_chat", canned(GATED_VERDICT))
    gated = agent.run_gated()
    agent.approve(gated)
    assert all(s.actor == agent.PROGRAM for s in gated.steps if s.ran)


def test_every_model_step_shows_the_text_it_returned(monkeypatch):
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    model_steps = [s for s in run.steps if s.actor == agent.MODEL_ACTOR]
    assert len(model_steps) == 3
    for step in model_steps:
        assert step.raw, "a model step must show the literal text, or the claim is unproven"
        assert not step.ran


def test_a_tool_call_is_two_steps_the_asking_and_the_running(monkeypatch):
    """Collapsing these into one line is what made the room think the model acts."""
    monkeypatch.setattr(agent, "_chat", canned(ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    asked = next(i for i, s in enumerate(run.steps)
                 if s.actor == agent.MODEL_ACTOR and "send_invite" in s.what)
    did = next(i for i, s in enumerate(run.steps) if s.ran and s.writes)
    assert asked < did, "the model asks first, the program runs after"


def test_declining_to_obey_runs_nothing_at_all(monkeypatch):
    """The proof that the program is in charge: same request, nothing happens."""
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain(obey=False)
    assert not any(s.ran for s in run.steps)
    assert agent.SENT == []
    assert any("does NOT run" in s.what for s in run.steps)


def test_every_crossing_shows_what_went_over_it(monkeypatch):
    """Both directions are visible, or the page only half-answers "who did what"."""
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    for step in run.steps:
        if step.crossing == "to-model":
            assert step.sent, f"step {step.what!r} crosses but shows no payload"
        if step.crossing == "from-model":
            assert step.raw, f"step {step.what!r} crosses but shows no reply"


def test_the_whole_conversation_is_resent_every_turn(monkeypatch):
    """The second misconception: that the model remembers. It does not.

    Each send must carry every message of the one before it, so the room can see
    the transcript growing rather than being told it does.
    """
    monkeypatch.setattr(agent, "_chat", canned(ASK_READS, ASK_WRITE, PLAIN_ANSWER))
    run = agent.run_plain()
    sends = [s.sent for s in run.steps if s.sent]
    assert len(sends) >= 2, "a multi-turn run should send more than once"

    counts = [int(text.split(" messages")[0]) for text in sends]
    assert counts == sorted(counts) and counts[-1] > counts[0], counts

    earlier = [l[4:] for l in sends[0].splitlines() if l.startswith(("NEW ", "    "))]
    later = [l[4:] for l in sends[-1].splitlines() if l.startswith(("NEW ", "    "))]
    for line in earlier:
        assert line in later, f"{line!r} was dropped from a later send"
    assert any(l.startswith("NEW ") for l in sends[-1].splitlines()), "nothing marked new"


def test_the_gated_question_offers_no_tools_at_all(monkeypatch):
    """The contrast that makes the gated engine's point in one glance."""
    monkeypatch.setattr(agent, "_chat", canned(GATED_VERDICT))
    run = agent.run_gated()
    asked = next(s for s in run.steps if s.crossing == "to-model")
    assert "no tools at all" in asked.sent
    assert "tool descriptions" not in asked.sent


def test_the_gated_engine_asks_the_model_exactly_once(monkeypatch):
    monkeypatch.setattr(agent, "_chat", canned(GATED_VERDICT))
    run = agent.run_gated()
    assert sum(1 for s in run.steps if s.actor == agent.MODEL_ACTOR) == 1
    assert run.waiting and agent.SENT == [], "nothing is sent before a person says yes"


def test_the_demo_needs_no_local_model():
    source = (REPO_ROOT / "apps" / "oq_agent" / "agent.py").read_text(encoding="utf-8")
    for banned in ("ollama", "localhost:11434", "torch", "transformers"):
        assert banned not in source.lower()


def test_the_readme_does_not_claim_the_plain_loop_spins():
    """Measured 2026-09-30: it does not. The README must not say otherwise."""
    readme = (REPO_ROOT / "apps" / "oq_agent" / "README.md").read_text(encoding="utf-8")
    assert "did NOT spin" in readme
    assert "behaved perfectly and you had no way to know it would" in readme
