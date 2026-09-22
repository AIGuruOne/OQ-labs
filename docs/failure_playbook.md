# Failure playbook

**Find it fast:** Ctrl+F the words the participant said out loud, or
scan the index. Each entry is laid out as They say / Radius /
Diagnose / Fix / Fallback / Tested.
**Trust level is in the "Tested" line.** REPRODUCED means it was broken on
purpose and the fix worked. SIMULATED means the code path was run
without Colab. NOT REPRODUCED means the entry comes from research only:
try the fix ONCE, then go straight to the fallback.

| # | They say | Radius |
|---|---|---|
| [1](#1-colab-will-not-load-or-connect) | "Colab won't open" / "access denied" / "stuck on Connecting" / "outputs are blank" | ROOM |
| [2](#2-downloads-crawl-on-the-venue-wi-fi) | "the pull is stuck at 12%" / "the download will take 40 minutes" | ROOM |
| [3](#3-pip-install-fails-on-the-oq-network) | "pip says the version doesn't exist" / "pip hangs" / "certificate verify failed" | ROOM |
| [4](#4-no-api-key-or-the-key-is-rejected) | "OPENAI_API_KEY not set" / "401" / "429" / "rate limit" | LAPTOP, ROOM if 429 |
| [5](#5-runtime-disconnected) | "Runtime disconnected" / "all my variables are gone" / `NameError` | LAPTOP, often several |
| [6](#6-no-gpu) | "Cannot connect to GPU backend" / "GPU : NONE" / "training crawls" | LAPTOP, often several |
| [7](#7-our-numbers-do-not-match-the-slide) | "we got 9/20, the slide says 8" / "fine-tuning made urgency worse" | ROOM (discussion) |
| [8](#8-installed-it-but-modulenotfounderror) | "I installed it but No module named" / "pip is compiling numpy" | LAPTOP |
| [9](#9-drive-will-not-mount) | "credential propagation was unsuccessful" / "mount failed" / "the popup didn't open" | LAPTOP, ROOM if sign-in blocked |
| [10](#10-ollama-will-not-answer) | "Is Ollama running?" / "Ollama is not installed" / "model not found" / "NOTHING MEASURED" | LAPTOP |
| [11](#11-out-of-memory) | "the laptop froze" / "requires more system memory" / "session crashed" / "CUDA out of memory" | LAPTOP |
| [12](#12-ollama-is-too-new-for-the-tuned-model) | "LoRA adapters are no longer supported" / "the install command gives 404" | LAPTOP |
| [13](#13-notebook-06-ignored-our-trained-adapter) | "it used THE PRE-BAKED ONE" / "run folder was started with different settings" | GROUP |
| [14](#14-port-already-in-use) | "address already in use" / "Only one usage of each socket address" / "Port 8000 is in use" | LAPTOP |
| [15](#15-pasted-tutorial-code-crashes-the-fine-tune) | "unexpected keyword argument 'warmup_ratio'" | GROUP |

**Colab blocked for everyone?** Go to [Part 2: the demo fallback ladder](#part-2-demo-fallback-ladder).
**Exact error text you don't see above?** Check [Part 3: the error-message reference](#part-3-error-message-reference-e1-e18).
The E-numbers there are the entry numbers this file used before
2026-09-23, so older notes that say "playbook entry 10" mean E10.

Ordered by likelihood x blast radius. ROOM = everyone stops. LAPTOP =
one participant; the room carries on while one person gets help. GROUP =
one capstone group.

---

# Part 1: the 15 room entries

## 1. Colab will not load or connect
- **They say:** "Colab won't open" / "it says access denied" / "blocked
  by policy" / "stuck on Connecting" / "cells won't run" / "the output is
  blank" / "it wants third-party cookies".
- **Radius:** ROOM if the OQ network blocks it. LAPTOP if the problem
  is that person's Google account.
- **Diagnose (one look):** open https://colab.research.google.com on the
  facilitator's laptop, on the same network, and run one cell.
  - It works: the network is fine. Look at the participant's account.
    Signed in with an OQ **work** Google account? An admin can switch
    Colab off for work users ("Users whose service is off can't access
    Colab", Google Workspace admin help).
  - It fails: the network. The whole room is affected.
  - Faster, without a browser: `python setup/setup_check.py --network`
    on any laptop names the blocked hosts (15 s on an open network).
    This is Python's view of the network, and a proxy can treat the
    browser differently.
- **Fix:**
  - Account: sign in with a personal Google account, in a separate
    browser profile.
  - Blank outputs, or a prompt about third-party cookies: allow
    third-party cookies for `googleusercontent.com` in the browser
    settings (Colab FAQ).
  - Network block: nothing fixes this in the room. Go to Part 2.
- **Fallback after 60 s:** [Part 2](#part-2-demo-fallback-ladder), step 2.
- **Worth knowing:** the Colab *runtime* is a machine in Google's data
  centre. Its pip installs, Ollama install, model pulls and git clone
  never touch OQ's network. If the Colab page works, the installs inside
  it work too, even when pip on the laptop is blocked (entry 3).
- **Tested:** NOT REPRODUCED. There is no OQ network here.
  - Measured 2026-09-22 on an open network: the host list and the
    status each host returns (`setup_check.py --network`). Also measured:
    a dead proxy and a proxy that answers 403, both of which the check
    reports as FAIL.
  - From Google's pages (primary sources): the Workspace switch and the
    cookie advice. Google publishes no allowlist for Colab.
  - The Sat 26 test in Part 2 is the real test.

## 2. Downloads crawl on the venue Wi-Fi
- **They say:** "the pull is stuck at 12%" / "the Ollama download says
  40 minutes" / "pip is taking forever".
- **Radius:** ROOM, for laptops only. On Colab the downloads run in
  Google's data centre: Ollama install 56 s, model pull 28 s on a T4
  (measured 2026-09-21), whatever the room's Wi-Fi is doing.
- **Diagnose:** is it a laptop or Colab? On a laptop, the pull's progress
  line shows MB/s. `llama3.2:1b` is 1.3 GB, so 1 MB/s means about 22
  minutes.
- **Fix:**
  - Move that group to Colab.
  - A pull that stopped: run the PULL CELL again (or `ollama pull
    llama3.2:1b`). It resumes where it stopped: measured, a re-pull began
    at 40 MB of 398 MB after a kill.
  - Stagger the downloads: one group at a time, not fifteen.
- **Fallback after 60 s:** the facilitator's USB kit (Part 2).
  - Models: quit Ollama. Copy the folder `models` from the kit over the
    laptop's `~/.ollama/models` (Windows: `%USERPROFILE%\.ollama\models`).
    Start Ollama again. `ollama list` should show `llama3.2:1b`.
  - Packages: use the wheelhouse on the same kit (entry 3).
- **Tested:** REPRODUCED 2026-09-22 on Windows, Ollama 0.12.10.
  - A pull killed after 6 s resumed on the next pull.
  - Copying `llama3.2:1b`'s manifest and blobs (6 files, 1.3 GB) into an
    empty store worked. A server started on that store listed the model
    with the same ID and answered in 6.9 s with no pull.
  - NOT tested: slow Wi-Fi itself (no throttling was done here); the
    copy on a Mac; copying into a store while Ollama is running (so quit
    it first).

## 3. pip install fails on the OQ network
- **They say:** "pip says the version doesn't exist" / "pip hangs, then
  fails" / "certificate verify failed" / "it says Retrying five times".
- **Radius:** ROOM, for laptops on the OQ network. Colab is not
  affected: its pip runs in Google's data centre.
- **Diagnose (one look):** `python setup/setup_check.py` and read the
  `PyPI reachable` row (7 s).
  - pip's own last line misleads: `ERROR: No matching distribution found
    for requests==2.32.4 (from versions: none)`. "from versions: none"
    means pip reached NOTHING. The pin is fine.
  - The cause is in the `WARNING: Retrying` lines above that last line:
    `ProxyError`, `ConnectTimeoutError`, or
    `SSLError(... CERTIFICATE_VERIFY_FAILED`.
- **Fix:**
  - The browser works through a proxy: ask OQ IT for its host and port,
    then run `python -m pip install --proxy http://HOST:PORT -r
    requirements.txt`.
  - `CERTIFICATE_VERIFY_FAILED` means the proxy inspects TLS. Ask OQ IT
    for the root certificate as a `.pem` file, then run `python -m pip
    install --cert ROOT.pem -r requirements.txt`.
  - pip 24.2 and later, on Python 3.10 and later, also trusts the
    Windows certificate store by itself (pip changelog 24.2). A venv
    made from Python 3.11.15 here came with pip **24.0**, which does not.
  - Ignore pip's "A new release of pip is available" notice. No upgrades
    in the room.
- **Fallback after 60 s:** install from the facilitator's USB wheelhouse,
  with no network at all:
  `python -m pip install --no-index --find-links WHEELHOUSE_FOLDER -r requirements.txt`.
  Or move the group to Colab.
- **Tested:** REPRODUCED 2026-09-22.
  - Failure times: a refused proxy fails after 22 s. A proxy that
    silently drops traffic fails after **103 s**, with the same
    misleading last line. `setup_check` reports both, and a proxy
    answering 403, as FAIL.
  - The wheelhouse: 115 files, 70 MB, built in 11 s. It installed into
    a fresh venv in 25 s with the proxy still dead, and the test suite
    passed on it.
  - Wheelhouses are per OS and per Python version. Windows ones for
    3.11 and 3.12 build from here. A Mac one must be built ON a Mac:
    cross-building from Windows fails with `pywin32` errors.
  - NOT REPRODUCED: TLS inspection, `--cert` and `--proxy` with a real
    proxy (no inspecting proxy here). Option text is from the pip
    26.2.1 docs.

## 4. No API key, or the key is rejected
- **They say:** "it says OPENAI_API_KEY not set" / "401" / "429" / "rate
  limit" / "it worked yesterday".
- **Radius:** LAPTOP for a missing, misspelt or wrong key. ROOM for a 429
  on a shared key: OpenAI applies limits "per organization and not per
  user", so fifteen people on one key share one limit.
- **Diagnose (one look):**
  - Local: `python setup/setup_check.py`, row `API key + live call`
    (6 s). It says which of three it is: `not set`; `Found OPEN_API_KEY`
    (a misspelling); or `rejected it (HTTP 401)`.
  - Colab: the key cell's first line says where it looked
    (`found in Colab Secrets` / `NOT SET`).
- **Fix:**
  - Missing, local: create `.env` at the repo root with exactly
    `OPENAI_API_KEY=...`, then re-run the key cell.
  - Wrong key (401), local: fix `.env`, then *Kernel > Restart & Run
    All*. A value already loaded wins over the file, so re-running the
    cell alone keeps the wrong key. Checkpoints make the re-run cheap.
  - Colab: key icon in the left sidebar > a secret named exactly
    `OPENAI_API_KEY` > *Notebook access* on > re-run the key cell. The
    paste prompt also works, but only for this runtime.
  - 429 for many people at once: this is the facilitator's problem, not
    theirs. Switch to the reserve key or top up credit. Read `error.code`:
    `credit_balance_exhausted` means money, and "Retrying ... won't
    restore API access".
- **Fallback after 60 s:** show the retained output of the lab
  (`solutions/01_fundamentals.ipynb`, `facilitator/prebaked_outputs/fundamentals/`).
- **Tested:** REPRODUCED 2026-09-22: missing, misspelt and wrong key, in
  both `setup_check` and the notebook helpers.
  - Found while reproducing: fixing `.env` and re-running the cell did
    NOT work. The key cell said "re-run this cell", which was untrue.
    Fixed in `notebooks/utils.py` the same day and tested. The wrong-key
    case still needs the restart, by design.
  - 429 and credit exhaustion: NOT REPRODUCED. Codes and quotes are from
    OpenAI's error-code page (primary, opened 2026-09-22).

## 5. Runtime disconnected
- **They say:** "it says Runtime disconnected" / "all my variables are
  gone" / "NameError: name 'CHECKPOINT_DIR' is not defined".
- **Radius:** LAPTOP. Often several at once after a break: Colab ends
  idle runtimes, and Google publishes no number for when.
- **Diagnose:** the Colab banner. Or a `NameError` on a name that an
  earlier cell set: the kernel is new.
- **Fix:** *Reconnect*, then *Runtime > Run all*. The first cell mounts
  Drive and clones the repo again, and every finished step reloads from
  its checkpoint. What a disconnect costs, measured:

  | Lab | Re-run after a disconnect |
  |---|---|
  | 03 | 19.6 s with everything saved. The WHOLE load test again (199 s locally, about a minute on a T4) if it died mid-test: the load driver saves only at the end |
  | 05 | resumes from the last checkpoint (one every 10 steps). Smoke run: resumed at step 4 of 6, 2.0 min |
  | 06 | 14 s with everything saved. Killed with 7 of 20 tuned replies saved: 1.0 min, only the 13 missing replies asked again |
  | 02, 03, 06 on a NEW Colab runtime | add the Ollama install (56 s) and the model pull (28 s) |

- **Fallback after 60 s:** show that lab's retained output (`solutions/`,
  `facilitator/prebaked_outputs/`). They re-run it in the next break.
- **Prevent it:** before lunch, tell the room to finish the running cell
  or expect to press *Run all* after the break.
- **Tested:** SIMULATED.
  - Kernel killed mid-run, then re-run, locally: 03 on 2026-09-22 (both
    rows above); 05, 05b and 06 on 2026-09-20.
  - NOT REPRODUCED ON COLAB: the Colab disconnect test is still owed
    for every notebook (`docs/timing_log.md`).

## 6. No GPU
- **They say:** "Cannot connect to GPU backend" / "GPU : NONE" / "No GPU
  in this Colab runtime" / "training is crawling".
- **Radius:** LAPTOP, but often several on Day 2 afternoon. The free GPU
  is "not guaranteed" (Colab FAQ), and quota is per Google account.
- **Diagnose (one look):** the notebook's first lines.
  - Notebook 05 prints `GPU        : NONE`.
  - Notebooks 02, 03 and 06 print `NVIDIA GPU: none found`.
  - A Colab dialog saying "You cannot currently connect to a GPU due to
    usage limits in Colab" means that account's GPU quota is used up.
- **Fix:**
  - No GPU selected: *Runtime > Change runtime type > T4 GPU > Save*,
    then *Run all*. Nothing is lost.
  - Quota used up: a teammate signs in with THEIR OWN account and runs
    it. Do not create extra accounts to get around a limit: the Colab
    FAQ forbids it.
  - Never Colab Pro.
- **Fallback after 60 s:**
  - 05: skip training. Notebook 06 then uses
    `checkpoints/adapter_prebaked/` by itself; that is what it is for.
  - 06: show `facilitator/prebaked_outputs/eval/06_base_vs_tuned/comparison.txt`.
  - 02 and 03: a laptop with Ollama is a supported path for these two.
- **Tested:**
  - REPRODUCED 2026-09-20 (E5, E12): the no-GPU paths ran on this
    machine, which has no NVIDIA GPU, and 06's refusal in a two-core
    container.
  - The quota dialog: NOT REPRODUCED. Its text comes from Colab GitHub
    issues of 2020 and 2022 (secondary sources), and may have changed.

## 7. Our numbers do not match the slide
- **They say:** "we got 9/20, the slide says 8" / "the other group got a
  different base score" / "fine-tuning made urgency WORSE" / "is ours
  broken?"
- **Radius:** ROOM. Nothing is broken, but the discussion can eat S12.
- **Diagnose (one look):** which column differs?
  - The BASE (untuned) column moves. At temperature 0, 9 to 12 of its 20
    replies change between machines and sittings. Schema-valid has been
    seen at 9, 10, 12 and 13 of 20.
  - The TUNED column was identical ticket for ticket on Windows, Linux
    and the T4.
- **Fix:** nothing to fix. Say: "the untuned model is inconsistent. That
  is the finding, and it's why we tune." Quote base numbers as "about".
  - For urgency (tuned 7/20 against the untuned 3B's 13/20): first show
    `facilitator/prebaked_outputs/eval/comparison_base1b_vs_tuned.txt`,
    the same model before and after, where urgency goes from 4/20 up to
    7/20 (5/20 up to 7/20 in notebook 06's own run). Then use the
    per-class rows.
- **Fallback after 60 s:** move on. The per-class rows carry the point.
- **Tested:** REPRODUCED, measured across three machines, 2026-09-20 and
  2026-09-21 (E8, E10).

## 8. Installed it but ModuleNotFoundError
- **They say:** "I installed it but it says No module named 'mcp'" / "pip
  is building numpy" / "Unknown compiler(s)" /
  "metadata-generation-failed".
- **Radius:** LAPTOP. Several, if people skipped the pre-program setup.
- **Diagnose (one look):**
  - In the failing notebook, run `import sys; print(sys.executable)`. In
    the terminal where they ran pip, run `python -c "import sys;
    print(sys.executable)"`. Two different paths means two Pythons.
  - Also run `python setup/setup_check.py` and read the `Python version`
    row. **3.14 = FAIL**: pinned numpy 2.1.3 has no 3.14 build, so pip
    tries to compile it. 3.13 = WARN: it installs, but is untested.
- **Fix:**
  - Two Pythons: point the notebook at the venv's kernel. In VS Code,
    use *Select Kernel* > `.venv`. For Jupyter, activate the venv first
    (`.venv\Scripts\activate`), then run `python -m notebook`.
  - Python 3.14: install Python 3.12 from python.org, then run
    `py -3.12 -m venv .venv` and
    `.venv\Scripts\python -m pip install -r requirements.txt`. That is
    five minutes, so it is the fallback, not the fix.
- **Fallback after 60 s:** that laptop uses Colab. Nothing to install there.
- **Tested:** REPRODUCED 2026-09-22.
  - `pip install numpy==2.1.3` in a Python 3.14 venv failed in 13 s with
    `ERROR: Unknown compiler(s)`.
  - `ModuleNotFoundError: No module named 'mcp'` came from this
    machine's default Python while the venv had it.
  - Found here: `setup_check` only WARNed on 3.14, and blamed the Day 2
    packages. Since 2026-09-22 it FAILs with the reason.
  - E6 is the headless-nbconvert version of the same trap (2026-09-20).

## 9. Drive will not mount
- **They say:** "the first cell failed" / "credential propagation was
  unsuccessful" / "mount failed" / "the Google popup didn't open". After
  that, every cell fails with `NameError: name 'CHECKPOINT_DIR'`.
- **Radius:** LAPTOP. ROOM if the OQ network or the browser policy
  blocks Google's sign-in popup; check entry 1 too.
- **Diagnose (one look):** the first cell's error.
  - `MessageError: Error: credential propagation was unsuccessful`: the
    popup was closed, blocked, or signed in as a different account.
  - `ValueError: mount failed: timeout during initial read of root
    folder`: Drive is slow, or My Drive's top level has too many files.
  - `ValueError: The domain policy has disabled Drive File Stream`: a
    work Google account where Drive is switched off.
  - `Mountpoint must not already contain files`: something was written
    to `/content/drive` before the mount.
- **Fix:**
  - Allow popups for `colab.research.google.com`. In the popup, pick
    the SAME account Colab is signed in with and tick every permission.
    Re-run the first cell.
  - Timeout: re-run the cell once.
  - Domain policy: use a personal account.
  - Mountpoint not empty: *Runtime > Disconnect and delete runtime*,
    then *Run all*.
- **Fallback after 60 s:** run WITHOUT Drive. Read out these two edits
  to the FIRST cell:
  1. put `#` in front of `drive.mount("/content/drive")`;
  2. change the checkpoint line to `CHECKPOINT_DIR = Path("/content/checkpoints")`.

  The lab runs. Checkpoints survive a reconnect to the same runtime,
  but NOT a new runtime.
- **Tested:** SIMULATED 2026-09-22.
  - The real first cell was run with a stand-in `google.colab` whose
    mount raised the verbatim errors. Each stopped the cell before
    `CHECKPOINT_DIR` was set. The two-line edit made it complete.
  - The error strings come from colabtools `drive.py` (main branch,
    primary). "credential propagation" comes from colabtools issue #5904
    (secondary): an open 2026 report that the popup never opens in
    Chrome 145. Another browser is the obvious try, but it is NOT verified.
  - NOT reproduced on Colab itself.

## 10. Ollama will not answer
- **They say:** "Is Ollama running?" / "Ollama is not installed on this
  machine" / "model not found" / "HTTP 404" / "NOTHING MEASURED.
  Preflight failed".
- **Radius:** LAPTOP, on the laptop path only. On Colab the server cell
  installs Ollama and starts it itself.
- **Diagnose (one look):** re-run the notebook's server cell. It prints
  what it found: the version and URL, or one of these messages.
  - `Endpoint 'local' unreachable ... Is Ollama running?`: no server
    running. **OR a proxy variable is catching `localhost`**: with
    `HTTP_PROXY` set, a running Ollama looks dead. Check with
    `gci env:*proxy*` (PowerShell) or `env | grep -i proxy` (Mac/Linux).
  - `Ollama is not installed on this machine`: not on `PATH`. Either it
    was installed after the kernel started, or it was never installed.
  - `Model 'llama3.2:1b' not found ... (HTTP 404)`: the model was never
    pulled, or the name is misspelt (`llama3.2:1b`, not `llama3.2-1b`).
  - `NOTHING MEASURED. Preflight failed` (notebook 03): the server cell
    above it was not run in this kernel (E16).
- **Fix:**
  - Not running: re-run the server cell. It starts `ollama serve`
    itself when Ollama is installed (6 s).
  - Proxy: add `NO_PROXY=localhost,127.0.0.1` to `.env`, then *Kernel >
    Restart & Run All*.
  - Not on `PATH`: restart the kernel, or open a new terminal. Never
    installed: `setup/ollama_setup.md` section 3.
  - 404: run the PULL CELL.
- **Fallback after 60 s:** that laptop moves to the Colab T4.
- **Tested:** REPRODUCED 2026-09-22.
  - Not installed: 4.1 s to the message.
  - The proxy trap: with `HTTP_PROXY` pointing at a dead proxy, calls
    to a running server failed with "Is Ollama running?". With
    `NO_PROXY` in `.env` they worked.
  - The 404 and preflight messages were provoked on purpose the same
    day (E14, E16).

## 11. Out of memory
- **They say:** "the laptop froze" / "everything is slow" / "model
  requires more system memory (15.9 GiB)" / "Your session crashed after
  using all available RAM" / "CUDA out of memory".
- **Radius:** LAPTOP.
- **Diagnose (one look):**
  - Laptop: `ollama ps`. `llama3.2:1b` at a 4096-token context shows
    1.4 GB, and so does its `CONTEXT` column (measured). A context in the
    tens of thousands, or a size of several GB, means the context length
    is too big. Task Manager > Memory shows the rest.
  - Colab: the crash banner. In notebook 05: `torch.OutOfMemoryError:
    CUDA out of memory. Tried to allocate ...`.
- **Fix:**
  - Laptop with Ollama: the desktop app's context-length slider set to
    its maximum makes `llama3.2:3b` need **15.9 GiB**. At 4096 it needs
    **2.3 GiB** (both measured). Set the app's context length to 4096,
    or quit the app and let the notebook's server cell start its own:
    the cell forces 4096.
  - Any laptop: close heavy apps. Kill leftover `python.exe` processes
    that still hold a model (E7).
  - Colab RAM crash: *Runtime > Restart session*, then *Run all*.
    Checkpoints carry the work.
  - CUDA OOM in 05: *Runtime > Restart session*. Put the settings back
    to the measured ones: `MODEL_NAME = "llama3.2-1b"`, `BATCH_SIZE = 4`,
    `MAX_LENGTH = 1024`. Use a new `RUN_NAME` if training settings
    changed (entry 13). Then *Run all*. Never a bigger GPU.
- **Fallback after 60 s:** show that lab's retained output. For 05, use
  the pre-baked adapter.
- **Tested:** partly.
  - REPRODUCED 2026-09-20: the 15.9 GiB refusal (E2).
  - The fix measured 2026-09-22: 15.9 GiB at the app's maximum, 2.3 GiB
    at 4096. BUT on 2026-09-22 the same setup did NOT refuse: Ollama
    swapped and loaded the model anyway. So the symptom may be "the
    laptop crawls", not an error.
  - Colab RAM crash and CUDA OOM: NOT REPRODUCED (no Colab here, no
    GPU). Their texts come from colabtools issue #5235 (secondary) and
    the PyTorch 2.11 source (primary).
  - CUDA OOM at the lab's settings is unlikely: the 1B model in 4-bit
    is 1.01 GB of the T4's 15 GB. Peak memory at batch 4 was never
    measured.

## 12. Ollama is too new for the tuned model
- **They say:** "the register cell failed" / "LoRA adapters are no
  longer supported" / "NOTE: this server is Ollama 0.34.2" / "the
  install command from the tutorial gives 404".
- **Radius:** LAPTOP: anyone who installed Ollama themselves.
- **Diagnose (one look):** `ollama --version`. The labs are pinned to
  **0.12.10**.
- **Fix:**
  - The tuned model (notebook 06) is **Colab T4 only**: open 06 in
    Colab. That is the supported path, not a workaround.
  - For 02 and 03 a newer Ollama is fine. Plain models still answer.
  - Do NOT downgrade Ollama on a participant laptop in the room. Never
    pipe `install.sh` into a notebook.
- **Fallback after 60 s:** show `facilitator/prebaked_outputs/eval/06_base_vs_tuned/comparison.txt`.
- **Tested:** REPRODUCED.
  - 2026-09-20: Ollama 0.34.2 and 0.33.3 containers (E11).
  - 2026-09-22: the tutorial's unversioned download URL returns 404,
    and the pinned one returns 200 (E15).

## 13. Notebook 06 ignored our trained adapter
- **They say:** "it says ADAPTER IN USE: THE PRE-BAKED ONE but we
  trained" / "RuntimeError: The run folder ... was started with
  different settings".
- **Radius:** GROUP.
- **Diagnose (one look):** notebook 06 prints a verdict line starting
  `->` for every folder it checked, just above the adapter line.
  - `folder does not exist`: the names in 06 differ from 05, or 05 ran
    under a different Google account.
  - `the weights file is cut off`: the runtime died while saving.
  - `no twin in Ollama`: that adapter was never registered with Ollama
    (a smoke-test run).
- **Fix:**
  - Names: `MODEL_NAME` and `RUN_NAME` in 06 must match notebook 05.
    Use the same Google account (so the same Drive). Re-run from the
    settings cell.
  - Cut-off file: re-run 05. It resumes and saves the adapter again.
  - Run-folder refusal in 05: set a new `RUN_NAME` (`"run2"`), then
    *Run all*.
- **Fallback after 60 s:** present with the pre-baked adapter, and say
  so when presenting.
- **Tested:** REPRODUCED 2026-09-20 (E4, E9): the folder deleted, and
  the weights file truncated to 9 MB, on purpose; also covered by
  `tests/test_compare_utils.py` and `tests/test_finetune_utils.py`.

## 14. Port already in use
- **They say:** "`ollama serve` stopped at once" / "address already in
  use" / "Only one usage of each socket address" / "Port 8000 is in use
  by something that is not the mock ERP".
- **Radius:** LAPTOP.
- **Diagnose (one look):** find out who holds the port.
  - Windows PowerShell:
    `Get-Process -Id (Get-NetTCPConnection -LocalPort 11434 -State Listen).OwningProcess`
  - Mac or Linux: `lsof -i :11434`.
  - For the mock ERP, use 8000 in place of 11434.
- **Fix:** the message names the next free port. Set
  `OLLAMA_BASE_URL=http://localhost:11435` in `.env` (or in `os.environ`
  in the settings cell) and run the cell again. Or stop the other
  program.
  - Mock ERP: add `--port 8001` and set
    `MOCK_ERP_URL=http://127.0.0.1:8001` (E18).
  - On Windows, a mock ERP that goes silent after a file save is
    different: that is `--reload` (E17).
- **Fallback after 60 s:** move to Colab.
- **Tested:** REPRODUCED 2026-09-22 with a plain HTTP server parked on
  the port. The message came in 4.2 s. The suggested next port served in
  6.3 s. The ERP side is E18.

## 15. Pasted tutorial code crashes the fine-tune
- **They say:** "TypeError: ... unexpected keyword argument
  'warmup_ratio'" (or `evaluation_strategy`, `group_by_length`,
  `tokenizer=`).
- **Radius:** GROUP.
- **Diagnose:** the `TypeError` names the argument. Code from a tutorial
  or a chatbot is written for transformers 4.x. Colab has 5.16.1.
- **Fix:** use the 5.x names:
  - `warmup_steps=0.1` (a float is a fraction)
  - `eval_strategy=`
  - `train_sampling_strategy="group_by_length"`
  - `processing_class=`

  Do NOT `pip install` an older transformers.
- **Fallback after 60 s:** paste the cell back from `solutions/05_finetune.ipynb`.
- **Tested:** REPRODUCED 2026-09-22 with transformers 5.16.1. All three
  old names raised `TypeError`, and the 5.x names were accepted.

---

# Part 2: demo fallback ladder

This is the top risk in BUILD_SPEC section 15: OQ's network policy
blocks Google, and the demo dies. There are three steps.

**Rule:** after 60 s on a step without progress, go down one step.
Never debug the network in front of the room.

## Before Day 1: what the facilitator machine needs (step 3 lives or dies here)
These are the commands for checking it. They were verified on the build
machine on 2026-09-22.

| Check | Command | Must show |
|---|---|---|
| Environment | `python setup/setup_check.py` | `RESULT: all checks passed` |
| Ollama version | `ollama --version` | `0.12.10`. This is the ONE machine that must be on 0.12.10 |
| Models | `ollama list` | `llama3.2:1b` and `oq-ticket-tuned` (register with `python scripts/register_adapter.py --adapter checkpoints/adapter_prebaked`) |
| Local Jupyter | `.venv\Scripts\python -m notebook solutions` | a browser tab listing the 7 solution notebooks (answered in 1 s here, notebook 6.5.7) |
| Nothing needs the network | turn Wi-Fi OFF, then *Run all* on `solutions/04_dataset_builder.ipynb` and `solutions/03_concurrency.ipynb` | `DATASET READY — environment=local`, `CONCURRENCY LAB DONE` |

**The USB kit** (entries 2 and 3). Keep it in the bag, not on Drive:
- The Ollama model store with `llama3.2:1b`: the `manifests/` and
  `blobs/` folders, 1.3 GB.
- Ollama 0.12.10 installers for Windows and macOS (the GitHub release
  `v0.12.10`).
- Python 3.12 installers.
- Wheelhouses, built with `python -m pip download -r requirements.txt -d wheelhouse-<os>-<py>`:
  - Windows, Python 3.11 and 3.12: 70 MB each, built on any Windows
    machine;
  - Mac: must be built on a Mac.
- A phone with a local data plan, and its cable.

## Step 1: Colab over the OQ network (the plan)
- **How it works:** the browser talks to colab.research.google.com. The
  runtime, a Google machine, does all installs and downloads.
- **What breaks here:** everything in [entry 1](#1-colab-will-not-load-or-connect):
  - the page;
  - Google sign-in;
  - the connection to the runtime;
  - the Drive popup;
  - rich outputs (third-party cookies for `googleusercontent.com`).
- **Say:** nothing. This is the plan.

## Step 2: Colab over the facilitator's phone hotspot
- **How to switch (facilitator laptop only, about 1 minute):**
  1. Turn on the phone's hotspot.
  2. On the laptop, leave OQ's Wi-Fi (or unplug the cable) and join the
     hotspot.
  3. Reload the Colab tab. The runtime is in Google's data centre, so
     it is still there unless it timed out. Reconnect, then *Run all*:
     finished steps reload from Drive.
  4. Run one cell to confirm.
- **What breaks:**
  - The room can no longer follow on their own laptops. A phone cannot
    carry 15 laptops, and OQ may not allow its staff to join an outside
    network: ask on Sat 26.
  - Mobile data: not measured. The heavy downloads happen in the
    runtime, so the hotspot carries only the page and the outputs.
  - Nothing else changes: same notebooks, same Drive, same numbers.
- **The room:**
  - Groups watch the projected demo.
  - Groups whose laptops passed the pre-program setup can run 02, 03
    and 04 locally alongside.
  - Everyone gets the notebook and its retained output in the repo for
    later.
- **Say:** "This network blocks Google's notebooks, so I've moved my
  laptop to my phone. Follow this lab on the screen. The notebook,
  its solution and every number I show are in the repo, so you can run
  it yourselves tonight."

## Step 3: fully local on the facilitator machine
- **How to switch (about 2 minutes):**
  1. `cd oq-advanced-ai`, then `.venv\Scripts\activate`.
  2. Run `ollama list` and check it shows `llama3.2:1b` and
     `oq-ticket-tuned`.
  3. Run `python -m notebook solutions` (or open the folder in VS Code).
  4. Open the lab's solution notebook, then *Run all*. Its first cell
     prints `Environment : local` and saves to `checkpoints/local`. The
     code is the same; the notebook switched paths by itself.
- **What breaks, lab by lab:**

  | Lab | Local? | What changes |
  |---|---|---|
  | 01 | needs `api.openai.com` | if OpenAI is blocked too: show `solutions/01_fundamentals.ipynb` and `facilitator/prebaked_outputs/fundamentals/` |
  | 02 | yes, except one hosted call | about 1 minute (measured) |
  | 03 | yes | 2.5 to 4 minutes (measured). The numbers are the laptop's, not a T4's. Say so |
  | 04 | yes | 7 seconds (measured) |
  | 05 | **no training**: about 3.5 hours on a CPU | show the retained T4 run in `solutions/05_finetune.ipynb`. The pre-baked adapter stands in |
  | 05b | Mac only | skip |
  | 06 | yes, on the facilitator's 0.12.10 | about 2.5 minutes (measured). It prints `LOCAL RUN - NOT A SUPPORTED PATH` on purpose: that is the participants' rule, not the facilitator's |
  | Day 5 mock ERP | yes | start it without `--reload` on Windows (E17) |

  Also: there is no Drive at this step. A crash of the facilitator
  laptop costs the lab, so show its pre-baked output.
- **Say:** "The network won't let us reach the cloud notebooks, so I'll
  run everything from my machine and you follow on screen. It's the same
  code: the first cell noticed it's running locally and switched paths.
  That's also how you'd run this inside OQ's own VM."

## Sat 26: what Ritesh checks from the OQ network port
Do this in the actual room, on the network participants will use. If
there is both a staff LAN and a guest Wi-Fi, test both. Use a
participant-type Google account: a personal one, and an OQ work one if
participants will use those. Write down pass or fail per line, with the
network name, and send it to Utkarsh.

| # | Check | Pass looks like | If it fails |
|---|---|---|---|
| 1 | `python setup/setup_check.py --network` | every host row PASS (15 s; up to 2 min if hosts time out) | note which hosts. Colab rows failing = step 2 is likely; pypi rows failing = laptops need the USB wheelhouse |
| 2 | open https://colab.research.google.com and sign in | the page loads, the sign-in completes | step 2 |
| 3 | open the *Open in Colab* link at the top of `notebooks/01_fundamentals.ipynb` | the notebook appears | GitHub or Colab blocked: step 2 |
| 4 | connect a CPU runtime; run the first cell | Drive popup completes, `Mounted at /content/drive`, then `Repo root : /content/oq-advanced-ai` | entry 9. Popup blocked by policy = ROOM |
| 5 | run notebook 04 to its first table | the table is visible | blank output = third-party cookies (entry 1) |
| 6 | leave the runtime idle 15 min, then run a cell | still connected | the proxy cuts long connections: warn the room, expect entry 5 after every break |
| 7 | *Change runtime type > T4 GPU*, run `!nvidia-smi`, then disconnect | `Tesla T4` | GPU not granted: entry 6 |
| 8 | Colab Secrets: add `OPENAI_API_KEY`; run notebook 01's key cell | `found in Colab Secrets` | entry 4. This is also the first ever Colab run of that cell |
| 9 | phone hotspot: join it, reload Colab | a cell runs | no signal in the room: step 2 is not available, go straight to step 3 |
| 10 | Wi-Fi off: run `solutions/04_dataset_builder.ipynb` and `solutions/03_concurrency.ipynb` locally | `DATASET READY`, `CONCURRENCY LAB DONE` | step 3 is broken: fix it before Sunday |

What was run on the build machine, 2026-09-22:
- Check 1 ran on an open network: all hosts PASS in 15 s. It was also
  run behind a dead proxy and behind a proxy answering 403: every row
  FAILs, with the reason.
- Check 10 ran with Python's internet cut by a dead proxy, NOT with
  Wi-Fi off. 04 finished in 9 s; 03 in 23 s, from its saved checkpoints.

No step has been run from an OQ network yet.

---

# Part 3: error-message reference (E1-E18)

The exact-text entries this playbook started from, which the Part 1
entries point to. The numbers are the ones this file used before
2026-09-23, so "playbook entry 10" in an older note means E10.

### E1. `OPENAI_API_KEY not set` (or 401 from the hosted API)
- **Symptom:** `setup_check.py` FAIL row, or `EndpointError: ... needs OPENAI_API_KEY`.
- **Cause:** no `.env` at repo root, or the variable is misspelled
  (seen in the wild as `OPEN_API_KEY` — setup_check names the
  misspelling when it sees one).
- **Fix:** `cp setup/.env.example .env`, set `OPENAI_API_KEY=...`
  exactly, re-run `python setup/setup_check.py`. In a notebook,
  re-run the key cell: since 2026-09-22 `utils.ensure_api_key` reads
  `.env` again each time. Before that, a `.env` fixed mid-session was
  not seen until a kernel restart, although the cell said "re-run this
  cell" (reproduced, fixed, `tests/test_fundamentals_utils.py`). A
  WRONG key already loaded still needs *Kernel > Restart*: a value in
  the environment beats the file, on purpose.
- **On Colab** (notebook 01 is the first that needs the hosted key
  there): the cloned repo has no `.env`. The key cell
  (`utils.ensure_api_key`) looks in Colab Secrets - key icon in the
  left sidebar, secret named exactly `OPENAI_API_KEY`, *Notebook
  access* switched on - and otherwise asks for a hidden one-time
  paste. A paste lasts for that runtime only; a disconnect means
  pasting again, a Secret does not. The Colab branch is untested on
  Colab as of 2026-09-22 (local branch tested); first Colab run of
  notebook 01 confirms it or lands here as its own entry.
- **Seen on:** 2026-09-19 (build machine).

### E2. Ollama: `model requires more system memory (15.9 GiB) than is available`
- **Symptom:** `EndpointError: Endpoint 'local' returned HTTP 500:
  {"error":{"message":"model requires more system memory (15.9 GiB)
  than is available (4.2 GiB)"...` for a model that is only 2 GB on
  disk. `run_eval.py` stops with "The endpoint is not answering".
- **Cause:** not the model - the context window. The Ollama desktop
  app has a context-length setting; at its maximum (262144 tokens) the
  KV cache alone needs many GB. `server.log` shows the giveaway line
  `requested context size too large for model num_ctx=262144`. A
  laptop with little free RAM hits this even at moderate settings.
- **Fix:** lower the context length in the Ollama app settings to
  4096 (the ticket prompts are under 1,000 tokens), or leave the app
  alone and start a second server:
  `OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 ollama serve`,
  then set `OLLAMA_BASE_URL=http://localhost:11435` in `.env`. In
  Colab the notebook starts the server itself, so set
  `OLLAMA_CONTEXT_LENGTH=4096` there too. Do NOT switch to a smaller
  or bigger model to get around it.
- **Seen on:** 2026-09-20 (build machine, Ollama 0.12.10, Windows 11,
  27.6 GB RAM with 3.2 GB free).
- **Not seen on 2026-09-22 under the same conditions:** a scratch
  server with `OLLAMA_CONTEXT_LENGTH=262144` and 4.5 GiB free.
  - `llama3.2:1b`: capped at its trained 131072 tokens, 5.2 GiB
    estimated, loaded in 18 s.
  - `llama3.2:3b`: 15.9 GiB estimated, and the log says `evicting a
    model to make space`. It LOADED anyway, in 20 s, leaning on swap.
  So the symptom can be a laptop that crawls instead of this error.
  The fix is the same: at 4096 the 3B model needs 2.3 GiB and loaded
  in 9 s.

### E3. Fine-tune notebook: `TypeError: TrainingArguments.__init__() got an unexpected keyword argument 'warmup_ratio'`
- **Symptom:** a participant pastes training arguments from a tutorial
  or a chatbot into notebook 05 and the `trainer` cell dies with an
  unexpected keyword: `warmup_ratio`, `group_by_length`,
  `evaluation_strategy`, or `tokenizer=` on `Trainer(...)`.
- **Cause:** Colab ships transformers 5.x. Those names are from 4.x
  and were removed. Almost everything on the web is still 4.x.
- **Fix:** use the 5.x names the notebook already has:
  `warmup_steps=0.1` (a float is a fraction), `train_sampling_strategy=
  "group_by_length"`, `eval_strategy=`, `processing_class=`. Do NOT
  `pip install` an older transformers to make the pasted code work.
- **Seen on:** 2026-09-20 (build machine, transformers 5.16.1 -
  found by introspecting the installed package before writing the cell).

### E4. Fine-tune notebook: `RuntimeError: The run folder ... was started with different settings (changed: lora_rank)`
- **Symptom:** the `runfolder` cell stops after a participant changes a
  TODO value and re-runs.
- **Cause:** by design. The run folder on Drive holds checkpoints made
  with the OLD settings; resuming them under new settings would
  produce a model nobody can describe.
- **Fix:** give the experiment a new `RUN_NAME` in the settings cell
  (`"run2"`) and Run all - the first run stays intact next to it. To
  really start over, delete the run folder it names.
- **Seen on:** 2026-09-20 (build machine; covered by
  `tests/test_finetune_utils.py`).

### E5. Fine-tune notebook: `GPU : NONE` and training crawls
- **Symptom:** the settings cell prints `GPU : NONE. A full run on a
  CPU takes hours`; the first training step takes minutes.
- **Cause:** the Colab runtime is a CPU runtime (the default), or the
  free GPU quota for that Google account is used up.
- **Fix:** *Runtime > Change runtime type > T4 GPU*, then Run all -
  nothing is lost, nothing had trained yet. Quota gone: pair up with a
  group that has a GPU, or skip training and use
  `checkpoints/adapter_prebaked/` in notebook 06 - that is what it is
  for. Measured for scale: 7.1 min on a T4, about 3.5 HOURS on a
  12-core laptop CPU. Do NOT reach for a paid tier.
- **Seen on:** 2026-09-20 (build machine has no GPU: ~40 tokens/s).

### E6. `ModuleNotFoundError: No module named 'torch'` when running a notebook headless, though torch IS installed
- **Symptom:** `python -m jupyter nbconvert --execute ...` fails on
  `import torch` inside the notebook, while `python -c "import torch"`
  works in the same terminal.
- **Cause:** two virtual environments. `python -m jupyter nbconvert`
  does not run nbconvert from the current interpreter - it launches
  the first `jupyter-nbconvert` on `PATH`, which belongs to whichever
  environment is *activated*, and the kernel starts there.
- **Fix:** call the module directly: `python -m nbconvert --to notebook
  --execute ...` using the interpreter of the environment you mean. If
  a stale `VIRTUAL_ENV` is set, clear it for the command
  (`env -u VIRTUAL_ENV ...`).
- **Seen on:** 2026-09-20 (build machine, `.venv` activated while
  running `.venv-finetune`).

### E7. Background work dies, or Ollama/Docker stop answering: the machine is out of RAM
- **Symptom:** long jobs vanish or stall with no error; everything is
  slow; Task Manager shows under 1 GB free.
- **Cause:** a killed notebook run can leave its kernel process alive,
  holding the whole model (9 GB seen here), and a Docker container
  left running holds its VM's memory. They do not show up as "the
  notebook", so they are easy to miss.
- **Fix:** Task Manager > Details > sort by memory > end orphaned
  `python.exe` processes; `docker ps` then `docker stop <id>`; in
  Ollama, `ollama stop <model>` unloads a model without stopping the
  server. One heavy job at a time on a 16 to 32 GB laptop.
- **Seen on:** 2026-09-20 (build machine, 27.6 GB RAM: a CPU training
  run and a container test together left 0.6 GB free).

### E8. Tuned model scores WORSE on urgency than the untuned 3B
- **Symptom:** in the S12 table the tuned 1B gets urgency 7/20 and the
  untuned `llama3.2:3b` gets 13/20. Somebody concludes fine-tuning
  made it worse.
- **Cause:** not a bug. The held-out 20 is half `low` and the 3B says
  `low` almost every time; the tuned model escalates by one level, as
  `gpt-4o-mini` does. Against its OWN base (`llama3.2:1b`, 4/20) the
  tuned model improved, and on the 72 validation tickets it gets 76%.
- **Fix:** show `comparison_base1b_vs_tuned.txt` (same model, before
  and after) first, then the four-way table, and use the per-class
  urgency rows to make the point. Full reasoning:
  `checkpoints/adapter_prebaked/README.md`, "Urgency".
- **Seen on:** 2026-09-20 (first run of `run_eval.py --endpoint tuned`).

### E9. Notebook 06 says `ADAPTER IN USE: THE PRE-BAKED ONE` but the group did train
- **Symptom:** the adapter cell of notebook 06 prints the pre-baked
  line for a group whose notebook 05 reached `ADAPTER READY`.
- **Cause:** read the `->` verdicts printed just above that line; it is
  one of three. `folder does not exist`: `MODEL_NAME` / `RUN_NAME` in
  notebook 06 are not the names used in notebook 05 (a second
  experiment was saved as `run2`), or notebook 05 ran under a different
  Google account, so a different Drive. `the weights file is cut off`:
  the runtime died while the adapter was being written. `no twin in
  Ollama`: the run was a smoke test.
- **Fix:** set the two names to match notebook 05 and re-run from the
  settings cell; the base run is reused, only the tuned run is asked
  again. For a cut-off file, re-run notebook 05: it resumes from its
  last checkpoint and saves the adapter again. If neither is quick,
  carry on with the pre-baked adapter and say so when presenting -
  that is what it is for.
- **Seen on:** 2026-09-20 (build machine: adapter folder deleted, and a
  weights file truncated to 9 MB, both on purpose;
  `tests/test_compare_utils.py`).

### E10. The base column in notebook 06 is a ticket off the header / the slides
- **Symptom:** the untuned model scores `category 9/20, urgency 5/20`
  where a reference table says `8/20, 4/20`; or two groups' base
  columns differ slightly. Somebody asks which one is right.
- **Cause:** both. `llama3.2:1b` untuned is not stable at temperature
  0 under Ollama: 9 of its 20 replies differed between two runs on the
  build machine on the same day, and the same single request sent
  twice gave two different replies (one of them missing its closing
  brace). Greedy decoding still depends on what the server processed
  just before (prompt cache, batch shapes), and a 1B model has many
  near-tied tokens. The tuned model moved on 1 reply of 20. Two
  complete runs from the same server state were identical. Across
  machines it is wider: the same Ollama 0.12.10 in a Linux container
  changed 12 of the 20 base replies (schema-valid 9/20 there, 12/20 on
  Windows; whole record 2/20 on both) and **0 of the 20 tuned
  replies**. On a Colab T4 (2026-09-21) the base scored 10/20
  schema-valid and routing 5/20, while the tuned column matched the
  other machines ticket for ticket.
- **Fix:** nothing to fix - use it. It is the "base model is
  inconsistent" point of BUILD_SPEC section 3, measured. Do not chase
  the difference, and do not build an argument on a single base
  ticket. The harness's own warning applies: one ticket is 5 points.
- **Seen on:** 2026-09-20 (build machine, Ollama 0.12.10, CPU; and a
  python:3.12-slim container on the same machine).

### E11. `Cannot register the adapter: this Ollama release has dropped LoRA adapters`
- **Symptom:** somebody runs notebook 06 (or
  `scripts/register_adapter.py`) on a laptop and the register cell
  stops; by hand, `ollama create` prints `Error: LoRA adapters are no
  longer supported`. `ollama list` shows the base model but no
  `oq-ticket-tuned`. The Ollama cell above it had already printed
  `LOCAL RUN - NOT A SUPPORTED PATH FOR THIS LAB`.
- **Cause:** the laptop has a current Ollama. Adapter import works on
  0.12.10, the release this repo is built and measured on; it fails on
  0.33.3 (`no Modelfile or safetensors files found`) and is refused on
  0.34.2. This is why the tuned endpoint is **Colab T4 only** (decision
  2026-09-21, `setup/ollama_setup.md`): in Colab the notebook installs
  0.12.10 itself.
- **Fix:** open notebook 06 in Colab on a T4 runtime. That is the
  supported path, not a workaround. Do NOT reinstall or downgrade
  Ollama on a participant's laptop in the room, and do NOT score a
  different model under the `tuned` name. If Colab is unreachable, show
  the pre-baked table (E12 says where it is).
- **Seen on:** 2026-09-20 (`ollama/ollama:0.34.2` and `:0.33.3`
  containers on the build machine, with `checkpoints/adapter_prebaked`).

### E12. Notebook 06 on a Colab CPU runtime: `No GPU in this Colab runtime`
- **Symptom:** the Ollama cell of notebook 06 stops with that message.
- **Cause:** by design. On two CPU cores one ticket takes longer than
  the endpoint's 120-second timeout, so the eval would die with `The
  endpoint is not answering` after a 1.9 GB download. Measured in a
  Linux container pinned to two cores: both first tickets timed out
  twice. With two CPUs' worth of time spread over many threads it
  limps: about 37 s per ticket, 30 minutes for the notebook - over its
  25-minute budget.
- **Fix:** *Runtime > Change runtime type > T4 GPU*, Run all. GPU quota
  used up after notebook 05: pair with a group that has a GPU, or show
  the pre-baked table - the no-model `--compare` command is in
  `facilitator/prebaked_outputs/eval/README.md`, the table itself in
  `06_base_vs_tuned/comparison.txt` there. A laptop is NOT the way out:
  the tuned endpoint is unsupported there (E11).
- **Seen on:** 2026-09-20 (python:3.12-slim containers, `--cpuset-cpus=0,1`
  and `--cpus=2`, Ollama 0.12.10).

### E13. Port already in use: `ollama serve stopped at once. Its last log line: Error: listen tcp 127.0.0.1:11434: bind: ...`
- **Symptom:** the Ollama cell of notebook 02/03/06 stops within a few
  seconds with that message. On Windows the log line ends `Only one
  usage of each socket address (protocol/network address/port) is
  normally permitted`; on Linux/macOS `address already in use`. By
  hand, `ollama serve` prints the same line and exits.
- **Cause:** another program holds the port. The helper only tries to
  start a server when nothing on the port *answers as Ollama*
  (`/api/version`), so it is not simply "the desktop app is running"
  - that case is used silently. It is a non-Ollama program on 11434,
  or an Ollama that has hung.
- **Fix:** the message names the next free port. Either stop the other
  program, or set `OLLAMA_BASE_URL=http://localhost:11435` (in `.env`,
  or `os.environ` in the settings cell) and run the cell again: the
  helper starts `ollama serve` on that port (`OLLAMA_HOST` is derived
  from it) and everything downstream follows the variable. By hand:
  `OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 ollama serve`.
  Before 2026-09-22 this case waited the full 60 s and then said only
  "did not answer"; `ollama_utils.start_server` now notices the exit
  and reports the log line at once (4 s measured).
- **Seen on:** 2026-09-22 (build machine, Windows 11: a Python HTTP
  server parked on the port on purpose; `tests/test_inference_utils.py`).

### E14. `Model 'llama3.2:1b' not found on Ollama (HTTP 404). Pull it first` / `Ollama is not installed on this machine`
- **Symptom:** the first of these from `get_endpoint("local").chat(...)`
  (`EndpointError`); or `OllamaError: llama3.2:1b is not on this server.
  Run the pull cell first.` from the notebook-02 helpers; or `Ollama is
  not installed on this machine. Install it once: setup/ollama_setup.md`
  from the server cell on a laptop. Also `Endpoint 'local' unreachable
  at http://localhost:11434/v1/chat/completions. Is Ollama running?`
  when nothing listens at all.
- **Cause:** in order: the server is up but the model was never pulled
  (or the name is misspelt - `llama3.2:1b`, not `llama3.2-1b`); the
  `ollama` program is not on `PATH` (freshly installed on Windows: the
  Jupyter kernel and old terminals keep the old `PATH`); no server is
  running and none could be started.
- **Fix:** run notebook 02's **PULL CELL** (or `ollama pull llama3.2:1b`;
  1.3 GB, the day before if on venue Wi-Fi); restart the kernel / open a
  new terminal after installing; start the Ollama app, or run the server
  cell again - `ensure_server` starts `ollama serve` itself when the
  program is installed (6 s measured). Section 6 of
  `setup/ollama_setup.md` has every message with its fix.
- **Seen on:** 2026-09-22 (build machine, all four messages provoked on
  purpose against Ollama 0.12.10; the not-installed message also in a
  clean Linux container).

### E15. The classic Ollama Linux install one-liner returns `404 Not Found`
- **Symptom:** `curl -fsSL https://ollama.com/download/ollama-linux-amd64.tgz | tar -xzf - -C /usr`
  (the command in most 2024-2025 Colab tutorials) fails: curl gets a
  404 and tar complains about an empty archive. `install.sh` itself
  wants a `zstd` tool that a Colab image may lack.
- **Cause:** Ollama's current releases (0.34.x, September 2026) publish
  Linux as `.tar.zst`; the unversioned `.tgz` URL now redirects to a
  release that has no such asset. Ollama also added a first-run
  sign-in prompt to the `ollama` command in 0.34.2.
- **Fix:** none needed for the labs - `ollama_utils.install_on_linux`
  fetches the **versioned** `.tgz` (`?version=0.12.10`, 1.88 GB,
  redirecting to the GitHub release asset), which still exists and is
  the release every reference number was measured on. Do not "fix" a
  notebook by piping `install.sh`; it installs a moving release that
  refuses the tuned adapter (E11). If the pinned URL ever
  disappears, the same file is at
  `https://github.com/ollama/ollama/releases/download/v0.12.10/ollama-linux-amd64.tgz`.
- **Seen on:** 2026-09-22 (`curl -sIL` on both URLs from the build
  machine: the pinned one answers `200`, `Content-Length: 1875523113`;
  the unversioned one `404`).

### E16. Notebook 03: `NOTHING MEASURED. Preflight failed after 4.1 s: nothing answered at that address` (or `no reply within 60 s`, or `the server answered HTTP 404`)
- **Symptom:** the load-test cell (TODO 1) stops within seconds with
  one of those three sentences from `scripts/concurrency_test.py`, exit
  code 2, and the assert `Nothing was measured - read the message
  above`. No files are written.
- **Cause:** the script sends ONE preflight request before any level
  and refuses to start a five-level test against an endpoint that
  cannot answer it. In order of likelihood: the server cell above was
  not run in this kernel (nothing on `OLLAMA_BASE_URL`); the model is
  still loading or the machine is far too slow (the 60 s timeout);
  `OLLAMA_MODEL` names a model the server does not have (404).
- **Fix:** run the server cell (it starts or finds Ollama, pulls and
  warms the model), then the load-test cell again. `no reply within 60
  s` on a laptop with no usable GPU means the lab cannot finish there in
  15 minutes: move to the Colab T4. For 404, check `MODEL_NAME` in the
  settings cell against `ollama list`. Do NOT raise `TIMEOUT_SECONDS`
  to make the preflight pass; a machine that needs a minute for one
  request needs 80 minutes for the test.
- **Also in this lab, not a failure:** a few `timeout` in the `failed`
  column at 16 callers on a slow laptop. The driver counts them and the
  table shows `at 16: N x timeout`; that is the honest result and the
  capacity read-off (TODO 2) never picks a level with a failure.
- **Seen on:** 2026-09-22 (build machine: all three messages provoked
  on purpose - `localhost:9`, a non-routable address with `--timeout 5`,
  a misspelt model - each stopping inside 5 s; `tests/test_concurrency_test.py`).

### E17. Mock ERP on Windows: `StatReload detected changes in '...'. Reloading...` and then nothing, or edits never picked up
- **Symptom:** a laptop runs `uvicorn services.mock_erp.main:app --reload`
  (the command in CLAUDE.md). It serves fine. After a file is saved,
  the log prints `WARNING:  StatReload detected changes ... Reloading...`
  and the server never comes back; requests hang or are refused; Ctrl+C
  may not stop it. Or no reload is detected at all for many seconds.
- **Cause:** two things, both in uvicorn 0.52.4 (the pin; plain
  `uvicorn`, no `watchfiles`, so the fallback `StatReload` is used).
  (1) On Windows uvicorn restarts its worker by sending `CTRL_C_EVENT`
  and waiting for it to exit; that hangs - an upstream issue (uvicorn
  #1972, fastapi discussion #13817). Reproduced here with a three-line
  FastAPI app, so it is not the ERP. (2) `StatReload` re-stats every
  `*.py` under the current folder on every pass; with `.venv` inside
  the repo that is 18,094 files and 7.2 s a pass on the build laptop.
- **Fix:** nobody needs `--reload` in the room: participants call the
  ERP, they do not edit it. Run `uvicorn services.mock_erp.main:app`
  (no `--reload`); to reset the ERP, stop it and start it again (a
  restart reloads the seed; every work order raised through the API is
  gone). If a terminal is stuck, close it and open a new one. Someone
  who is editing the ERP on Windows: add `--reload-dir services/mock_erp`
  to fix the slow scan, and still expect (1). Do NOT "fix" it by
  downgrading uvicorn or installing `uvicorn[standard]` - the stack is
  frozen. On Linux and Colab `--reload` works (restart 0.7 s after a
  save, measured in `python:3.12-slim` and `python:3.13-slim`).
- **Seen on:** 2026-09-22 (build machine, Windows 11, Python 3.11,
  uvicorn 0.52.4: no restart within 60 s, with and without
  `--reload-dir`, with and without a console attached).

### E18. Mock ERP: `Port 8000 is in use by something that is not the mock ERP`
- **Symptom:** the start cell (`start_in_background(port=8000)`)
  raises that sentence; or `uvicorn services.mock_erp.main:app` exits
  (code 3) with `ERROR: [Errno 10048] error while attempting to bind on
  address ('127.0.0.1', 8000): only one usage of each socket address
  (protocol/network address/port) is normally permitted` (Windows text;
  Linux words it differently).
- **Cause:** something else holds port 8000 - another course's
  service, a second copy of the ERP in a forgotten terminal
  (`start_in_background` recognises the ERP by its `/health` reply and
  REUSES it, so only a foreign server gets this message).
- **Fix:** pick another port everywhere at once:
  `start_in_background(port=8001)`, or `uvicorn ... --port 8001`, and
  set `MOCK_ERP_URL=http://127.0.0.1:8001` in `.env` for whatever calls
  it. `python -m services.mock_erp.tour --base-url http://127.0.0.1:8001`
  checks the result.
- **Seen on:** 2026-09-22 (build machine, provoked on purpose: a plain
  HTTP server on the port, `tests/test_mock_erp.py`; and a second
  uvicorn on a port the ERP already held, for the Errno 10048 text).
