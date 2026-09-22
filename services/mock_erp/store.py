"""The mock ERP's data: loaded from three JSON files, held in memory.

No database. A restart reloads the seed files, so every restart is the
same clean ERP - and every work order raised through the API is gone.
That is on purpose: a lab that went wrong is fixed by a restart.

The routes in main.py call these methods and nothing else touches the
data, so this file is the whole of the ERP's behaviour.
"""

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .seed import TARGET_DAYS          # days from raised to target, by priority

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
RESOURCES = ["equipment", "work_orders", "maintenance_history"]

GULF_TIME = timezone(timedelta(hours=4))
OPEN_STATUSES = ("released", "in_progress", "on_hold")


class Conflict(Exception):
    """The write would duplicate a work order that already exists."""

    def __init__(self, message, existing_work_order_id):
        super().__init__(message)
        self.existing_work_order_id = existing_work_order_id


class UnknownEquipment(Exception):
    """The write names a tag that is not in the equipment master."""


def paginate(rows, limit, offset):
    """Cut one page out of a filtered list. Same envelope for every list."""
    page = rows[offset:offset + limit]
    has_more = offset + limit < len(rows)
    return {
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "next_offset": offset + limit if has_more else None,
        "items": page,
    }


class ErpStore:
    def __init__(self, data_dir=None):
        data_dir = Path(data_dir or DEFAULT_DATA_DIR)
        fingerprint = hashlib.sha256()
        loaded = {}
        for name in RESOURCES:
            raw = (data_dir / f"{name}.json").read_bytes()
            fingerprint.update(raw)
            loaded[name] = json.loads(raw)

        self.data_fingerprint = fingerprint.hexdigest()[:12]
        self.equipment = {row["tag"]: row for row in loaded["equipment"]}
        self.work_orders = {row["work_order_id"]: row for row in loaded["work_orders"]}
        self.history = {row["record_id"]: row for row in loaded["maintenance_history"]}
        self.raised_since_start = 0
        self.started = datetime.now(GULF_TIME).replace(microsecond=0).isoformat()
        # Two POSTs at once must not get the same work order number.
        self.write_lock = threading.Lock()

    def counts(self):
        return {
            "equipment": len(self.equipment),
            "work_orders": len(self.work_orders),
            "maintenance_history": len(self.history),
        }

    # -----------------------------------------------------------------
    # Equipment master
    # -----------------------------------------------------------------

    def open_work_orders_for(self, tag):
        open_orders = [order for order in self.work_orders.values()
                       if order["equipment_tag"] == tag and order["status"] in OPEN_STATUSES]
        open_orders.sort(key=lambda order: order["created"], reverse=True)
        return [order["work_order_id"] for order in open_orders]

    def equipment_view(self, row):
        """The stored row plus the one field worked out at read time."""
        return {**row, "open_work_orders": self.open_work_orders_for(row["tag"])}

    def get_equipment(self, tag):
        row = self.equipment.get(tag)
        if row is None:
            return None
        return self.equipment_view(row)

    def list_equipment(self, filters):
        rows = []
        for tag in sorted(self.equipment):
            row = self.equipment[tag]
            if filters.site and row["site"] != filters.site:
                continue
            if filters.equipment_type and row["equipment_type"] != filters.equipment_type:
                continue
            if filters.criticality and row["criticality"] != filters.criticality:
                continue
            if filters.status and row["status"] != filters.status:
                continue
            rows.append(row)
        page = paginate(rows, filters.limit, filters.offset)
        page["items"] = [self.equipment_view(row) for row in page["items"]]
        return page

    # -----------------------------------------------------------------
    # Maintenance history (newest first)
    # -----------------------------------------------------------------

    def get_history_record(self, record_id):
        return self.history.get(record_id)

    def list_history(self, filters):
        rows = []
        for row in self.history.values():
            if filters.equipment_tag and row["equipment_tag"] != filters.equipment_tag:
                continue
            if filters.site and row["site"] != filters.site:
                continue
            if filters.work_type and row["work_type"] != filters.work_type:
                continue
            if filters.failure_mode:
                wanted = filters.failure_mode.lower()
                if wanted not in (row["failure_mode"] or "").lower():
                    continue
            if filters.since and row["date"] < filters.since.isoformat():
                continue
            if filters.until and row["date"] > filters.until.isoformat():
                continue
            rows.append(row)
        rows.sort(key=lambda row: (row["date"], row["record_id"]), reverse=True)
        return paginate(rows, filters.limit, filters.offset)

    # -----------------------------------------------------------------
    # Work orders (newest first)
    # -----------------------------------------------------------------

    def get_work_order(self, work_order_id):
        return self.work_orders.get(work_order_id)

    def list_work_orders(self, filters):
        rows = []
        for row in self.work_orders.values():
            if filters.equipment_tag and row["equipment_tag"] != filters.equipment_tag:
                continue
            if filters.site and row["site"] != filters.site:
                continue
            if filters.status and row["status"] != filters.status:
                continue
            if filters.work_type and row["work_type"] != filters.work_type:
                continue
            if filters.priority and row["priority"] != filters.priority:
                continue
            if filters.source_ticket and row["source_ticket"] != filters.source_ticket:
                continue
            rows.append(row)
        rows.sort(key=lambda row: (row["created"], row["work_order_id"]), reverse=True)
        return paginate(rows, filters.limit, filters.offset)

    # -----------------------------------------------------------------
    # THE ONE WRITE: raise a work order and release it to the site crew
    # -----------------------------------------------------------------

    def raise_work_order(self, request):
        """Create a work order in status `released`. Returns the new row.

        Raises UnknownEquipment if the tag is not in the equipment
        master, Conflict if the source ticket already has a work order.
        """
        equipment = self.equipment.get(request.equipment_tag)
        if equipment is None:
            raise UnknownEquipment(request.equipment_tag)

        with self.write_lock:
            if request.source_ticket:
                for order in self.work_orders.values():
                    if order["source_ticket"] == request.source_ticket:
                        raise Conflict(
                            f"Ticket {request.source_ticket} already has work order "
                            f"{order['work_order_id']} (status {order['status']}). One work "
                            f"order per ticket: read it with GET /work-orders/"
                            f"{order['work_order_id']}.",
                            order["work_order_id"])

            highest = max(int(work_order_id[3:]) for work_order_id in self.work_orders)
            work_order_id = f"WO-{highest + 1:06d}"
            now = datetime.now(GULF_TIME).replace(microsecond=0)
            target = now.date() + timedelta(days=TARGET_DAYS[request.priority])

            order = {
                "work_order_id": work_order_id,
                "equipment_tag": equipment["tag"],
                "site": equipment["site"],
                "work_type": request.work_type,
                "priority": request.priority,
                "status": "released",
                "title": request.title,
                "description": request.description,
                "requested_by": request.requested_by,
                "approved_by": request.approved_by,
                "source_ticket": request.source_ticket,
                "raised_via": "api",
                "created": now.isoformat(),
                "target_date": target.isoformat(),
                "completed_date": None,
            }
            self.work_orders[work_order_id] = order
            self.raised_since_start += 1
        return order

