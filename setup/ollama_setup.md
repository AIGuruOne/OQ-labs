# Ollama setup (Colab and local)

Ollama is the model server the Day 2 labs run: it holds a model's
weights in memory and answers HTTP requests on a port. This guide is
written to be followed **alone, during a live session**, by someone
whose machine is behaving differently from everyone else's. Every
command below was run on 2026-09-22 (Windows 11, a clean Linux
container, and the notebook helpers) and the output shown is real.

Notebooks 02, 03 and 06 do everything in this guide for you through
`notebooks/ollama_utils.py`. Read it when a notebook cell says
"see setup/ollama_setup.md", or when you want to know what that cell
just did.

**Contents.** 1 The two facts · 2 Colab · 3 Laptop install
(Windows / macOS / Linux) · 4 Pull the model · 5 Verify ·
6 Troubleshooting · 7 Environment variables · 8 The tuned endpoint is
Colab T4 only · 9 Versions verified.

---

## 1. The two facts every other file relies on

- Ollama serves an **OpenAI-compatible API** at
  `http://localhost:11434/v1`. `config/endpoints.py` talks to it for the
  `local` and `tuned` endpoints, with the same request it sends the
  vendor API. The address is `OLLAMA_BASE_URL` in `.env`.
- `setup/setup_check.py` treats an unreachable Ollama as **WARN, not
  FAIL**: it is only needed from Day 2, and on Colab the notebooks
  install it themselves.

---

## 2. Colab: nothing to install by hand

The notebook does it. `ollama_utils.ensure_server(IN_COLAB, ...)`
downloads **one pinned release** and starts it; you watch it print.
What it runs is exactly this, and you can type it into a Colab cell
yourself if a helper ever fails:

```bash
# 1. download the pinned release (1.88 GB, carries its own GPU libraries) and unpack it
!curl -fsSL 'https://ollama.com/download/ollama-linux-amd64.tgz?version=0.12.10' | tar -xzf - -C /usr/local
# 2. serve in the background with a small fixed context; log to a file
!OLLAMA_CONTEXT_LENGTH=4096 nohup ollama serve > /content/ollama.log 2>&1 &
# 3. verify
!curl -s http://localhost:11434/api/version
!ollama pull llama3.2:1b
```

Real output of those commands on a clean Linux machine, 2026-09-22
(two CPU cores, home broadband):

```
$ curl -fsSL 'https://ollama.com/download/ollama-linux-amd64.tgz?version=0.12.10' | tar -xzf - -C /usr/local
install took 226 s
$ ollama --version
ollama version is 0.12.10
$ curl -s http://localhost:11434/api/version
{"version":"0.12.10"}
$ ollama pull llama3.2:1b
pull took 160 s
```

Things to know about Colab specifically:

| Fact | Consequence |
|---|---|
| **The runtime is thrown away when you disconnect.** Ollama and the pulled model live on the runtime's disk, not on Drive | Every fresh runtime installs and pulls again. Measured on a T4 (2026-09-21): install **56 s**, pull of `llama3.2:1b` **28 s**. The "pull the day before" advice is for laptops; on Colab it cannot help |
| **Why a pinned `.tgz` and not `install.sh`** | The moving install script fetches whatever is current. Current releases (0.34.x) ship Linux as `.tar.zst`, need the `zstd` tool, and refuse LoRA adapters - so the tuned endpoint of notebook 06 would not exist. The versioned `.tgz` URL still serves 0.12.10, the release every reference number in this repo was measured on |
| **T4 GPU runtime** (*Runtime > Change runtime type*) | 100% of a 1B model in GPU memory, about a second a reply. Free tier is enough; nothing needs Pro |
| **CPU runtime** (two cores) | **Not measured on Colab.** Notebook 02 does not refuse it, but two-core containers on the build machine (2026-09-22) gave **3 tokens a second** and a 30 s ticket reply with a CPU-time quota (`--cpus=2`), and a first call of **194 s** then a 600 s read timeout with two pinned cores (`--cpuset-cpus=0,1`). Expect to blow the budget; take the T4. Notebook 06 refuses a CPU runtime outright |
| Downloads come from `ollama.com` and `github.com` (the `.tgz` redirects there) and `registry.ollama.ai` (the model) | If OQ's network blocks any of these the install cell stops with `Ollama did not install ... Is the network blocking ollama.com?`. Fallback ladder: phone hotspot (BUILD_SPEC section 15) |
| The server log is `eval_runs/ollama_server.log` under the cloned repo (`/content/oq-advanced-ai/`) | First place to look when a model will not load |

---

## 3. Laptop install (once, before Day 2 - ideally at the Day 1 tech check)

Install from https://ollama.com/download. Any current release runs the
plain models the labs pull (`llama3.2:1b`, `llama3.2:3b`); only the
fine-tuned adapter needs the pinned release, and that is supported on
Colab only (section 8). **Do not install or upgrade Ollama in the room
on Day 2** - a 1.5 GB installer over venue Wi-Fi is the risk this
guide exists to avoid.

### Windows

1. Download `OllamaSetup.exe` and run it (no admin rights needed; it
   installs under `%LOCALAPPDATA%\Programs\Ollama`).
2. The installer starts the **Ollama desktop app**, which runs the
   server in the background and adds a tray icon. From then on the app
   starts with Windows and the server is always on port 11434.
3. **Open a new terminal** (PowerShell or Command Prompt - the installer
   updated `PATH`, existing windows do not see it) and check:

```
> ollama --version
ollama version is 0.12.10          <- yours will be newer; that is fine
```

Notes seen on the build machine (Windows 11, app 0.12.10):
- The app has a **context length setting**. At its maximum (262144)
  even a 2 GB model asks for 15.9 GiB of memory and fails to load
  (`docs/failure_playbook.md` entry 2). Set it to 4096 for the labs,
  or leave the app alone and run a second server on another port
  (section 6, "port already in use").
- `ollama serve` in a terminal while the app is running fails with
  `bind: Only one usage of each socket address` - the app already
  holds the port. That is not an error to fix: use the app's server.
- Logs: `%LOCALAPPDATA%\Ollama\server.log` (the app also writes
  `app.log` there). Models: `%HOMEPATH%\.ollama\models`.

### macOS

1. Download `Ollama.dmg`, drag Ollama to Applications, open it once.
   It runs in the menu bar and serves on port 11434.
2. In Terminal: `ollama --version`.
3. Logs: `~/.ollama/logs/server.log`. Models: `~/.ollama/models`.
   (Apple Silicon: Ollama uses the GPU through Metal automatically -
   `ollama ps` shows `100% GPU`.)

Not tested on a Mac during the build (there is none on the build side);
paths are from Ollama's own docs, verified 2026-09-22.

### Linux

The official one-liner installs the current release and a systemd
service:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

To install the **pinned** release by hand instead (what Colab does, no
systemd, no root beyond `/usr/local`):

```bash
curl -fsSL 'https://ollama.com/download/ollama-linux-amd64.tgz?version=0.12.10' | sudo tar -xzf - -C /usr/local
OLLAMA_CONTEXT_LENGTH=4096 ollama serve      # leave this terminal open, or add nohup ... &
```

Logs: `journalctl -u ollama` for the service; the terminal itself for a
hand-started server. Models: `/usr/share/ollama/.ollama/models` for
the service, `~/.ollama/models` for a hand-started server.

---

## 4. Pull the model (the live risk - do it the day before)

```
$ ollama pull llama3.2:1b
pulling manifest
pulling 74701a8c35f6: 100% ...  1.3 GB     (a progress bar redraws on one line; the notebook prints every 10% instead)
verifying sha256 digest
writing manifest
success
pull took 160 s                                (clean Linux container, home broadband, 2026-09-22)
$ ollama list
NAME           ID              SIZE      MODIFIED
llama3.2:1b    baf6a787fdff    1.3 GB    Less than a second ago
```

| Model | Download | What it is for |
|---|---|---|
| `llama3.2:1b` | **1.3 GB** (`Q8_0`) | **The Day 2 model.** Notebooks 02 and 03 run it; notebook 05 fine-tunes it; notebook 06 compares base against tuned. One pull serves the day |
| `llama3.2:3b` | 2.0 GB (`Q4_K_M`) | Optional. Answers noticeably better; `.env`'s default `OLLAMA_MODEL` and P4's reference eval. Pull it only if Wi-Fi allows |

- A pull is **resumable and idempotent**: interrupted, run it again and
  it continues; complete, it returns at once. The notebook's pull cell
  (`ollama_utils.ensure_model`) asks the server first and skips the
  download when the model is listed - so it is safe to run alone the
  day before and safe to run twice.
- **Venue Wi-Fi:** 1.3 GB at 2 MB/s is eleven minutes; at 500 kB/s,
  forty-five. Pull during the Day 1 tech check, not in the S7 slot.
  A pull that prints nothing for a minute is a network problem, not a
  slow one.
- **Offline backup (untested during the build):** models are plain
  files. Copying a machine's `~/.ollama/models` folder (both `blobs/`
  and `manifests/`) into the same place on another machine of any OS
  should make `ollama list` show the model without a download; the
  store is the same layout on every platform. Test this on two laptops
  before relying on it in the room.

---

## 5. Verify - four checks, in order

```bash
# 1. is a server answering?
curl -s http://localhost:11434/api/version
{"version":"0.12.10"}

# 2. is the model there?
ollama list

# 3. does it answer?  (first call also loads the model: a few seconds)
curl -s http://localhost:11434/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"llama3.2:1b","messages":[{"role":"user","content":"Say hello in five words."}],"temperature":0,"max_tokens":30}'
{"id":"chatcmpl-960","object":"chat.completion","model":"llama3.2:1b", ... "content":"Hello, it's nice to meet you." ... "usage":{"prompt_tokens":31,"completion_tokens":10,"total_tokens":41}}

# 4. does the repo see it?
python setup/setup_check.py            # the "Ollama reachable" row should read PASS
python -c "from config.endpoints import get_endpoint; print(get_endpoint('local').chat('Say hello in five words.'))"
```

`ollama ps` shows what is loaded, where (`17%/83% CPU/GPU` on the
build laptop's integrated GPU; `100% GPU` on a T4), and the context
length the server gave it.

---

## 6. Troubleshooting

Each symptom below is the exact text you will see, followed by the
cause and the fix. All of them were provoked on purpose on 2026-09-22
unless a different date is given.

### `Endpoint 'local' unreachable at http://localhost:11434/v1/chat/completions. Is Ollama running?`
Nothing listens on the port. **Windows / macOS:** start the Ollama app
(tray / menu bar icon appears). **Linux:** `ollama serve` in a
terminal, or `sudo systemctl start ollama`. **In a notebook:** run the
server cell again - `ensure_server` starts `ollama serve` itself when
the program is installed (measured: 6 s from the call to a server
answering). Check with `curl -s localhost:11434/api/version`.

### `Ollama is not installed on this machine. Install it once: setup/ollama_setup.md`
The notebook could not find the `ollama` program. Section 3. On
Windows, if you installed it a minute ago, **open a new terminal / restart
the Jupyter kernel** - the old process has the old `PATH`.

### `ollama: command not found` right after installing
Same cause: `PATH`. New terminal. On Windows the binary is
`%LOCALAPPDATA%\Programs\Ollama\ollama.exe` if you need the full path.

### `Model 'llama3.2:1b' not found on Ollama (HTTP 404). Pull it first: ollama pull llama3.2:1b`
The server is up but has no such model - `ollama list` will not show
it. Section 4. In a notebook, the **PULL CELL** does this and skips if
the model is already there. Also check the spelling: `llama3.2:1b`, not
`llama3.2-1b` or `llama-3.2:1b`.

### `ollama serve stopped at once. Its last log line: Error: listen tcp 127.0.0.1:11434: bind: address already in use` (Windows: `Only one usage of each socket address ... is normally permitted`)
Something already holds the port. Two cases:
- **It is Ollama itself** (the desktop app, or an `ollama serve` in
  another terminal). Nothing to fix - use it. The notebook helper only
  tries to start a server when nothing *answers as Ollama* on the port,
  so if you see this message from the notebook it is the second case.
- **It is another program**, or an Ollama that has hung. Either stop
  that program, or serve on a free port and point the labs at it:

  ```bash
  OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=4096 ollama serve
  ```
  and in `.env`: `OLLAMA_BASE_URL=http://localhost:11435`. The
  notebook's message names the next free port for you. (Measured: the
  clash is reported 4 s after the cell starts, not after a 60 s wait.)

### `model requires more system memory (15.9 GiB) than is available` for a 1.3 GB model
Not the model: the **context length**. The desktop app's setting, or
`OLLAMA_CONTEXT_LENGTH`, is very large and the memory for context is
what does not fit. Set it to 4096 (the ticket prompts are under 1,000
tokens) - in the app's settings, or by running a second server as
above. Seen 2026-09-20 on the build machine; `docs/failure_playbook.md`
entry 2.

### `NOTE: this server is Ollama 0.34.2; the labs are built and measured on 0.12.10`
Printed by the notebook when your laptop's Ollama is not the pinned
release. **Not an error for notebooks 02 and 03**: plain pulled models
answer on any release (pulling `llama3.2:1b` was seen to work on 0.33.3
and 0.34.2). It matters only for the fine-tuned adapter - section 8.

### `ollama --version` prints `Warning: could not connect to a running Ollama instance` and then `client version is ...`
Normal when no server is running: the command reports the client's
version and notes it could not ask a server for its own. Not a fault.

### The pull is slow, or stalls
Venue Wi-Fi. A pull is resumable: Ctrl-C and run it again later, it
continues. Options in order: wait for it (progress prints every 10%
in the notebook); pull on a phone hotspot; copy the model folder from a
laptop that has it (section 4, untested); on Colab, nothing to do - its
network pulls the model in about 30 s.

### Colab: `NVIDIA GPU: none found` and every reply takes many seconds
You are on a CPU runtime. *Runtime > Change runtime type > T4 GPU*,
then *Run all*. Notebook 02 works on a CPU runtime, slowly; notebook 06
stops on purpose (its 20-ticket evals would exceed the endpoint timeout
on two cores).

### Colab: `Ollama did not install: ... Is the network blocking ollama.com?`
The download from `ollama.com` (redirecting to `github.com`) was
blocked or failed. Retry once; then the hotspot step of the fallback
ladder. There is no pip package to fall back to - Ollama is a binary.

### Replies at temperature 0 are not identical between runs
Not a fault. A small model has many near-tied token choices and the
server's state between requests tips them; measured across sittings
and machines, 9 to 12 of 20 `llama3.2:1b` replies changed
(`docs/failure_playbook.md` entry 10). Notebook 02's TODO 1 shows it
live. Deterministic-by-setting is not deterministic.

### Where the logs are
| Where | Log |
|---|---|
| Windows app | `%LOCALAPPDATA%\Ollama\server.log` (`app.log` beside it) |
| macOS app | `~/.ollama/logs/server.log` |
| Linux service | `journalctl -u ollama --no-pager` |
| Started by a notebook (laptop or Colab) | `eval_runs/ollama_server.log` under the repo |
| Container | `docker logs <name>` |

### Stopping things
`ollama stop llama3.2:1b` unloads a model and keeps the server;
quitting the app (tray / menu bar) stops the server on Windows and
macOS; `pkill ollama` or `sudo systemctl stop ollama` on Linux. In
Colab, *Runtime > Disconnect and delete runtime* removes everything.

---

## 7. Environment variables

| Variable | Read by | Meaning | Lab value |
|---|---|---|---|
| `OLLAMA_BASE_URL` | this repo (`config/endpoints.py`, `ollama_utils`, `setup_check.py`) | where the server is, without `/v1` | `http://localhost:11434` |
| `OLLAMA_MODEL` | this repo (`config/endpoints.py`) | which model the `local` endpoint means | `llama3.2:3b` in `.env.example`; notebook 02 sets `llama3.2:1b` for its own run |
| `TUNED_MODEL` | this repo | the name the adapter is registered under | `oq-ticket-tuned` |
| `OLLAMA_HOST` | the `ollama` command and `ollama serve` | bind address of the server (`host:port`) | set for you by `ollama_utils.point_command_line_at_server` from `OLLAMA_BASE_URL` |
| `OLLAMA_CONTEXT_LENGTH` | `ollama serve` | context window every model is served with | `4096` (the helper sets it when it starts a server) |
| `OLLAMA_MODELS` | `ollama serve` | where model files live | default per OS, section 3 |
| `OLLAMA_KEEP_ALIVE` | `ollama serve` | how long a model stays in memory after a request (`5m` default; `-1` forever; `0` unload at once) | default |

---

## 8. The tuned endpoint is Colab T4 only (decision, 2026-09-21)

**Notebook 06, and anything else that needs the `tuned` endpoint, is
supported on Google Colab's free T4 runtime and nowhere else.** A
laptop is NOT a supported path for the tuned model, and participants
are not asked to install or downgrade anything to make it one.

Why: the `tuned` endpoint exists only after `ollama create` has turned
the LoRA adapter folder into a model (`scripts/register_adapter.py`).
Tested 2026-09-20 with `checkpoints/adapter_prebaked`:

| Ollama | `ollama create` with `ADAPTER <folder>` |
|---|---|
| 0.12.10 (Windows, and Linux in a container) | works - every reference score was measured on it |
| 0.33.3 | fails: `no Modelfile or safetensors files found` |
| 0.34.2 (current, released 2026-09-15) | refused: `Error: LoRA adapters are no longer supported` |

In Colab the notebook installs 0.12.10 itself, so the version is ours.
On a laptop it is whatever the participant installed, and anyone
installing this month gets a release that refuses adapters. A Colab
*CPU* runtime is not an alternative either: on two cores one ticket
takes longer than the endpoint's 120-second timeout, and the notebook
stops at once when it finds no GPU.

What this does NOT change: the `local` endpoint - a plain pulled model,
notebooks 02 and 03 - needs no adapter and is not affected by the
removal. (Pulling `llama3.2:1b` was seen to work on 0.33.3 and 0.34.2;
chatting with it on those releases was not tested here.)

What a laptop run of notebook 06 does: it still runs, prints `LOCAL RUN
- NOT A SUPPORTED PATH FOR THIS LAB`, and says whether the Ollama it
found is 0.12.10. With 0.12.10 it works - that is how the build machine
produces the reference output and how the tests were run. With anything
newer the register cell stops with a sentence pointing back to Colab.
Do not reinstall Ollama in the room.

**For the pre-program email:** ask anyone who ALREADY has Ollama
installed to run `ollama --version` and send back the line it prints,
and ask everyone who will use a laptop on Day 2 to install Ollama and
run `ollama pull llama3.2:1b` before Sunday (sections 3 and 4). Nobody
is asked to install, upgrade or downgrade for the tuned model. The
answers tell us before Sunday how many laptops carry a release that
refuses adapters, and so how hard Day 2 S12 and Day 4 S19 lean on
Colab being reachable from OQ's network.

**One machine is the exception - the facilitator's.** The demo fallback
ladder (BUILD_SPEC section 15: Colab, hotspot, fully local) ends on
Ritesh's laptop, and "fully local" includes the tuned model. That one
machine needs Ollama 0.12.10 installed deliberately and checked with
`ollama --version` on the morning of Day 2 (the desktop app can update
itself; how to stop that on 0.12.10 was not tested here). Installers
for that release are still published:
`https://github.com/ollama/ollama/releases/download/v0.12.10/OllamaSetup.exe`
(Windows), `.../Ollama.dmg` (macOS), `.../ollama-linux-amd64.tgz`
(Linux).

---

## 9. Versions verified (2026-09-22)

| What | Verified | Where |
|---|---|---|
| Current Ollama release | **v0.34.2**, 2026-09-15. Linux assets are `.tar.zst` (1.43 GB); the `latest` `.tgz` URL returns 404 | github.com/ollama/ollama/releases |
| Pinned release | **0.12.10**; `ollama-linux-amd64.tgz?version=0.12.10` resolves to the GitHub release asset, 1,875,523,113 bytes | `curl -sIL` on the URL |
| OpenAI-compatible fields | `/v1/chat/completions` accepts `temperature`, `top_p`, `max_tokens`, `seed`, `response_format`, `stop`, `stream`, `tools`; the reply carries `usage` and `finish_reason` | docs.ollama.com/api/openai-compatibility, and the live 0.12.10 |
| Native timing fields | `/api/chat` returns `load_duration`, `prompt_eval_duration`, `eval_duration` in nanoseconds and `prompt_eval_count`, `eval_count` | docs.ollama.com/api/chat, and the live 0.12.10 |
| Model sizes | `llama3.2:1b` 1.3 GB (`Q8_0`, 1.2B parameters, 131072 max context); `llama3.2:3b` 2.0 GB (`Q4_K_M`) | ollama.com/library/llama3.2, and `ollama show` |
| Log and model paths | Windows `%LOCALAPPDATA%\Ollama\server.log`, `%HOMEPATH%\.ollama`; macOS `~/.ollama/logs/server.log`; Linux `journalctl -u ollama` | docs.ollama.com/troubleshooting; the Windows paths also checked on the build machine |
| Default served context | 4096 in current releases (FAQ); the labs set it explicitly anyway | docs.ollama.com/faq |
