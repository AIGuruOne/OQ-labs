"""Mock ERP API: equipment master, maintenance history, work orders.

Run it (from the repo root):
    uvicorn services.mock_erp.main:app --reload          # http://127.0.0.1:8000/docs

Read endpoints across all three resources, and EXACTLY ONE write:
POST /work-orders, which raises a work order and releases it to the
site crew. That write is what the Day 4 approval interrupt and the
Day 5 MCP server gate. tests/test_mock_erp.py fails if a second write
appears.

Files:  models.py  the shapes (what /docs shows)
        store.py   the data and the rules (in memory, reset on restart)
        main.py    this file: HTTP routes, errors, the API key check
        seed.py    generates data/*.json (never run by the server)
        launch.py  start/stop it in the background (Colab, tests)
"""

import os
import re
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Path as PathParam, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import APIKeyHeader
from starlette.exceptions import HTTPException as StarletteHTTPException

from .models import (
    EQUIPMENT_TAG_PATTERN,
    RECORD_ID_PATTERN,
    TICKET_ID_PATTERN,
    WORK_ORDER_ID_PATTERN,
    Equipment,
    EquipmentFilters,
    EquipmentPage,
    ErrorResponse,
    Health,
    HistoryFilters,
    HistoryPage,
    MaintenanceRecord,
    WorkOrder,
    WorkOrderCreate,
    WorkOrderFilters,
    WorkOrderPage,
)
from .store import Conflict, ErpStore, UnknownEquipment

SERVICE = "mock-erp"
VERSION = "1.0.0"
REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------
# Settings: environment variables, or the repo-root .env
# ---------------------------------------------------------------------


def setting(name):
    """An environment variable, else the same key in the repo-root .env.

    Stdlib only, like config/endpoints.py. A real exported variable
    always wins over the file.
    """
    if name in os.environ:
        return os.environ[name]
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.strip().partition("=")
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    return ""


# ---------------------------------------------------------------------
# Errors. Every error body is an ErrorResponse:
#   {"error": "<code>", "message": "<a sentence>", ...}
# ---------------------------------------------------------------------


class ErpError(Exception):
    def __init__(self, status_code, error, message, problems=None, existing_work_order_id=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = {"error": error, "message": message}
        if problems:
            self.body["problems"] = problems
        if existing_work_order_id:
            self.body["existing_work_order_id"] = existing_work_order_id


PATTERN_HINTS = {
    EQUIPMENT_TAG_PATTERN: "must look like P-1201A or HX-3040",
    WORK_ORDER_ID_PATTERN: "must look like WO-118305",
    RECORD_ID_PATTERN: "must look like MH-000224",
    TICKET_ID_PATTERN: "must look like INC-004412",
}


def check_id(value, pattern, where):
    """Upper-case an id from the URL and check its shape (422 if wrong)."""
    value = value.strip().upper()
    if not re.fullmatch(pattern, value):
        raise ErpError(422, "validation_failed", "The request was not processed: 1 problem. "
                                                 "Nothing was changed.",
                       problems=[{"where": where, "problem": PATTERN_HINTS[pattern], "got": value}])
    return value


def describe_problem(error):
    """One pydantic error -> one sentence a person can act on."""
    kind = error["type"]
    message = error["msg"]
    if kind == "missing":
        return "is required"
    if kind == "extra_forbidden":
        return "is not a field this endpoint accepts (check the spelling; /docs lists the fields)"
    if kind == "string_pattern_mismatch":
        return PATTERN_HINTS.get(error.get("ctx", {}).get("pattern"), message)
    if kind == "value_error":
        return message.removeprefix("Value error, ")
    return message[0].lower() + message[1:]


def shorten(value):
    if isinstance(value, str) and len(value) > 80:
        return value[:77] + "..."
    return value


def on_validation_error(request: Request, exc: RequestValidationError):
    errors = exc.errors()

    # 1. The body is not JSON at all: a missing quote, a trailing comma.
    for error in errors:
        if error["type"] == "json_invalid":
            position = error["loc"][1] if len(error["loc"]) > 1 else "?"
            reason = error.get("ctx", {}).get("error", "decode error")
            body = ErpError(400, "malformed_body",
                            f"The request body is not valid JSON ({reason} at character "
                            f"{position}). Check quotes, commas and brackets. Nothing was changed.")
            return JSONResponse(body.body, status_code=400)

    # 2. A body was sent, but not as JSON.
    content_type = request.headers.get("content-type", "")
    sent_body = request.headers.get("content-length", "0") != "0"
    body_errors = [error for error in errors if error["loc"] == ("body",)]
    if body_errors and sent_body and "application/json" not in content_type:
        body = ErpError(415, "unsupported_media_type",
                        f"Send the body as JSON with the header Content-Type: application/json "
                        f"(this request said '{content_type or 'nothing'}'). Nothing was changed.")
        return JSONResponse(body.body, status_code=415)

    # 3. Everything else: one line per problem.
    problems = []
    for error in errors:
        where = ".".join(str(part) for part in error["loc"])
        if where == "body" and error["type"] == "missing":
            problem = "a JSON body is required"
        elif where == "body" and error["type"] == "model_attributes_type":
            problem = "must be a JSON object: {\"equipment_tag\": ..., ...}"
        else:
            problem = describe_problem(error)
        entry = {"where": where, "problem": problem}
        if error["type"] != "missing" and not isinstance(error.get("input"), dict):
            entry["got"] = shorten(error.get("input"))
        problems.append(entry)

    count = len(problems)
    message = (f"The request was not processed: {count} problem{'s' if count > 1 else ''}. "
               f"Nothing was changed.")
    return JSONResponse(ErpError(422, "validation_failed", message, problems).body, status_code=422)


def on_http_error(request: Request, exc: StarletteHTTPException):
    """Starlette's own 404 (no such URL) and 405 (wrong method)."""
    method, path = request.method, request.url.path
    if exc.status_code == 404:
        body = {"error": "not_found",
                "message": f"No such endpoint: {method} {path}. The list is at /docs."}
    elif exc.status_code == 405:
        if path.startswith("/work-orders/"):
            reason = ("Work orders cannot be changed, cancelled or deleted through this API. "
                      "A planner does that in the ERP itself.")
        else:
            reason = "This API is read-only except for POST /work-orders."
        body = {"error": "method_not_allowed", "message": f"{method} is not allowed on {path}. {reason}"}
    else:
        body = {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


def on_erp_error(request: Request, exc: ErpError):
    return JSONResponse(exc.body, status_code=exc.status_code)


# ---------------------------------------------------------------------
# Dependencies: the data, and the optional API key
# ---------------------------------------------------------------------


def get_store(request: Request) -> ErpStore:
    return request.app.state.store


Store = Annotated[ErpStore, Depends(get_store)]

api_key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False,
    description="Only when the server was started with MOCK_ERP_API_KEY set.")


def check_api_key(request: Request, sent: Annotated[str | None, Depends(api_key_header)]):
    """No production auth here (BUILD_SPEC section 14): one shared key
    from the environment, or nothing at all. OIDC is a talk topic."""
    expected = request.app.state.api_key
    if not expected:
        return
    if sent is None:
        raise ErpError(401, "unauthorised", "Send the header X-API-Key. This server was started "
                                            "with MOCK_ERP_API_KEY set.")
    if not secrets.compare_digest(sent.encode(), expected.encode()):
        raise ErpError(401, "unauthorised", "X-API-Key does not match MOCK_ERP_API_KEY.")


# ---------------------------------------------------------------------
# OpenAPI text: this is what participants read at /docs
# ---------------------------------------------------------------------

DESCRIPTION = """
A small, fake ERP for the labs. **Everything in it is synthetic**: sites, tags,
manufacturers, work orders. It stands in for the plant maintenance system that
tickets call *AssetHive*.

### Three resources

| Resource | Endpoints | Id looks like |
|---|---|---|
| Equipment master | `GET /equipment`, `GET /equipment/{tag}` | `P-1201A` |
| Maintenance history | `GET /maintenance-history`, `GET /maintenance-history/{record_id}` | `MH-000224` |
| Work orders | `GET /work-orders`, `GET /work-orders/{work_order_id}`, **`POST /work-orders`** | `WO-118305` |

### The one write

`POST /work-orders` **raises a work order and releases it to the site crew.**
Priority 1 calls a crew out at once. There is no endpoint to change, cancel or
delete a work order: once raised, only a planner in the real ERP can undo it.
That is why an agent must never call it without a person approving first
(Day 4 approval interrupt; Day 5 MCP server gate). The body must name who
approved it in `approved_by`. The ERP records that name; it cannot check it.

### Conventions

- **Lists** are pages: `?limit=` (1 to 100, default 20) and `?offset=`. The reply
  carries `total` and `next_offset` (null on the last page). Unknown query
  parameters are refused, so a typo is an error rather than an unfiltered list.
- **Ids** are case-insensitive: `p-1201a` finds `P-1201A`.
- **Dates** are ISO 8601. Timestamps carry the Gulf offset (`+04:00`).
- **Errors** always look like `{"error": "not_found", "message": "..."}`.
  Validation errors add `problems`: one `{where, problem, got}` per problem.
- **Auth**: none by default. If the server was started with `MOCK_ERP_API_KEY`
  set, send it as `X-API-Key` (the *Authorize* button). `GET /health` is always open.
- **State** lives in memory. A restart reloads the seed data: every work order
  raised through the API is gone, and the ERP is identical on every machine.
"""

TAGS = [
    {"name": "Equipment master", "description": "What is installed where. Read only."},
    {"name": "Maintenance history", "description": "Completed work: what failed, what was done. Read only."},
    {"name": "Work orders", "description": "Requests for work. Read, plus the ONE write."},
    {"name": "Service", "description": "Is it up, and with which data."},
]

NOT_FOUND = {404: {"model": ErrorResponse, "description": "No such record."}}
INVALID = {422: {"model": ErrorResponse, "description": "A parameter or field is wrong. `problems` says which."}}
AUTH = {401: {"model": ErrorResponse, "description": "Only when MOCK_ERP_API_KEY is set: key missing or wrong."}}

# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------

router = APIRouter(dependencies=[Depends(check_api_key)], responses=AUTH)


@router.get("/equipment", response_model=EquipmentPage, tags=["Equipment master"],
            summary="List equipment", responses=INVALID)
def list_equipment(filters: Annotated[EquipmentFilters, Query()], store: Store):
    """Equipment, sorted by tag, one page at a time. Every filter is optional
    and they combine with AND: `?site=MRB&equipment_type=pump`."""
    return store.list_equipment(filters)


@router.get("/equipment/{tag}", response_model=Equipment, tags=["Equipment master"],
            summary="Get one piece of equipment", responses={**NOT_FOUND, **INVALID})
def get_equipment(tag: Annotated[str, PathParam(description="Equipment tag, any case.", examples=["P-1201A"])],
                  store: Store):
    """One row of the equipment master, plus `open_work_orders`: the work
    orders on this tag that are not finished yet."""
    tag = check_id(tag, EQUIPMENT_TAG_PATTERN, "path.tag")
    row = store.get_equipment(tag)
    if row is None:
        raise ErpError(404, "not_found", f"No equipment with tag {tag}. Find tags with "
                                         f"GET /equipment?site=MRB (sites: HBT KTF MRB SHZ TMQ WQR ZFL).")
    return row


@router.get("/maintenance-history", response_model=HistoryPage, tags=["Maintenance history"],
            summary="List maintenance history", responses=INVALID)
def list_history(filters: Annotated[HistoryFilters, Query()], store: Store):
    """Completed work, newest first. The usual question is
    `?equipment_tag=P-1201A`: what has been done to this pump before?"""
    return store.list_history(filters)


@router.get("/maintenance-history/{record_id}", response_model=MaintenanceRecord,
            tags=["Maintenance history"], summary="Get one maintenance record",
            responses={**NOT_FOUND, **INVALID})
def get_history_record(
        record_id: Annotated[str, PathParam(description="Maintenance record id.", examples=["MH-000224"])],
        store: Store):
    """One maintenance record: what failed, what was done, which parts."""
    record_id = check_id(record_id, RECORD_ID_PATTERN, "path.record_id")
    row = store.get_history_record(record_id)
    if row is None:
        raise ErpError(404, "not_found", f"No maintenance record {record_id}. Search with "
                                         f"GET /maintenance-history?equipment_tag=P-1201A.")
    return row


@router.get("/work-orders", response_model=WorkOrderPage, tags=["Work orders"],
            summary="List work orders", responses=INVALID)
def list_work_orders(filters: Annotated[WorkOrderFilters, Query()], store: Store):
    """Work orders, newest first. Use `?source_ticket=INC-004412` to check
    whether a ticket already has one before raising another."""
    return store.list_work_orders(filters)


@router.get("/work-orders/{work_order_id}", response_model=WorkOrder, tags=["Work orders"],
            summary="Get one work order", responses={**NOT_FOUND, **INVALID})
def get_work_order(
        work_order_id: Annotated[str, PathParam(description="Work order id.", examples=["WO-118305"])],
        store: Store):
    """One work order, whatever its status. A work order raised through
    POST /work-orders is readable here straight away."""
    work_order_id = check_id(work_order_id, WORK_ORDER_ID_PATTERN, "path.work_order_id")
    row = store.get_work_order(work_order_id)
    if row is None:
        raise ErpError(404, "not_found", f"No work order {work_order_id}. Search with "
                                         f"GET /work-orders?equipment_tag=P-1201A.")
    return row


@router.post(
    "/work-orders", status_code=201, response_model=WorkOrder, tags=["Work orders"],
    summary="Raise a work order and release it to the site crew (THE ONE WRITE)",
    responses={
        400: {"model": ErrorResponse, "description": "The body is not valid JSON."},
        409: {"model": ErrorResponse, "description": "This source ticket already has a work order."},
        415: {"model": ErrorResponse, "description": "The body was not sent as application/json."},
        **INVALID,
    },
)
def raise_work_order(request_body: WorkOrderCreate, response: Response, store: Store):
    """**Consequential and not reversible through this API.** The new work
    order is created in status `released`: it is on the site crew's list
    the moment this returns, and priority 1 calls a crew out now. There is
    no endpoint to edit, cancel or delete it.

    Call it only after a named person has approved the exact body you are
    about to send, and put that person in `approved_by`.

    - `201 Created`: the new work order; its URL is in the `Location` header.
    - `409 Conflict`: `source_ticket` already has a work order (a retry after a
      timeout lands here instead of raising a duplicate).
    - `422`: a field is wrong, or the tag is not in the equipment master.
      Nothing was written.
    """
    try:
        order = store.raise_work_order(request_body)
    except UnknownEquipment:
        raise ErpError(422, "validation_failed", "The request was not processed: 1 problem. "
                                                 "Nothing was changed.",
                       problems=[{"where": "body.equipment_tag",
                                  "problem": "is not in the equipment master "
                                             "(GET /equipment lists the tags)",
                                  "got": request_body.equipment_tag}])
    except Conflict as conflict:
        raise ErpError(409, "conflict", str(conflict),
                       existing_work_order_id=conflict.existing_work_order_id)

    response.headers["Location"] = f"/work-orders/{order['work_order_id']}"
    print(f"[{SERVICE}] WRITE raised {order['work_order_id']} on {order['equipment_tag']} "
          f"({order['site']}), priority {order['priority']}, approved_by={order['approved_by']!r}, "
          f"source_ticket={order['source_ticket']}", flush=True)
    return order


service_router = APIRouter(tags=["Service"])


@service_router.get("/health", response_model=Health, summary="Is it up?")
def health(request: Request, store: Store):
    """Always open, even with an API key set. `data_fingerprint` is the same
    on every machine and every restart; `work_orders_raised_since_start`
    counts calls to the one write since this process started."""
    return {
        "status": "ok",
        "service": SERVICE,
        "version": VERSION,
        "auth": "api_key" if request.app.state.api_key else "off",
        "data_fingerprint": store.data_fingerprint,
        "started": store.started,
        "counts": store.counts(),
        "work_orders_raised_since_start": store.raised_since_start,
    }


@service_router.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


# ---------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------


def create_app(data_dir=None, api_key=None):
    """Build the app with a fresh copy of the seed data.

    data_dir  defaults to MOCK_ERP_DATA_DIR, else services/mock_erp/data
    api_key   defaults to MOCK_ERP_API_KEY; empty means no key needed
    """
    if data_dir is None:
        data_dir = setting("MOCK_ERP_DATA_DIR") or None
    if api_key is None:
        api_key = setting("MOCK_ERP_API_KEY")

    app = FastAPI(title="Mock ERP (lab)", version=VERSION, description=DESCRIPTION,
                  openapi_tags=TAGS)
    app.state.store = ErpStore(data_dir)
    app.state.api_key = api_key

    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(StarletteHTTPException, on_http_error)
    app.add_exception_handler(ErpError, on_erp_error)
    app.include_router(router)
    app.include_router(service_router)

    counts = app.state.store.counts()
    print(f"[{SERVICE}] loaded {counts['equipment']} equipment, {counts['work_orders']} work orders, "
          f"{counts['maintenance_history']} maintenance records "
          f"(data {app.state.store.data_fingerprint}); auth {'api_key' if api_key else 'off'}",
          flush=True)
    return app


app = create_app()
