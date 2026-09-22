"""Checks for scripts/concurrency_test.py and the two versions of notebook 03.

    python -m pytest tests/test_concurrency_test.py -v

The script's helpers are pure and tested directly; the network parts are
tested against a tiny local HTTP server that answers like an
OpenAI-compatible endpoint (slowly, on purpose, so concurrency is visible)
and against a port nobody listens on. No Ollama needed. The notebook
checks read the .ipynb files; they do not execute them. Executing the
solution needs Ollama with llama3.2:1b - about four minutes on the build
machine:

    python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/03_concurrency.ipynb
"""

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import concurrency_test as ct  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "concurrency_test.py"
NOTEBOOK = "03_concurrency.ipynb"
TODO_CELL_IDS = ["load-todo", "knee-todo"]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_parse_levels():
    assert ct.parse_levels("1,2,4,8") == [1, 2, 4, 8]
    assert ct.parse_levels(" 3, 1 ") == [3, 1]
    with pytest.raises(ValueError):
        ct.parse_levels("0,2")
    with pytest.raises(ValueError):
        ct.parse_levels("2,2")
    with pytest.raises(ValueError):
        ct.parse_levels("")


def test_percentile_is_nearest_rank():
    values = list(range(1, 17))           # 1..16
    assert ct.percentile(values, 0.5) == 8
    assert ct.percentile(values, 0.95) == 15   # the second-slowest of 16
    assert ct.percentile(values, 1.0) == 16
    assert ct.percentile([7.0], 0.95) == 7.0
    assert ct.percentile([], 0.5) is None


def result(seconds, ok=True, tokens=64, error=None):
    return {"seconds": seconds, "ok": ok, "status": 200 if ok else None, "reply_tokens": tokens if ok else None,
            "error": error}


def test_summarise_level_counts_failures_and_does_not_average_them_in():
    results = [result(1.0), result(2.0), result(3.0), result(60.0, ok=False, error="timeout"),
               result(0.1, ok=False, error="HTTP 429")]
    row = ct.summarise_level(4, results, wall_seconds=10.0)
    assert row["requests"] == 5 and row["ok"] == 3 and row["failed"] == 2
    assert row["p50_seconds"] == 2.0 and row["max_seconds"] == 3.0
    assert row["requests_per_second"] == 0.3
    assert row["reply_tokens"] == 192 and row["reply_tokens_per_second"] == 19.2
    assert row["errors"] == {"timeout": 1, "HTTP 429": 1}


def test_summarise_level_with_nothing_back():
    row = ct.summarise_level(8, [result(60.0, ok=False, error="timeout")] * 3, wall_seconds=60.0)
    assert row["ok"] == 0 and row["failed"] == 3
    assert row["p50_seconds"] is None and row["p95_seconds"] is None and row["max_seconds"] is None
    assert row["requests_per_second"] == 0.0


def sample_levels():
    return [
        ct.summarise_level(1, [result(4.0)] * 4, 16.0),
        ct.summarise_level(2, [result(4.2)] * 4, 8.4),
        ct.summarise_level(4, [result(8.0)] * 4, 8.0),
        ct.summarise_level(8, [result(16.0)] * 3 + [result(60.0, ok=False, error="timeout")], 16.0),
    ]


def test_highest_level_within_target():
    levels = sample_levels()
    assert ct.highest_level_within(levels, 10.0)["concurrency"] == 4
    assert ct.highest_level_within(levels, 4.1)["concurrency"] == 1
    assert ct.highest_level_within(levels, 3.0) is None
    # a level with a failure never qualifies, however good its p95
    assert ct.highest_level_within(levels, 100.0)["concurrency"] == 4


def test_table_and_chart_are_ascii_and_under_100_columns():
    for text in (ct.render_table(sample_levels()), ct.text_chart(sample_levels())):
        assert text.isascii()
        for line in text.splitlines():
            assert len(line) <= 100, line
    table = ct.render_table(sample_levels())
    assert "1 x timeout" in table
    chart = ct.text_chart(sample_levels())
    assert "1 failed" in chart
    assert "16 at once" not in chart and "  8 at once |" in chart


def test_chart_with_no_replies_at_all_does_not_crash():
    levels = [ct.summarise_level(1, [result(1.0, ok=False, error="connection")], 1.0)]
    chart = ct.text_chart(levels)
    assert "no reply came back" in chart


def test_parallel_slots_from_log(tmp_path):
    log = tmp_path / "ollama_server.log"
    log.write_text('msg=load request="{Operation:commit Parallel:1 BatchSize:512}"\n'
                   'msg=load request="{Operation:commit Parallel:4 BatchSize:512}"\n', encoding="utf-8")
    assert ct.parallel_slots_from_log(log) == 4
    assert ct.parallel_slots_from_log(tmp_path / "missing.log") is None
    log.write_text("nothing useful\n", encoding="utf-8")
    assert ct.parallel_slots_from_log(log) is None


def test_load_prompts_drops_the_answer():
    prompts = ct.load_prompts(REPO_ROOT / "data" / "eval" / "heldout_20.jsonl")
    assert len(prompts) == 20
    for messages in prompts:
        assert [m["role"] for m in messages] == ["system", "user"]


# ---------------------------------------------------------------------------
# The network path, against a stand-in server
# ---------------------------------------------------------------------------


class SlowChatHandler(BaseHTTPRequestHandler):
    """Answers /v1/chat/completions after a fixed delay, one request per thread."""
    delay = 0.2
    lock = threading.Lock()
    in_flight = 0
    peak = 0

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        with SlowChatHandler.lock:
            SlowChatHandler.in_flight += 1
            SlowChatHandler.peak = max(SlowChatHandler.peak, SlowChatHandler.in_flight)
        time.sleep(self.delay)
        with SlowChatHandler.lock:
            SlowChatHandler.in_flight -= 1
        if body.get("model") == "missing":
            self.send_response(404)
            self.end_headers()
            return
        reply = {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 10, "completion_tokens": body.get("max_tokens", 1)}}
        payload = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


from socketserver import ThreadingMixIn  # noqa: E402


class ThreadedServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


@pytest.fixture(scope="module")
def stand_in():
    server = ThreadedServer(("127.0.0.1", 0), SlowChatHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def test_run_level_really_runs_requests_concurrently(stand_in):
    SlowChatHandler.peak = 0
    prompts = [[{"role": "user", "content": "hi"}]]
    results, wall = ct.run_level(stand_in, {}, "m", prompts, concurrency=4, request_count=8,
                                 max_tokens=5, timeout=5)
    assert all(r["ok"] for r in results) and len(results) == 8
    assert all(r["reply_tokens"] == 5 for r in results)
    assert SlowChatHandler.peak == 4
    assert wall < 8 * SlowChatHandler.delay       # faster than sequential


def test_one_request_reports_kinds_of_failure(stand_in):
    prompt = [{"role": "user", "content": "hi"}]
    timed_out = ct.one_request(stand_in, {}, "m", prompt, 5, timeout=0.05)
    assert timed_out["ok"] is False and timed_out["error"] == "timeout"
    not_found = ct.one_request(stand_in, {}, "missing", prompt, 5, timeout=5)
    assert not_found["ok"] is False and not_found["error"] == "HTTP 404" and not_found["status"] == 404
    refused = ct.one_request("http://127.0.0.1:9/v1", {}, "m", prompt, 5, timeout=5)
    assert refused["ok"] is False and refused["error"] == "connection"


def run_script(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


def test_script_end_to_end_against_the_stand_in(stand_in, tmp_path):
    completed = run_script("--base-url", stand_in, "--model", "m", "--levels", "1,2,4", "--requests", "4",
                           "--out", str(tmp_path), "--run-id", "t", "--timeout", "5")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.isascii()
    assert "concurrency  requests    ok  failed" in completed.stdout
    summary = json.loads((tmp_path / "t_summary.json").read_text(encoding="utf-8"))
    assert [row["concurrency"] for row in summary["levels"]] == [1, 2, 4]
    assert all(row["ok"] == 4 and row["failed"] == 0 for row in summary["levels"])
    assert summary["settings"]["requests_per_level"] == 4
    rows = (tmp_path / "t_requests.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 12


def test_script_exits_2_at_once_when_nothing_listens(tmp_path):
    started = time.time()
    completed = run_script("--base-url", "http://127.0.0.1:9/v1", "--model", "m", "--out", str(tmp_path))
    assert completed.returncode == 2
    assert "NOTHING MEASURED" in completed.stderr
    assert time.time() - started < 30
    assert not list(tmp_path.glob("*.json"))


def test_script_exits_2_on_a_timeout_not_hangs(tmp_path):
    # A non-routable address: the connect never completes. The preflight must give up at --timeout.
    started = time.time()
    completed = run_script("--base-url", "http://10.255.255.1/v1", "--model", "m", "--timeout", "3",
                           "--out", str(tmp_path))
    assert completed.returncode == 2
    assert "NOTHING MEASURED" in completed.stderr
    assert time.time() - started < 30


def test_script_refuses_bad_arguments(tmp_path):
    assert run_script("--levels", "0,1").returncode == 2
    assert run_script("--base-url", "http://127.0.0.1:9/v1").returncode == 2    # --model missing
    assert run_script("--endpoint", "nowhere").returncode == 2


# ---------------------------------------------------------------------------
# Notebook 03: hygiene (Contract 2) and what this lab promises
# ---------------------------------------------------------------------------


def load_cells(folder):
    return json.loads((REPO_ROOT / folder / NOTEBOOK).read_text(encoding="utf-8"))["cells"]


def source_of(cell):
    return "".join(cell["source"])


def printed_by(cell):
    return "".join("".join(output.get("text", "")) for output in cell["outputs"])


def cell_by_id(cells, cell_id):
    return next(cell for cell in cells if cell["id"] == cell_id)


@pytest.fixture(scope="module")
def participant_cells():
    return load_cells("notebooks")


@pytest.fixture(scope="module")
def solution_cells():
    return load_cells("solutions")


def test_participant_outputs_are_cleared(participant_cells):
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [], f"cell {cell['id']} has outputs"
            assert cell["execution_count"] is None


def test_the_two_versions_differ_only_in_the_todo_cells(participant_cells, solution_cells):
    assert [c["id"] for c in participant_cells] == [c["id"] for c in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            assert source_of(mine) != source_of(theirs)
        else:
            assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs"


def test_todo_cells_have_a_gap_a_hint_and_a_loud_failure(participant_cells):
    todo_cells = [c for c in participant_cells if c["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 2
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "= ..." in source
        assert "Hint:" in source
        assert f"TODO {number} is not filled in yet" in source


def test_the_solution_has_no_gap_left(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            for line in source_of(cell).splitlines():
                code = line.split("#")[0]
                assert "= ..." not in code, f"cell {cell['id']}: {line}"


def test_first_code_cell_is_the_environment_detection_cell(participant_cells):
    template = json.loads((REPO_ROOT / "notebooks" / "_template.ipynb").read_text(encoding="utf-8"))
    template_first = next(c for c in template["cells"] if c["cell_type"] == "code")
    first = next(c for c in participant_cells if c["cell_type"] == "code")
    assert source_of(first) == source_of(template_first)


def test_every_code_cell_has_a_markdown_cell_before_it(participant_cells):
    for position, cell in enumerate(participant_cells):
        if cell["cell_type"] == "code":
            assert participant_cells[position - 1]["cell_type"] == "markdown", cell["id"]


def test_header_declares_runtime_needs_and_correct_result(participant_cells):
    header = source_of(participant_cells[0])
    for phrase in ["**Expected runtime:**", "**Needs:**", "**A correct result looks like:**",
                   "15 minutes", "CONCURRENCY LAB DONE", "If the runtime disconnects", "T4"]:
        assert phrase in header, phrase
    for placeholder in ["TBD", "__", "SINGLE_S", "XX"]:
        assert placeholder not in header


def test_installs_are_exactly_pinned_and_match_requirements(participant_cells):
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    install_lines = [line for c in participant_cells for line in source_of(c).splitlines() if "%pip install" in line]
    assert install_lines
    for line in install_lines:
        assert "-U" not in line.split() and "--upgrade" not in line
        packages = [word for word in line.split() if "==" in word]
        assert packages, line
        for package in packages:
            assert package in requirements, package


def test_never_asks_for_a_bigger_accelerator_or_pro(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        for forbidden in ["A100", "L4 GPU", "V100", "High-RAM", "Colab Pro"]:
            assert forbidden not in source_of(cell)
    metadata = json.loads((REPO_ROOT / "notebooks" / NOTEBOOK).read_text(encoding="utf-8"))["metadata"]
    assert metadata["colab"]["gpuType"] == "T4"


def test_ollama_comes_only_from_the_shared_helper(participant_cells):
    """No second install path: no curl, no install.sh, no pip for Ollama."""
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            source = source_of(cell)
            assert "curl" not in source and "install.sh" not in source
    server = source_of(cell_by_id(participant_cells, "server"))
    assert "ollama_utils.ensure_server(IN_COLAB" in server
    assert "ollama_utils.ensure_model(" in server and "ollama_utils.warm_up(" in server


def test_a_colab_cpu_runtime_is_refused(participant_cells):
    server = source_of(cell_by_id(participant_cells, "server"))
    assert "if IN_COLAB and gpu is None:" in server
    assert "raise RuntimeError" in server


def test_the_caveat_is_stated_where_the_results_appear(participant_cells):
    """The notebook must say, in plain words, next to the chart and the table, that the
    numbers are this runtime's and not OQ's production numbers."""
    header = source_of(participant_cells[0])
    chart_why = source_of(cell_by_id(participant_cells, "chart-why"))
    table_why = source_of(cell_by_id(participant_cells, "table-why"))
    final = source_of(cell_by_id(participant_cells, "final"))
    assert "not what OQ would see in production" in header
    assert "not what OQ would see in production" in chart_why
    assert "the numbers are this machine's" in table_why
    assert "not OQ's production numbers" in final


def test_the_notebook_scores_nothing_itself_and_calls_the_script(participant_cells):
    load = source_of(cell_by_id(participant_cells, "load-todo"))
    assert "compare_utils.run_command(command)" in load
    assert '"--endpoint", "local"' in load
    assert "utils.load_json(load_dir" in load          # milestone: load the saved result instead of re-running
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            assert "ThreadPoolExecutor" not in source_of(cell)


def test_the_solution_ran_clean_and_shows_the_lesson(solution_cells):
    """The retained solution is a real run: every code cell has an execution count, none
    errored, and the table shows the sequential-backend shape."""
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is not None, cell["id"]
            for output in cell["outputs"]:
                assert output.get("output_type") != "error", cell["id"]
    final = printed_by(cell_by_id(solution_cells, "final"))
    assert "CONCURRENCY LAB DONE" in final
    assert "not OQ's production numbers" in final
    server = printed_by(cell_by_id(solution_cells, "server"))
    assert "requests processed at once (OLLAMA_NUM_PARALLEL): 1" in server
    table = printed_by(cell_by_id(solution_cells, "table"))
    # the lesson, in numbers: p95 at 16 callers is several times p95 at 1; throughput plateaus
    ratio_line = next(line for line in table.splitlines() if line.startswith("p95 latency"))
    ratio = float(ratio_line.split("(")[-1].rstrip("x)"))
    assert ratio >= 3.0, ratio_line
    # ... and throughput has hit its ceiling: the last two levels are within 15% of each other
    summary = json.loads((REPO_ROOT / "facilitator" / "prebaked_outputs" / "concurrency"
                          / "03_load_llama3.2_1b_1-2-4-8-16_summary.json").read_text(encoding="utf-8"))
    last, before = summary["levels"][-1], summary["levels"][-2]
    assert abs(last["requests_per_second"] - before["requests_per_second"]) <= 0.15 * before["requests_per_second"]
    assert "requests processed at once (OLLAMA_NUM_PARALLEL): 1" in server
    # the pre-baked summary IS the retained run's summary
    assert str(last["p95_seconds"]) in table


def test_the_solution_todo_values_agree_with_its_own_output(solution_cells):
    load = source_of(cell_by_id(solution_cells, "load-todo"))
    assert "LEVELS = [1, 2, 4, 8, 16]" in load
    knee = source_of(cell_by_id(solution_cells, "knee-todo"))
    assert "LATENCY_TARGET_SECONDS = 10" in knee
    knee_output = printed_by(cell_by_id(solution_cells, "knee-todo"))
    assert "latency target      : p95 <= 10 s" in knee_output
    assert "callers inside it   :" in knee_output
