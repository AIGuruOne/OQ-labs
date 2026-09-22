"""Brief 5, similar-ticket assist: the starter AFTER a group built on it.

This is capstone/my_usecase.py with the five extension points filled in
for brief 5 (facilitator/use_case_briefs.md). What the group changed:

    SETTINGS         names, prompt version "brief5-1", 5 neighbours
    gather_context   each neighbour carries how the desk handled it (queue and
                     action from ticket_labels.jsonl - the resolution field a real
                     desk has) and NOT its body, which holds the requester's name
    build_messages   the model sees the ticket AND the five neighbours
    check_output     + an invented routing queue is a problem, not a proposal
    decide           the proposal carries its evidence; model and neighbour vote
                     are compared; a model failure falls back to the vote alone

Run it:   python -m capstone.run ticket INC-005310 --usecase capstone.examples.brief5_similar_tickets
Score it: python -m capstone.run eval --usecase capstone.examples.brief5_similar_tickets
"""

import json

from jsonschema import Draft202012Validator

from capstone.wiring import REPO_ROOT      # also puts notebooks/ on the import path
import dataset_utils  # noqa: E402

# ===========================================================================
# 5. SETTINGS
# ===========================================================================

GROUP = "group-5a"                   # your group name; goes in every audit line
SYSTEM_ID = "SYS-DESK-05"            # your governance template 1 id
USE_CASE = "Brief 5: similar-ticket assist (neighbours + proposed queue with evidence)"
PROMPT_VERSION = "brief5-1"          # change it whenever build_messages changes

ENDPOINT = None                      # None = LLM_ENDPOINT from .env, or "local" / "hosted" / "tuned"
MY_INDEX = None                      # None = the reference index. Or "path/to/index.json",
                                     # or "your.module:make_index" (see reference_index/adapter_example.py)
MY_ADAPTER_DIR = None                # None = the pre-baked adapter. Or your notebook 05 adapter folder

NEIGHBOURS = 5                       # similar past tickets to look up
COST_CAP_USD_PER_MONTH = 5.00        # hosted calls stop when the month's estimate reaches this
# $ per million tokens for the hosted model. From facilitator/cost_model.xlsx (gpt-5.4-mini row);
# the default hosted model (gpt-4o-mini) is not in the cost model, so this is an ESTIMATE.
HOSTED_PRICE_PER_MTOK = {"input": 0.75, "output": 4.50}

SCHEMA = dataset_utils.load_schema(REPO_ROOT / "data" / "finetune" / "ticket_schema.json")
VALIDATOR = Draft202012Validator(SCHEMA)

# The queues the desk has (Contract 1). The schema leaves routing_queue a free string.
KNOWN_QUEUES = ["identity_access", "end_user_computing", "network_ops", "erp_support",
                "apps_support", "telecom_voice", "security_ops", "service_desk_l1"]

# How each past ticket was handled. The held-out 20 are not in the index, so an
# eval on them cannot look up its own answer.
LABELS_FILE = REPO_ROOT / "data" / "finetune" / "ticket_labels.jsonl"
HANDLED = {}
for label in dataset_utils.load_jsonl(LABELS_FILE):
    HANDLED[label["ticket_id"]] = label["record"]


# ===========================================================================
# 1. What to look up before asking the model
# ===========================================================================

def gather_context(ticket, tools):
    """tools.search(query, k, filters) -> Contract 5 hits
       tools.plant_tags(text)          -> ["P-1201A", ...]
       tools.equipment(tag)            -> the equipment record via MCP, or {"tag", "error"}"""
    hits = tools.search(ticket["text"], k=NEIGHBOURS)

    # What a desk agent may see of a past ticket: subject, queue, action. Never the body.
    neighbours = []
    for hit in hits:
        handled = HANDLED[hit["doc_id"]]
        neighbours.append({
            "doc_id": hit["doc_id"],
            "score": hit["score"],
            "metadata": {"title": hit["metadata"]["title"]},
            "routing_queue": handled["routing_queue"],
            "requested_action": handled["requested_action"],
        })

    # The neighbours' vote: the most common queue, ties to the higher-ranked neighbour.
    queues = [neighbour["routing_queue"] for neighbour in neighbours]
    vote = None
    for queue in queues:
        if vote is None or queues.count(queue) > queues.count(vote):
            vote = queue

    equipment = []
    for tag in tools.plant_tags(ticket["text"]):
        equipment.append(tools.equipment(tag))

    return {"neighbours": neighbours, "vote": vote, "equipment": equipment}


# ===========================================================================
# 2. What the model is sent
# ===========================================================================

def build_messages(ticket, context):
    """The ticket, then the neighbours as reference. The system prompt is unchanged,
    so the reply is still the seven-field record the harness scores."""
    lines = ["", "---", "Similar past tickets and how the desk handled them (reference only):"]
    for number, neighbour in enumerate(context["neighbours"], start=1):
        lines.append(f'{number}. "{neighbour["metadata"]["title"]}" -> routing_queue: '
                     f'{neighbour["routing_queue"]}; requested_action: {neighbour["requested_action"]}')
    user_text = ticket["text"] + "\n".join(lines)
    return [
        {"role": "system", "content": dataset_utils.SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
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

    queue = record.get("routing_queue")
    if queue not in KNOWN_QUEUES:
        problems.append(f"routing_queue {queue!r} is not a queue the desk has (invented)")

    return record, {"valid": problems == [], "problems": problems}


# ===========================================================================
# 4. What happens next
# ===========================================================================

def decide(output, validation, ticket, context):
    """Nothing is applied: the agent sees a proposed queue WITH its evidence and chooses."""
    evidence = [f'{n["doc_id"]} {n["routing_queue"]}' for n in context["neighbours"]]
    vote = context["vote"]

    if not validation["valid"]:
        return {"action": "show_neighbours_only", "why": "; ".join(validation["problems"]),
                "proposed_queue": vote, "proposed_by": "neighbour vote", "evidence": evidence}

    model_queue = output["routing_queue"]
    if model_queue == vote:
        return {"action": "propose_queue", "why": "model and neighbours agree",
                "proposed_queue": model_queue, "proposed_by": "model + neighbours", "evidence": evidence}
    return {"action": "agent_chooses", "why": f"model says {model_queue}, neighbours say {vote}",
            "proposed_queue": model_queue, "proposed_by": "model (neighbours disagree)",
            "evidence": evidence}
