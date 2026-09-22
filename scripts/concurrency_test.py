"""Drive rising concurrent load at a chat endpoint and report what breaks.

    python scripts/concurrency_test.py --endpoint local
    python scripts/concurrency_test.py --endpoint hosted --levels 1,4,16 --requests 8
    python scripts/concurrency_test.py --base-url http://localhost:11436/v1 --model llama3.2:1b
    python scripts/concurrency_test.py --endpoint local --out checkpoints/local/concurrency --run-id 03_load

What it does, in one sentence: for each concurrency level it starts that
many client threads, every thread sends a request and waits for the reply
before sending the next (a "closed loop" - the shape of N people or N
integrations hitting the server at once), until the level's request count
is used up. Then it reports, per level:

    requests, ok, failed       how many came back, how many did not
    p50 / p95 / max seconds    the latency a typical and an unlucky caller saw
    requests per second        throughput - what the SERVER got through
    reply tokens per second    the same, in the unit the server actually works in

Every request is one POST to {base_url}/chat/completions - the same call
config/endpoints.py makes (Contract 3), so the numbers apply to whatever
that endpoint is: an Ollama server on this machine, one on a VM, or a
vendor API. Nothing here is Ollama-specific.

Prompts are real synthetic tickets from data/eval/heldout_20.jsonl with the
house system prompt, so the token counts match the work OQ would send.
A reply cap (--max-tokens) keeps every request the same size; the model
may stop earlier, and the token column shows what it actually wrote.

Before any level runs, ONE preflight request goes out. If it cannot
connect, the script exits with code 2 and a sentence - it never sits on a
dead endpoint for the whole test. Once inside a level, a request that
times out or errors is counted as a failure, and the level reports it.

Output: a table on stdout (ASCII, under 100 columns), plus
<out>/<run_id>_summary.json (one row per level, plus the settings) and
<out>/<run_id>_requests.jsonl (one row per request). The notebook reads
the summary; nothing else needs the request rows.

Uses `requests` and the standard library only.
"""

import argparse
import json
import os
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

DEFAULT_LEVELS = [1, 2, 4, 8, 16]
DEFAULT_REQUESTS_PER_LEVEL = 16
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_TOKENS = 64
DEFAULT_DATASET = REPO_ROOT / "data" / "eval" / "heldout_20.jsonl"
CONNECT_TIMEOUT_CAP = 10        # seconds to wait for a TCP connection, never more


# ---------------------------------------------------------------------------
# Small pure helpers (tested in tests/test_concurrency_test.py)
# ---------------------------------------------------------------------------


def parse_levels(text):
    """'1,2,4,8' -> [1, 2, 4, 8]. Refuses zero, negatives and repeats."""
    levels = []
    for word in text.split(","):
        word = word.strip()
        if not word:
            continue
        level = int(word)
        if level < 1:
            raise ValueError(f"a concurrency level must be 1 or more, got {level}")
        if level in levels:
            raise ValueError(f"concurrency level {level} is listed twice")
        levels.append(level)
    if not levels:
        raise ValueError("no concurrency levels given")
    return levels


def percentile(values, fraction):
    """The value at `fraction` (0.5 = median, 0.95 = p95) by nearest rank.
    Small samples on purpose: 16 requests give a p95 that is the second-slowest one."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(round(fraction * len(ordered))))
    return ordered[min(rank, len(ordered)) - 1]


def summarise_level(concurrency, results, wall_seconds):
    """One row of the report from a level's request results.

    results: [{"seconds", "ok", "reply_tokens", "error"}, ...]
    Latency percentiles are over the requests that CAME BACK; failures are
    counted, not averaged in (a timeout is not a latency, it is a lost call).
    """
    ok_results = [r for r in results if r["ok"]]
    ok_seconds = [r["seconds"] for r in ok_results]
    reply_tokens = sum(r.get("reply_tokens") or 0 for r in ok_results)
    errors = {}
    for r in results:
        if not r["ok"]:
            errors[r["error"]] = errors.get(r["error"], 0) + 1
    return {
        "concurrency": concurrency,
        "requests": len(results),
        "ok": len(ok_results),
        "failed": len(results) - len(ok_results),
        "p50_seconds": round(percentile(ok_seconds, 0.5), 2) if ok_seconds else None,
        "p95_seconds": round(percentile(ok_seconds, 0.95), 2) if ok_seconds else None,
        "max_seconds": round(max(ok_seconds), 2) if ok_seconds else None,
        "wall_seconds": round(wall_seconds, 2),
        "requests_per_second": round(len(ok_results) / wall_seconds, 2) if wall_seconds > 0 else None,
        "reply_tokens": reply_tokens,
        "reply_tokens_per_second": round(reply_tokens / wall_seconds, 1) if wall_seconds > 0 else None,
        "errors": errors,
    }


def highest_level_within(levels, target_seconds):
    """The highest concurrency whose p95 stayed at or under the target with
    no failures - or None if even the lowest level missed it.
    This is the number the sizing worksheet starts from."""
    best = None
    for row in sorted(levels, key=lambda r: r["concurrency"]):
        if row["failed"] == 0 and row["p95_seconds"] is not None and row["p95_seconds"] <= target_seconds:
            best = row
    return best


def fmt(value, width, decimals=2):
    """A number right-aligned in `width` columns; '-' when there is none."""
    if value is None:
        return "-".rjust(width)
    if isinstance(value, int):
        return str(value).rjust(width)
    return f"{value:.{decimals}f}".rjust(width)


def render_table(levels):
    """The report as plain ASCII, under 100 columns."""
    lines = []
    lines.append("concurrency  requests    ok  failed   p50 s   p95 s   max s   req/s  tokens/s")
    lines.append("-" * 82)
    for row in levels:
        lines.append(
            fmt(row["concurrency"], 11) + fmt(row["requests"], 10) + fmt(row["ok"], 6) + fmt(row["failed"], 8)
            + fmt(row["p50_seconds"], 8) + fmt(row["p95_seconds"], 8) + fmt(row["max_seconds"], 8)
            + fmt(row["requests_per_second"], 8) + fmt(row["reply_tokens_per_second"], 10, 1)
        )
    for row in levels:
        if row["errors"]:
            kinds = ", ".join(f"{count} x {kind}" for kind, count in sorted(row["errors"].items()))
            lines.append(f"  at {row['concurrency']}: {kinds}"[:98])
    return "\n".join(lines)


def text_chart(levels, key="p95_seconds", width=50, title="p95 latency (seconds) as concurrency rises"):
    """One bar per concurrency level, drawn with '#'. Failures are marked on the bar's line.
    Plain text on purpose: it survives a Windows console, a projector and a headless run."""
    values = [row[key] for row in levels if row[key] is not None]
    biggest = max(values) if values else 1.0
    lines = [title, ""]
    for row in levels:
        value = row[key]
        bar_length = int(round(width * value / biggest)) if value and biggest else 0
        bar = "#" * bar_length
        label = f"{row['concurrency']:>3} at once |"
        number = f" {value:.2f}" if value is not None else " (no reply came back)"
        failed = f"   {row['failed']} failed" if row["failed"] else ""
        lines.append(f"{label}{bar}{number}{failed}")
    lines.append("")
    lines.append(f"scale: '#' = {biggest / width:.2f} s;  the longest bar is {biggest:.2f} s")
    return "\n".join(lines)


def parallel_slots_from_log(log_path):
    """How many requests the server runs at once, read from the last model load in
    `ollama serve`'s log (the line says `Parallel:N`). None if the log does not say -
    for example when the server was already running and we never saw its log.
    Ollama 0.12.10 defaults to 1 (OLLAMA_NUM_PARALLEL); /api/ps does not report it."""
    import re
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = re.findall(r"Parallel:(\d+)", text)
    return int(found[-1]) if found else None


# ---------------------------------------------------------------------------
# Prompts: real synthetic tickets, so the token counts are honest
# ---------------------------------------------------------------------------


def load_prompts(dataset_path):
    """[[system, user], ...] from a fine-tuning pair file (Contract 1). The
    expected answer (third message) is dropped - this is a load test, not an eval."""
    prompts = []
    for line in Path(dataset_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        prompts.append(row["messages"][:2])
    if not prompts:
        raise ValueError(f"no rows in {dataset_path}")
    return prompts


# ---------------------------------------------------------------------------
# One request, timed
# ---------------------------------------------------------------------------


def one_request(base_url, headers, model, messages, max_tokens, timeout):
    """POST one chat completion and time it. Never raises: the result says what happened.

        {"seconds", "ok", "status", "reply_tokens", "error"}

    error is a short kind - "timeout", "connection", "HTTP 429" - so a level's
    failures can be counted by cause.
    """
    body = {"model": model, "messages": messages, "temperature": 0.0, "max_tokens": max_tokens}
    started = time.perf_counter()
    result = {"seconds": None, "ok": False, "status": None, "reply_tokens": None, "error": None}
    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=body,
                                 timeout=(min(CONNECT_TIMEOUT_CAP, timeout), timeout))
        result["status"] = response.status_code
        if response.status_code == 200:
            usage = response.json().get("usage") or {}
            result["ok"] = True
            result["reply_tokens"] = usage.get("completion_tokens")
        else:
            result["error"] = f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection"
    except (requests.exceptions.RequestException, ValueError) as error:
        result["error"] = type(error).__name__
    result["seconds"] = round(time.perf_counter() - started, 3)
    return result


# ---------------------------------------------------------------------------
# One level: N closed-loop clients sharing a pool of requests
# ---------------------------------------------------------------------------


def run_level(base_url, headers, model, prompts, concurrency, request_count, max_tokens, timeout):
    """Send request_count requests with `concurrency` clients at once.
    Returns (results, wall_seconds). Each client takes the next prompt in turn."""
    jobs = [prompts[i % len(prompts)] for i in range(request_count)]

    def send(messages):
        return one_request(base_url, headers, model, messages, max_tokens, timeout)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(send, jobs))
    return results, time.perf_counter() - started


# ---------------------------------------------------------------------------
# Where to send it: an endpoint name (Contract 3) or an explicit URL
# ---------------------------------------------------------------------------


def resolve_target(args):
    """{"base_url", "model", "headers", "label"} from --endpoint or --base-url/--model."""
    if args.base_url:
        if not args.model:
            stop("--base-url needs --model as well.")
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if args.api_key_from_env and api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return {"base_url": args.base_url.rstrip("/"), "model": args.model, "headers": headers,
                "label": args.label or args.model}

    from config.endpoints import get_endpoint, EndpointError
    try:
        endpoint = get_endpoint(args.endpoint)
    except (EndpointError, ValueError) as error:
        stop(f"Cannot use endpoint '{args.endpoint}': {error}")
    headers = {"Content-Type": "application/json"}
    if endpoint._config.api_key:                       # the hosted API wants a bearer token
        headers["Authorization"] = f"Bearer {endpoint._config.api_key}"
    return {"base_url": endpoint.base_url, "model": endpoint.model, "headers": headers,
            "label": args.label or f"{args.endpoint} ({endpoint.model})"}


def stop(message):
    """Nothing was measured: say why on stderr and exit 2 (1 is never used; 0 = the test ran)."""
    print(message, file=sys.stderr)
    sys.exit(2)


def preflight(target, prompts, max_tokens, timeout):
    """One request before the test. Exits 2 with a sentence if it fails - a
    dead endpoint must not cost the room a whole test's worth of timeouts."""
    say(f"preflight: one request to {target['base_url']}/chat/completions (model {target['model']}) ...")
    result = one_request(target["base_url"], target["headers"], target["model"], prompts[0], max_tokens, timeout)
    if result["ok"]:
        say(f"preflight: ok in {result['seconds']} s, {result['reply_tokens']} reply tokens")
        return result
    reason = {
        "connection": "nothing answered at that address (connection refused, or no route). Is the server running, "
                      "and is the URL right? Ollama: `ollama serve`, then check OLLAMA_BASE_URL.",
        "timeout": f"no reply within {timeout} s. The server is up but not answering - a model still loading, "
                   "or a machine far too slow for this test. Raise --timeout only if you know why.",
    }.get(result["error"], f"the server answered {result['error']}. Check the model name and, for the hosted API, the key.")
    stop(f"NOTHING MEASURED. Preflight failed after {result['seconds']} s: {reason}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def say(text, end="\n"):
    """Print one line in ONE write and flush it, so a notebook that reads this script's
    output through a pipe (compare_utils.run_command) shows each progress line the
    moment it is complete."""
    sys.stdout.write(text + end)
    sys.stdout.flush()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    where = parser.add_argument_group("where to send the load")
    where.add_argument("--endpoint", default="local", help="Contract 3 endpoint name: local, hosted or tuned (default local)")
    where.add_argument("--base-url", help="explicit OpenAI-compatible base URL ending in /v1 (overrides --endpoint)")
    where.add_argument("--model", help="model name, required with --base-url")
    where.add_argument("--api-key-from-env", action="store_true",
                       help="with --base-url: send OPENAI_API_KEY as a bearer token")
    how = parser.add_argument_group("how much load")
    how.add_argument("--levels", default=",".join(str(n) for n in DEFAULT_LEVELS),
                     help=f"comma-separated concurrency levels (default {','.join(str(n) for n in DEFAULT_LEVELS)})")
    how.add_argument("--requests", type=int, default=DEFAULT_REQUESTS_PER_LEVEL,
                     help=f"requests per level (default {DEFAULT_REQUESTS_PER_LEVEL})")
    how.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS,
                     help=f"seconds to wait for one reply before counting it failed (default {DEFAULT_TIMEOUT_SECONDS})")
    how.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                     help=f"reply cap per request (default {DEFAULT_MAX_TOKENS})")
    how.add_argument("--dataset", default=str(DEFAULT_DATASET), help="pair file to take prompts from")
    out = parser.add_argument_group("output")
    out.add_argument("--out", default=str(REPO_ROOT / "eval_runs" / "concurrency"), help="folder for the two output files")
    out.add_argument("--run-id", default=None, help="file name stem (default: 03_load_<endpoint>_<timestamp>)")
    out.add_argument("--label", default=None, help="what to call this target in the report")
    out.add_argument("--note", default="", help="free text saved in the summary, e.g. 'Colab T4' or 'OLLAMA_NUM_PARALLEL=4'")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        levels = parse_levels(args.levels)
    except ValueError as error:
        stop(f"--levels: {error}")
    if args.requests < 1:
        stop("--requests must be 1 or more")

    target = resolve_target(args)
    if not Path(args.dataset).exists():
        stop(f"No prompt file at {args.dataset}. Run from the repo, or pass --dataset.")
    prompts = load_prompts(args.dataset)
    say(f"target : {target['label']} at {target['base_url']}")
    say(f"load   : levels {levels}, {args.requests} requests per level, reply cap {args.max_tokens} tokens, "
        f"timeout {args.timeout:g} s, {len(prompts)} distinct ticket prompts")
    if os.environ.get("OLLAMA_NUM_PARALLEL"):
        say(f"note   : OLLAMA_NUM_PARALLEL={os.environ['OLLAMA_NUM_PARALLEL']} is set in this environment")
    first = preflight(target, prompts, args.max_tokens, args.timeout)
    say("")

    all_results = []
    level_rows = []
    for concurrency in levels:
        say(f"concurrency {concurrency:>3}: sending {args.requests} requests ...", end=" ")
        results, wall = run_level(target["base_url"], target["headers"], target["model"], prompts,
                                  concurrency, args.requests, args.max_tokens, args.timeout)
        row = summarise_level(concurrency, results, wall)
        level_rows.append(row)
        for result in results:
            all_results.append({"concurrency": concurrency, **result})
        say(f"done in {wall:.1f} s  (p95 {fmt(row['p95_seconds'], 1).strip()} s, {row['failed']} failed)")

    say("")
    say(render_table(level_rows))

    run_id = args.run_id or f"03_load_{args.endpoint if not args.base_url else 'url'}_{time.strftime('%Y%m%dT%H%M%S')}"
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_id": run_id,
        "label": target["label"],
        "base_url": target["base_url"],
        "model": target["model"],
        "levels": level_rows,
        "settings": {"levels": levels, "requests_per_level": args.requests, "max_tokens": args.max_tokens,
                     "timeout_seconds": args.timeout, "dataset": str(args.dataset), "prompts": len(prompts)},
        "preflight": first,
        "machine": {"platform": platform.platform(), "python": platform.python_version(),
                    "OLLAMA_NUM_PARALLEL": os.environ.get("OLLAMA_NUM_PARALLEL")},
        "note": args.note,
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    summary_path = out_dir / f"{run_id}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    requests_path = out_dir / f"{run_id}_requests.jsonl"
    requests_path.write_text("".join(json.dumps(r) + "\n" for r in all_results), encoding="utf-8")
    say("")
    say(f"saved  : {summary_path}")
    say(f"         {requests_path}")
    # Failures at high concurrency are the lesson, not a script error: exit 0 whenever
    # the test ran. Exit 2 (from preflight) means nothing was measured.
    return 0


if __name__ == "__main__":
    sys.exit(main())
