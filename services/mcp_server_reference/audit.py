"""One audit line per tool call. Written in ONE place, so no tool can forget.

Every `tools/call` that reaches the server passes through
`AuditMiddleware` before anything else looks at it - before the SDK
checks the request state, before the tool runs - and the middleware
writes exactly one JSON line when the call is over, whatever happened:
a result, an error, a refusal, or a request the SDK threw out.

The line is governance template 5.1.2 (facilitator/governance_pack/
05_audit_logging.md), field for field:

    ts, event, trace_id, request_id, server, server_version, caller,
    tool, access, args_sha256, args_redacted, approval, status,
    upstream, result_sha256, records, ms

The middleware also applies the three rules that must hold for EVERY
tool, so they cannot be skipped by one tool's code:

1. The class table decides. A tool's access class ("read" / "write")
   comes from the server's TOOL_ACCESS table, not from the tool's
   annotations. A tool that is not in the table is treated as a write.
2. Read-only by default. A write while writes are switched off is
   refused here, and the refusal is logged.
3. Rate limits (the MCP spec says servers MUST rate-limit tool calls):
   per caller, per class, per minute. Over the limit = refused, logged.

A tool adds what only it knows through `note(...)`: the ERP client
notes the upstream status of every ERP call; the approval gate notes
the approval block. Nothing else in a tool touches the log.
"""

import collections
import contextvars
import datetime
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path

from mcp_types import INVALID_PARAMS, CallToolResult, TextContent
from mcp.shared.exceptions import MCPError

# The line being built for the tool call in progress. The middleware
# sets it; note() adds to it from inside the tool.
CURRENT_CALL = contextvars.ContextVar("current_tool_call", default=None)

# Argument names whose values never reach the log.
SECRET_WORDS = ("password", "secret", "token", "api_key", "apikey", "authorization", "credential")
MAX_LOGGED_TEXT = 200

RATE_LIMITS_PER_MINUTE = {"read": 120, "write": 10}

# Where the log goes unless --audit-log says otherwise. checkpoints/ is
# git-ignored, so a lab log is never committed by accident.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = REPO_ROOT / "checkpoints" / "local" / "mcp_audit" / "tool_call.jsonl"


def utc_now():
    """ISO 8601, UTC, milliseconds: 2026-10-01T05:12:03.123Z"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def sha256_of(value):
    """sha256 of the value as compact JSON with sorted keys, so the same
    arguments always give the same hash."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact(arguments):
    """The arguments as they may appear in the log: secret-looking keys
    removed, long text cut. (Personal data rules: governance template 2.4.)"""
    safe = {}
    for key, value in arguments.items():
        if any(word in key.lower() for word in SECRET_WORDS):
            safe[key] = "[redacted]"
        elif isinstance(value, str) and len(value) > MAX_LOGGED_TEXT:
            safe[key] = value[:MAX_LOGGED_TEXT] + f"... ({len(value)} chars)"
        else:
            safe[key] = value
    return safe


def note(**fields):
    """From inside a tool: add fields to this call's audit line
    (upstream=..., approval=..., status="refused"). Outside a tool call
    it does nothing, so helpers can call it unconditionally."""
    line = CURRENT_CALL.get()
    if line is not None:
        line.update(fields)


class AuditLog:
    """An append-only JSON Lines file. One write() = one line, flushed."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, line):
        text = json.dumps(line, ensure_ascii=True, separators=(",", ":"))
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as log_file:
                log_file.write(text + "\n")
                log_file.flush()

    def read(self):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]


class RateLimiter:
    """At most `limit` calls per caller per class in any 60-second window."""

    def __init__(self, limits_per_minute):
        self.limits = limits_per_minute
        self.calls = collections.defaultdict(collections.deque)
        self._lock = threading.Lock()

    def allow(self, caller, access):
        now = time.monotonic()
        with self._lock:
            recent = self.calls[(caller, access)]
            while recent and now - recent[0] > 60:
                recent.popleft()
            if len(recent) >= self.limits[access]:
                return False
            recent.append(now)
            return True


def caller_of(meta):
    """Who is calling. There is no login in the lab, so this is the client's
    own name from _meta - self-reported, and the line says so. With real
    authorisation (OAuth, BUILD_SPEC section 14) it becomes the principal."""
    info = meta.get("io.modelcontextprotocol/clientInfo") or {}
    name = info.get("name") or "unknown-client"
    return f"unverified-client:{name}"


def trace_id_of(meta):
    """The W3C trace id from _meta.traceparent ("00-<32 hex>-<16 hex>-01"),
    so one approval's two rounds and the model call join up. A request
    without one gets a fresh id."""
    traceparent = meta.get("traceparent") or ""
    parts = traceparent.split("-")
    if len(parts) == 4 and len(parts[1]) == 32:
        return parts[1]
    return uuid.uuid4().hex


def records_in(result):
    """How many records a result carries: the items of a page, or one record."""
    structured = result.get("structuredContent")
    if not structured or result.get("isError"):
        return 0
    if isinstance(structured.get("items"), list):
        return len(structured["items"])
    return 1


def refused_result(reason):
    return CallToolResult(content=[TextContent(type="text", text=f"Refused: {reason}")],
                          is_error=True)


def is_bad_request_state(error):
    data = error.error.data if isinstance(error.error.data, dict) else {}
    return error.error.code == INVALID_PARAMS and data.get("reason") == "invalid_request_state"


class AuditMiddleware:
    """Put it FIRST on the server's middleware list (outermost), so it also
    sees the requests the SDK rejects before any tool runs."""

    def __init__(self, log, server_name, server_version, tool_access, writes_enabled):
        self.log = log
        self.server_name = server_name
        self.server_version = server_version
        self.tool_access = tool_access
        self.writes_enabled = writes_enabled
        self.rate_limiter = RateLimiter(RATE_LIMITS_PER_MINUTE)

    def refusal_for(self, tool, access, caller):
        """Why this call must not run at all, or None."""
        if tool not in self.tool_access:
            return (f"'{tool}' is not in this server's class table (TOOL_ACCESS), "
                    f"so it is treated as a write and refused.")
        if access == "write" and not self.writes_enabled:
            return (f"'{tool}' writes to the ERP and this server was started READ-ONLY. "
                    f"A person restarts it with --enable-writes; nothing a client sends can.")
        if not self.rate_limiter.allow(caller, access):
            return (f"rate limit: at most {RATE_LIMITS_PER_MINUTE[access]} {access} calls "
                    f"a minute per caller.")
        return None

    async def __call__(self, ctx, call_next):
        if ctx.method != "tools/call":
            return await call_next(ctx)

        params = ctx.params or {}
        meta = params.get("_meta") or {}
        tool = params.get("name")
        arguments = params.get("arguments") or {}
        caller = caller_of(meta)
        access = self.tool_access.get(tool, "write")
        started = time.perf_counter()

        line = {
            "ts": utc_now(),
            "event": "tool_call",
            "trace_id": trace_id_of(meta),
            "request_id": ctx.request_id,
            "server": self.server_name,
            "server_version": self.server_version,
            "caller": caller,
            "tool": tool,
            "access": access,
            "args_sha256": sha256_of(arguments),
            "args_redacted": redact(arguments),
            "approval": {"required": access == "write"},
            "status": None,
            "upstream": None,
            "result_sha256": None,
            "records": 0,
            "ms": None,
        }

        refusal = self.refusal_for(tool, access, caller)
        if refusal is not None:
            line["status"] = "refused"
            line["approval"] = {"required": True, "decision": "rejected", "by": "server",
                                "ts": utc_now(), "reason": refusal}
            result = refused_result(refusal)
            line["result_sha256"] = sha256_of(result.model_dump(mode="json", by_alias=True))
            self.finish(line, started)
            return result

        token = CURRENT_CALL.set(line)
        try:
            result = await call_next(ctx)
        except MCPError as error:
            if access == "write" and is_bad_request_state(error):
                line["status"] = "refused"
                line["approval"] = {"required": True, "decision": "rejected", "by": "server",
                                    "ts": utc_now(),
                                    "reason": "requestState failed verification: tampered, "
                                              "expired, or minted for other arguments"}
            else:
                line["status"] = "error"
            line["result_sha256"] = sha256_of({"error": error.error.code})
            self.finish(line, started)
            raise
        except Exception:
            line["status"] = "error"
            self.finish(line, started)
            raise
        finally:
            CURRENT_CALL.reset(token)

        if not isinstance(result, dict):
            result = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        if result.get("resultType") == "input_required":
            line["status"] = "refused"           # nothing written: the approval question went out
        elif result.get("isError"):
            if line["status"] is None:
                line["status"] = "error"         # a tool that refused has already said "refused"
        else:
            line["status"] = "ok"
        line["records"] = records_in(result)
        line["result_sha256"] = sha256_of(result.get("structuredContent", result))
        self.finish(line, started)
        return result

    def finish(self, line, started):
        line["ms"] = round((time.perf_counter() - started) * 1000, 1)
        self.log.write(line)
