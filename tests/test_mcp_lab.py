"""Lab 11a and notebooks/mcp_lab.py.

No server is started here - these check structure, and that 11a stays the simple rung
rather than growing into 11b. The helper drives the repo's OWN reference MCP server, so
if that server's tools change, this test says so.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NB = REPO_ROOT / "notebooks" / "11a_mcp_basics.ipynb"
sys.path.insert(0, str(REPO_ROOT / "notebooks"))


def cells():
    return json.loads(NB.read_text(encoding="utf-8"))["cells"]


def code():
    return "\n".join("".join(c["source"]) for c in cells() if c["cell_type"] == "code")


def test_the_header_carries_the_contract_2_skill_block():
    header = "".join(cells()[0]["source"])
    assert "## What you will be able to do after this" in header
    assert "**You will know it landed**" in header
    assert "**Where you use it:**" in header
    assert "A correct result looks like:" in header
    assert "All data in this lab is synthetic" in header


def test_it_needs_no_model_no_key_and_no_gpu():
    """11a is about authority, not about a model. A model call here would be noise."""
    header = "".join(cells()[0]["source"]).lower()
    assert "no gpu" in header and "no model call" in header and "no api key" in header
    src = code()
    for banned in ("OPENAI_API_KEY", "OpenAI(", "chat.completions", "ollama"):
        assert banned not in src, f"11a must not use {banned}"


def test_kiss_no_long_cells():
    for cell in (c for c in cells() if c["cell_type"] == "code"):
        lines = [l for l in "".join(cell["source"]).splitlines() if l.strip()]
        assert len(lines) <= 12, f"a {len(lines)}-line cell belongs in mcp_lab.py"


def test_it_shows_both_servers_and_all_three_outcomes():
    src = code()
    assert 'mcp.tools("read_only")' in src and 'mcp.tools("writes")' in src
    assert 'server="read_only"' in src, "the write must be attempted against the read-only server"
    assert "request_write()" in src, "and against the one that allows writes"
    assert "mcp.answer(" in src, "and a person must answer the form"
    assert "mcp.audit(" in src, "the audit log is the evidence; show it"


def test_the_helper_drives_the_repos_own_reference_server():
    """If 11a ever grows its own server, the lab stops teaching S26's server."""
    helper = (REPO_ROOT / "notebooks" / "mcp_lab.py").read_text(encoding="utf-8")
    assert "services.mcp_server_reference import launch" in helper
    assert "class " not in helper.split("ACCESS")[0], "mcp_lab must not define a server of its own"


def test_the_access_table_matches_the_real_server():
    """mcp_lab repeats the server's tool classes for display. They must not drift."""
    import mcp_lab
    server_src = (REPO_ROOT / "services" / "mcp_server_reference" / "server.py").read_text(encoding="utf-8")
    block = re.search(r"TOOL_ACCESS = \{(.*?)\}", server_src, re.S).group(1)
    real = dict(re.findall(r'"(\w+)":\s*"(\w+)"', block))
    shown = {k: v.lower() for k, v in mcp_lab.ACCESS.items()}
    assert shown == real, f"mcp_lab.ACCESS has drifted from server.py\n  lab:    {shown}\n  server: {real}"


def test_the_two_servers_use_different_ports():
    import mcp_lab
    assert mcp_lab.WRITES_PORT != mcp_lab.READ_ONLY_PORT, \
        "both servers run at once on purpose - one port cannot hold both"


def test_the_work_order_arguments_are_complete():
    """A missing required field turns the approval demo into a validation error."""
    import mcp_lab
    server_src = (REPO_ROOT / "services" / "mcp_server_reference" / "server.py").read_text(encoding="utf-8")
    sig = server_src[server_src.index("def raise_work_order("):]
    sig = sig[:sig.index(") -> ")]
    required = [m.group(1) for m in re.finditer(r"^\s{12}(\w+):", sig, re.M)
                if m.group(1) not in ("ctx",) and "= None" not in sig.split(m.group(1))[1][:40]]
    missing = [r for r in required if r not in mcp_lab.WORK_ORDER]
    assert not missing, f"mcp_lab.WORK_ORDER is missing required arguments: {missing}"
