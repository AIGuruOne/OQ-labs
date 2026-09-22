"""Helpers for notebook 02 (run a model yourself).

Import after the environment-detection cell has run:

    import inference_utils

    card = inference_utils.model_card("llama3.2:1b")        # what was actually downloaded
    timing = inference_utils.chat_timed("llama3.2:1b", messages)   # reply + the server's own clock
    runs = inference_utils.run_experiments("llama3.2:1b", messages, settings)

Two Ollama APIs appear here, on purpose, because the notebook wants
both facts they give:

    /v1/chat/completions   the OpenAI-compatible call - the SAME request
                           config/endpoints.py makes, so what works here
                           works against the vendor API unchanged
    /api/chat              Ollama's native call - the only one that
                           reports load time, prompt tokens and reply
                           tokens with the server's own nanosecond clock,
                           which is where a tokens-per-second figure
                           comes from

Everything prints in plain ASCII: the room has a projector and Windows
consoles. Uses `requests` and the standard library only.
"""

import json
import time

import requests

import ollama_utils

NANOSECONDS_PER_SECOND = 1_000_000_000


# ---------------------------------------------------------------------------
# What did I download?
# ---------------------------------------------------------------------------


def model_card(model_name, base_url=None):
    """The facts about a pulled model, from /api/show and /api/tags:

        {"name", "family", "parameter_size", "quantization", "disk_gb",
         "max_context_length", "capabilities"}

    parameter_size is the model's own label ("1.2B"); quantization is how
    many bits each weight was squeezed to for download ("Q8_0" = 8 bits,
    "Q4_K_M" = about 4.5). Together they explain the file size.
    """
    base_url = base_url or ollama_utils.server_url()
    shown = requests.post(f"{base_url}/api/show", json={"model": model_name}, timeout=30)
    if shown.status_code == 404:
        raise ollama_utils.OllamaError(f"{model_name} is not on this server. Run the pull cell first.")
    shown.raise_for_status()
    shown = shown.json()
    details = shown.get("details", {})
    info = shown.get("model_info", {})

    disk_bytes = 0
    for model in requests.get(f"{base_url}/api/tags", timeout=10).json().get("models", []):
        if model.get("name") == model_name or model.get("name") == model_name + ":latest":
            disk_bytes = model.get("size", 0)

    context_lengths = [value for key, value in info.items() if key.endswith(".context_length")]
    return {
        "name": model_name,
        "family": details.get("family"),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "disk_gb": round(disk_bytes / 1e9, 2),
        "max_context_length": context_lengths[0] if context_lengths else None,
        "capabilities": shown.get("capabilities", []),
    }


def print_model_card(card, served_context_length):
    """One block a participant can read across the room."""
    print(f"model            : {card['name']}")
    print(f"family           : {card['family']}")
    print(f"parameters       : {card['parameter_size']}")
    print(f"quantization     : {card['quantization']}   (bits per weight in the download)")
    print(f"on disk          : {card['disk_gb']} GB")
    print(f"context, maximum : {card['max_context_length']} tokens  (what the model was trained to hold)")
    print(f"context, served  : {served_context_length} tokens  (what THIS server gives it: OLLAMA_CONTEXT_LENGTH)")
    print(f"capabilities     : {', '.join(card['capabilities'])}")


# ---------------------------------------------------------------------------
# One call with the server's own clock
# ---------------------------------------------------------------------------


def chat_timed(model_name, messages, options=None, base_url=None, timeout=600):
    """Send `messages` through Ollama's native /api/chat and return the reply
    with the server's own timing:

        {"reply", "done_reason",
         "prompt_tokens", "reply_tokens",
         "load_seconds", "prompt_seconds", "generate_seconds", "total_seconds",
         "tokens_per_second"}

    load_seconds is the time to bring the model into memory - zero once it
    is loaded and stays loaded. tokens_per_second is reply_tokens over
    generate_seconds: the number the sizing worksheet (S8) starts from.
    `options` is Ollama's dict: temperature, top_p, seed, num_predict (the
    reply cap), stop.
    """
    base_url = base_url or ollama_utils.server_url()
    request_body = {"model": model_name, "messages": messages, "stream": False,
                    "options": options or {}}
    response = requests.post(f"{base_url}/api/chat", json=request_body, timeout=timeout)
    if response.status_code == 404:
        raise ollama_utils.OllamaError(f"{model_name} is not on this server: {response.text[:200]}. "
                                       "Run the pull cell first.")
    if response.status_code != 200:
        raise ollama_utils.OllamaError(f"/api/chat failed: HTTP {response.status_code} {response.text[:300]}")
    body = response.json()

    generate_seconds = body.get("eval_duration", 0) / NANOSECONDS_PER_SECOND
    reply_tokens = body.get("eval_count", 0)
    tokens_per_second = round(reply_tokens / generate_seconds, 1) if generate_seconds > 0 else 0.0
    return {
        "reply": body["message"]["content"],
        "done_reason": body.get("done_reason"),
        "prompt_tokens": body.get("prompt_eval_count", 0),
        "reply_tokens": reply_tokens,
        "load_seconds": round(body.get("load_duration", 0) / NANOSECONDS_PER_SECOND, 2),
        "prompt_seconds": round(body.get("prompt_eval_duration", 0) / NANOSECONDS_PER_SECOND, 2),
        "generate_seconds": round(generate_seconds, 2),
        "total_seconds": round(body.get("total_duration", 0) / NANOSECONDS_PER_SECOND, 2),
        "tokens_per_second": tokens_per_second,
    }


def print_timing(timing):
    print(f"load model       : {timing['load_seconds']:>7.2f} s   (0 once it is already in memory)")
    print(f"read the prompt  : {timing['prompt_seconds']:>7.2f} s   ({timing['prompt_tokens']} tokens)")
    print(f"write the reply  : {timing['generate_seconds']:>7.2f} s   ({timing['reply_tokens']} tokens)")
    print(f"total            : {timing['total_seconds']:>7.2f} s")
    print(f"speed            : {timing['tokens_per_second']:>7.1f} tokens per second, one request at a time")


# ---------------------------------------------------------------------------
# Generation parameters: the same prompt, different settings, twice each
# ---------------------------------------------------------------------------


def chat_openai_style(model_name, messages, settings, base_url=None, timeout=600):
    """POST /v1/chat/completions - exactly what config/endpoints.py sends -
    and return the WHOLE response body, so the notebook can look at every
    field, not just the text. `settings` are OpenAI-style fields:
    temperature, top_p, max_tokens, seed, stop."""
    base_url = base_url or ollama_utils.server_url()
    request_body = {"model": model_name, "messages": messages}
    request_body.update(settings)
    response = requests.post(f"{base_url}/v1/chat/completions", json=request_body, timeout=timeout)
    if response.status_code != 200:
        raise ollama_utils.OllamaError(f"/v1/chat/completions failed: HTTP {response.status_code} "
                                       f"{response.text[:300]}")
    return response.json()


def run_experiments(model_name, messages, experiments, repeats=2, base_url=None):
    """For each named settings dict, ask the same question `repeats` times.

    Returns {name: {"settings", "replies": [...], "finish_reasons": [...],
                    "reply_tokens": [...], "identical": bool, "seconds": [...]}}

    `identical` is whether every repeat gave byte-for-byte the same text.
    That is the fact the participant is asked to predict per setting.
    """
    results = {}
    for name, settings in experiments.items():
        replies, finish_reasons, reply_tokens, seconds = [], [], [], []
        for _ in range(repeats):
            started = time.time()
            body = chat_openai_style(model_name, messages, settings, base_url=base_url)
            seconds.append(round(time.time() - started, 2))
            choice = body["choices"][0]
            replies.append(choice["message"]["content"])
            finish_reasons.append(choice.get("finish_reason"))
            reply_tokens.append(body.get("usage", {}).get("completion_tokens"))
        results[name] = {
            "settings": settings,
            "replies": replies,
            "finish_reasons": finish_reasons,
            "reply_tokens": reply_tokens,
            "identical": len(set(replies)) == 1,
            "seconds": seconds,
        }
    return results


def common_prefix_length(texts):
    """How many leading characters every text in the list shares."""
    if not texts:
        return 0
    shortest = min(len(text) for text in texts)
    for position in range(shortest):
        if len({text[position] for text in texts}) > 1:
            return position
    return shortest


def print_experiments(results, width=90):
    for name, result in results.items():
        print(f"=== {name}: {json.dumps(result['settings'])}")
        for number, reply in enumerate(result["replies"], start=1):
            shown = one_line(reply, width)
            print(f"  try {number}: {shown}")
            print(f"         finish_reason={result['finish_reasons'][number - 1]}  "
                  f"tokens={result['reply_tokens'][number - 1]}  {result['seconds'][number - 1]} s")
        if result["identical"]:
            print(f"  the {len(result['replies'])} replies are IDENTICAL")
        else:
            shared = common_prefix_length(result["replies"])
            print(f"  the {len(result['replies'])} replies are DIFFERENT (identical for the first {shared} characters)")
            if result["settings"].get("temperature", 1.0) == 0:
                print("  ... at temperature 0. 'Always the likeliest token' still depends on what the server did just")
                print("  before (its cache, its batch shape), and a small model has many near-tied tokens.")
        print()


# ---------------------------------------------------------------------------
# Reading a reply
# ---------------------------------------------------------------------------


def one_line(text, width=90):
    """Collapse whitespace and cut to `width` characters for a table cell.
    Non-ASCII characters are escaped so a Windows console can show them."""
    flat = " ".join(str(text).split())
    flat = flat.encode("ascii", "backslashreplace").decode("ascii")
    if len(flat) > width:
        return flat[: width - 3] + "..."
    return flat


def parse_json_reply(text):
    """Try to read a reply as ONE JSON object, the way the eval harness does.

    Returns (record_or_None, verdict) where verdict is one of:
        "valid JSON object"          json.loads worked and gave a dict
        "JSON inside a code fence"   fenced - a human sees JSON, a parser does not
        "not JSON"                   anything else
    """
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed, "valid JSON object"
        return None, "not JSON"
    except json.JSONDecodeError:
        pass
    if stripped.startswith("```"):
        inner = stripped.strip("`")
        if inner.startswith("json"):
            inner = inner[4:]
        try:
            parsed = json.loads(inner.strip())
            if isinstance(parsed, dict):
                return parsed, "JSON inside a code fence"
        except json.JSONDecodeError:
            pass
    return None, "not JSON"


def marks_text(marks, total):
    """One phrase for a table cell: '4/6 right; wrong: urgency, impact'.
    A reply with no readable record says so instead of '0/6 right'."""
    if len(marks["missing"]) == total:
        return f"no readable record (0/{total})"
    return f"{len(marks['right'])}/{total} right; wrong: {', '.join(marks['wrong']) or '-'}"


def compare_records(record, expected):
    """Which of the expected fields the record got exactly right.
    Returns {"right": [...], "wrong": [...], "missing": [...]}"""
    right, wrong, missing = [], [], []
    for field, expected_value in expected.items():
        if record is None or field not in record:
            missing.append(field)
        elif record[field] == expected_value:
            right.append(field)
        else:
            wrong.append(field)
    return {"right": right, "wrong": wrong, "missing": missing}


# ---------------------------------------------------------------------------
# The side-by-side table
# ---------------------------------------------------------------------------


def side_by_side(rows, left_title, right_title, label_width=22, column_width=36):
    """Render [(label, left_value, right_value), ...] as an ASCII table
    under 100 columns. Long values are cut, never wrapped."""
    lines = []
    header = f"{'':<{label_width}} | {left_title:<{column_width}} | {right_title:<{column_width}}"
    lines.append(header)
    lines.append("-" * len(header))
    for label, left, right in rows:
        lines.append(f"{label:<{label_width}} | {one_line(left, column_width):<{column_width}} "
                     f"| {one_line(right, column_width):<{column_width}}")
    return "\n".join(lines)
