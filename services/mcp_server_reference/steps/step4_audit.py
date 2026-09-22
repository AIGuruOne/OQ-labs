"""S26 checkpoint after STEP 4 (and step 5, which changes no code): one audit line per tool call.

    python -m services.mcp_server_reference.steps.step4_audit
    python -m services.mcp_server_reference.call get_equipment tag=P-1201A
    python -m services.mcp_server_reference.call get_equipment tag=X-0000
    type checkpoints\\local\\mcp_audit\\tool_call.jsonl          (Windows; cat on Mac/Linux)

What you can see now: every tool call - a success, an ERP 404, a
refused unknown tool - leaves exactly one JSON line in the audit log,
in the shape of governance template 5.1.2. The class table below says
which tools read and which write; a tool that is not in it is refused.

Step 5 uses this same file: start the ERP with MOCK_ERP_API_KEY, watch
the server fail with a 401 sentence, give the server the key through
its environment (never in code), and find the key in no audit line.
"""

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.caching import CacheHint
from mcp_types import ToolAnnotations
from pydantic import Field

from services.mcp_server_reference import audit, erp_client
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

# The class table (governance template 4.2). THIS decides read or write,
# not the annotations below: annotations are hints a client may ignore.
# A tool missing from this table is refused as if it were a write.
TOOL_ACCESS = {
    "get_equipment": "read",
    "get_maintenance_history": "read",
    "list_work_orders": "read",
}

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

Tag = Annotated[str, Field(pattern=EQUIPMENT_TAG_PATTERN,
                           description="Equipment tag, upper case, e.g. P-1201A")]


def build_server(audit_log_path=audit.DEFAULT_LOG_PATH):
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP.",
        cache_hints={"tools/list": CacheHint(ttl_ms=300_000, scope="public"),
                     "server/discover": CacheHint(ttl_ms=300_000, scope="public")},
    )

    # One audit line per tool call - first on the list, so it sees everything.
    audit_log = audit.AuditLog(audit_log_path)
    mcp.middleware.insert(0, audit.AuditMiddleware(
        audit_log, SERVER_NAME, SERVER_VERSION, TOOL_ACCESS, writes_enabled=False))

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
