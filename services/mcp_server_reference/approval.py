"""The approval gate on the one write, as an MCP 2026-07-28 Multi Round-Trip Request.

The server cannot call the client any more (2026-07-28 removed
server-initiated requests). So when `raise_work_order` needs a person's
approval it RETURNS the question, and the client asks the person and
calls the same tool again with the answer attached:

    round 1   client -> tools/call raise_work_order {arguments}
              server -> resultType "input_required"
                        inputRequests: {"approval": elicitation/create form}
                        requestState:  sealed by the SDK (see below)
    (the client shows the form to a person; they approve or reject)
    round 2   client -> tools/call raise_work_order {same arguments}
                        + inputResponses {"approval": {action, content}}
                        + requestState (echoed exactly)
              server -> the created work order, or a refusal

What the requestState is and who protects it: this module writes a
small JSON note (which arguments were shown, when, a one-time nonce).
The SDK's RequestStateBoundary seals it with AES-256-GCM before it
leaves, binds it to this method, this tool and a digest of these exact
arguments, gives it a 10-minute expiry, and refuses (JSON-RPC -32602)
any echo that was tampered with, expired, or sent with other
arguments. The spec requires that integrity; the SDK does it.

What this module adds on top, because the spec says a one-time
redemption MUST be enforced server-side: each approval can be used
ONCE. The used nonces are kept in memory (one process, the lab
default); several replicas would keep them in a shared store. With
OQ_MCP_STATE_KEY set, a restart within the 10 minutes forgets which
approvals were used - the ERP's own 409 on a repeated source_ticket is
then the only guard against a replay, so a production copy needs the
shared store.

What the gate does NOT prove: that a human answered. It proves the
server asked about these exact arguments and got a decision from the
client within 10 minutes, naming an approver on the allowed list. Who
typed it is the host application's job (and, in production, its login).
"""

import json
import threading
import uuid

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.request_state import RequestStateSecurity
from mcp_types import ElicitRequest, ElicitRequestFormParams, ElicitResult, InputRequiredResult

from services.mcp_server_reference import audit
from services.mcp_server_reference.erp_client import setting

APPROVAL_KEY = "approval"          # the key in inputRequests / inputResponses
STATE_VERSION = 1

_used_nonces = set()
_used_lock = threading.Lock()


class Refused(ToolError):
    """The write did not happen, on purpose. The audit line says 'refused'."""


def state_security():
    """How the SDK seals the requestState: AES-256-GCM, 10-minute expiry.

    OQ_MCP_STATE_KEY (a secret of at least 32 characters, from the
    environment or .env) lets a restarted server - or a second copy behind
    a load balancer - accept an approval the first one asked for. Without
    it a fresh key is made at start-up, so a restart forgets every
    pending approval (the lab default: one process)."""
    key = setting("OQ_MCP_STATE_KEY")
    if key:
        return RequestStateSecurity(keys=[key], ttl=600)
    return RequestStateSecurity.ephemeral(ttl=600)


def allowed_approvers():
    """Who may approve a work order: OQ_MCP_APPROVERS, comma-separated
    (governance template 4.4 names the people)."""
    text = setting("OQ_MCP_APPROVERS", "planner:salim,planner:aisha,planner:nasser")
    return [name.strip() for name in text.split(",") if name.strip()]


def approval_form_schema():
    """The form the person fills in. Flat, primitive fields only: that is
    what an elicitation form may contain."""
    return {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "title": "Decision", "enum": ["approve", "reject"]},
            "approver": {"type": "string", "title": "Approver", "enum": allowed_approvers()},
            "reason": {"type": "string", "title": "Reason (required, also for an approval)",
                       "minLength": 3, "maxLength": 200},
        },
        "required": ["decision", "approver", "reason"],
    }


def approval_message(proposal, evidence):
    """What the approver reads. Governance template 4.3: the exact action
    and its exact arguments, and the evidence behind it."""
    request_text = json.dumps(proposal, indent=2, ensure_ascii=True)
    return (
        "APPROVAL NEEDED: raise_work_order writes to the ERP.\n"
        "If you approve, exactly this is sent (approved_by = the approver you pick):\n"
        f"POST /work-orders\n{request_text}\n\n"
        f"What the server checked: {evidence}\n"
        "A work order is released to the site crew at once. The API cannot change, "
        "cancel or delete it afterwards."
    )


def client_can_show_forms(ctx):
    """The spec: never send an elicitation to a client that did not declare it."""
    capabilities = ctx.client_capabilities
    if capabilities is None or capabilities.elicitation is None:
        return False
    return capabilities.elicitation.form is not None or capabilities.elicitation.url is None


def ask(ctx, proposal, evidence):
    """Round 1: return the question instead of writing."""
    if not client_can_show_forms(ctx):
        audit.note(status="refused",
                   approval={"required": True, "decision": "rejected", "by": "server",
                             "ts": audit.utc_now(), "reason": "client cannot show an approval form"})
        raise Refused("this client did not declare the elicitation (form) capability, so it "
                      "cannot show a person the approval form. Use a client that can.")

    state = {
        "v": STATE_VERSION,
        "proposal_sha256": audit.sha256_of(proposal),
        "nonce": uuid.uuid4().hex,
        "asked_at": audit.utc_now(),
    }
    form = ElicitRequest(params=ElicitRequestFormParams(
        mode="form",
        message=approval_message(proposal, evidence),
        requested_schema=approval_form_schema(),
    ))
    audit.note(approval={"required": True, "decision": "pending", "by": None, "ts": None,
                         "reason": None})
    return InputRequiredResult(input_requests={APPROVAL_KEY: form},
                               request_state=json.dumps(state))


def answer_in(ctx):
    """Round 2's answer, or None if this is round 1."""
    responses = ctx.input_responses or {}
    return responses.get(APPROVAL_KEY)


def refuse(reason, decided_by="server"):
    audit.note(status="refused",
               approval={"required": True, "decision": "rejected", "by": decided_by,
                         "ts": audit.utc_now(), "reason": reason})
    if decided_by == "server":
        raise Refused(reason)
    raise Refused(f"rejected by {decided_by}: {reason} (nothing written)")


def use_once(nonce):
    """True the first time a nonce is presented, False ever after."""
    with _used_lock:
        if nonce in _used_nonces:
            return False
        _used_nonces.add(nonce)
        return True


def check(ctx, proposal, answer):
    """Round 2: return the approver's name, or refuse. Every refusal is logged."""
    if ctx.request_state is None:
        refuse("an approval arrived without the server's requestState: the server never "
               "asked this question, so this is not an approval")
    try:
        state = json.loads(ctx.request_state)
    except ValueError:
        refuse("the requestState is not one this server wrote")
    if state.get("v") != STATE_VERSION:
        refuse("the requestState is from another version of this server")
    if state.get("proposal_sha256") != audit.sha256_of(proposal):
        refuse("the approval was given for different arguments")
    if not use_once(state.get("nonce")):
        refuse("this approval was already used once; a replayed approval is refused")

    if not isinstance(answer, ElicitResult):
        refuse("the answer to the approval question is not a form answer")
    if answer.action == "decline":
        refuse("the person declined to answer the approval form (nothing written)")
    if answer.action != "accept":
        refuse("the person cancelled the approval form (nothing written)")

    content = answer.content or {}
    decision = content.get("decision")
    approver = content.get("approver")
    reason = str(content.get("reason") or "").strip()
    if approver not in allowed_approvers():
        refuse(f"'{approver}' is not on the approver list (OQ_MCP_APPROVERS)")
    if decision not in ("approve", "reject") or len(reason) < 3:
        refuse("the approval form came back incomplete: decision and a reason are required")
    if decision == "reject":
        refuse(reason, decided_by=approver)

    audit.note(approval={"required": True, "decision": "approved", "by": approver,
                         "ts": audit.utc_now(), "reason": reason})
    return approver
