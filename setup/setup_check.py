"""Environment check for the OQ Advanced AI for IT labs.

Run it from the repo root:

    python setup/setup_check.py
    python setup/setup_check.py --network   # also: can this network reach
                                            # every host the week needs?

It prints a pass/fail table and exits non-zero if anything needs
fixing. Every row tells you what to do about a failure. Send the
output to the facilitator if you are stuck.

Uses ONLY the Python standard library on purpose: you can (and
should) run it BEFORE installing anything, on a fresh machine or a
fresh Colab runtime. One of its jobs is to tell you whether installs
will work at all.

Statuses:
    PASS  - ready
    WARN  - not blocking, but read the note
    FAIL  - must be fixed before Day 1
    INFO  - reported for the facilitator, never a failure
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Network checks get a short timeout so the whole script stays fast.
TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Small helpers (stdlib only)
# ---------------------------------------------------------------------------


def load_dotenv() -> None:
    """Load KEY=value lines from the repo-root .env into os.environ.

    Real environment variables win over the file.
    """
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def http_get(url: str, headers: dict = None):
    """GET a URL. Returns (status_code, body_text) or (None, error_text)."""
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")
    except Exception as err:  # noqa: BLE001 - report, never crash
        return None, f"{type(err).__name__}: {err}"


def in_colab() -> bool:
    return "google.colab" in sys.modules or Path("/content").exists()


# ---------------------------------------------------------------------------
# Checks. Each returns (status, detail).
# ---------------------------------------------------------------------------


def check_python_version():
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if (3, 10) <= sys.version_info[:2] <= (3, 12):
        return "PASS", f"Python {version}"
    if sys.version_info[:2] >= (3, 14):
        # Measured 2026-09-22: numpy==2.1.3 (Colab's version, pinned in
        # requirements.txt) has no wheel for 3.14, so pip tries to compile
        # it and stops with "Unknown compiler(s)" on a normal laptop.
        return "FAIL", (
            f"Python {version}: requirements.txt will NOT install on it "
            "(numpy 2.1.3 has no build for this version, so pip tries to "
            "compile it and fails). Install Python 3.12 or 3.11 and make "
            "the venv with that one. docs/failure_playbook.md entry 8."
        )
    if sys.version_info[:2] == (3, 13):
        return "WARN", (
            f"Python {version} — labs are tested on 3.10-3.12; the Day 2 "
            "fine-tuning packages may not install on this version. "
            "Install Python 3.11 or 3.12 for local work."
        )
    return "FAIL", (
        f"Python {version} is too old. Install Python 3.11 or 3.12."
    )


def check_pip():
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS * 3,
        )
    except Exception as err:  # noqa: BLE001
        return "FAIL", f"Could not run pip: {err}"
    if result.returncode != 0:
        return "FAIL", (
            "pip is broken: " + (result.stderr or result.stdout).strip()[:200]
        )
    return "PASS", result.stdout.strip()


def check_pypi_reachable():
    status, body = http_get("https://pypi.org/simple/")
    if status == 200:
        return "PASS", "pypi.org reachable — installs will work"
    return "FAIL", (
        f"Cannot reach pypi.org ({body if status is None else 'HTTP ' + str(status)}). "
        "pip installs will fail. Check network / proxy, or try a phone hotspot."
    )


def check_api_key():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        hint = (
            "Copy setup/.env.example to .env in the repo root and fill in "
            "OPENAI_API_KEY."
        )
        # The single most common way this goes wrong: the variable exists
        # but under a misspelled name.
        for near_miss in ("OPEN_API_KEY", "OPENAI_KEY", "OPEN_AI_API_KEY"):
            if os.environ.get(near_miss):
                hint = (
                    f"Found {near_miss} — the labs need it named exactly "
                    "OPENAI_API_KEY. Rename it in your .env."
                )
                break
        return "FAIL", "OPENAI_API_KEY not set. " + hint

    base_url = os.environ.get(
        "HOSTED_BASE_URL", "https://api.openai.com/v1"
    ).rstrip("/")
    status, body = http_get(
        f"{base_url}/models", headers={"Authorization": f"Bearer {key}"}
    )
    if status == 200:
        return "PASS", f"Key present and a live call to {base_url} succeeded"
    if status == 401:
        return "FAIL", (
            "OPENAI_API_KEY is set but the API rejected it (HTTP 401). "
            "The key is wrong, expired, or for a different service."
        )
    if status is None:
        return "FAIL", (
            f"Key is set but {base_url} is unreachable: {body}. "
            "Check network / proxy."
        )
    return "FAIL", f"Key is set but {base_url} answered HTTP {status}."


def check_ollama():
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    status, body = http_get(f"{base}/api/version")
    if status == 200:
        try:
            version = json.loads(body).get("version", "unknown")
        except json.JSONDecodeError:
            version = "unknown"
        return "PASS", f"Ollama {version} responding at {base}"
    return "WARN", (
        f"Ollama not reachable at {base}. Fine before Day 2 — the labs "
        "install it inside Colab. For the local path see setup/ollama_setup.md."
    )


def check_drive():
    if not in_colab():
        return "INFO", "Not running in Colab — Drive check not applicable"
    try:
        import google.colab  # noqa: F401
    except ImportError:
        return "FAIL", (
            "Looks like Colab but the google.colab module is missing — "
            "use a standard Colab runtime."
        )
    if Path("/content/drive/MyDrive").exists():
        return "PASS", "Google Drive is mounted"
    return "PASS", (
        "Drive is mountable (not yet mounted — the notebooks mount it "
        "in their first cell)"
    )


def check_disk_space():
    usage = shutil.disk_usage(REPO_ROOT)
    free_gb = usage.free / (1024**3)
    if free_gb >= 10:
        return "PASS", f"{free_gb:.1f} GB free"
    if free_gb >= 5:
        return "WARN", (
            f"Only {free_gb:.1f} GB free. Model files need several GB — "
            "free up space before Day 2."
        )
    return "FAIL", (
        f"Only {free_gb:.1f} GB free. Not enough for model files — "
        "free at least 10 GB."
    )


def check_gpu():
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
            if result.returncode == 0 and result.stdout.strip():
                return "INFO", f"GPU present: {result.stdout.strip()}"
        except Exception:  # noqa: BLE001
            pass
    return "INFO", (
        "No NVIDIA GPU detected. Fine — GPU labs run on Colab's free T4."
    )


# ---------------------------------------------------------------------------
# --network: can THIS network reach every host the week needs?
# ---------------------------------------------------------------------------

# One row per host: (url, the HTTP status it answers with on an open network,
# what stops working without it). The statuses were measured 2026-09-22.
# A corporate proxy that blocks a host usually answers with its own page
# (403, 407, or a 200/302 to a "blocked" page) or not at all - both show here
# as FAIL. Python's view is not the browser's: a proxy can treat them
# differently, so the Colab rows are a first signal, and the browser test in
# docs/failure_playbook.md Part 2 is the real one.
NETWORK_HOSTS = [
    ("https://colab.research.google.com/", 200, "Colab itself - every lab in the browser"),
    ("https://accounts.google.com/ServiceLogin", 200, "Google sign-in - Colab and Drive"),
    ("https://drive.google.com/", 200, "Drive - checkpoints that survive a disconnect"),
    ("https://www.gstatic.com/generate_204", 204, "Google static files - the Colab page"),
    ("https://github.com/Utkarsh-09/AI_GURU_labs", 200, "the lab repo - Open in Colab links, git clone"),
    ("https://pypi.org/simple/requests/", 200, "pip index - installs on a laptop"),
    ("https://files.pythonhosted.org/packages/7c/e4/56027c4a6b4ae70ca9de302488c5ca95ad4a39e190093d6c1a8ace08341b/requests-2.32.4-py3-none-any.whl",
     200, "pip downloads - installs on a laptop"),
    ("https://api.openai.com/v1/models", 401, "hosted model API (401 = reachable, no key sent)"),
    ("https://ollama.com/", 200, "Ollama download - installing it on a laptop"),
    ("https://registry.ollama.ai/v2/library/llama3.2/manifests/1b", 200, "Ollama model pulls on a laptop"),
    ("https://huggingface.co/api/models/unsloth/Llama-3.2-1B-Instruct", 200, "model download for fine-tuning"),
]


def check_host(url, expected_status):
    status, body = http_get(url)
    if status == expected_status:
        return "PASS", f"HTTP {status}"
    if status is None:
        return "FAIL", f"no answer: {body[:90]}"
    return "FAIL", f"HTTP {status}, expected {expected_status} - blocked, or a proxy's own page"


def network_rows():
    rows = []
    for url, expected_status, needed_for in NETWORK_HOSTS:
        host = url.split("/")[2]
        status, detail = check_host(url, expected_status)
        rows.append((host, status, f"{detail}. Needed for: {needed_for}"))
    return rows


# ---------------------------------------------------------------------------
# Run everything and print the table
# ---------------------------------------------------------------------------

CHECKS = [
    ("Python version", check_python_version),
    ("pip available", check_pip),
    ("PyPI reachable", check_pypi_reachable),
    ("API key + live call", check_api_key),
    ("Ollama reachable", check_ollama),
    ("Google Drive", check_drive),
    ("Disk space", check_disk_space),
    ("GPU", check_gpu),
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Environment check for the OQ labs.")
    parser.add_argument("--network", action="store_true",
                        help="also test whether this network reaches every host the week needs "
                             "(run it on the OQ network before Day 1)")
    args = parser.parse_args(argv)

    load_dotenv()

    where = "Colab" if in_colab() else "local machine"
    print(f"\nOQ Advanced AI — environment check ({where})")
    print("=" * 78)

    rows = []
    for label, check in CHECKS:
        try:
            status, detail = check()
        except Exception as err:  # noqa: BLE001 - a check must never crash the script
            status, detail = "FAIL", f"Check crashed: {type(err).__name__}: {err}"
        rows.append((label, status, detail))

    if args.network:
        rows.extend(network_rows())

    width = max(len(label) for label, _, _ in rows)
    for label, status, detail in rows:
        print(f"{label:<{width}} [{status:^4}] {detail}")

    failures = [label for label, status, _ in rows if status == "FAIL"]
    warnings = [label for label, status, _ in rows if status == "WARN"]

    print("=" * 78)
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED: {', '.join(failures)}")
        print("Fix the FAIL rows above, then run this script again.")
    elif warnings:
        print("RESULT: ready, with warnings — read the WARN rows above.")
    else:
        print("RESULT: all checks passed. You are ready.")
    print()

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
