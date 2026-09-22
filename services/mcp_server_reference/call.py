"""Talk to the MCP server by hand and see every byte: headers and bodies.

    python -m services.mcp_server_reference.call discover
    python -m services.mcp_server_reference.call list
    python -m services.mcp_server_reference.call get_equipment tag=P-1201A
    python -m services.mcp_server_reference.call get_maintenance_history tag=P-1201A limit=3
    python -m services.mcp_server_reference.call raise_work_order --args-file wo.json
    python -m services.mcp_server_reference.call raise_work_order --args-file wo.json \
        --approve planner:salim --reason "seal history checked"

No SDK on this side on purpose: this is what any HTTP client does to
speak MCP 2026-07-28. Each request is ONE POST to /mcp carrying:

  headers  MCP-Protocol-Version, Mcp-Method, and Mcp-Name for tools/call
  body     JSON-RPC 2.0; params._meta carries the protocol version,
           the client's name and its capabilities - every time, because
           there is no initialize and no session to remember them

A tool that answers `input_required` (the write) is handled the way the
spec says: show the person the form, then call AGAIN with a new id, the
same arguments, the answers in `inputResponses` and the `requestState`
echoed exactly. With --approve/--reject that answer comes from the
command line; without them you are asked at the terminal.

Options: --url (default MCP_SERVER_URL, else http://127.0.0.1:8100/mcp),
--brief (bodies only, no headers), --no-forms (declare no elicitation
capability: the server must then refuse the write).
Output is ASCII, at most 100 columns.
"""

import argparse
import itertools
import json
import os
import secrets
import sys
import textwrap

import requests

PROTOCOL_VERSION = "2026-07-28"
WIDTH = 100
MAX_TEXT = 72            # longer strings are cut when shown (the full value is still sent)
MAX_BODY_LINES = 45


def short(value):
    """A copy of a JSON value with long strings cut, for display only."""
    if isinstance(value, str) and len(value) > MAX_TEXT:
        first_line = value.splitlines()[0] if value.splitlines() else value
        return first_line[:MAX_TEXT - 20] + f"...[{len(value)} chars]"
    if isinstance(value, dict):
        return {key: short(item) for key, item in value.items()}
    if isinstance(value, list):
        return [short(item) for item in value]
    return value


def json_lines(value, indent=0, room=WIDTH - 6):
    """Pretty JSON that keeps any small object or list on one line."""
    pad = " " * indent
    inline = json.dumps(value, ensure_ascii=True)
    if len(pad) + len(inline) <= room or not isinstance(value, (dict, list)) or not value:
        return [pad + inline]
    if isinstance(value, dict):
        lines = [pad + "{"]
        for key, item in value.items():
            item_lines = json_lines(item, indent + 1, room)
            lines.append(pad + " " + json.dumps(key) + ": " + item_lines[0].lstrip())
            lines.extend(item_lines[1:])
            lines[-1] += ","
        lines[-1] = lines[-1][:-1]
        return lines + [pad + "}"]
    lines = [pad + "["]
    for item in value:
        item_lines = json_lines(item, indent + 1, room)
        lines.extend(item_lines)
        lines[-1] += ","
    lines[-1] = lines[-1][:-1]
    return lines + [pad + "]"]


def show_body(prefix, body):
    lines = json_lines(short(body))
    if len(lines) > MAX_BODY_LINES:
        lines = lines[:MAX_BODY_LINES] + [f"... ({len(lines) - MAX_BODY_LINES} more lines)"]
    for line in lines:
        print(f"{prefix} {line}"[:WIDTH])


def show_error_text(reply_json):
    """A failed tool call's message, in full: the body above cuts long strings,
    and this is the sentence a person (or the model) needs to read."""
    result = reply_json.get("result") or {}
    if not result.get("isError"):
        return
    for block in result.get("content", []):
        for piece in textwrap.wrap(block.get("text", ""), WIDTH - 12):
            print(f"<<< [error] {piece}")


class McpWire:
    """A minimal MCP 2026-07-28 client over plain HTTP, printing as it goes."""

    def __init__(self, url, client_name="oq-wire-client", forms=True, brief=False, quiet=False,
                 protocol_version=PROTOCOL_VERSION):
        self.url = url
        self.protocol_version = protocol_version
        self.client_name = client_name
        self.forms = forms
        self.brief = brief
        self.quiet = quiet
        self.ids = itertools.count(1)
        # One trace for everything this client does, so the audit lines of
        # both rounds of an approval share a trace_id.
        self.trace_id = secrets.token_hex(16)
        self.exchanges = []            # (request headers, request body, reply) for the record

    def meta(self):
        capabilities = {"elicitation": {"form": {}}} if self.forms else {}
        return {
            "io.modelcontextprotocol/protocolVersion": self.protocol_version,
            "io.modelcontextprotocol/clientInfo": {"name": self.client_name, "version": "1.0"},
            "io.modelcontextprotocol/clientCapabilities": capabilities,
            "traceparent": f"00-{self.trace_id}-{secrets.token_hex(8)}-01",
        }

    def send(self, method, params=None, title=None, headers_override=None):
        """POST one JSON-RPC request. Returns (http_status, reply_json)."""
        params = dict(params or {})
        params["_meta"] = self.meta()
        body = {"jsonrpc": "2.0", "id": next(self.ids), "method": method, "params": params}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": self.protocol_version,
            "Mcp-Method": method,
        }
        if method in ("tools/call", "prompts/get"):
            headers["Mcp-Name"] = params["name"]
        if method == "resources/read":
            headers["Mcp-Name"] = params["uri"]
        headers.update(headers_override or {})
        headers = {name: value for name, value in headers.items() if value is not None}

        reply = requests.post(self.url, json=body, headers=headers, timeout=30)
        try:
            reply_json = reply.json()
        except ValueError:
            reply_json = {"(not JSON)": reply.text[:300]}
        self.exchanges.append({"request_headers": headers, "request": body,
                               "status": reply.status_code,
                               "response_headers": dict(reply.headers), "response": reply_json})
        if not self.quiet:
            self.print_exchange(title or method, headers, body, reply, reply_json)
        return reply.status_code, reply_json

    def print_exchange(self, title, headers, body, reply, reply_json):
        print("=" * WIDTH)
        print(f"{title}"[:WIDTH])
        print("-" * WIDTH)
        path = "/" + self.url.split("/", 3)[-1]
        print(f">>> POST {path} HTTP/1.1")
        if not self.brief:
            for name, value in headers.items():
                print(f">>> {name}: {value}"[:WIDTH])
        show_body(">>>", body)
        print(f"<<< HTTP {reply.status_code} {reply.reason}")
        if not self.brief:
            for name, value in reply.headers.items():
                print(f"<<< {name}: {value}"[:WIDTH])
        show_body("<<<", reply_json)
        show_error_text(reply_json)

    def call_tool(self, name, arguments, title=None, **extra):
        params = {"name": name, "arguments": arguments, **extra}
        return self.send("tools/call", params, title=title or f"tools/call {name}")


def ask_person(form_request, approve=None, reject=None, reason=None):
    """Turn an elicitation form into an answer: from the flags, or from a person."""
    params = form_request["params"]
    print("=" * WIDTH)
    print("THE CLIENT SHOWS THE PERSON THIS FORM (no network traffic in this step)")
    print("-" * WIDTH)
    for line in params["message"].splitlines():
        for piece in textwrap.wrap(line, WIDTH - 6) or [""]:
            print(f"  | {piece}")
    schema = params["requestedSchema"]
    for field, spec in schema["properties"].items():
        choices = f" one of {spec['enum']}" if "enum" in spec else ""
        print(f"  | field {field}:{choices}"[:WIDTH])

    if approve:
        content = {"decision": "approve", "approver": approve, "reason": reason or "approved"}
    elif reject:
        content = {"decision": "reject", "approver": reject, "reason": reason or "rejected"}
    else:
        print("  Answer the form. An empty decision cancels.")
        decision = input("  decision (approve / reject): ").strip()
        if not decision:
            return {"action": "cancel"}
        approver = input(f"  approver {schema['properties']['approver']['enum']}: ").strip()
        typed_reason = input("  reason: ").strip()
        content = {"decision": decision, "approver": approver, "reason": typed_reason}
    print(f"  -> answer: {json.dumps(content)}"[:WIDTH])
    return {"action": "accept", "content": content}


def call_with_approval(wire, name, arguments, approve=None, reject=None, reason=None):
    """The whole MRTR exchange: call, answer the form, call again. Returns the final reply."""
    status, first = wire.call_tool(name, arguments, title=f"tools/call {name}")
    result = first.get("result") or {}
    if result.get("resultType") != "input_required":
        return first

    answers = {}
    for key, form_request in (result.get("inputRequests") or {}).items():
        answers[key] = ask_person(form_request, approve, reject, reason)

    retry = {"inputResponses": answers}
    if "requestState" in result:
        retry["requestState"] = result["requestState"]      # echoed exactly, never read
    status, second = wire.call_tool(name, arguments, title=f"tools/call {name} AGAIN: same "
                                                           f"arguments + inputResponses + requestState",
                                    **retry)
    return second


def parse_arguments(pairs, args_file):
    """tag=P-1201A limit=3 -> {"tag": "P-1201A", "limit": 3}; or a JSON file."""
    if args_file:
        with open(args_file, encoding="utf-8") as handle:
            return json.load(handle)
    arguments = {}
    for pair in pairs:
        key, _, text = pair.partition("=")
        try:
            arguments[key] = json.loads(text)
        except ValueError:
            arguments[key] = text
    return arguments


def main():
    parser = argparse.ArgumentParser(description="Speak MCP 2026-07-28 by hand.")
    parser.add_argument("what", help="discover | list | <tool name>")
    parser.add_argument("pairs", nargs="*", help="tool arguments as key=value")
    parser.add_argument("--args-file", help="tool arguments as a JSON file")
    parser.add_argument("--url", default=os.environ.get("MCP_SERVER_URL",
                                                        "http://127.0.0.1:8100/mcp"))
    parser.add_argument("--approve", metavar="APPROVER", help="answer the approval form: approve")
    parser.add_argument("--reject", metavar="APPROVER", help="answer the approval form: reject")
    parser.add_argument("--reason", help="the reason typed on the form")
    parser.add_argument("--brief", action="store_true", help="bodies only, no HTTP headers")
    parser.add_argument("--no-forms", action="store_true",
                        help="declare no elicitation capability")
    args = parser.parse_args()

    wire = McpWire(args.url, forms=not args.no_forms, brief=args.brief)
    try:
        if args.what == "discover":
            status, reply = wire.send("server/discover")
        elif args.what == "list":
            status, reply = wire.send("tools/list")
        else:
            arguments = parse_arguments(args.pairs, args.args_file)
            reply = call_with_approval(wire, args.what, arguments,
                                       args.approve, args.reject, args.reason)
    except requests.RequestException:
        print(f"Nothing answered at {args.url}. Is the MCP server running? "
              f"(python -m services.mcp_server_reference.server)")
        return 2

    result = reply.get("result") or {}
    if "error" in reply or result.get("isError"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
