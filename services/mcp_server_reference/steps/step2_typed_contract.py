"""S26 checkpoint after STEP 2: the tool's input is a contract, not a string.

    python -m services.mcp_server_reference.steps.step2_typed_contract
    python -m services.mcp_server_reference.call list
    python -m services.mcp_server_reference.call get_equipment tag=pump-one

What you can see now: tools/list shows the tag's pattern and
description in the inputSchema, and a tag that breaks the pattern is
refused by the server before the ERP is ever called.
"""

from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from services.mcp_server_reference import erp_client
from services.mcp_server_reference.launch import run_from_command_line
from services.mock_erp.models import EQUIPMENT_TAG_PATTERN, Equipment

SERVER_NAME = "oq-erp-mcp"
SERVER_VERSION = "0.1.0"

Tag = Annotated[str, Field(pattern=EQUIPMENT_TAG_PATTERN,
                           description="Equipment tag, upper case, e.g. P-1201A")]


def build_server():
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP.",
    )

    @mcp.tool()
    def get_equipment(tag: Tag) -> Equipment:
        """One equipment master record by tag, with its open work orders."""
        record = erp_client.get(f"/equipment/{tag}")
        return Equipment.model_validate(record)

    return mcp


if __name__ == "__main__":
    run_from_command_line(build_server)
