"""Shared helpers for the lab notebooks.

Import after the environment-detection cell has run (it puts this
folder on sys.path):

    import utils
    utils.save_json(CHECKPOINT_DIR, "scores", scores)
    scores = utils.load_json(CHECKPOINT_DIR, "scores", default=None)

Checkpoint rule (docs/notebook_conventions.md): save at every
milestone, and write cells that LOAD the checkpoint if it exists
instead of recomputing. A runtime disconnect then costs the current
cell, never the session.

JSON for anything human-readable (records, tables, configs).
Pickle only for objects JSON cannot hold (a fitted index, a model).
"""

import json
import pickle
from pathlib import Path

# Sentinel: lets load_json(default=None) distinguish "no default given"
# from "the default is None".
_NO_DEFAULT = object()


def checkpoint_path(checkpoint_dir, name: str, suffix: str) -> Path:
    """Full path for a named checkpoint, e.g. .../scores.json."""
    return Path(checkpoint_dir) / f"{name}{suffix}"


# ---------------------------------------------------------------------------
# JSON checkpoints — for records, tables, configs. Human-readable.
# ---------------------------------------------------------------------------


def save_json(checkpoint_dir, name: str, obj) -> Path:
    """Save `obj` as pretty-printed JSON. Returns the path written."""
    path = checkpoint_path(checkpoint_dir, name, ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"checkpoint saved: {path}")
    return path


def load_json(checkpoint_dir, name: str, default=_NO_DEFAULT):
    """Load a JSON checkpoint. Returns `default` if it does not exist."""
    path = checkpoint_path(checkpoint_dir, name, ".json")
    if not path.exists():
        if default is _NO_DEFAULT:
            raise FileNotFoundError(
                f"No checkpoint '{name}' in {checkpoint_dir}. "
                "Run the cell that creates it first."
            )
        return default
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pickle checkpoints — for objects JSON cannot hold.
# ---------------------------------------------------------------------------


def save_pickle(checkpoint_dir, name: str, obj) -> Path:
    """Save `obj` with pickle. Returns the path written."""
    path = checkpoint_path(checkpoint_dir, name, ".pkl")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(obj, handle)
    print(f"checkpoint saved: {path}")
    return path


def load_pickle(checkpoint_dir, name: str, default=_NO_DEFAULT):
    """Load a pickle checkpoint. Returns `default` if it does not exist."""
    path = checkpoint_path(checkpoint_dir, name, ".pkl")
    if not path.exists():
        if default is _NO_DEFAULT:
            raise FileNotFoundError(
                f"No checkpoint '{name}' in {checkpoint_dir}. "
                "Run the cell that creates it first."
            )
        return default
    with open(path, "rb") as handle:
        return pickle.load(handle)


# ---------------------------------------------------------------------------
# The hosted-API key — .env locally, Colab Secrets on Colab.
# ---------------------------------------------------------------------------


def ensure_api_key(in_colab: bool, name: str = "OPENAI_API_KEY") -> bool:
    """Put the hosted-API key into os.environ and say where it came from.

    Locally the key lives in the repo-root `.env` (config.endpoints loads
    it on import). On Colab the cloned repo has no `.env`, so the key
    comes from Colab Secrets (the key icon in the left sidebar, name it
    exactly OPENAI_API_KEY and switch on "Notebook access"), and failing
    that from a one-time paste prompt that is never echoed.

    Returns True when the key is set. Never prints any part of the key.
    """
    import os

    if os.environ.get(name):
        print(f"{name}: found in the environment")
        return True

    if in_colab:
        try:
            from google.colab import userdata

            os.environ[name] = userdata.get(name)
            print(f"{name}: found in Colab Secrets")
            return True
        except Exception:  # noqa: BLE001 - no secret, or access not granted
            pass
        import getpass

        pasted = getpass.getpass(
            f"{name} not in Colab Secrets. Paste it here (not shown): "
        ).strip()
        if pasted:
            os.environ[name] = pasted
            print(f"{name}: taken from the paste prompt (this runtime only)")
            return True
        print(f"{name}: NOT SET. Add it under the key icon on the left, then re-run.")
        return False

    # Local: importing config.endpoints loads the repo-root .env - but only
    # on the FIRST import in this kernel. Read the file again, so a .env
    # fixed after the kernel started is seen when this cell is re-run
    # (docs/failure_playbook.md entry 4). A value already in the
    # environment still wins over the file.
    import config.endpoints

    config.endpoints._load_dotenv()

    if os.environ.get(name):
        print(f"{name}: found in .env")
        return True
    print(
        f"{name}: NOT SET. Copy setup/.env.example to .env at the repo "
        "root, fill it in, and re-run this cell. Check the spelling of "
        "the variable name."
    )
    return False
