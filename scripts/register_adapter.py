"""Register a fine-tuned adapter with Ollama, so the `tuned` endpoint works.

    python scripts/register_adapter.py --adapter checkpoints/adapter_prebaked
    python scripts/register_adapter.py --adapter <your adapter folder> --name oq-ticket-tuned

What it does, in three steps you could do by hand:

  1. Reads adapter_config.json to find which base model the adapter
     was trained on, and looks up the SAME model's name in Ollama
     (notebooks/finetune_utils.MODEL_CHOICES).
  2. Writes a two-line Modelfile:   FROM <base>   /   ADAPTER <folder>
  3. Runs `ollama create <name> -f Modelfile`. Ollama converts the
     safetensors adapter itself; no other tool is involved.

After this, `get_endpoint("tuned")` (config/endpoints.py) and
`run_eval.py --endpoint tuned` reach the tuned model with no code change.

The adapter MUST sit on the base model it was trained on. An adapter
is a set of corrections to one specific model's weights; on any other
model it is noise. That is why --base is looked up, not guessed.

Exit codes: 0 = registered, 2 = could not run (with a sentence saying why).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "notebooks"))

DEFAULT_NAME = os.environ.get("TUNED_MODEL", "oq-ticket-tuned")

# Tickets plus the system prompt are under 1,000 tokens. A fixed, small
# context keeps memory low and start-up fast whatever the machine's
# Ollama default is (some desktop installs default to 256k).
CONTEXT_LENGTH = 4096


def stop(message):
    """Exit with code 2 and one readable sentence - never a stack trace."""
    print(f"Cannot register the adapter: {message}")
    sys.exit(2)


def find_ollama_base(adapter_dir):
    """The Ollama name of the model this adapter was trained on."""
    import finetune_utils

    config_path = adapter_dir / "adapter_config.json"
    if not config_path.exists():
        stop(f"{config_path} does not exist. Is --adapter the folder with adapter_model.safetensors in it?")
    adapter_config = json.loads(config_path.read_text(encoding="utf-8"))
    trained_on = adapter_config.get("base_model_name_or_path")

    for choice in finetune_utils.MODEL_CHOICES.values():
        if choice["hf_repo"] == trained_on and choice["ollama_base"]:
            return choice["ollama_base"], trained_on
    stop(f"the adapter was trained on '{trained_on}', which has no Ollama twin in "
         "finetune_utils.MODEL_CHOICES. Pass --base <ollama model> if you know the right one.")


def build_modelfile(ollama_base, adapter_dir):
    lines = [
        f"FROM {ollama_base}",
        f"ADAPTER {adapter_dir.resolve().as_posix()}",
        f"PARAMETER num_ctx {CONTEXT_LENGTH}",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Register a LoRA adapter with Ollama as the tuned model.")
    parser.add_argument("--adapter", required=True, help="folder holding adapter_model.safetensors + adapter_config.json")
    parser.add_argument("--name", default=DEFAULT_NAME, help=f"Ollama model name to create (default: {DEFAULT_NAME})")
    parser.add_argument("--base", default=None, help="Ollama base model; default: looked up from the adapter's config")
    parser.add_argument("--print-modelfile", action="store_true", help="print the Modelfile and stop, without calling Ollama")
    args = parser.parse_args()

    adapter_dir = Path(args.adapter)
    if not (adapter_dir / "adapter_model.safetensors").exists():
        stop(f"no adapter_model.safetensors in {adapter_dir}.")

    if args.base:
        ollama_base, trained_on = args.base, "(given with --base)"
    else:
        ollama_base, trained_on = find_ollama_base(adapter_dir)

    modelfile_text = build_modelfile(ollama_base, adapter_dir)
    print(f"adapter     : {adapter_dir}")
    print(f"trained on  : {trained_on}")
    print(f"Ollama base : {ollama_base}")
    print(f"new model   : {args.name}")
    print("Modelfile   :")
    for line in modelfile_text.splitlines():
        print(f"    {line}")

    if args.print_modelfile:
        return

    if shutil.which("ollama") is None:
        stop("the `ollama` command is not installed here. See setup/ollama_setup.md.")

    with tempfile.TemporaryDirectory() as build_dir:
        modelfile_path = Path(build_dir) / "Modelfile"
        modelfile_path.write_text(modelfile_text, encoding="utf-8")
        completed = subprocess.run(
            ["ollama", "create", args.name, "-f", str(modelfile_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

    # Judge by the text as well as the exit code.
    output = (completed.stderr or "") + (completed.stdout or "")
    if "no longer supported" in output:
        stop("this Ollama release has dropped LoRA adapters (seen on 0.34.2: 'LoRA adapters are no "
             "longer supported'). The tuned endpoint is supported on Colab only, where the notebooks "
             "install the pinned Ollama 0.12.10 themselves - open notebook 06 there, on a T4 runtime. "
             "Background: setup/ollama_setup.md.")
    if completed.returncode != 0 or "Error:" in output:
        reason = output.strip().splitlines()
        stop(f"`ollama create` failed: {reason[-1] if reason else 'no message'} "
             "(is the Ollama server running? try `ollama list`)")

    print(f"Registered. Test it:  python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl "
          f"--endpoint tuned --label tuned")


if __name__ == "__main__":
    main()
