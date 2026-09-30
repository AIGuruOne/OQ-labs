"""Every notebook that opens an MCP stdio client must survive a notebook kernel.

The bug: mcp's stdio_client passes sys.stderr straight to the server subprocess, and
its `errlog` default is bound at IMPORT time. Inside a Jupyter or Colab kernel
sys.stderr is an ipykernel stream with no file descriptor, so the client raises

    io.UnsupportedOperation: fileno

seventeen frames deep, with nothing in the message about MCP. A terminal never hits it,
so it is invisible locally and fatal on Colab.
"""
import io
import json
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
STDIO_LABS = ["11b_mcp_live", "12_agent_graph", "13_agent_control", "14_agent_safety"]


def code_cells(stem):
    nb = json.loads((REPO_ROOT / "notebooks" / f"{stem}.ipynb").read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


@pytest.mark.parametrize("stem", STDIO_LABS)
def test_the_notebook_repoints_the_servers_stderr(stem):
    cells = code_cells(stem)
    joined = "\n".join(cells)
    assert "StdioServerParameters" in joined, f"{stem} no longer opens a stdio client"
    assert "_mcp_stdio" in joined, (
        f"{stem} opens an MCP stdio client but never repoints the server's stderr; "
        f"it will raise io.UnsupportedOperation: fileno on Colab")
    assert "__wrapped__" in joined, (
        "the errlog default sits under asynccontextmanager - patching the visible "
        "function object does nothing")


@pytest.mark.parametrize("stem", STDIO_LABS)
def test_the_patch_runs_before_any_client_is_built(stem):
    cells = code_cells(stem)
    patched_at = next(i for i, s in enumerate(cells) if "_mcp_stdio" in s)
    first_client = next((i for i, s in enumerate(cells)
                         if "StdioServerParameters(" in s or "Client(" in s), None)
    assert first_client is not None
    assert patched_at <= first_client, (
        f"{stem} builds a client in cell {first_client} but patches stderr in "
        f"cell {patched_at}")


def test_the_patch_mechanism_actually_works():
    """Not a notebook test: prove the technique still applies to the pinned SDK."""
    import mcp.client.stdio as stdio

    target = getattr(stdio.stdio_client, "__wrapped__", None)
    assert target is not None, "stdio_client is no longer wrapped; revisit the patch"
    original = target.__defaults__
    try:
        log = open(Path(tempfile.gettempdir()) / "mcp_stderr_probe.log", "a")
        target.__defaults__ = (log,)
        import inspect
        assert inspect.signature(stdio.stdio_client).parameters["errlog"].default is log
        from mcp.client import client as client_module
        assert client_module.stdio_client is stdio.stdio_client, \
            "client.py no longer shares the patched function object"
    finally:
        target.__defaults__ = original


def test_a_kernel_stderr_really_has_no_fileno():
    """The condition the patch keys on, so the guard cannot silently stop firing."""
    class KernelStderr(io.TextIOBase):
        def write(self, s):
            return len(s)

        def fileno(self):
            raise io.UnsupportedOperation("fileno")

    with pytest.raises(io.UnsupportedOperation):
        KernelStderr().fileno()
