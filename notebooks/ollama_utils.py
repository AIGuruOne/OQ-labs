"""Get an Ollama server answering, in Colab or on a laptop.

Import after the environment-detection cell has run:

    import ollama_utils

    server = ollama_utils.ensure_server(IN_COLAB, CHECKPOINT_DIR)
    ollama_utils.ensure_model("llama3.2:1b")

What is here - each step is something you could do by hand in a terminal:

    install_on_linux    Colab only: download ONE pinned release and unpack it
    gpu_name            which GPU Ollama will find, if any
    start_server        `ollama serve` in the background, then wait until it answers
    ensure_model        `ollama pull <name>`, skipped when the model is already there
    warm_up             load the model with one tiny request; report seconds and the GPU share

The server address is OLLAMA_BASE_URL (default http://localhost:11434) -
the same variable config/endpoints.py reads, so the notebook, the eval
harness and the `ollama` command line all talk to the same server.

Uses `requests` and the standard library only.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

# The exact Ollama release Colab installs. It is the release every
# reference score in this repo was measured on (docs/timing_log.md,
# checkpoints/adapter_prebaked/README.md) - and the only tested release
# that can still turn a LoRA adapter into a model: 0.33.3 fails to
# import one, 0.34.2 says "LoRA adapters are no longer supported".
# Pinned like any other dependency: never "latest".
OLLAMA_VERSION = "0.12.10"
OLLAMA_LINUX_URL = f"https://ollama.com/download/ollama-linux-amd64.tgz?version={OLLAMA_VERSION}"
LINUX_INSTALL_DIR = "/usr/local"

# Tickets plus the system prompt are under 1,000 tokens. A small fixed
# context keeps memory low whatever the machine's default is
# (docs/failure_playbook.md entry 2).
CONTEXT_LENGTH = 4096

DEFAULT_BASE_URL = "http://localhost:11434"
SERVER_START_TIMEOUT_SECONDS = 60


class OllamaError(RuntimeError):
    """Ollama cannot be used. The message says what to check."""


def server_url():
    """Where the Ollama server is (no trailing slash, no /v1)."""
    return os.environ.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def server_version(base_url=None):
    """The running server's version, or None if nothing answers."""
    base_url = base_url or server_url()
    try:
        response = requests.get(f"{base_url}/api/version", timeout=3)
        return response.json().get("version")
    except (requests.exceptions.RequestException, ValueError):
        return None


def point_command_line_at_server(base_url):
    """The `ollama` command line reads OLLAMA_HOST, not OLLAMA_BASE_URL.
    Set it, so `ollama create` reaches the same server the notebook uses."""
    parsed = urlparse(base_url)
    os.environ["OLLAMA_HOST"] = f"{parsed.hostname}:{parsed.port or 11434}"
    return os.environ["OLLAMA_HOST"]


def install_on_linux():
    """Colab: download the pinned release and unpack it under /usr/local.

    This is what Ollama's own install script does, minus the parts a
    Colab runtime does not need (a systemd service, GPU driver setup).
    About 1.9 GB - the archive carries its own GPU libraries.
    """
    if not sys.platform.startswith("linux"):
        raise OllamaError("install_on_linux is for Colab. On a laptop install Ollama once, "
                          "by hand: setup/ollama_setup.md.")
    print(f"Downloading Ollama {OLLAMA_VERSION} (about 1.9 GB, usually under a minute in Colab) ...")
    started = time.time()
    pipeline = f"set -o pipefail; curl -fsSL '{OLLAMA_LINUX_URL}' | tar -xzf - -C {LINUX_INSTALL_DIR}"
    completed = subprocess.run(["bash", "-c", pipeline], capture_output=True, text=True)
    if completed.returncode != 0 or shutil.which("ollama") is None:
        last_lines = (completed.stderr or completed.stdout).strip().splitlines()[-3:]
        raise OllamaError("Ollama did not install: " + " | ".join(last_lines)
                          + f"\n  Tried: {OLLAMA_LINUX_URL}\n  Is the network blocking ollama.com?")
    print(f"Installed to {shutil.which('ollama')} in {time.time() - started:.0f} s")


def start_server(log_path):
    """Run `ollama serve` in the background and wait until it answers.
    Its log goes to log_path - the first place to look when a model will not load."""
    base_url = server_url()
    environment = dict(os.environ)
    environment["OLLAMA_CONTEXT_LENGTH"] = str(CONTEXT_LENGTH)

    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")

    options = {}
    if os.name == "posix":
        # Its own session: interrupting a notebook cell must not stop the server.
        options["start_new_session"] = True
    process = subprocess.Popen(["ollama", "serve"], stdout=log_file, stderr=subprocess.STDOUT,
                               env=environment, **options)

    deadline = time.time() + SERVER_START_TIMEOUT_SECONDS
    while time.time() < deadline:
        version = server_version(base_url)
        if version is not None:
            return version
        if process.poll() is not None:
            # It died at once. The log's last line says why - usually the port.
            raise OllamaError(explain_server_exit(base_url, log_path))
        time.sleep(1)
    raise OllamaError(f"`ollama serve` was started but {base_url} did not answer within "
                      f"{SERVER_START_TIMEOUT_SECONDS} s. Read the log: {log_path}")


def last_log_line(log_path):
    """The last non-empty line of a log file, or '' if there is none."""
    try:
        lines = [line for line in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.strip()]
    except OSError:
        return ""
    return lines[-1].strip() if lines else ""


def explain_server_exit(base_url, log_path):
    """Turn the last log line of a dead `ollama serve` into a sentence that says what to do.

    The one seen in the wild is the port: another program (usually the Ollama
    desktop app, or a stale `ollama serve`) already holds it. If that program
    were an Ollama server we would have talked to it instead of starting one -
    so whatever holds the port is NOT an Ollama server, or is one that is not
    answering.
    """
    reason = last_log_line(log_path)
    port = urlparse(base_url).port or 11434
    message = f"`ollama serve` stopped at once. Its last log line: {reason or '(empty log)'}"
    if "address already in use" in reason.lower() or "only one usage of each socket address" in reason.lower():
        message += (f"\n  Port {port} is held by another program that is not answering as Ollama."
                    f"\n  Either stop that program, or serve on a free port: set"
                    f"\n  OLLAMA_BASE_URL=http://localhost:{port + 1} in .env (or os.environ) and run this cell again."
                    f"\n  (`OLLAMA_HOST=127.0.0.1:{port + 1} ollama serve` is the same thing by hand.)")
    else:
        message += f"\n  Full log: {log_path}"
    return message


def ensure_server(in_colab, log_dir):
    """Make sure an Ollama server answers. Returns what it found:

        {"url", "version", "started_here", "installed_here"}

    Already running -> used as it is. Not running -> started. Not
    installed -> installed first on Colab; on a laptop that is a
    one-time manual step, so the error says where the guide is.
    """
    base_url = server_url()
    point_command_line_at_server(base_url)
    found = {"url": base_url, "version": server_version(base_url),
             "started_here": False, "installed_here": False}

    if found["version"] is None:
        if shutil.which("ollama") is None:
            if not in_colab:
                raise OllamaError("Ollama is not installed on this machine. "
                                  "Install it once: setup/ollama_setup.md - then run this cell again.")
            install_on_linux()
            found["installed_here"] = True
        found["version"] = start_server(Path(log_dir) / "ollama_server.log")
        found["started_here"] = True

    if found["version"] != OLLAMA_VERSION:
        print(f"NOTE: this server is Ollama {found['version']}; the labs are built and measured on {OLLAMA_VERSION}.")
        print("      Plain models still answer, but a fine-tuned adapter may not load: releases from 0.33 on")
        print("      fail to import one, and 0.34 refuses outright. The tuned endpoint is supported on Colab only.")
    return found


def gpu_name():
    """The NVIDIA GPU in this machine, e.g. 'Tesla T4', or None (asks nvidia-smi).
    With a GPU a 1B model answers a ticket in about a second; without one, many seconds."""
    if shutil.which("nvidia-smi") is None:
        return None
    completed = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                               capture_output=True, text=True)
    names = completed.stdout.strip().splitlines()
    if completed.returncode != 0 or names == []:
        return None
    return names[0].strip()


def list_models(base_url=None):
    """Names of the models this server already has, e.g. ['llama3.2:1b']."""
    base_url = base_url or server_url()
    response = requests.get(f"{base_url}/api/tags", timeout=10)
    response.raise_for_status()
    return sorted(model["name"] for model in response.json().get("models", []))


def ensure_model(model_name, base_url=None):
    """Pull model_name unless the server already has it. Returns
    "already there" or "pulled". Prints progress: no silent minutes."""
    base_url = base_url or server_url()
    if model_name in list_models(base_url):
        return "already there"

    print(f"Pulling {model_name} ...")
    started = time.time()
    last_shown = -1
    request_body = {"model": model_name, "stream": True}
    with requests.post(f"{base_url}/api/pull", json=request_body, stream=True, timeout=(10, 600)) as response:
        if response.status_code != 200:
            raise OllamaError(f"Pull of {model_name} failed: HTTP {response.status_code} {response.text[:300]}")
        for line in response.iter_lines():
            if not line:
                continue
            update = json.loads(line)
            if "error" in update:
                raise OllamaError(f"Pull of {model_name} failed: {update['error']}")
            if update.get("total"):
                percent = int(100 * update.get("completed", 0) / update["total"])
                tenth = percent // 10
                if tenth > last_shown and update["total"] > 50_000_000:
                    last_shown = tenth
                    print(f"  {percent:>3}% of {update['total'] / 1e9:.1f} GB")

    if model_name not in list_models(base_url):
        raise OllamaError(f"The pull of {model_name} ended, but the server does not list the model.")
    print(f"Pulled {model_name} in {time.time() - started:.0f} s")
    return "pulled"


def warm_up(model_name, base_url=None):
    """Load model_name into memory with one tiny request, so the first
    real ticket does not pay for the load. Returns:

        {"seconds": how long load + reply took, "gpu_share": 0.0 to 1.0,
         "context_length": the context the server gave the model}

    gpu_share is the server's own report of how much of the model sits
    in GPU memory (any GPU Ollama supports, not only NVIDIA). 0.0 = all CPU.
    context_length comes from /api/ps too: OLLAMA_CONTEXT_LENGTH on a server
    this helper started, the app's setting on a desktop app, None if unknown.
    """
    base_url = base_url or server_url()
    started = time.time()
    request_body = {"model": model_name, "prompt": "Reply with the word: ready", "stream": False,
                    "options": {"num_predict": 4, "temperature": 0}}
    try:
        response = requests.post(f"{base_url}/api/generate", json=request_body, timeout=600)
    except requests.exceptions.RequestException as error:
        raise OllamaError(f"{model_name} did not answer its warm-up request: {error}")
    if response.status_code != 200:
        raise OllamaError(f"{model_name} could not be loaded: HTTP {response.status_code} {response.text[:300]}")
    seconds = round(time.time() - started, 1)

    gpu_share = 0.0
    context_length = None
    running = requests.get(f"{base_url}/api/ps", timeout=10).json().get("models", [])
    for model in running:
        if model.get("name", "").split(":latest")[0] == model_name.split(":latest")[0] and model.get("size"):
            gpu_share = round(model.get("size_vram", 0) / model["size"], 2)
            # The context the SERVER gave this model (OLLAMA_CONTEXT_LENGTH or the
            # desktop app's setting) - not the model's own maximum.
            context_length = model.get("context_length")
    return {"seconds": seconds, "gpu_share": gpu_share, "context_length": context_length}
