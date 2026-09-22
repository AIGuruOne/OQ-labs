"""Tests for setup/setup_check.py - only the rules that decide PASS / WARN / FAIL
without touching the network."""

import collections
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("setup_check", REPO_ROOT / "setup" / "setup_check.py")
setup_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_check)

VersionInfo = collections.namedtuple("VersionInfo", "major minor micro releaselevel serial")


def status_for(monkeypatch, minor):
    monkeypatch.setattr(sys, "version_info", VersionInfo(3, minor, 0, "final", 0))
    return setup_check.check_python_version()


def test_supported_versions_pass(monkeypatch):
    for minor in (11, 12):
        status, _ = status_for(monkeypatch, minor)
        assert status == "PASS"


def test_python_3_13_is_a_warning_because_the_base_stack_still_installs(monkeypatch):
    # Every pin in requirements.txt has a Windows wheel for 3.13 (checked with
    # pip download --only-binary=:all: on 2026-09-22), and Colab's default is 3.13.
    status, _ = status_for(monkeypatch, 13)
    assert status == "WARN"


def test_python_3_14_fails_and_says_why(monkeypatch):
    # Reproduced 2026-09-22: numpy==2.1.3 has no 3.14 wheel; pip tries to compile
    # it and stops with "Unknown compiler(s)". A WARN here let people carry on
    # into a failed install on Day 1.
    status, detail = status_for(monkeypatch, 14)
    assert status == "FAIL"
    assert "numpy" in detail and "3.12" in detail and "failure_playbook" in detail


def test_old_python_fails(monkeypatch):
    status, _ = status_for(monkeypatch, 9)
    assert status == "FAIL"


# ---------------------------------------------------------------------------
# --network (no real network: http_get is replaced)
# ---------------------------------------------------------------------------


def test_a_host_passes_only_on_the_status_it_gives_on_an_open_network(monkeypatch):
    monkeypatch.setattr(setup_check, "http_get", lambda url, headers=None: (401, ""))
    assert setup_check.check_host("https://api.openai.com/v1/models", 401)[0] == "PASS"
    # A proxy's own "blocked" page is an answer too - it must not pass.
    monkeypatch.setattr(setup_check, "http_get", lambda url, headers=None: (403, "<html>blocked</html>"))
    status, detail = setup_check.check_host("https://colab.research.google.com/", 200)
    assert status == "FAIL" and "403" in detail


def test_no_answer_is_a_failure_with_the_reason(monkeypatch):
    reason = "URLError: <urlopen error Tunnel connection failed: 403 Forbidden>"
    monkeypatch.setattr(setup_check, "http_get", lambda url, headers=None: (None, reason))
    status, detail = setup_check.check_host("https://pypi.org/simple/requests/", 200)
    assert status == "FAIL" and "Tunnel connection failed" in detail


def test_every_network_row_says_what_breaks_without_it(monkeypatch):
    monkeypatch.setattr(setup_check, "http_get", lambda url, headers=None: (None, "down"))
    rows = setup_check.network_rows()
    assert len(rows) == len(setup_check.NETWORK_HOSTS)
    for host, status, detail in rows:
        assert "." in host and status == "FAIL" and "Needed for:" in detail


def test_the_default_run_does_not_probe_the_network(monkeypatch, capsys):
    called = []
    monkeypatch.setattr(setup_check, "network_rows", lambda: called.append(1) or [])
    monkeypatch.setattr(setup_check, "CHECKS", [("Python version", lambda: ("PASS", "x"))])
    assert setup_check.main([]) == 0
    assert called == []
    assert setup_check.main(["--network"]) == 0
    assert called == [1]
