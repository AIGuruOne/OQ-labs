"""The shapes the mock ERP reads and writes.

Everything a participant sees in /docs comes from here: field names,
descriptions, allowed values, examples. Change a field here and the
API, the validation and the docs all change together.

Three resources, read-only:   Equipment, MaintenanceRecord, WorkOrder
One write:                    WorkOrderCreate  (POST /work-orders)
"""

import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------
# Shared vocabulary
# ---------------------------------------------------------------------

EQUIPMENT_TAG_PATTERN = r"^[A-Z]{1,3}-[0-9]{4}[A-Z]?$"      # P-1201A, HX-3040
WORK_ORDER_ID_PATTERN = r"^WO-[0-9]{6}$"                     # WO-118305
RECORD_ID_PATTERN = r"^MH-[0-9]{6}$"                         # MH-000224
TICKET_ID_PATTERN = r"^INC-[0-9]{6}$"                        # INC-004412


def to_upper(value):
    """Let callers write mrb or p-1201a; store and compare upper case."""
    if isinstance(value, str):
        return value.strip().upper()
    return value


def to_lower(value):
    if isinstance(value, str):
        return value.strip().lower()
    return value


SiteCode = Annotated[
    Literal["HBT", "KTF", "MRB", "SHZ", "TMQ", "WQR", "ZFL"],
    BeforeValidator(to_upper),
]
EquipmentType = Annotated[
    Literal["pump", "compressor", "heat_exchanger", "air_cooler", "vessel", "column",
            "tank", "control_valve"],
    BeforeValidator(to_lower),
]
EquipmentStatus = Annotated[
    Literal["in_service", "standby", "out_of_service"], BeforeValidator(to_lower)]
Criticality = Annotated[Literal["A", "B", "C"], BeforeValidator(to_upper)]
WorkType = Annotated[
    Literal["corrective", "preventive", "inspection"], BeforeValidator(to_lower)]
WorkOrderStatus = Annotated[
    Literal["released", "in_progress", "on_hold", "completed", "cancelled"],
    BeforeValidator(to_lower),
]
Priority = Literal[1, 2, 3, 4]


# ---------------------------------------------------------------------
# The three resources
# ---------------------------------------------------------------------


class Equipment(BaseModel):
    """One row of the equipment master."""

    tag: str = Field(description="Equipment tag, unique across the ERP.", examples=["P-1201A"])
    site: SiteCode = Field(description="Three-letter site code.")
    unit: str = Field(description="Process unit: the first two digits of the tag number.",
                      examples=["12"])
    equipment_type: EquipmentType
    description: str = Field(examples=["Crude transfer pump"])
    manufacturer: str = Field(examples=["Veltrane Pumps"])
    model: str = Field(examples=["VP-450"])
    serial_number: str = Field(examples=["VP2014-40711"])
    rating: str = Field(description="Nameplate rating, free text.",
                        examples=["180 m3/h at 120 m head"])
    install_date: datetime.date
    criticality: Criticality = Field(
        description="A = safety or production critical, B = important, C = everything else.")
    status: EquipmentStatus
    open_work_orders: list[str] = Field(
        description="Work orders on this tag that are released, in progress or on hold, "
                    "newest first. Worked out at read time, so a new work order shows here "
                    "at once.",
        examples=[["WO-195893"]])


class Part(BaseModel):
    part_number: str = Field(examples=["30-2201-01"])
    description: str = Field(examples=["Mechanical seal cartridge"])
    quantity: int = Field(examples=[1])


class MaintenanceRecord(BaseModel):
    """What was found and what was done: one record per completed work order."""

    record_id: str = Field(examples=["MH-000224"])
    equipment_tag: str = Field(examples=["P-1201A"])
    site: SiteCode
    work_order_id: str = Field(description="The completed work order this record closes.",
                               examples=["WO-118305"])
    date: datetime.date = Field(description="Date the work was completed.")
    work_type: WorkType
    failure_mode: str | None = Field(
        description="What failed. null for planned maintenance and inspections.",
        examples=["mechanical seal leak"])
    action_taken: str
    parts: list[Part]
    downtime_hours: float
    performed_by: str = Field(examples=["MRB rotating equipment crew"])


class WorkOrder(BaseModel):
    """A work order: a request for a crew to do work on one piece of equipment."""

    work_order_id: str = Field(examples=["WO-118305"])
    equipment_tag: str = Field(examples=["P-1201A"])
    site: SiteCode = Field(description="Taken from the equipment master, never from the caller.")
    work_type: WorkType
    priority: Priority = Field(
        description="1 emergency (crew called out now), 2 urgent (2 days), 3 normal (7 days), "
                    "4 planned (next window, 28 days).")
    status: WorkOrderStatus
    title: str
    description: str
    requested_by: str
    approved_by: str = Field(description="The person who approved raising it.")
    source_ticket: str | None = Field(description="The service desk ticket it came from, if any.",
                                      examples=["INC-004412"])
    raised_via: Literal["erp_screen", "api"] = Field(
        description="erp_screen = raised by a planner in the ERP itself (all seed data); "
                    "api = raised through POST /work-orders.")
    created: str = Field(description="ISO 8601 with the Gulf offset.",
                         examples=["2026-09-22T10:41:07+04:00"])
    target_date: datetime.date = Field(description="created + 0 / 2 / 7 / 28 days for priority 1 / 2 / 3 / 4.")
    completed_date: datetime.date | None


# ---------------------------------------------------------------------
# The one write
# ---------------------------------------------------------------------


class WorkOrderCreate(BaseModel):
    """The body of POST /work-orders. Unknown fields are refused, so a typo
    such as `prority` is an error, not a silently ignored field."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{
            "equipment_tag": "P-1201A",
            "work_type": "corrective",
            "priority": 2,
            "title": "P-1201A abnormal noise, suspect seal",
            "description": "Control room reports P-1201A screen red and the pump sounds wrong. "
                           "Seal replaced under WO-118305 in May 2026. Inspect seal and bearings.",
            "requested_by": "Control room operator, MRB",
            "approved_by": "Salim (maintenance planner, MRB)",
            "source_ticket": "INC-004412",
        }]},
    )

    equipment_tag: Annotated[str, BeforeValidator(to_upper)] = Field(
        pattern=EQUIPMENT_TAG_PATTERN,
        description="Must be a tag in the equipment master (GET /equipment/{tag}).")
    work_type: WorkType
    priority: Priority = Field(
        description="1 emergency: the site crew is called out NOW. 2 urgent: within 2 days. "
                    "3 normal: within 7 days. 4 planned: next maintenance window.")
    title: str = Field(min_length=5, max_length=80)
    description: str = Field(min_length=10, max_length=2000)
    requested_by: str = Field(min_length=2, max_length=80,
                              description="Who asked for the work.")
    approved_by: str = Field(
        min_length=2, max_length=80,
        description="The PERSON who approved raising this work order. Required. The ERP records "
                    "it; it cannot check it. The check happens before this call: the agent's "
                    "approval interrupt and the MCP server's gate.")
    source_ticket: Annotated[str | None, BeforeValidator(to_upper)] = Field(
        default=None, pattern=TICKET_ID_PATTERN,
        description="Service desk ticket this came from. One work order per ticket: a second "
                    "POST with the same ticket gets 409 Conflict.")


# ---------------------------------------------------------------------
# Query parameters for the list endpoints. Unknown parameters are
# refused (extra="forbid"), so `?stauts=released` is a 422 that names
# the typo instead of an unfiltered list that looks like an answer.
# ---------------------------------------------------------------------


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(20, ge=1, le=100, description="Items per page, 1 to 100.")
    offset: int = Field(0, ge=0, description="How many items to skip.")


class EquipmentFilters(PageParams):
    site: SiteCode | None = None
    equipment_type: EquipmentType | None = None
    criticality: Criticality | None = None
    status: EquipmentStatus | None = None


class WorkOrderFilters(PageParams):
    equipment_tag: Annotated[str | None, BeforeValidator(to_upper)] = Field(
        None, pattern=EQUIPMENT_TAG_PATTERN)
    site: SiteCode | None = None
    status: WorkOrderStatus | None = None
    work_type: WorkType | None = None
    # A query string arrives as text, so an int with bounds, not Literal[1, 2, 3, 4].
    priority: int | None = Field(None, ge=1, le=4)
    source_ticket: Annotated[str | None, BeforeValidator(to_upper)] = Field(
        None, pattern=TICKET_ID_PATTERN)


class HistoryFilters(PageParams):
    equipment_tag: Annotated[str | None, BeforeValidator(to_upper)] = Field(
        None, pattern=EQUIPMENT_TAG_PATTERN)
    site: SiteCode | None = None
    work_type: WorkType | None = None
    failure_mode: str | None = Field(
        None, description="Case-insensitive substring match, e.g. `seal`.")
    since: datetime.date | None = Field(None, description="On or after this date (ISO 8601).")
    until: datetime.date | None = Field(None, description="On or before this date (ISO 8601).")

    @model_validator(mode="after")
    def since_before_until(self):
        if self.since and self.until and self.since > self.until:
            raise ValueError(f"since ({self.since}) is after until ({self.until})")
        return self


# ---------------------------------------------------------------------
# Envelopes: pages, errors, health
# ---------------------------------------------------------------------


class Page(BaseModel):
    total: int = Field(description="Items matching the filters, across all pages.")
    limit: int
    offset: int
    next_offset: int | None = Field(description="Pass as ?offset= for the next page; null on the last.")


class EquipmentPage(Page):
    items: list[Equipment]


class WorkOrderPage(Page):
    items: list[WorkOrder]


class HistoryPage(Page):
    items: list[MaintenanceRecord]


class Problem(BaseModel):
    where: str = Field(description="body.priority, query.site, path.tag ...",
                       examples=["body.priority"])
    problem: str = Field(examples=["must be one of 1, 2, 3, 4"])
    got: object | None = Field(default=None, description="The value that was sent, if any.")


class ErrorResponse(BaseModel):
    """Every error the ERP returns has this shape."""

    error: str = Field(description="Short machine-readable code.",
                       examples=["not_found", "validation_failed", "malformed_body",
                                 "unsupported_media_type", "conflict", "method_not_allowed",
                                 "unauthorised"])
    message: str = Field(description="One or two sentences a person can act on.")
    problems: list[Problem] | None = Field(
        default=None, description="validation_failed only: one entry per problem.")
    existing_work_order_id: str | None = Field(
        default=None, description="conflict only: the work order that already exists.")


class Health(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    auth: Literal["off", "api_key"] = Field(
        description="off = no key needed (lab default). api_key = send X-API-Key.")
    data_fingerprint: str = Field(
        description="sha256 (first 12 hex digits) of the three seed files loaded at startup. "
                    "The same on every machine and every restart.")
    started: str
    counts: dict[str, int]
    work_orders_raised_since_start: int
