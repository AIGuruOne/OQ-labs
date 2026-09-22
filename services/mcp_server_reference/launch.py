"""Run the MCP server: in the foreground (a terminal) or in the background
(a notebook, Colab, the tests).

    # terminal - what server.py and every step file call at the bottom
    serve(mcp, port=8100)

    # notebook / tests
    from services.mcp_server_reference.launch import start_in_background, stop
    server = start_in_background(port=8100, enable_writes=True)
    print(server.url, server.info["tools"])     # http://127.0.0.1:8100/mcp [...]
    ...
    stop(server)

Transport: Streamable HTTP, MCP 2026-07-28 (one POST per request, no
session, JSON replies). The same endpoint also answers 2025-era clients
that still send `initialize`: the SDK serves both eras on one URL.
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
DEFAULT_PORT = 8100


def serve(mcp, host="127.0.0.1", port=DEFAULT_PORT, transport="http"):
    """Serve `mcp` until Ctrl+C. Bound to 127.0.0.1 on purpose: the spec says a
    local server SHOULD NOT listen on every interface."""
    if transport == "stdio":
        mcp.run("stdio")        # for hosts that launch the server themselves
        return

    import uvicorn

    app = mcp.streamable_http_app(json_response=True, host=host)
    print(f"MCP server '{mcp.name}' {mcp.version} at http://{host}:{port}/mcp  (Ctrl+C stops it)",
          flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def run_from_command_line(build_server, description="oq-erp-mcp"):
    """The bottom of server.py and of every step file: read the standard
    flags, build the server, serve it.

        --host 127.0.0.1  --port 8100  --enable-writes  --audit-log PATH  --transport http|stdio

    A step file whose build_server() does not take enable_writes or
    audit_log_path yet (the early steps) simply does not get them.
    """
    import argparse
    import inspect

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--enable-writes", action="store_true",
                        help="register the write tool (still gated by an approval)")
    parser.add_argument("--audit-log", type=Path, default=None,
                        help="JSON Lines audit file, appended")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    args = parser.parse_args()

    accepted = inspect.signature(build_server).parameters
    options = {}
    if "enable_writes" in accepted:
        options["enable_writes"] = args.enable_writes
    elif args.enable_writes:
        parser.error("this version of the server has no write tool yet")
    if "audit_log_path" in accepted and args.audit_log is not None:
        options["audit_log_path"] = args.audit_log

    from services.mcp_server_reference.erp_client import base_url

    mcp = build_server(**options)
    if args.transport == "http":
        mode = "WRITES ENABLED (each needs an approval)" if args.enable_writes else "READ-ONLY"
        print(f"{mode}. ERP: {base_url()}", flush=True)
    serve(mcp, host=args.host, port=args.port, transport=args.transport)


@dataclass
class RunningServer:
    url: str                    # http://127.0.0.1:8100/mcp
    info: dict                  # version, tools, writes_enabled - from server/discover + tools/list
    process: object = None      # subprocess.Popen, or None if we reused one
    log_path: Path = None


def mcp_post(url, method, timeout):
    """One MCP 2026-07-28 request with the standard library (so it works before
    anything is installed). Returns the result object."""
    meta = {"io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "oq-launcher", "version": "1"},
            "io.modelcontextprotocol/clientCapabilities": {}}
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": {"_meta": meta}}).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": method})
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read().decode("utf-8"))["result"]


def probe(base_url, timeout=2.0):
    """What answers at base_url/mcp? Asks server/discover, the one call every
    2026-07-28 server must answer.
    Returns ("oq-erp-mcp", info), ("other", None) or ("nothing", None)."""
    url = f"{base_url}/mcp"
    try:
        discovered = mcp_post(url, "server/discover", timeout)
        tools = mcp_post(url, "tools/list", timeout)["tools"]
    except urllib.error.HTTPError:
        return "other", None
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
        return "nothing", None
    except (ValueError, KeyError, TypeError):
        return "other", None
    server_info = (discovered.get("_meta") or {}).get("io.modelcontextprotocol/serverInfo", {})
    if server_info.get("name") != "oq-erp-mcp":
        return "other", None
    tool_names = [tool["name"] for tool in tools]
    return "oq-erp-mcp", {"version": server_info.get("version"), "tools": tool_names,
                          "writes_enabled": "raise_work_order" in tool_names}


def last_lines(path, count=10):
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no log)"
    return "\n".join(lines[-count:]) or "(log is empty)"


def start_in_background(port=DEFAULT_PORT, host="127.0.0.1", enable_writes=False,
                        audit_log=None, module="services.mcp_server_reference.server",
                        env=None, log_path=None, wait_seconds=30):
    """Start the MCP server as a child process; return once it answers server/discover.

    A server already answering on the port is reused only if its
    read-only / writes setting is the one asked for; otherwise this stops
    with a sentence (two different servers on one port is a lab accident).
    """
    base_url = f"http://{host}:{port}"
    what, info = probe(base_url)
    if what == "oq-erp-mcp":
        if info["writes_enabled"] != enable_writes:
            raise RuntimeError(f"An oq-erp-mcp server on port {port} has writes_enabled="
                               f"{info['writes_enabled']}; you asked for {enable_writes}. "
                               f"Stop it, or use another port.")
        print(f"An oq-erp-mcp server is already running at {base_url}/mcp. Reusing it.")
        return RunningServer(url=f"{base_url}/mcp", info=info)
    if what == "other":
        raise RuntimeError(f"Port {port} is in use by something that is not oq-erp-mcp. "
                           f"Pass another port, e.g. start_in_background(port={port + 1}).")

    if log_path is None:
        log_path = Path(tempfile.gettempdir()) / f"oq_erp_mcp_{port}.log"
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = [sys.executable, "-m", module, "--host", host, "--port", str(port)]
    if enable_writes:
        command.append("--enable-writes")
    if audit_log is not None:
        command += ["--audit-log", str(audit_log)]
    child_env = dict(os.environ)
    child_env.update(env or {})
    log_file = open(log_path, "w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=REPO_ROOT, env=child_env,
                               stdout=log_file, stderr=subprocess.STDOUT)
    log_file.close()

    started = time.monotonic()
    while time.monotonic() - started < wait_seconds:
        if process.poll() is not None:
            raise RuntimeError(f"The MCP server stopped at once (exit code {process.returncode}). "
                               f"Last lines of {log_path}:\n{last_lines(log_path)}")
        what, info = probe(base_url, timeout=1.0)
        if what == "oq-erp-mcp":
            seconds = time.monotonic() - started
            mode = "writes ENABLED (gated)" if enable_writes else "read-only"
            print(f"MCP server up at {base_url}/mcp in {seconds:.1f} s, {mode} (pid {process.pid}).")
            return RunningServer(url=f"{base_url}/mcp", info=info, process=process,
                                 log_path=log_path)
        time.sleep(0.25)

    process.terminate()
    raise RuntimeError(f"The MCP server did not answer within {wait_seconds} s. "
                       f"Last lines of {log_path}:\n{last_lines(log_path)}")


def stop(server):
    """Stop a server this module started. A reused one is left alone."""
    if server.process is None:
        print(f"Not stopping {server.url}: this session did not start it.")
        return
    server.process.terminate()
    try:
        server.process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.process.kill()
        server.process.wait(timeout=10)
    print(f"MCP server at {server.url} stopped (pid {server.process.pid}).")
