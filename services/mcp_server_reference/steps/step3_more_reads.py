"""S26 checkpoint after STEP 3: three read tools, marked read-only, a cacheable list.

    python -m services.mcp_server_reference.steps.step3_more_reads
    python -m services.mcp_server_reference.call list --brief
    python -m services.mcp_server_reference.call get_maintenance_history tag=P-1201A limit=3
    python -m services.mcp_server_reference.call list_work_orders equipment_tag=P-1201A

What you can see now: three tools, each with readOnlyHint true; the
tools/list reply carries ttlMs and cacheScope (2026-07-28 cacheable
lists) and comes back in the same order every time.
"""

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.caching import CacheHint
from mcp_types import ToolAnnotations
from pydantic import Field

from services.mcp_server_reference import erp_client
from services.mcp_server_reference.launch import run_from_command_line
from services.mock_erp.models import (
    EQUIPMENT_TAG_PATTERN,
    TICKET_ID_PATTERN,
    Equipment,
    HistoryPage,
    WorkOrderPage,
)

SERVER_NAME = "oq-erp-mcp"
SERVER_VERSION = "0.1.0"

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

Tag = Annotated[str, Field(pattern=EQUIPMENT_TAG_PATTERN,
                           description="Equipment tag, upper case, e.g. P-1201A")]


def build_server():
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP.",
        cache_hints={"tools/list": CacheHint(ttl_ms=300_000, scope="public"),
                     "server/discover": CacheHint(ttl_ms=300_000, scope="public")},
    )

    @mcp.tool(annotations=READ_ONLY)
    def get_equipment(tag: Tag) -> Equipment:
        """One equipment master record by tag, with its open work orders."""
        record = erp_client.get(f"/equipment/{tag}")
        return Equipment.model_validate(record)

    @mcp.tool(annotations=READ_ONLY)
    def get_maintenance_history(
        tag: Tag,
        limit: Annotated[int, Field(ge=1, le=50, description="How many records, newest first")] = 10,
    ) -> HistoryPage:
        """Completed maintenance on one piece of equipment, newest first."""
        page = erp_client.get("/maintenance-history", {"equipment_tag": tag, "limit": limit})
        return HistoryPage.model_validate(page)

    @mcp.tool(annotations=READ_ONLY)
    def list_work_orders(
        equipment_tag: Tag | None = None,
        status: Literal["released", "in_progress", "on_hold", "completed", "cancelled"] | None = None,
        source_ticket: Annotated[str | None, Field(pattern=TICKET_ID_PATTERN,
                                                   description="e.g. INC-004412")] = None,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> WorkOrderPage:
        """Work orders, newest first. Every filter is optional; they combine with AND."""
        filters = {"equipment_tag": equipment_tag, "status": status,
                   "source_ticket": source_ticket, "limit": limit}
        filters = {name: value for name, value in filters.items() if value is not None}
        page = erp_client.get("/work-orders", filters)
        return WorkOrderPage.model_validate(page)

    return mcp


if __name__ == "__main__":
    run_from_command_line(build_server)
