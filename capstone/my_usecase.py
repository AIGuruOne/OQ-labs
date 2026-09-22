"""YOUR use case. This is the file your group edits.

The scaffold (capstone/wiring.py) runs every ticket through five steps.
Four of them are functions below; the model call in the middle is the
scaffold's, through the endpoint switch, so the model can change without
this file changing.

    1. gather_context(ticket, tools)      -> what you look up first
    2. build_messages(ticket, context)    -> what the model is sent
       [the scaffold calls the model, logs the call, enforces the cost cap]
    3. check_output(reply, ...)           -> is the reply usable?
    4. decide(output, validation, ...)    -> what happens next (never a silent write)
    5. the SETTINGS block                 -> names, model, your index, your adapter, cost cap

As shipped it is the STARTER: ticket in, the seven-field record out,
with similar past tickets and the equipment master shown beside it.
It runs as-is. capstone/examples/brief5_similar_tickets.py is the same
file after a group built brief 5 on it - read it for a worked example.

Run it:   python -m capstone.run ticket INC-005310
Score it: python -m capstone.run eval
"""

import json

from jsonschema import Draft202012Validator

from capstone.wiring import REPO_ROOT      # also puts notebooks/ on the import path
import dataset_utils  # noqa: E402

# ===========================================================================
# 5. SETTINGS
# ===========================================================================

GROUP = "group-0"                    # your group name; goes in every audit line
SYSTEM_ID = "SYS-CAPSTONE-00"        # your governance template 1 id
USE_CASE = "Starter: ticket to structured record, with similar tickets and equipment"
PROMPT_VERSION = "starter-1"         # change it whenever build_messages changes

ENDPOINT = None                      # None = LLM_ENDPOINT from .env, or "local" / "hosted" / "tuned"
MY_INDEX = None                      # None = the reference index. Or "path/to/index.json",
                                     # or "your.module:make_index" (see reference_index/adapter_example.py)
MY_ADAPTER_DIR = None                # None = the pre-baked adapter. Or your notebook 05 adapter folder

NEIGHBOURS = 3                       # similar past tickets to look up
COST_CAP_USD_PER_MONTH = 5.00        # hosted calls stop when the month's estimate reaches this
# $ per million tokens for the hosted model. From facilitator/cost_model.xlsx (gpt-5.4-mini row);
# the default hosted model (gpt-4o-mini) is not in the cost model, so this is an ESTIMATE.
HOSTED_PRICE_PER_MTOK = {"input": 0.75, "output": 4.50}

SCHEMA = dataset_utils.load_schema(REPO_ROOT / "data" / "finetune" / "ticket_schema.json")
VALIDATOR = Draft202012Validator(SCHEMA)


# ===========================================================================
# 1. What to look up before asking the model
# ===========================================================================

def gather_context(ticket, tools):
    """tools.search(query, k, filters) -> Contract 5 hits
       tools.plant_tags(text)          -> ["P-1201A", ...]
       tools.equipment(tag)            -> the equipment record via MCP, or {"tag", "error"}"""
    neighbours = tools.search(ticket["text"], k=NEIGHBOURS)

    equipment = []
    for tag in tools.plant_tags(ticket["text"]):
        equipment.append(tools.equipment(tag))

    return {"neighbours": neighbours, "equipment": equipment}


# ===========================================================================
# 2. What the model is sent
# ===========================================================================

def build_messages(ticket, context):
    """The starter sends the ticket exactly as the model was trained and scored on it
    (Day 2): the neighbours and equipment are shown to the PERSON, not the model."""
    return [
        {"role": "system", "content": dataset_utils.SYSTEM_PROMPT},
        {"role": "user", "content": ticket["text"]},
    ]


# ===========================================================================
# 3. Is the reply usable?
# ===========================================================================

def check_output(reply, ticket, context):
    """Returns (output, validation). output is None when the reply cannot be used."""
    try:
        record = json.loads(reply)
    except json.JSONDecodeError:
        return None, {"valid": False, "problems": ["the reply is not JSON"]}
    if not isinstance(record, dict):
        return None, {"valid": False, "problems": ["the reply is JSON but not an object"]}

    problems = []
    for error in VALIDATOR.iter_errors(record):
        where = "/".join(str(part) for part in error.path) or "(record)"
        problems.append(f"{where}: {error.message}")

    # An asset tag that is not in the ticket was invented, even if its format is right.
    asset_tag = record.get("asset_tag")
    if asset_tag and asset_tag.lower() not in ticket["text"].lower():
        problems.append(f"asset_tag {asset_tag} is not in the ticket text (invented)")

    return record, {"valid": problems == [], "problems": problems}


# ===========================================================================
# 4. What happens next
# ===========================================================================

def decide(output, validation, ticket, context):
    """Nothing is ever applied here. A valid record is PROPOSED to a desk agent;
    anything else falls back to the empty form, with the reason logged."""
    if validation["valid"]:
        return {"action": "propose_to_agent", "why": "schema-valid, nothing invented"}
    return {"action": "empty_form", "why": "; ".join(validation["problems"])}
