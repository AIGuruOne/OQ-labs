"""The capstone plumbing. Groups read this; they do not need to edit it.

Your code goes in a use-case file (capstone/my_usecase.py). This module
connects it to what the week built, and says out loud what it connected:

    endpoint   config/endpoints.py (Contract 3)          local | hosted | tuned
    index      your index, else the reference index      Contract 5
    adapter    your adapter, else the pre-baked one      behind the "tuned" endpoint
    ERP + MCP  services/mock_erp + mcp_server_reference  ONE read tool: get_equipment
    audit      llm_call, tool_call, index_write lines    governance template 5.1

Anything of yours that is missing or broken falls back to the pre-baked
piece, and the status table says FALLBACK and why. Nothing falls back
quietly.
"""

import datetime
import hashlib
import importlib
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

import compare_utils  # noqa: E402
from capstone.contract import check_description, check_hits  # noqa: E402
from capstone.reference_index.bm25 import (DEFAULT_EXCLUDE, DEFAULT_SOURCE, build_index,  # noqa: E402
                                           load_index, plant_tags_in, read_ids, sha256_of_file)
from config.endpoints import get_endpoint  # noqa: E402

WIDTH = 100
PREBAKED_ADAPTER = REPO_ROOT / "checkpoints" / "adapter_prebaked"
DEFAULT_OUT = REPO_ROOT / "checkpoints" / "local" / "capstone"
TEMPERATURE = 0.0          # the same settings scripts/run_eval.py uses, so numbers compare
MAX_TOKENS = 512


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ascii_text(value):
    return str(value).encode("ascii", "replace").decode("ascii")


def wrapped(line, width=WIDTH, indent=11):
    """A status line wrapped to the width, continuation lines indented under the value."""
    return textwrap.wrap(ascii_text(line), width, subsequent_indent=" " * indent) or [""]


def one_line(value, width=WIDTH):
    """One printable line: ASCII, inner whitespace collapsed, leading indent kept, cut to width."""
    text = ascii_text(value)
    indent = text[:len(text) - len(text.lstrip(" "))]
    flat = indent + " ".join(text.split())
    return flat if len(flat) <= width else flat[:width - 3] + "..."


# ---------------------------------------------------------------------------
# Audit log: one JSON object per line, append only (governance template 5.1)
# ---------------------------------------------------------------------------

class AuditLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, fields):
        line = {"ts": utc_now(), **fields}
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
        return line

    def lines(self):
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]


# ---------------------------------------------------------------------------
# The index: yours, else the reference one
# ---------------------------------------------------------------------------

def load_your_index(setting):
    """setting is "path/to/saved_index.json" or "package.module:function"."""
    if ":" in setting and not Path(setting).exists():
        module_name, function_name = setting.split(":", 1)
        module = importlib.import_module(module_name)
        return getattr(module, function_name)()
    return load_index(setting)


def reference_index(out_dir, index_log):
    """Load the saved reference index if it matches the corpus, else build and save it."""
    saved_path = Path(out_dir) / "reference_index.json"
    if saved_path.exists():
        saved = load_index(saved_path)
        same_source = saved.describe().get("source_sha256") == sha256_of_file(DEFAULT_SOURCE)
        same_exclusions = saved.describe().get("excluded") == len(read_ids(DEFAULT_EXCLUDE))
        if same_source and same_exclusions:
            return saved, f"loaded {saved_path.name} (saved earlier)"
    index = build_index(index_log=index_log)
    index.save(saved_path)
    return index, f"built now and saved to {saved_path.name}; {index.describe()['items']} index_write lines"


def resolve_index(setting, out_dir, index_log):
    """Returns (index, row). row says which index and why."""
    if setting:
        try:
            index = load_your_index(setting)
            info = check_description(index.describe())
            check_hits(index.search("password reset", k=3), 3)     # one probe search
            return index, {"source": "yours", "info": info, "note": f"from {setting}"}
        except Exception as error:      # noqa: BLE001 - any failure means: fall back, visibly
            reason = f"{setting} did not load: {type(error).__name__}: {error}"
    else:
        reason = "MY_INDEX is not set"
    index, how = reference_index(out_dir, index_log)
    return index, {"source": "FALLBACK", "info": index.describe(), "note": f"{reason}; reference index {how}"}


# ---------------------------------------------------------------------------
# The adapter behind the "tuned" endpoint: yours, else the pre-baked one
# ---------------------------------------------------------------------------

def resolve_adapter(setting):
    if setting:
        problem = compare_utils.adapter_problem(setting)
        if problem is None:
            return {"source": "yours", "path": str(setting),
                    "fingerprint": compare_utils.adapter_fingerprint(Path(setting)), "note": ""}
        reason = f"{setting}: {problem}"
    else:
        reason = "MY_ADAPTER_DIR is not set"
    return {"source": "FALLBACK", "path": str(PREBAKED_ADAPTER),
            "fingerprint": compare_utils.adapter_fingerprint(PREBAKED_ADAPTER),
            "note": f"{reason}; using the pre-baked adapter"}


def ollama_base_url():
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def ollama_models():
    """{name: digest} from Ollama, or None if Ollama does not answer."""
    try:
        reply = requests.get(f"{ollama_base_url()}/api/tags", timeout=3)
        reply.raise_for_status()
    except requests.RequestException:
        return None
    return {model["name"]: model["digest"] for model in reply.json().get("models", [])}


def with_tag(model_name):
    return model_name if ":" in model_name else f"{model_name}:latest"


def tuned_model_row(out_dir):
    """Is the tuned model on Ollama, and which adapter was it registered from?"""
    tuned_name = os.environ.get("TUNED_MODEL", "oq-ticket-tuned")
    models = ollama_models()
    if models is None:
        return {"state": "no Ollama", "fingerprint": None,
                "note": f"Ollama does not answer at {ollama_base_url()} (the tuned endpoint needs it)"}
    if with_tag(tuned_name) not in models:
        return {"state": "not registered", "fingerprint": None,
                "note": f"{tuned_name} is not on Ollama: python -m capstone.run register-adapter"}
    marker_path = Path(out_dir) / "tuned_registration.json"
    if marker_path.exists():
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        return {"state": "registered", "fingerprint": marker["fingerprint"],
                "note": f"{tuned_name} registered by the scaffold from the {marker['source']} adapter "
                        f"{marker['fingerprint']} on {marker['registered'][:10]}"}
    return {"state": "registered", "fingerprint": None,
            "note": f"{tuned_name} is on Ollama but was registered outside the scaffold: which "
                    f"adapter is unknown. Run register-adapter to be sure"}


def register_adapter(adapter_row, out_dir):
    """Register the chosen adapter as the tuned model (scripts/register_adapter.py)."""
    env = dict(os.environ)
    env["OLLAMA_HOST"] = ollama_base_url().replace("http://", "").replace("https://", "")
    command = [sys.executable, str(REPO_ROOT / "scripts" / "register_adapter.py"),
               "--adapter", adapter_row["path"]]
    print("Running:", " ".join(command), flush=True)
    completed = subprocess.run(command, env=env, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        return False
    marker = {"source": "yours" if adapter_row["source"] == "yours" else "pre-baked",
              "path": adapter_row["path"], "fingerprint": adapter_row["fingerprint"],
              "registered": utc_now(), "ollama_model": os.environ.get("TUNED_MODEL", "oq-ticket-tuned")}
    marker_path = Path(out_dir) / "tuned_registration.json"
    marker_path.write_text(json.dumps(marker, indent=2), encoding="utf-8")
    print(f"Recorded which adapter backs the tuned model: {marker_path}")
    return True


# ---------------------------------------------------------------------------
# The mock ERP and the MCP server (read-only), started or reused
# ---------------------------------------------------------------------------

class Services:
    """Starts (or reuses) the ERP and a READ-ONLY MCP server. stop() stops only what it started."""

    def __init__(self, out_dir, erp_port=8000, mcp_port=8100):
        from services.mcp_server_reference.launch import start_in_background as start_mcp
        from services.mock_erp.launch import start_in_background as start_erp

        self.erp = None
        self.mcp = None
        self.problem = None
        self.erp_url = f"http://127.0.0.1:{erp_port}"
        self.tool_log = Path(out_dir) / "audit" / "tool_call.jsonl"
        try:
            self.erp = start_erp(port=erp_port)
            os.environ["MOCK_ERP_URL"] = self.erp_url           # the MCP server reads it
            self.mcp = start_mcp(port=mcp_port, enable_writes=False, audit_log=self.tool_log)
        except Exception as error:      # noqa: BLE001 - no ERP means no equipment lookup, not a crash
            self.problem = f"{type(error).__name__}: {error}"

    def row(self):
        if self.problem:
            return {"state": "UNAVAILABLE", "note": one_line(self.problem, 300)}
        started = "reused" if self.mcp.process is None else "started"
        return {"state": "up", "note": f"ERP {self.erp_url} data {self.erp.health.get('data_fingerprint')}; "
                                        f"MCP {self.mcp.url} ({started}, read-only); tool used: get_equipment"}

    def stop(self):
        from services.mcp_server_reference.launch import stop as stop_mcp
        from services.mock_erp.launch import stop as stop_erp
        if self.mcp is not None and self.mcp.process is not None:
            stop_mcp(self.mcp)
        if self.erp is not None and self.erp.process is not None:
            stop_erp(self.erp)


# ---------------------------------------------------------------------------
# Tools the use case calls: the index and the ONE MCP tool
# ---------------------------------------------------------------------------

class Tools:
    """What gather_context() gets. Every call is remembered for the audit line's context_ids."""

    def __init__(self, index, services, trace_id, ticket_id):
        self.ticket_id = ticket_id
        self.index = index
        self.services = services
        self.trace_id = trace_id
        self.context_ids = []

    def search(self, query, k=5, filters=None):
        """Contract 5 hits, checked. The ticket being handled is never its own neighbour."""
        hits = check_hits(self.index.search(query, k=k + 1, filters=filters), k + 1)
        hits = [hit for hit in hits if hit["doc_id"] != self.ticket_id][:k]
        self.context_ids += [hit["chunk_id"] for hit in hits]
        return hits

    def plant_tags(self, text):
        return plant_tags_in(text)

    def equipment(self, tag):
        """get_equipment through the MCP server. Returns the record, or {"tag", "error"}."""
        if self.services is None or self.services.mcp is None:
            return {"tag": tag, "error": "ERP/MCP not running"}
        from services.mcp_server_reference.call import McpWire
        wire = McpWire(self.services.mcp.url, client_name="oq-capstone", quiet=True)
        wire.trace_id = self.trace_id            # joins the server's tool_call line to our llm_call line
        status, reply = wire.call_tool("get_equipment", {"tag": tag})
        self.context_ids.append(f"mcp:get_equipment:{tag}")
        result = reply.get("result") or {}
        if status != 200 or result.get("isError") or "error" in reply:
            texts = [part.get("text", "") for part in result.get("content", [])]
            message = " ".join(texts) or json.dumps(reply.get("error"))
            return {"tag": tag, "error": one_line(message, 200)}
        return result.get("structuredContent") or {"tag": tag, "error": "no structured result"}


# ---------------------------------------------------------------------------
# Cost: an estimate per call, and a monthly cap
# ---------------------------------------------------------------------------

class CostCapReached(RuntimeError):
    pass


def cost_of(endpoint_name, usage, price_per_mtok):
    """Hosted = tokens x the price in your use case file. Self-hosted = 0 per call (the VM is a fixed cost)."""
    if endpoint_name != "hosted" or not usage:
        return 0.0
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    cost = tokens_in * price_per_mtok["input"] / 1e6 + tokens_out * price_per_mtok["output"] / 1e6
    return round(cost, 6)


def spent_this_month(llm_log):
    month = utc_now()[:7]
    total = 0.0
    for line in llm_log.lines():
        if line["ts"].startswith(month):
            total += line.get("cost_estimate") or 0.0
    return round(total, 6)


# ---------------------------------------------------------------------------
# The capstone: everything wired, and one ticket through the pipeline
# ---------------------------------------------------------------------------

class Capstone:
    def __init__(self, usecase, out_dir=DEFAULT_OUT, endpoint=None, index_setting=None,
                 adapter_setting=None, start_services=True, erp_port=8000, mcp_port=8100):
        self.usecase = usecase
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.llm_log = AuditLog(self.out_dir / "audit" / "llm_call.jsonl")
        self.index_log = AuditLog(self.out_dir / "audit" / "index_write.jsonl")

        self.endpoint_name = endpoint or usecase.ENDPOINT or os.environ.get("LLM_ENDPOINT", "hosted")
        self.index, self.index_row = resolve_index(index_setting or usecase.MY_INDEX, self.out_dir,
                                                   self.index_log)
        self.adapter_row = resolve_adapter(adapter_setting or usecase.MY_ADAPTER_DIR)
        self.tuned_row = tuned_model_row(self.out_dir)
        self.services = Services(self.out_dir, erp_port, mcp_port) if start_services else None
        self.llm = get_endpoint(self.endpoint_name)

    def model_fingerprint(self):
        if self.endpoint_name == "tuned":
            return self.tuned_row["fingerprint"] or "unknown (registered outside the scaffold)"
        if self.endpoint_name == "local":
            digest = (ollama_models() or {}).get(with_tag(self.llm.model))
            return digest[:12] if digest else "unknown"
        info = self.llm.last_reply_info or {}
        return info.get("model") or self.llm.model

    def status_lines(self):
        index_info = self.index_row["info"]
        spent = spent_this_month(self.llm_log)
        services_row = self.services.row() if self.services else {"state": "OFF", "note": "not started (--no-services, or not needed for this command)"}
        adapter = self.adapter_row
        return [
            f"use case   {self.usecase.__name__}: {self.usecase.USE_CASE}",
            f"endpoint   {self.endpoint_name}: {self.llm.model} @ {self.llm.base_url}",
            f"index      {self.index_row['source']}: {index_info['name']} build {index_info['build_id']}, "
            f"{index_info['items']} items",
            f"           {self.index_row['note']}",
            f"adapter    {adapter['source']}: {adapter['path']} (fingerprint {adapter['fingerprint']})",
            *([f"           {adapter['note']}"] if adapter["note"] else []),
            f"tuned      {self.tuned_row['state']}: {self.tuned_row['note']}",
            f"ERP + MCP  {services_row['state']}: {services_row['note']}",
            f"audit      {self.llm_log.path.parent}",
            f"cost cap   ${spent:.4f} spent this month of ${self.usecase.COST_CAP_USD_PER_MONTH:.2f}",
        ]

    def print_status(self):
        print("=" * WIDTH)
        print("CAPSTONE WIRING (FALLBACK = your own piece was not usable; the pre-baked one is in use)")
        print("-" * WIDTH)
        for line in self.status_lines():
            for piece in wrapped(line):
                print(piece)
        print("=" * WIDTH)

    def run_ticket(self, ticket):
        """ticket = {"ticket_id", "text"}. Returns the result dict; writes one llm_call line."""
        usecase = self.usecase
        trace_id = os.urandom(16).hex()
        tools = Tools(self.index, self.services, trace_id, ticket["ticket_id"])
        started = time.perf_counter()

        context = usecase.gather_context(ticket, tools)
        messages = usecase.build_messages(ticket, context)

        spent = spent_this_month(self.llm_log)
        if spent >= usecase.COST_CAP_USD_PER_MONTH:
            raise CostCapReached(f"${spent:.4f} spent this month; the cap in {usecase.__name__} is "
                                 f"${usecase.COST_CAP_USD_PER_MONTH:.2f}. No model call was made.")

        reply = self.llm.chat(messages=messages, temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
        info = self.llm.last_reply_info or {}
        usage = info.get("usage") or {}

        output, validation = usecase.check_output(reply, ticket, context)
        decision = usecase.decide(output, validation, ticket, context)
        seconds = round(time.perf_counter() - started, 2)

        prompt_text = json.dumps(messages, ensure_ascii=False)
        self.llm_log.write({
            "event": "llm_call",
            "trace_id": trace_id,
            "system_id": usecase.SYSTEM_ID,
            "caller": f"{usecase.GROUP}/capstone-cli",
            "item_id": ticket["ticket_id"],
            "endpoint": self.endpoint_name,
            "model": self.llm.model,
            "model_fingerprint": self.model_fingerprint(),
            "prompt_sha256": sha256_text(prompt_text),
            "prompt_version": usecase.PROMPT_VERSION,
            "context_ids": tools.context_ids,
            "output": output,
            "validation": validation,
            "tokens_in": usage.get("prompt_tokens"),
            "tokens_out": usage.get("completion_tokens"),
            "seconds": seconds,
            "truncated": info.get("finish_reason") == "length",
            "cost_estimate": cost_of(self.endpoint_name, usage, usecase.HOSTED_PRICE_PER_MTOK),
        })
        return {"ticket": ticket, "trace_id": trace_id, "context": context, "reply": reply,
                "output": output, "validation": validation, "decision": decision,
                "seconds": seconds, "tokens_in": usage.get("prompt_tokens"),
                "tokens_out": usage.get("completion_tokens")}

    def register_chosen_adapter(self):
        return register_adapter(self.adapter_row, self.out_dir)

    def close(self):
        if self.services is not None:
            self.services.stop()
