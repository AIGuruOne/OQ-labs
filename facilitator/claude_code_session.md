# Claude Code configuration session (45 minutes)

**When this runs:** Day 1, S1, only if the diagnostic in
`01_fundamentals.ipynb` sends the room down the COMPRESSED path. The
notebook then finishes at about 09:30 and this session fills the
reclaimed 45 minutes, 09:30 to 10:15, before the break and S2.

**What it is:** install Claude Code, sign in, understand the three
files that configure it, and finish one real task against this repo
with the safety rails on. Participants leave with a working install on
their own laptop and a `CLAUDE.md` habit they can take to their own
repos.

**What it is not:** a tour of every feature. Hooks, skills, MCP and
headless mode get one sentence each and a link. Day 5 S26 builds an MCP
server; that is where the deeper agent tooling lives.

**Facts verified 2026-09-22** against the official docs at
`code.claude.com/docs` (the `docs.claude.com/en/docs/claude-code/*`
URLs now redirect there). The docs pages carry no visible dates; the
changelog's newest entry was **2.1.278, 19 September 2026**. Two things
could not be verified and are NOT taught below: the exact stable-channel
version number, and the `#` shortcut for saving a memory (absent from
the current commands and interactive-mode pages).

---

## Before the day (facilitator pre-flight, 20 minutes, not in the room)

| # | Check | Why |
|---|---|---|
| 1 | **Decide how the room authenticates.** Claude Code has no free tier: it needs a Claude Pro/Max/Team/Enterprise login, or an Anthropic Console API key (`ANTHROPIC_API_KEY`), or an enterprise cloud route (Bedrock / Vertex / Microsoft Foundry). Source: `code.claude.com/docs/en/authentication`, `/docs/en/setup`. | Nothing else in this session works without it. **This is a decision for Ritesh** (section "What I need from you" at the end). The cheapest room-wide option is one Console workspace with per-key spend limits and one key per participant, handed out on paper and revoked on Thursday. |
| 2 | Install it yourself on the facilitator laptop with the commands in step 1 below and run `claude doctor`. | The install runs in the room from the network the room has. |
| 3 | If OQ's network uses a TLS-inspecting proxy: get the corporate root CA as a `.pem` and the proxy URL. Set `HTTPS_PROXY=http://proxy:port` and `NODE_EXTRA_CA_CERTS=<path to .pem>` (source: `/docs/en/network-config`). SOCKS proxies are not supported; NTLM/Kerberos proxies need an LLM gateway instead. | A proxy that is not configured looks like "the install hangs". |
| 4 | Ask OQ IT, in the pre-program email, to allow `api.anthropic.com`, `claude.ai`, `claude.com`, `platform.claude.com`, `downloads.claude.ai` (installer and updates), `registry.npmjs.org` (only if anyone uses the npm route or `npx` MCP servers), `code.claude.com` (docs lookups). Source: `/docs/en/network-config`. | Same as 3. |
| 5 | Print this file's steps 1 to 4 as a one-page handout. | People install faster from paper than from a projector. |
| 6 | Fallback if the room cannot install at all: run the whole session from the facilitator laptop on the projector, with participants reading along on the handout, and hand out the "take-home" section. | A blocked download must not eat 45 minutes. |

---

## Run of show

| Clock | Min | Step |
|---|---|---|
| 09:30 | 5 | 0. What Claude Code is, and why an IT team cares |
| 09:35 | 10 | 1. Install and sign in |
| 09:45 | 8 | 2. The three configuration files, and `CLAUDE.md` in this repo |
| 09:53 | 17 | 3. A first real task against this repo, with plan mode and permissions |
| 10:10 | 5 | 4. Take-home: what to set up on Monday, what never to do |

Timing is tight on purpose. Step 3 is the one that can overrun; step 4
can be handed out on paper if it does.

---

## 0. What it is (5 min, talk)

Claude Code is a command-line agent: it reads your repo, plans, edits
files, runs commands and tests, and asks before anything risky. It is
the same loop the room just wrote in Part C of the notebook (model
proposes an action, your side runs it, the result goes back), with a
file system and a shell as the tools and a permission system in front
of the tools.

Why it matters for this audience:

- It is how the labs in this repo were built, and `CLAUDE.md` in the
  repo root is the artefact that kept an agent from breaking them.
- On Day 5 the groups write an MCP server. Claude Code is an MCP
  client, so the server they build can be plugged into it.
- Enterprise routes exist (Bedrock, Google Cloud, Microsoft Foundry),
  so this is deployable inside OQ's cloud boundary rather than a
  personal tool.

---

## 1. Install and sign in (10 min, everyone types)

Source: `code.claude.com/docs/en/setup` and `/docs/en/quickstart`.

**Native installer (the documented "Recommended" route, no Node.js
needed, no Administrator rights on Windows):**

```powershell
# Windows PowerShell
irm https://claude.ai/install.ps1 | iex
```

```bash
# macOS, Linux, WSL
curl -fsSL https://claude.ai/install.sh | bash
```

Also documented: `winget install Anthropic.ClaudeCode`,
`brew install --cask claude-code`, and signed apt/dnf/apk repositories.
The npm route (`npm install -g @anthropic-ai/claude-code`) is still
supported but listed under "advanced", and as of 2.1.198 it needs
Node.js 22 or later. Use the native installer in the room.

Windows note from the docs: Git for Windows is optional but
recommended (it gives Claude Code a Bash tool; without it the agent
uses a PowerShell tool). Everyone who cloned this repo already has it.

**Verify:**

```
claude --version
claude doctor
```

`claude --version` prints something like `2.1.xxx (Claude Code)`.
`claude doctor` is a read-only check of the install; the in-session
`/doctor` can also fix things.

**Sign in:** in the repo folder, run `claude`. A browser opens for the
Claude account login. If the browser cannot call back (WSL2, SSH, a
locked-down machine), paste the code at "Paste code here if prompted".
`/login` switches accounts, `/logout` clears credentials, `/status`
shows which credential is active.

**If the room is on API keys instead:** set the key in the shell first
and Claude Code skips the browser (it asks once to approve the key):

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # PowerShell, this window only
```

```bash
export ANTHROPIC_API_KEY="sk-ant-..."       # bash, this window only
```

Two things the docs say that trip people: a set `ANTHROPIC_API_KEY`
**wins over** a subscription login (unset it to go back), and the
subscription route needs a paid plan; the free claude.ai plan has no
Claude Code access.

**Enterprise routes, one line each, for the decision later:**
`CLAUDE_CODE_USE_BEDROCK=1` + `AWS_REGION` (Amazon Bedrock),
`CLAUDE_CODE_USE_VERTEX=1` + `CLOUD_ML_REGION` +
`ANTHROPIC_VERTEX_PROJECT_ID` (Google Cloud), `CLAUDE_CODE_USE_FOUNDRY=1`
+ `ANTHROPIC_FOUNDRY_RESOURCE` (Microsoft Foundry). Sources:
`/docs/en/amazon-bedrock`, `/docs/en/google-vertex-ai`,
`/docs/en/microsoft-foundry`.

**Corporate proxy:** `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY` are
honoured; a corporate root CA in the OS trust store works without
configuration, otherwise `NODE_EXTRA_CA_CERTS=/path/to/ca.pem`.
`claude --debug` and `/status` show whether the proxy and extra CA
were picked up. Source: `/docs/en/network-config`.

---

## 2. Three files and a memory (8 min, half talk, half typing)

Source: `code.claude.com/docs/en/settings`, `/docs/en/memory`,
`/docs/en/permissions`.

**Settings, highest precedence first:**

| File | Who it is for |
|---|---|
| Managed settings (`C:\Program Files\ClaudeCode\managed-settings.json` on Windows, `/etc/claude-code/managed-settings.json` on Linux, `/Library/Application Support/ClaudeCode/managed-settings.json` on macOS) | The IT department. Cannot be overridden below. This is where OQ would pin the provider, block `--dangerously-skip-permissions` (`permissions.disableBypassPermissionsMode: "disable"`) and set the proxy. |
| `.claude/settings.local.json` in the repo | You, this repo, not committed. "Yes, and don't ask again" writes here. |
| `.claude/settings.json` in the repo | The team. Committed. Shared permission rules and hooks. |
| `~/.claude/settings.json` | You, every repo. |

Permission rules look like this (strict JSON, no comments):

```json
{
  "permissions": {
    "allow": ["Bash(python -m pytest *)", "Bash(git diff *)"],
    "deny": ["Read(./.env)"]
  }
}
```

Rules are evaluated deny first, then ask, then allow. The space before
`*` in `Bash(npm run *)` matters. `/permissions` opens a dialog to view
and edit them by scope; `/config` opens the settings UI (theme, model,
auto-update channel).

**Have everyone do this now:** create `.claude/settings.local.json`
in their clone with the `deny` rule above. The `.env` in this repo
holds a real API key; the agent should never read it. (The repo's
`.gitignore` already ignores that file.)

**`CLAUDE.md`, the file that matters most.** Claude Code reads, and
concatenates, root-most first:

- managed policy `CLAUDE.md` (same folders as managed settings),
- `~/.claude/CLAUDE.md` (personal, every repo),
- `./CLAUDE.md` or `./.claude/CLAUDE.md` in the working directory and
  every directory above it, plus `CLAUDE.local.md` (personal, ignore
  it in git),
- `.claude/rules/*.md` topic files (loaded at start, or only when
  matching files are touched if they carry `paths:` front matter),
- `CLAUDE.md` files in subdirectories, on demand when files there are
  read.

`@path/to/file` inside a `CLAUDE.md` imports another file (depth 4).
`/init` writes a starter file, or proposes improvements if one exists.
`/memory` opens the files for editing. Since 2026, **auto memory** is
on by default: the agent writes its own notes under
`~/.claude/projects/<project>/memory/`; `autoMemoryEnabled: false`
turns it off. Keep a `CLAUDE.md` under about 200 lines.

**Read this repo's `CLAUDE.md` together (3 min).** Open it and point
at:

- the six **NEVER** lines under "Hard rules": each one is a real way an
  agent broke or nearly broke this build (unpinned installs, schema
  edits, silent model upgrades, committed keys);
- "Notebook style": the legibility test the room's own notebooks were
  held to;
- "Commands": the agent learns how to test its own work from here;
- the "Session knowledge" block: written by the agent sessions that
  built the repo, kept current, and the reason a fresh session does
  not repeat old mistakes.

The lesson: `CLAUDE.md` is a runbook for a colleague who has read
nothing else. Write it that way.

---

## 3. A first real task in this repo (17 min, everyone types)

The task uses the repo's own synthetic data, follows the conventions
`CLAUDE.md` states (scripts take arguments, no hard-coded paths), has a
result the room can check, and touches nothing the labs depend on.

**3a. Start in plan mode (2 min).** In the repo root:

```
claude
```

Accept the folder-trust prompt (it is your own clone). Press
`Shift+Tab` once: the mode indicator shows **plan**. In plan mode the
agent reads and proposes, but edits nothing. (`Alt+M` on Windows if
`Shift+Tab` does not cycle; or start with `claude --permission-mode plan`.)

**3b. Ask for the plan (3 min).** Type:

> Read CLAUDE.md. Then plan a new script `scripts/ticket_stats.py` that
> reads `corpus/tickets/tickets_raw.jsonl` and
> `data/finetune/ticket_labels.jsonl` and prints a table of ticket
> counts per category and per urgency. It must take the two paths as
> arguments, use only the standard library, and follow the repo's
> conventions. Do not write anything yet.

Watch what it reads first. It should read `CLAUDE.md`, then look at
the two files' shape, then propose a short plan that mentions
`argparse` and no hard-coded paths. If it proposes `pandas`, ask why,
since the rule in `CLAUDE.md` is "stdlib only" for scripts that must
run before `pip install`.

**3c. Let it build, with the rails on (7 min).** `Shift+Tab` back to
the default (manual) mode and type:

> Go ahead. Then run it on the two files and show me the output.

It will ask permission to write the file and to run `python
scripts/ticket_stats.py ...`. Read each request before answering. The
expected output is a small table; access tickets are the biggest
category by a wide margin and telecom and erp are the smallest. That
imbalance is real and deliberate (BUILD_SPEC section 8B), and Day 2
S10 is about noticing it.

Then:

> Run `python -m pytest tests/ -q` to make sure nothing else changed.

`tests/` takes under a minute and must stay green; the new script has
no test, which is fine for a 10-minute exercise.

**3d. Look at the diff, then decide (5 min).** In a second terminal:

```
git status
git diff --stat
```

One new file, nothing else touched. That is the property to check
after every agent session: **the diff is the deliverable, not the
conversation.** Two ways to end:

- keep it: `git checkout -b my-first-claude-task`, commit;
- discard it: delete the file (`git clean -n` shows what is untracked;
  `git clean -f scripts/ticket_stats.py` removes it).

Either is fine. Do not push to the shared repo today.

Useful commands to show while people finish: `/cost` (now an alias of
`/usage`) for what the session spent, `/compact` to shrink a long
conversation, `/clear` to start over, `/model` to pick a model for the
session (`s` = this session only), `/resume` to pick up an earlier
session, `/help`.

---

## 4. Take-home (5 min, talk; hand out on paper if late)

**Set up on Monday, in your own repo:**

1. `claude` in the repo, then `/init` to draft a `CLAUDE.md`. Rewrite
   it by hand into: what the repo is, the hard rules, how to test,
   what an agent must never touch. Commit it.
2. A committed `.claude/settings.json` with the team's allow/deny
   rules, starting with `"deny": ["Read(./.env)"]` and whatever holds
   your secrets.
3. A branch per agent session. Review the diff, not the transcript.

**Never on a real machine:** `--dangerously-skip-permissions` (the
same as `--permission-mode bypassPermissions`). The docs' own wording:
only in isolated containers or VMs without internet access, where the
agent cannot damage the host. An IT department can block it for every
user in managed settings.

**One sentence each, with the docs page to read:**

- **Skills** (`.claude/skills/<name>/SKILL.md`, invoked as `/name`):
  a reusable prompt-plus-instructions file for a repeated task; the
  older `.claude/commands/*.md` still works. `/docs/en/skills`.
- **Hooks** (a `hooks` block in any settings file): shell commands run
  at lifecycle events, such as `PreToolUse` to block a command
  pattern regardless of what the model wants; the documented way to
  enforce a rule `CLAUDE.md` can only request. `/docs/en/hooks-guide`.
- **MCP servers** (`claude mcp add ...`): the same protocol the groups
  implement on Day 5 S26; the Day 5 server plugs into Claude Code the
  same way. `/docs/en/mcp`.
- **Headless** (`claude -p "query"`, `--output-format json`,
  `--allowedTools`): run it from CI or a ticket-triage job; `--bare`
  skips hooks and `CLAUDE.md` and needs an API key, not a login.
  `/docs/en/headless`.
- **IDEs:** VS Code extension (Extensions view, search "Claude Code";
  bundles its own CLI for the chat panel) and the JetBrains plugin
  (runs the CLI, so install the CLI first). `/docs/en/vs-code`,
  `/docs/en/jetbrains`.

---

## If it goes wrong

| Symptom | Likely cause | Do this |
|---|---|---|
| Installer hangs or fails to download | Proxy or firewall (`downloads.claude.ai`) | Set `HTTPS_PROXY`; if still stuck, switch to the projector fallback (pre-flight 6). |
| `claude --version` works, `claude` says the browser could not connect | Callback blocked | Use the "paste code" login route, or the API-key route. |
| Login succeeds but every request fails with a certificate error | TLS inspection | `NODE_EXTRA_CA_CERTS=<corporate root .pem>`; check with `claude --debug` (look for "CA certs: Appended extra certificates"). |
| "You need a paid plan" | Free claude.ai account | API-key route with the key handed out (pre-flight 1). |
| Agent wants to install a package or upgrade pip | It did not read `CLAUDE.md`, or was asked something outside it | Say no. Ask it to re-read `CLAUDE.md` and explain the rule it would break. This is the teaching moment of the session. |
| A participant ran with permissions bypassed and files changed unexpectedly | Bypass mode | `git status`, `git diff`, `git checkout -- .` and `git clean -fd` (their own clone, nothing shared). |

---

## What I need from you (Ritesh / Utkarsh)

1. **Authentication decision for the room** (pre-flight 1). Three
   viable options: (a) one Anthropic Console workspace, one key per
   participant with a spend limit, revoked Thursday; (b) Claude Team
   seats for the week; (c) skip hands-on install, run it on the
   projector only. Nothing here can be tested before that decision.
2. **Network check from an OQ port on Saturday 26 Sept** (BUILD_SPEC
   section 15 already plans this for Colab): add `claude --version`
   and a first `claude` login to that test.
3. Confirm the session may create `scripts/ticket_stats.py` in
   participants' clones (it is not committed by us; the room may keep
   or delete it).
