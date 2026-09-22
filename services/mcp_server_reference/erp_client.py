"""The MCP server's only way to reach the mock ERP.

    from services.mcp_server_reference import erp_client
    equipment = erp_client.get("/equipment/P-1201A")
    created = erp_client.post("/work-orders", body)

Where the ERP is and its key come from the environment (or the repo-root
.env), never from code or from a tool's arguments:

    MOCK_ERP_URL       default http://127.0.0.1:8000
    MOCK_ERP_API_KEY   empty = the ERP needs no key (the lab default)

Every call tells the audit log which upstream system answered and with
which HTTP status, so a tool never has to remember to. A reply that is
not 2xx becomes an ErpError whose message is written for the model (and
the person reading the log), with the ERP's own sentence in it.
"""

import os
from pathlib import Path

import requests
from mcp.server.mcpserver.exceptions import ToolError

from services.mcp_server_reference import audit

REPO_ROOT = Path(__file__).resolve().parents[2]
TIMEOUT_SECONDS = 10


class ErpError(ToolError):
    """The ERP answered with an error, or did not answer at all.

    A ToolError, so a tool can let it fly: the SDK turns it into a tool
    result with isError true and this message, which the model can read
    and act on (a wrong tag, a missing field)."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status          # the ERP's HTTP status, or None if it never answered


def setting(name, default=""):
    """An environment variable, else the same key in the repo-root .env.

    Same rule as services/mock_erp/main.py: a real exported variable
    always wins over the file.
    """
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == name:
                return value.strip().strip('"').strip("'") or default
    return default


def base_url():
    return setting("MOCK_ERP_URL", "http://127.0.0.1:8000").rstrip("/")


def headers():
    """The ERP key goes in a header here and nowhere else: not in a tool
    argument, not in a result, not in the audit log."""
    api_key = setting("MOCK_ERP_API_KEY")
    if api_key:
        return {"X-API-Key": api_key}
    return {}


def get(path, params=None):
    """GET from the ERP. Returns the JSON body; raises ErpError on anything but 200."""
    return _send("GET", path, params=params)


def post(path, body):
    """POST to the ERP. Returns the JSON body; raises ErpError on anything but 201."""
    return _send("POST", path, body=body)


def _send(method, path, params=None, body=None):
    url = base_url() + path
    try:
        reply = requests.request(method, url, params=params, json=body,
                                 headers=headers(), timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        audit.note(upstream={"system": "mock_erp", "status": None})
        raise ErpError(None, f"The mock ERP did not answer at {base_url()}. "
                             f"Is it running? (uvicorn services.mock_erp.main:app)")

    audit.note(upstream={"system": "mock_erp", "status": reply.status_code})
    if reply.status_code in (200, 201):
        return reply.json()

    try:
        error_body = reply.json()
    except ValueError:
        error_body = {}
    erp_message = error_body.get("message", reply.text[:200])
    for problem in error_body.get("problems", []):
        erp_message += f" [{problem.get('where')}: {problem.get('problem')}]"
    if reply.status_code == 401:
        erp_message = ("The ERP refused the MCP server's key (401). Set MOCK_ERP_API_KEY "
                       "for the MCP server to the key the ERP was started with.")
    raise ErpError(reply.status_code, f"ERP said {reply.status_code}: {erp_message}")
