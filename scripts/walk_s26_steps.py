"""Walk the S26 build sequence as a participant would, and save the output.

    python scripts/walk_s26_steps.py --out facilitator/prebaked_outputs/mcp_server

Copies each checkpoint (services/mcp_server_reference/steps/, then
server.py) over s26_server.py in the repo root, starts it on port 8100
with the mock ERP on port 8000, runs that step's commands from
facilitator/mcp_build_sequence.md, and writes step<N>.txt, the audit log
(audit_after_walk.jsonl) and timings.json to --out. Deletes
s26_server.py at the end. Ports 8000 and 8100 must be free.
About a minute; step 8 runs the MCP Inspector, so it needs Node.js.
"""

import argparse
import difflib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description="Walk the S26 build sequence.")
parser.add_argument("--out", type=Path, required=True, help="folder for the transcripts")
OUT = parser.parse_args().out
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(REPO))

from services.mcp_server_reference.launch import start_in_background, stop  # noqa: E402
from services.mock_erp.launch import start_in_background as start_erp, stop as stop_erp  # noqa: E402

PY = sys.executable
PARTICIPANT = REPO / "s26_server.py"
AUDIT = REPO / "checkpoints" / "local" / "mcp_audit" / "s26_walk.jsonl"
STEPS = "services/mcp_server_reference/steps"
WO = "facilitator/prebaked_outputs/mcp_server/work_order.json"
WO2 = "facilitator/prebaked_outputs/mcp_server/work_order_2.json"

timings = []
previous_text = ""


def run(command, env_extra=None, log=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.update(env_extra or {})
    started = time.monotonic()
    done = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)
    seconds = time.monotonic() - started
    text = f"$ {' '.join(command[1:] if command[0] == PY else command)}\n{done.stdout}{done.stderr}"
    text += f"[exit {done.returncode}, {seconds:.1f} s]\n\n"
    if log is not None:
        log.append(text)
    return done, seconds


def write_lf(path, text):
    """Write with LF line endings on every OS (write_text gives CRLF on Windows)."""
    path.write_bytes(text.encode("utf-8"))


def changed_lines(old, new):
    count = 0
    for line in difflib.ndiff(old.splitlines(), new.splitlines()):
        if line.startswith("+ ") and line[2:].strip() and not line[2:].strip().startswith("#"):
            count += 1
    return count


def step(number, title, checkpoint, commands, enable_writes=False, env=None):
    global previous_text
    log = [f"STEP {number}: {title}\ncheckpoint: {checkpoint}\n\n"]
    source = (REPO / checkpoint).read_text(encoding="utf-8")
    code_part = source.split('"""', 2)[2]
    typed = changed_lines(previous_text, code_part)
    previous_text = code_part
    shutil.copyfile(REPO / checkpoint, PARTICIPANT)
    started = time.monotonic()
    server = start_in_background(port=8100, module="s26_server", enable_writes=enable_writes,
                                 audit_log=AUDIT, env=env,
                                 log_path=REPO / "checkpoints" / "local" / "s26_server.log")
    start_seconds = time.monotonic() - started
    command_seconds = 0.0
    try:
        for command in commands:
            done, seconds = run([PY, "-m"] + command, log=log)
            command_seconds += seconds
    finally:
        stop(server)
    timings.append({"step": number, "title": title, "lines_typed": typed,
                    "server_start_s": round(start_seconds, 1),
                    "commands_s": round(command_seconds, 1)})
    write_lf(OUT / f"step{number}.txt", "".join(log))
    print(f"step {number}: typed {typed} lines, start {start_seconds:.1f} s, "
          f"commands {command_seconds:.1f} s")


CALL = "services.mcp_server_reference.call"
if AUDIT.exists():
    AUDIT.unlink()

walk_started = time.monotonic()
# Step 0: the ERP, as a participant starts it (no key: the lab default).
erp = start_erp(port=8000, api_key="")
try:
    step(1, "one tool", f"{STEPS}/step1_first_tool.py",
         [[CALL, "discover"], [CALL, "get_equipment", "tag=P-1201A", "--brief"]])
    step(2, "typed contract", f"{STEPS}/step2_typed_contract.py",
         [[CALL, "list", "--brief"], [CALL, "get_equipment", "tag=pump-one", "--brief"]])
    step(3, "more reads", f"{STEPS}/step3_more_reads.py",
         [[CALL, "list", "--brief"],
          [CALL, "get_maintenance_history", "tag=P-1201A", "limit=2", "--brief"],
          [CALL, "list_work_orders", "equipment_tag=P-1201A", "limit=2", "--brief"]])
    step(4, "audit", f"{STEPS}/step4_audit.py",
         [[CALL, "get_equipment", "tag=P-1201A", "--brief"],
          [CALL, "get_equipment", "tag=X-0000", "--brief"],
          [CALL, "delete_everything", "--brief"]])
finally:
    stop_erp(erp)

# Step 5: the ERP now demands a key. First the server without it, then with it.
erp = start_erp(port=8000, api_key="s26-lab-key-7f3a")
try:
    step("5a", "secrets: server has no key", f"{STEPS}/step4_audit.py",
         [[CALL, "get_equipment", "tag=P-1201A", "--brief"]], env={"MOCK_ERP_API_KEY": ""})
    step("5b", "secrets: key from the environment", f"{STEPS}/step4_audit.py",
         [[CALL, "get_equipment", "tag=P-1201A", "--brief"]],
         env={"MOCK_ERP_API_KEY": "s26-lab-key-7f3a"})
finally:
    stop_erp(erp)

erp = start_erp(port=8000, api_key="")
try:
    step("6a", "gated write, read-only start", "services/mcp_server_reference/server.py",
         [[CALL, "raise_work_order", "--args-file", WO, "--brief"]])
    step("6b", "gated write, --enable-writes", "services/mcp_server_reference/server.py",
         [[CALL, "raise_work_order", "--args-file", WO, "--approve", "planner:salim",
           "--reason", "seal history checked"],
          [CALL, "list_work_orders", "source_ticket=INC-004412", "--brief"]],
         enable_writes=True)
    step(7, "try to break the gate", "services/mcp_server_reference/server.py",
         [[CALL, "raise_work_order", "--args-file", WO2, "--brief", "--reject",
           "planner:aisha", "--reason", "duplicate of the job raised in step 6"],
          [CALL, "raise_work_order", "--args-file", WO2, "--brief", "--no-forms"],
          [CALL, "raise_work_order", "--args-file", WO2, "--brief", "--approve",
           "intern:bob", "--reason", "looks fine"]],
         enable_writes=True)
finally:
    stop_erp(erp)

log = []
done, seconds = run([PY, "services/mcp_server_reference/test_inspector.py", "--module",
                     "s26_server", "--inspector"], log=log)
write_lf(OUT / "step8.txt", "".join(log))
timings.append({"step": 8, "title": "prove it", "lines_typed": 0, "server_start_s": 0,
                "commands_s": round(seconds, 1), "exit": done.returncode})
print(f"step 8: test_inspector exit {done.returncode}, {seconds:.1f} s")

audit_lines = AUDIT.read_text(encoding="utf-8").splitlines()
write_lf(OUT / "audit_after_walk.jsonl", "\n".join(audit_lines) + "\n")
write_lf(OUT / "timings.json", json.dumps(timings, indent=1))
PARTICIPANT.unlink()
print(f"walk total machine time {time.monotonic() - walk_started:.1f} s; "
      f"{len(audit_lines)} audit lines")
