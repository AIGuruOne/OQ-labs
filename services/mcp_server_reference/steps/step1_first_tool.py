"""S26 checkpoint after STEP 1: an MCP server with one tool.

    python -m services.mcp_server_reference.steps.step1_first_tool
    python -m services.mcp_server_reference.call discover
    python -m services.mcp_server_reference.call get_equipment tag=P-1201A

What you can see now: server/discover answers with no handshake, and
one tool reads the equipment master through the mock ERP. The return
type (Equipment, the ERP's own model) became the tool's output schema.
"""

from mcp.server import MCPServer

from services.mcp_server_reference import erp_client
from services.mcp_server_reference.launch import run_from_command_line
from services.mock_erp.models import Equipment

SERVER_NAME = "oq-erp-mcp"
SERVER_VERSION = "0.1.0"


def build_server():
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP.",
    )

    @mcp.tool()
    def get_equipment(tag: str) -> Equipment:
        """One equipment master record by tag, with its open work orders."""
        record = erp_client.get(f"/equipment/{tag}")
        return Equipment.model_validate(record)

    return mcp


if __name__ == "__main__":
    run_from_command_line(build_server)
