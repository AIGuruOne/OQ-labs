"""Generate the mock ERP's seed data: equipment master, work orders,
maintenance history. Deterministic: the same seed writes the same bytes.

    python -m services.mock_erp.seed --seed 42
    python -m services.mock_erp.seed --seed 42 --out <folder> --tickets <tickets_raw.jsonl>

The server never runs this. It loads the three JSON files this writes
(services/mock_erp/data/), so startup takes well under a second and
every participant starts from the same ERP. tests/test_mock_erp.py
fails if the committed files and this generator disagree.

Everything here is invented (BUILD_SPEC section 9): tags, sites,
manufacturers, part numbers. Consistency with the ticket corpus is
deliberate:
  - every plant tag a ticket mentions is in the equipment master, at
    the site of the first ticket that mentions it;
  - every work order a ticket mentions exists, on the tag that ticket
    names;
  - the brief 4 story holds: P-1201A had its mechanical seal replaced
    under WO-118305 in May 2026.
"""

import argparse
import json
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TICKETS = REPO_ROOT / "corpus" / "tickets" / "tickets_raw.jsonl"
DEFAULT_OUT = Path(__file__).resolve().parent / "data"

# The ticket corpus's invented site codes (scripts/ticket_phrases.py,
# SITE_WEIGHTS). A test checks the two lists agree.
SITES = ["HBT", "KTF", "MRB", "SHZ", "TMQ", "WQR", "ZFL"]

# Seed history runs from here to SEED_END. "Today" for the ERP.
HISTORY_START = date(2024, 1, 1)
SEED_END = date(2026, 9, 20)

# Every ERP timestamp carries the Gulf offset, so a timestamp written by
# the seed and one written by the API read the same way.
UTC_OFFSET = "+04:00"

EQUIPMENT_PER_SITE = 12

# Days from "raised" to "target", by priority. Also used by the API.
TARGET_DAYS = {1: 0, 2: 2, 3: 7, 4: 28}

# ---------------------------------------------------------------------
# Equipment types, keyed by tag prefix (the same prefixes the ticket
# generator uses: scripts/ticket_phrases.py PLANT_TAG_PREFIXES).
# ---------------------------------------------------------------------

EQUIPMENT_TYPES = {
    "P": {
        "equipment_type": "pump",
        "services": ["Crude transfer pump", "Produced water injection pump",
                     "Condensate booster pump", "Lube oil pump", "Firewater jockey pump",
                     "Chemical injection pump"],
        "manufacturers": {"Veltrane Pumps": "VP", "Kalvik Fluidworks": "KF"},
    },
    "K": {
        "equipment_type": "compressor",
        "services": ["Gas lift compressor", "Instrument air compressor",
                     "Flash gas compressor", "Export gas booster compressor"],
        "manufacturers": {"Halvard Compression": "HC", "Tessmar Rotating": "TR"},
    },
    "HX": {
        "equipment_type": "heat_exchanger",
        "services": ["Crude/crude heat exchanger", "Gas cooler",
                     "Lean/rich amine exchanger", "Condensate cooler"],
        "manufacturers": {"Quenby Thermal": "QT", "Brekka Fabrication": "BF"},
    },
    "E": {
        "equipment_type": "air_cooler",
        "services": ["Air-cooled exchanger, export gas", "Air-cooled exchanger, lube oil",
                     "Air-cooled exchanger, compressor discharge"],
        "manufacturers": {"Quenby Thermal": "QT"},
    },
    "V": {
        "equipment_type": "vessel",
        "services": ["Production separator", "Test separator", "Knock-out drum",
                     "Flare knock-out drum"],
        "manufacturers": {"Brekka Fabrication": "BF"},
    },
    "C": {
        "equipment_type": "column",
        "services": ["Stabiliser column", "Amine contactor", "Glycol contactor"],
        "manufacturers": {"Brekka Fabrication": "BF"},
    },
    "T": {
        "equipment_type": "tank",
        "services": ["Crude storage tank", "Diesel day tank", "Produced water tank"],
        "manufacturers": {"Brekka Fabrication": "BF"},
    },
    "FV": {
        "equipment_type": "control_valve",
        "services": ["Flow control valve, export line", "Flow control valve, fuel gas",
                     "Flow control valve, injection header"],
        "manufacturers": {"Duvane Controls": "DC", "Sorvik Valves": "SV"},
    },
}

# What goes wrong, what was done, what was used - by equipment type.
# (failure mode, action taken, [(part number, description, quantity)])
# Part numbers are NN-NNNN-NN on purpose: nothing like an equipment tag.
FAILURES = {
    "pump": [
        ("mechanical seal leak", "Replaced mechanical seal cartridge, flushed seal plan, checked alignment",
         [("30-2201-01", "Mechanical seal cartridge", 1), ("31-0415-01", "O-ring kit", 1)]),
        ("bearing overheating", "Replaced drive end bearing, renewed lube oil, trended temperature 24 h",
         [("32-6312-01", "Bearing 6312 C3", 1), ("33-0046-01", "Lube oil ISO VG 46, 20 L", 1)]),
        ("high vibration", "Laser aligned pump and motor, replaced coupling element",
         [("34-0110-01", "Coupling element", 1)]),
        ("cavitation", "Cleaned suction strainer, confirmed NPSH margin with operations", []),
        ("impeller wear", "Replaced impeller and wear rings",
         [("35-3040-01", "Impeller", 1), ("36-3041-01", "Wear ring set", 1)]),
    ],
    "compressor": [
        ("high discharge temperature", "Cleaned intercooler, replaced discharge valve",
         [("37-7710-01", "Discharge valve assembly", 1)]),
        ("low lube oil pressure", "Replaced lube oil filter, repaired pressure switch",
         [("38-0220-01", "Lube oil filter element", 2), ("39-0031-01", "Pressure switch", 1)]),
        ("high vibration", "Balanced impeller, replaced journal bearing",
         [("40-1180-01", "Journal bearing", 1)]),
        ("surge trip", "Recalibrated anti-surge valve positioner, reviewed trip log", []),
    ],
    "heat_exchanger": [
        ("tube leak", "Located and plugged two leaking tubes, hydrotested",
         [("41-0019-01", "Tube plug", 4)]),
        ("fouling, high pressure drop", "Hydrojetted tube bundle, reinstalled", []),
        ("gasket leak", "Replaced channel cover gasket, retorqued",
         [("42-0908-01", "Spiral wound gasket", 2)]),
    ],
    "air_cooler": [
        ("fan belt failure", "Replaced fan belts, set tension",
         [("43-0520-01", "Fan belt set", 1)]),
        ("fin fouling", "Water washed fin banks", []),
        ("fan motor trip", "Replaced fan motor bearing, megger tested motor",
         [("44-6205-01", "Bearing 6205", 2)]),
    ],
    "vessel": [
        ("level transmitter fault", "Replaced level transmitter, recalibrated",
         [("45-4100-01", "Level transmitter", 1)]),
        ("relief valve passing", "Removed PSV for bench test, fitted spare",
         [("46-0112-01", "Pressure safety valve, spare", 1)]),
        ("internal corrosion found", "Recorded wall thickness, scheduled repair at next shutdown", []),
    ],
    "column": [
        ("level control unstable", "Retuned level controller, checked control valve stroke", []),
        ("tray damage suspected", "Gamma scan arranged, results within limits", []),
        ("corrosion under insulation", "Stripped insulation, cleaned and painted, reinsulated",
         [("47-0075-01", "Insulation, 75 mm, per m2", 6)]),
    ],
    "tank": [
        ("roof seal damage", "Replaced floating roof seal section",
         [("48-2200-01", "Roof seal section", 3)]),
        ("level gauge fault", "Replaced radar level gauge",
         [("49-0810-01", "Radar level gauge", 1)]),
        ("bottom corrosion found", "Recorded pitting, scheduled bottom repair", []),
    ],
    "control_valve": [
        ("valve hunting", "Replaced positioner, stroke tested",
         [("50-0340-01", "Valve positioner", 1)]),
        ("packing leak", "Repacked stem, retorqued gland",
         [("51-0022-01", "Stem packing set", 1)]),
        ("actuator air leak", "Replaced actuator diaphragm",
         [("52-0150-01", "Actuator diaphragm", 1)]),
        ("valve sticking", "Cleaned trim, lubricated stem, stroke tested", []),
    ],
}

PREVENTIVE_ACTIONS = [
    "Routine PM: lubricated, checked alignment, vibration within limits",
    "PM done per plan. no defects",
    "Quarterly PM completed, filters changed",
    "PM: checked and cleaned, all readings normal",
]
PREVENTIVE_PARTS = [("53-0100-01", "Filter element", 1)]

INSPECTION_ACTIONS = [
    "Annual inspection, no findings",
    "Statutory inspection complete, certificate renewed",
    "Inspection: minor external corrosion noted, paint touch-up requested",
    "Thickness survey done, readings within limits",
]

CREW_BY_TYPE = {
    "pump": "rotating equipment crew", "compressor": "rotating equipment crew",
    "heat_exchanger": "static equipment crew", "air_cooler": "mechanical crew",
    "vessel": "static equipment crew", "column": "static equipment crew",
    "tank": "static equipment crew", "control_valve": "instrument crew",
}

REQUESTERS = ["Operations shift supervisor", "Control room operator", "Reliability engineer",
              "Area operator", "Maintenance supervisor"]

# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------

PLANT_TAG = re.compile(r"\b(?:HX|FV|P|K|V|C|E|T)-\d{4}[AB]?\b")
WORK_ORDER = re.compile(r"\bWO-\d{6}\b")


def tag_prefix(tag):
    return tag.split("-")[0]


def stamp(day, hour, minute):
    """ISO 8601 local time with the Gulf offset: 2026-05-18T07:40:00+04:00."""
    moment = datetime(day.year, day.month, day.day, hour, minute)
    return moment.isoformat() + UTC_OFFSET


def random_day(rng, start, end):
    span = (end - start).days
    return start + timedelta(days=rng.randrange(span + 1))


def work_hours_stamp(rng, day):
    return stamp(day, rng.randrange(6, 16), rng.randrange(60))


# ---------------------------------------------------------------------
# 1. What the ticket corpus mentions
# ---------------------------------------------------------------------


def read_ticket_mentions(tickets_path):
    """Plant tags and work orders the tickets mention, in ticket order.

    Returns (tags, work_orders):
      tags         {tag: site of the first ticket that mentions it}
      work_orders  [{"work_order_id", "tag" or None, "site", "ticket_id", "created"}]
    """
    tags = {}
    work_orders = []
    seen_work_orders = set()
    with open(tickets_path, encoding="utf-8") as handle:
        for line in handle:
            ticket = json.loads(line)
            text = ticket["subject"] + "\n" + ticket["body"]
            tags_here = PLANT_TAG.findall(text)
            for tag in tags_here:
                tags.setdefault(tag, ticket["site"])
            for work_order_id in WORK_ORDER.findall(text):
                if work_order_id in seen_work_orders:
                    continue
                seen_work_orders.add(work_order_id)
                work_orders.append({
                    "work_order_id": work_order_id,
                    "tag": tags_here[0] if tags_here else None,
                    "site": ticket["site"],
                    "ticket_id": ticket["ticket_id"],
                    "created": ticket["created"][:10],
                })
    return tags, work_orders


# ---------------------------------------------------------------------
# 2. Equipment master
# ---------------------------------------------------------------------


def make_equipment(rng, tag, site, service=None, status=None, criticality=None):
    kind = EQUIPMENT_TYPES[tag_prefix(tag)]
    equipment_type = kind["equipment_type"]
    manufacturer = rng.choice(sorted(kind["manufacturers"]))
    model_prefix = kind["manufacturers"][manufacturer]
    install_year = rng.randrange(2008, 2023)
    install_date = date(install_year, rng.randrange(1, 13), rng.randrange(1, 29))
    return {
        "tag": tag,
        "site": site,
        "unit": tag.split("-")[1][:2],
        "equipment_type": equipment_type,
        "description": service or rng.choice(kind["services"]),
        "manufacturer": manufacturer,
        "model": f"{model_prefix}-{rng.randrange(10, 90) * 10}",
        "serial_number": f"{model_prefix}{install_year}-{rng.randrange(10000, 100000)}",
        "rating": make_rating(rng, equipment_type),
        "install_date": install_date.isoformat(),
        "criticality": criticality or rng.choice(["A", "B", "B", "C", "C"]),
        "status": status or ("standby" if tag.endswith("B") else rng.choice(
            ["in_service"] * 9 + ["out_of_service"])),
    }


def make_rating(rng, equipment_type):
    if equipment_type == "pump":
        return f"{rng.randrange(20, 400)} m3/h at {rng.randrange(40, 300)} m head"
    if equipment_type == "compressor":
        return f"{rng.randrange(8, 120) * 50} kW"
    if equipment_type in ("heat_exchanger", "air_cooler"):
        return f"{rng.randrange(5, 120) / 10} MW duty"
    if equipment_type in ("vessel", "column"):
        return f"design {rng.randrange(5, 90)} barg"
    if equipment_type == "tank":
        return f"{rng.randrange(2, 60) * 500} m3"
    return f"Class {rng.choice([150, 300, 600])}, {rng.choice([2, 3, 4, 6, 8])} in"


def make_new_tag(rng, taken):
    while True:
        prefix = rng.choice(sorted(EQUIPMENT_TYPES))
        tag = f"{prefix}-{rng.randrange(1001, 4600)}{rng.choice(['', '', 'A', 'B'])}"
        if tag not in taken:
            return tag


def build_equipment(rng, ticket_tags):
    equipment = {}

    # The brief 4 pump and its standby twin.
    equipment["P-1201A"] = make_equipment(rng, "P-1201A", "MRB", service="Crude transfer pump",
                                          status="in_service", criticality="A")
    equipment["P-1201B"] = make_equipment(rng, "P-1201B", "MRB", service="Crude transfer pump",
                                          status="standby", criticality="A")

    # Every plant tag a ticket mentions.
    for tag in sorted(ticket_tags):
        if tag not in equipment:
            equipment[tag] = make_equipment(rng, tag, ticket_tags[tag])

    # Top every site up to EQUIPMENT_PER_SITE.
    for site in SITES:
        while sum(1 for item in equipment.values() if item["site"] == site) < EQUIPMENT_PER_SITE:
            tag = make_new_tag(rng, equipment)
            equipment[tag] = make_equipment(rng, tag, site)

    return [equipment[tag] for tag in sorted(equipment)]


# ---------------------------------------------------------------------
# 3. Completed work (maintenance history) and its work orders
# ---------------------------------------------------------------------


def make_history_event(rng, item, day):
    """One piece of completed work on one piece of equipment."""
    work_type = rng.choice(["corrective", "corrective", "preventive", "preventive", "inspection"])
    if work_type == "corrective":
        failure_mode, action, parts = rng.choice(FAILURES[item["equipment_type"]])
        downtime = round(rng.uniform(2, 36), 1)
        priority = rng.choice([1, 2, 2, 3])
    elif work_type == "preventive":
        failure_mode, action = None, rng.choice(PREVENTIVE_ACTIONS)
        parts = PREVENTIVE_PARTS if rng.random() < 0.5 else []
        downtime = round(rng.uniform(0, 6), 1)
        priority = 4
    else:
        failure_mode, action, parts = None, rng.choice(INSPECTION_ACTIONS), []
        downtime = 0.0
        priority = 4
    return {
        "item": item, "day": day, "work_type": work_type, "failure_mode": failure_mode,
        "action_taken": action, "parts": parts, "downtime_hours": downtime, "priority": priority,
    }


def title_for(event):
    item = event["item"]
    if event["work_type"] == "corrective":
        return f"{item['tag']} {event['failure_mode']}"
    if event["work_type"] == "preventive":
        return f"{item['tag']} planned maintenance"
    return f"{item['tag']} inspection"


def description_for(event):
    item = event["item"]
    if event["work_type"] == "corrective":
        return (f"{item['description']} {item['tag']} at {item['site']}: {event['failure_mode']} "
                f"reported by operations. Investigate and repair.")
    if event["work_type"] == "preventive":
        return f"Planned maintenance on {item['description'].lower()} {item['tag']} per the PM plan."
    return f"Scheduled inspection of {item['description'].lower()} {item['tag']}."


def brief4_events(equipment_by_tag):
    """The story brief 4 depends on, written out by hand."""
    pump = equipment_by_tag["P-1201A"]
    return [
        {"item": pump, "day": date(2025, 2, 9), "work_type": "corrective",
         "failure_mode": "bearing overheating",
         "action_taken": "Replaced drive end bearing, renewed lube oil, trended temperature 24 h",
         "parts": [("32-6312-01", "Bearing 6312 C3", 1), ("33-0046-01", "Lube oil ISO VG 46, 20 L", 1)],
         "downtime_hours": 9.5, "priority": 2},
        {"item": pump, "day": date(2025, 11, 3), "work_type": "preventive", "failure_mode": None,
         "action_taken": "Routine PM: lubricated, checked alignment, vibration within limits",
         "parts": [], "downtime_hours": 3.0, "priority": 4},
        {"item": pump, "day": date(2026, 5, 18), "work_type": "corrective",
         "failure_mode": "mechanical seal leak",
         "action_taken": "Replaced mechanical seal cartridge, flushed seal plan, checked alignment. "
                         "Seal faces scored, suspect dry running at start-up",
         "parts": [("30-2201-01", "Mechanical seal cartridge", 1), ("31-0415-01", "O-ring kit", 1)],
         "downtime_hours": 14.0, "priority": 2, "work_order_id": "WO-118305"},
    ]


def assign_work_order_ids(events, reserved):
    """History work orders get numbers that rise with the date.

    Roughly 9.55 numbers a day since HISTORY_START (other crafts and
    sites use the numbers in between), so WO-118305 sits in May 2026
    among its neighbours. Numbers already used elsewhere are skipped.
    """
    used = set(reserved)
    previous = 0
    for event in events:
        if "work_order_id" in event:
            continue
        days = (event["day"] - HISTORY_START).days
        number = max(previous + 1, 110000 + int(days * 9.55))
        while f"WO-{number:06d}" in used:
            number += 1
        event["work_order_id"] = f"WO-{number:06d}"
        used.add(event["work_order_id"])
        previous = number


def build_history(rng, equipment):
    equipment_by_tag = {item["tag"]: item for item in equipment}
    events = brief4_events(equipment_by_tag)
    for item in equipment:
        if item["tag"] == "P-1201A":
            continue
        for _ in range(rng.randrange(1, 6)):
            day = random_day(rng, HISTORY_START, SEED_END - timedelta(days=10))
            events.append(make_history_event(rng, item, day))
    events.sort(key=lambda event: (event["day"], event["item"]["tag"]))
    return events


def history_to_records(rng, events):
    """Turn completed events into (work orders, maintenance records)."""
    work_orders = []
    records = []
    for number, event in enumerate(events, start=1):
        item = event["item"]
        completed = event["day"]
        raised = completed - timedelta(days=rng.randrange(0, 5) if event["priority"] < 3
                                       else rng.randrange(3, 20))
        work_orders.append({
            "work_order_id": event["work_order_id"],
            "equipment_tag": item["tag"],
            "site": item["site"],
            "work_type": event["work_type"],
            "priority": event["priority"],
            "status": "completed",
            "title": title_for(event),
            "description": description_for(event),
            "requested_by": f"{rng.choice(REQUESTERS)}, {item['site']}",
            "approved_by": f"Maintenance planner, {item['site']}",
            "source_ticket": None,
            "raised_via": "erp_screen",
            "created": work_hours_stamp(rng, raised),
            "target_date": (raised + timedelta(days=TARGET_DAYS[event["priority"]])).isoformat(),
            "completed_date": completed.isoformat(),
        })
        records.append({
            "record_id": f"MH-{number:06d}",
            "equipment_tag": item["tag"],
            "site": item["site"],
            "work_order_id": event["work_order_id"],
            "date": completed.isoformat(),
            "work_type": event["work_type"],
            "failure_mode": event["failure_mode"],
            "action_taken": event["action_taken"],
            "parts": [{"part_number": part, "description": text, "quantity": quantity}
                      for part, text, quantity in event["parts"]],
            "downtime_hours": event["downtime_hours"],
            "performed_by": f"{item['site']} {CREW_BY_TYPE[item['equipment_type']]}",
        })
    return work_orders, records


# ---------------------------------------------------------------------
# 4. Work that is not finished yet
# ---------------------------------------------------------------------


def open_work_order(rng, item, work_order_id, raised_day, status, title=None, description=None,
                    work_type=None, priority=None):
    work_type = work_type or rng.choice(["corrective", "corrective", "preventive", "inspection"])
    if priority is None:
        priority = rng.choice([2, 3, 3]) if work_type == "corrective" else 4
    if title is None:
        if work_type == "corrective":
            failure_mode = rng.choice(FAILURES[item["equipment_type"]])[0]
            title = f"{item['tag']} {failure_mode}"
            description = (f"{item['description']} {item['tag']} at {item['site']}: "
                           f"{failure_mode} reported by operations. Investigate and repair.")
        elif work_type == "preventive":
            title = f"{item['tag']} planned maintenance"
            description = f"Planned maintenance on {item['description'].lower()} {item['tag']} per the PM plan."
        else:
            title = f"{item['tag']} inspection"
            description = f"Scheduled inspection of {item['description'].lower()} {item['tag']}."
    return {
        "work_order_id": work_order_id,
        "equipment_tag": item["tag"],
        "site": item["site"],
        "work_type": work_type,
        "priority": priority,
        "status": status,
        "title": title,
        "description": description,
        "requested_by": f"{rng.choice(REQUESTERS)}, {item['site']}",
        "approved_by": f"Maintenance planner, {item['site']}",
        "source_ticket": None,
        "raised_via": "erp_screen",
        "created": work_hours_stamp(rng, raised_day),
        "target_date": (raised_day + timedelta(days=TARGET_DAYS[priority])).isoformat(),
        "completed_date": None,
    }


def build_open_work(rng, equipment, ticket_work_orders, used_ids):
    equipment_by_tag = {item["tag"]: item for item in equipment}
    work_orders = []

    # The work orders the tickets mention: "AssetHive will not open
    # WO-131192 for HX-2629". They exist, on the tag the ticket names,
    # raised a few days before the ticket.
    # A ticket with a work order but no tag gets equipment at its own site.
    # Work that old tickets mention is finished; recent ones are still open.
    for mention in ticket_work_orders:
        tag = mention["tag"]
        if tag is None:
            site_tags = sorted(item["tag"] for item in equipment if item["site"] == mention["site"])
            tag = site_tags[len(work_orders) % len(site_tags)]
        ticket_day = date.fromisoformat(mention["created"])
        raised_day = ticket_day - timedelta(days=rng.randrange(1, 6))
        if ticket_day < date(2026, 7, 1):
            status = "completed"
        else:
            status = rng.choice(["released", "in_progress"])
        order = open_work_order(rng, equipment_by_tag[tag], mention["work_order_id"], raised_day, status)
        if status == "completed":
            order["completed_date"] = (ticket_day + timedelta(days=rng.randrange(1, 10))).isoformat()
        work_orders.append(order)
        used_ids.add(mention["work_order_id"])

    # Current work across the sites, raised in the last six weeks.
    # Every out-of-service item has one open corrective work order.
    # Numbers carry on from the newest history work order.
    history_numbers = [int(work_order_id[3:]) for work_order_id in used_ids
                       if int(work_order_id[3:]) < 120000]
    next_number = max(history_numbers) + 40
    candidates = [item for item in equipment if item["tag"] not in ("P-1201A", "P-1201B")]
    chosen = [item for item in candidates if item["status"] == "out_of_service"]
    others = [item for item in candidates if item["status"] != "out_of_service"]
    rng.shuffle(others)
    chosen += others[:24]
    chosen.sort(key=lambda item: item["tag"])
    for item in chosen:
        while f"WO-{next_number:06d}" in used_ids:
            next_number += 1
        work_order_id = f"WO-{next_number:06d}"
        used_ids.add(work_order_id)
        next_number += rng.randrange(2, 12)
        raised_day = random_day(rng, SEED_END - timedelta(days=42), SEED_END)
        if item["status"] == "out_of_service":
            order = open_work_order(rng, item, work_order_id, raised_day, "in_progress",
                                    work_type="corrective", priority=2)
        else:
            order = open_work_order(rng, item, work_order_id, raised_day,
                                    rng.choice(["released", "released", "in_progress", "on_hold"]))
        work_orders.append(order)

    # Two cancelled ones, so the status is not only theoretical.
    for item in others[24:26]:
        work_order_id = f"WO-{next_number:06d}"
        used_ids.add(work_order_id)
        next_number += 3
        raised_day = random_day(rng, SEED_END - timedelta(days=60), SEED_END - timedelta(days=30))
        order = open_work_order(rng, item, work_order_id, raised_day, "cancelled")
        order["title"] += " (duplicate)"
        work_orders.append(order)

    return work_orders


# ---------------------------------------------------------------------
# 5. Put it together
# ---------------------------------------------------------------------


def build_seed(seed, tickets_path):
    rng = random.Random(seed)
    ticket_tags, ticket_work_orders = read_ticket_mentions(tickets_path)

    equipment = build_equipment(rng, ticket_tags)

    events = build_history(rng, equipment)
    reserved = {mention["work_order_id"] for mention in ticket_work_orders} | {"WO-118305"}
    assign_work_order_ids(events, reserved)
    history_orders, records = history_to_records(rng, events)

    used_ids = {order["work_order_id"] for order in history_orders}
    current_orders = build_open_work(rng, equipment, ticket_work_orders, used_ids)

    work_orders = sorted(history_orders + current_orders, key=lambda order: order["work_order_id"])
    return {
        "equipment": equipment,
        "work_orders": work_orders,
        "maintenance_history": records,
    }


def write_seed(data, out_dir):
    """One JSON file per resource, LF line endings, stable key order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows in data.items():
        path = out_dir / f"{name}.json"
        text = json.dumps(rows, indent=1, ensure_ascii=True) + "\n"
        path.write_bytes(text.encode("ascii"))
        written.append((path, len(rows)))
    return written


def main():
    parser = argparse.ArgumentParser(description="Generate the mock ERP seed data.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tickets", type=Path, default=DEFAULT_TICKETS,
                        help="ticket corpus to take plant tags and work orders from")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    data = build_seed(args.seed, args.tickets)
    for path, count in write_seed(data, args.out):
        print(f"wrote {count:4d} rows  {path}")


if __name__ == "__main__":
    main()
