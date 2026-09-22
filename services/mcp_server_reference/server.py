"""oq-erp-mcp: the reference MCP server over the mock ERP (Day 5 S26).

This is the file the room builds, one step at a time
(facilitator/mcp_build_sequence.md). Every step's checkpoint is in
steps/; after the last step your file should read like this one.

    python -m services.mcp_server_reference.server                  # read-only (default)
    python -m services.mcp_server_reference.server --enable-writes  # the one write, gated

Protocol: MCP 2026-07-28 over Streamable HTTP at http://127.0.0.1:8100/mcp.
No initialize, no session: every request carries its own version and
capabilities, and server/discover says what this server is.

Four tools. Three read. One writes, is switched off unless a person
starts the server with --enable-writes, and even then asks for an
approval (a Multi Round-Trip Request) before it writes anything.
Every tool call writes one audit line (governance template 5.1.2).
"""

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.caching import CacheHint
from mcp.server.mcpserver import Context
from mcp_types import InputRequiredResult, ToolAnnotations
from pydantic import Field

from services.mcp_server_reference import approval, audit, erp_client
from services.mcp_server_reference.launch import run_from_command_line
from services.mock_erp.models import (
    EQUIPMENT_TAG_PATTERN,
    TICKET_ID_PATTERN,
    Equipment,
    HistoryPage,
    WorkOrder,
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
    "raise_work_order": "write",
}

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)
GATED_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                              idempotent_hint=False, open_world_hint=False)

Tag = Annotated[str, Field(pattern=EQUIPMENT_TAG_PATTERN,
                           description="Equipment tag, upper case, e.g. P-1201A")]


def build_server(enable_writes=False, audit_log_path=audit.DEFAULT_LOG_PATH):
    mcp = MCPServer(
        name=SERVER_NAME,
        version=SERVER_VERSION,
        instructions="Equipment master, maintenance history and work orders of the mock ERP. "
                     "Reads are free. raise_work_order needs a named approver.",
        request_state_security=approval.state_security(),
        cache_hints={"tools/list": CacheHint(ttl_ms=300_000, scope="public"),
                     "server/discover": CacheHint(ttl_ms=300_000, scope="public")},
    )

    # One audit line per tool call - first on the list, so it sees everything.
    audit_log = audit.AuditLog(audit_log_path)
    mcp.middleware.insert(0, audit.AuditMiddleware(
        audit_log, SERVER_NAME, SERVER_VERSION, TOOL_ACCESS, writes_enabled=enable_writes))

    # ---- the reads ------------------------------------------------------

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

    # ---- the one write --------------------------------------------------

    if enable_writes:

        @mcp.tool(annotations=GATED_WRITE)
        def raise_work_order(
            ctx: Context,
            equipment_tag: Tag,
            work_type: Literal["corrective", "preventive", "inspection"],
            priority: Annotated[Literal[1, 2, 3, 4], Field(
                description="1 emergency (today), 2 within 2 days, 3 within 7, 4 within 28")],
            title: Annotated[str, Field(min_length=5, max_length=80)],
            description: Annotated[str, Field(min_length=10, max_length=2000)],
            requested_by: Annotated[str, Field(min_length=2, max_length=80)],
            source_ticket: Annotated[str | None, Field(pattern=TICKET_ID_PATTERN)] = None,
        ) -> WorkOrder | InputRequiredResult:
            """Raise a work order for the site crew. NEEDS A PERSON'S APPROVAL (a form)."""
            proposal = {"equipment_tag": equipment_tag, "work_type": work_type,
                        "priority": priority, "title": title, "description": description,
                        "requested_by": requested_by, "source_ticket": source_ticket}

            answer = approval.answer_in(ctx)
            if answer is None:
                # Round 1: show the person the exact request, and what we checked.
                equipment = erp_client.get(f"/equipment/{equipment_tag}")
                evidence = (f"{equipment['tag']} is '{equipment['description']}' at "
                            f"{equipment['site']}, criticality {equipment['criticality']}, "
                            f"status {equipment['status']}, open work orders: "
                            f"{', '.join(equipment['open_work_orders']) or 'none'}.")
                return approval.ask(ctx, proposal, evidence)

            # Round 2: only an approval this server asked for, for these arguments, once.
            approver = approval.check(ctx, proposal, answer)
            created = erp_client.post("/work-orders", {**proposal, "approved_by": approver})
            return WorkOrder.model_validate(created)

    return mcp


if __name__ == "__main__":
    run_from_command_line(build_server)
