"""Start the mock ERP in the background, wait until it answers, stop it.

For a notebook (Colab or local) and for the tests. On a laptop you can
equally run `uvicorn services.mock_erp.main:app --reload` in a terminal.

    from services.mock_erp.launch import start_in_background, stop
    erp = start_in_background(port=8000, log_path=CHECKPOINT_DIR / "mock_erp.log")
    print(erp.base_url, erp.health["counts"])
    ...
    stop(erp)

A notebook cell cannot run uvicorn in the foreground: the cell would
never finish. So the server runs as a child process, its output goes
to a log file, and this module polls GET /health until it answers.
Stdlib only, so it works before anything is installed.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class RunningErp:
    base_url: str               # http://127.0.0.1:8000
    health: dict                # the GET /health reply when it came up
    process: object = None      # subprocess.Popen, or None if we reused a running ERP
    log_path: Path = None       # where the server's output goes


def probe(base_url, timeout=2.0):
    """What answers at base_url? Returns ("mock-erp", health), ("other", None)
    or ("nothing", None)."""
    try:
        with urllib.request.urlopen(f"{base_url}/health", timeout=timeout) as reply:
            body = json.loads(reply.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return "other", None                    # something answered, with an error
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return "nothing", None
    except ValueError:
        return "other", None                    # it answered, but not with JSON
    if isinstance(body, dict) and body.get("service") == "mock-erp":
        return "mock-erp", body
    return "other", None


def last_lines(path, count=8):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no log)"
    return "\n".join(lines[-count:]) or "(log is empty)"


def start_in_background(port=8000, host="127.0.0.1", log_path=None, api_key=None,
                        wait_seconds=30):
    """Start the mock ERP and return once GET /health answers.

    If a mock ERP already answers on that port (a cell run twice, a kernel
    restarted while the server lived on), it is reused and nothing new is
    started: the reply says how many work orders it has already raised.

    api_key  None = whatever MOCK_ERP_API_KEY says (usually nothing);
             "" = force no key; "abc" = require X-API-Key: abc.
    """
    base_url = f"http://{host}:{port}"
    what, health = probe(base_url)
    if what == "mock-erp":
        print(f"A mock ERP is already running at {base_url} (started {health['started']}, "
              f"{health['work_orders_raised_since_start']} work orders raised since). Reusing it. "
              f"Restart the runtime for a clean ERP.")
        return RunningErp(base_url=base_url, health=health)
    if what == "other":
        raise RuntimeError(f"Port {port} is in use by something that is not the mock ERP. "
                           f"Pass another port, e.g. start_in_background(port={port + 1}).")

    if log_path is None:
        log_path = Path(tempfile.gettempdir()) / f"mock_erp_{port}.log"
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    if api_key is not None:
        env["MOCK_ERP_API_KEY"] = api_key
    command = [sys.executable, "-m", "uvicorn", "services.mock_erp.main:app",
               "--host", host, "--port", str(port)]
    log_file = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=REPO_ROOT, env=env,
                               stdout=log_file, stderr=subprocess.STDOUT)
    log_file.close()                            # the child keeps its own handle

    started = time.monotonic()
    while time.monotonic() - started < wait_seconds:
        if process.poll() is not None:
            raise RuntimeError(f"The mock ERP stopped at once (exit code {process.returncode}). "
                               f"Last lines of {log_path}:\n{last_lines(log_path)}")
        what, health = probe(base_url, timeout=1.0)
        if what == "mock-erp":
            seconds = time.monotonic() - started
            print(f"Mock ERP up at {base_url} in {seconds:.1f} s (pid {process.pid}). "
                  f"Docs: {base_url}/docs")
            print(f"Server log: {log_path}")
            return RunningErp(base_url=base_url, health=health, process=process, log_path=log_path)
        time.sleep(0.25)

    process.terminate()
    raise RuntimeError(f"The mock ERP did not answer within {wait_seconds} s. "
                       f"Last lines of {log_path}:\n{last_lines(log_path)}")


def stop(erp):
    """Stop a server this module started. A reused one is left alone."""
    if erp.process is None:
        print(f"Not stopping {erp.base_url}: this session did not start it.")
        return
    erp.process.terminate()
    try:
        erp.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        erp.process.kill()
        erp.process.wait(timeout=10)
    print(f"Mock ERP at {erp.base_url} stopped (pid {erp.process.pid}).")
