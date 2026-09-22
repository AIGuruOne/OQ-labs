# Notebook conventions (Interface Contract #2)

Every notebook in `notebooks/` and `solutions/` follows this structure,
in this order. The cells below are copy-pasteable — start every new
notebook from `notebooks/_template.ipynb`, which implements all of it.

Owner: Utkarsh. Consumers: every notebook in the repo, both slices.

---

## Cell 1 — header (markdown)

Every notebook declares up front what it costs and what success looks
like. Fill in every field; delete none.

```markdown
# <NN_notebook_name>: <Plain-English Title>

**Session:** Day <N>, S<NN> — <session name>
**Expected runtime:** <NN> minutes on <Colab free-tier CPU | Colab free-tier T4>
**Needs:** <API key? Ollama? GPU? which corpus/data files?>
**A correct result looks like:** <one or two sentences describing the
final output a participant can check against — a table with specific
columns, a file at a specific path, a score above a threshold>

> All data in this lab is synthetic. No real OQ material anywhere.
```

## Cell 2 — environment detection (code, FIRST code cell, verbatim)

One notebook, two environments. This cell branches Colab vs local,
mounts Drive (Colab only), locates the repo, and sets three variables
every later cell may use: `IN_COLAB`, `REPO_ROOT`, `CHECKPOINT_DIR`.

```python
# Environment detection: Colab vs local. Sets IN_COLAB, REPO_ROOT, CHECKPOINT_DIR.
import os
import sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules

# The repo URL participants clone in Colab. Set once, here.
REPO_URL = "https://github.com/Utkarsh-09/AI_GURU_labs.git"

if IN_COLAB:
    # Drive first: checkpoints survive a runtime disconnect.
    from google.colab import drive
    drive.mount("/content/drive")

    REPO_ROOT = Path("/content/oq-advanced-ai")
    if not REPO_ROOT.exists():
        os.system(f"git clone --depth 1 {REPO_URL} {REPO_ROOT}")
    CHECKPOINT_DIR = Path("/content/drive/MyDrive/oq-advanced-ai-checkpoints")
else:
    # Local: find the repo root by walking up until BUILD_SPEC.md appears.
    here = Path.cwd()
    REPO_ROOT = next(
        (p for p in [here, *here.parents] if (p / "BUILD_SPEC.md").exists()),
        here,
    )
    CHECKPOINT_DIR = REPO_ROOT / "checkpoints" / "local"

CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# Make repo modules importable: config.endpoints, notebooks/utils.py
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

print(f"Environment : {'Colab' if IN_COLAB else 'local'}")
print(f"Repo root   : {REPO_ROOT}")
print(f"Checkpoints : {CHECKPOINT_DIR}")
```

## Cell 3 — pinned install cell (code)

Each notebook installs ONLY what it needs, with exact pins that match
`requirements.txt`. Never `pip install -U`, never an unpinned name,
never the whole requirements file on Colab (slow, and Colab already
has most of it).

```python
# Pinned installs — versions match requirements.txt. Colab only;
# local machines installed requirements.txt during setup.
if IN_COLAB:
    %pip install -q requests==2.32.4 python-dotenv==1.2.3
print("Install cell done.")
```

Rules:
- Exact `==` pins only. The pin MUST match `requirements.txt`.
- If Colab preinstalls the package (torch, transformers, numpy,
  pandas...), do not reinstall it — rely on the preinstalled version
  and pin `requirements.txt` to match it.
- If the notebook needs a package Colab does not have, add it here AND
  to `requirements.txt` (ask Ritesh first — dependency additions are a
  raise-first change).

## Cell 3b — the hosted-API key (only notebooks that call the hosted endpoint)

A cloned repo on Colab has no `.env`, so a notebook that uses
`get_endpoint("hosted")` puts this cell right after the install cell.
`utils.ensure_api_key` looks in the environment, then (Colab) in
**Colab Secrets** under the name `OPENAI_API_KEY`, then asks for a
one-time hidden paste; locally it relies on `.env`. It never prints
the key. Tell participants once: key icon in the left sidebar, secret
named exactly `OPENAI_API_KEY`, *Notebook access* on.

```python
import utils  # shared helpers from notebooks/utils.py

key_ok = utils.ensure_api_key(IN_COLAB)
assert key_ok, "No OPENAI_API_KEY. Follow the message above, then re-run this cell."
```

Reference: `notebooks/01_fundamentals.ipynb`, cell `key`.

When the hosted call is only a comparison at the end of an otherwise
local lab (notebook 02), keep the cell in the same place but replace
the `assert` with a printed warning, and put `assert key_ok, "..."` at
the top of the one cell that needs the key. A missing key then costs
that cell, not the lab. Reference: `notebooks/02_local_inference.ipynb`,
cells `key` and `hosted-todo`.

## Cell 4 onward — the lab

- **One idea per cell.** A markdown cell before every code cell says
  *why*, not what.
- **No silent success.** Every cell ends by printing the shape or a
  sample of what it just produced.
- **Helpers live in `notebooks/utils.py`** and get imported
  (`import utils`), never inlined at 80 lines.

## Checkpointing (required at every milestone)

Runtimes disconnect. A disconnect must cost the current cell, never
the session. At every milestone — after ingestion, after training,
after an eval table — save to `CHECKPOINT_DIR`, and structure the cell
so re-running loads instead of recomputing:

```python
import utils

# Milestone pattern: load if the checkpoint exists, compute if not.
scores = utils.load_json(CHECKPOINT_DIR, "scores", default=None)
if scores is None:
    scores = expensive_computation()          # the real work
    utils.save_json(CHECKPOINT_DIR, "scores", scores)
print(f"{len(scores)} rows (from "
      f"{'checkpoint' if scores else 'fresh run'})")
```

`utils.py` provides: `save_json`, `load_json`, `save_pickle`,
`load_pickle`, `checkpoint_path`. JSON for anything human-readable
(tables, records); pickle only for objects JSON cannot hold.

After a disconnect: reconnect, run Cell 2 (remount + paths), run the
install cell, then run the milestone cells — each one loads its
checkpoint and continues.

## TODO markers (participant notebooks only)

Participant notebooks in `notebooks/` carry numbered TODO gaps. The
matching notebook in `solutions/` fills them with the same numbering.

```python
# ── TODO 1 ─────────────────────────────────────────────────────────
# Build the prompt that asks the model for STRICT JSON matching the
# ticket schema. Hint: tell it what to do with missing fields.
prompt = ...  # <- replace the ... with your code
# ───────────────────────────────────────────────────────────────────
```

Rules:
- Marker style is exactly `# ── TODO <n> ─...` so participants can
  Ctrl+F "TODO" and find every gap.
- The gap is `...` (Ellipsis) — running the cell unmodified fails
  loudly with a clear error instead of silently doing nothing.
- Each TODO carries a hint. Nobody starts from a blank line.
- Two files, never one: `notebooks/<name>.ipynb` (gaps, outputs
  cleared before commit) and `solutions/<name>.ipynb` (complete,
  outputs retained). Never commented-out answers in one file.

## Final cell — the declared result

The last cell prints the thing the header promised, so "done" is
checkable at a glance in a busy room.
