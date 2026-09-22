"""Hygiene checks for notebooks/02_local_inference.ipynb and its solution.

    python -m pytest tests/test_notebook_02.py -v

These read the .ipynb files; they do not execute them. Executing needs an
Ollama server (any release; 0.12.10 is the measured one), llama3.2:1b
pulled or a network to pull it, and OPENAI_API_KEY for the one comparison
call - about a minute on the build machine:

    python -m nbconvert --to notebook --execute --output-dir <elsewhere> solutions/02_local_inference.ipynb
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME = "02_local_inference.ipynb"
TODO_CELL_IDS = ["params-todo", "hosted-todo"]


def load_cells(folder):
    notebook = json.loads((REPO_ROOT / folder / NAME).read_text(encoding="utf-8"))
    return notebook["cells"]


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


# ---------------------------------------------------------------------------
# Contract 2: the conventions every notebook follows
# ---------------------------------------------------------------------------


def test_participant_outputs_are_cleared(participant_cells):
    for cell in participant_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [], f"cell {cell['id']} has outputs"
            assert cell["execution_count"] is None, f"cell {cell['id']} has an execution count"


def test_the_two_versions_differ_only_in_the_todo_cells(participant_cells, solution_cells):
    assert [cell["id"] for cell in participant_cells] == [cell["id"] for cell in solution_cells]
    for mine, theirs in zip(participant_cells, solution_cells):
        if mine["id"] in TODO_CELL_IDS:
            assert source_of(mine) != source_of(theirs)
        else:
            assert source_of(mine) == source_of(theirs), f"cell {mine['id']} differs between the two versions"


def test_todo_cells_have_a_gap_a_hint_and_a_loud_failure(participant_cells):
    todo_cells = [cell for cell in participant_cells if cell["id"] in TODO_CELL_IDS]
    assert len(todo_cells) == 2
    for number, cell in enumerate(todo_cells, start=1):
        source = source_of(cell)
        assert f"── TODO {number} ─" in source
        assert "..." in source
        assert "Hint:" in source
        assert f"TODO {number} is not filled in yet" in source


def test_the_solution_has_no_gap_left(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            for line in source_of(cell).splitlines():
                code = line.split("#")[0]
                assert "= ..." not in code and ": ...," not in code, f"cell {cell['id']}: {line}"


def test_first_code_cell_is_the_environment_detection_cell(participant_cells):
    template = json.loads((REPO_ROOT / "notebooks" / "_template.ipynb").read_text(encoding="utf-8"))
    template_first_code = next(cell for cell in template["cells"] if cell["cell_type"] == "code")
    first_code = next(cell for cell in participant_cells if cell["cell_type"] == "code")
    assert source_of(first_code) == source_of(template_first_code)


def test_every_code_cell_has_a_markdown_cell_before_it(participant_cells):
    for position, cell in enumerate(participant_cells):
        if cell["cell_type"] == "code":
            assert participant_cells[position - 1]["cell_type"] == "markdown", f"cell {cell['id']}"


def test_header_declares_runtime_needs_and_correct_result(participant_cells):
    header = source_of(participant_cells[0])
    for phrase in ["**Expected runtime:**", "**Needs:**", "**A correct result looks like:**",
                   "40 minutes", "LOCAL INFERENCE READY", "If the runtime disconnects", "PULL CELL"]:
        assert phrase in header, phrase
    for placeholder in ["TBD", "__", "LOCAL_MACHINE_SECONDS", "TWO_CORE"]:
        assert placeholder not in header, "header still has a placeholder"


def test_installs_are_exactly_pinned_and_match_requirements(participant_cells):
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    install_lines = [line for cell in participant_cells for line in source_of(cell).splitlines()
                     if "%pip install" in line]
    assert install_lines, "no install cell"
    for line in install_lines:
        assert "-U" not in line.split() and "--upgrade" not in line
        packages = [word for word in line.split() if "==" in word]
        assert packages, f"unpinned install: {line}"
        for package in packages:
            assert package in requirements, f"{package} is not pinned in requirements.txt"


def test_never_asks_for_a_bigger_accelerator_or_pro(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        source = source_of(cell)
        for forbidden in ["A100", "L4 GPU", "V100", "High-RAM", "Colab Pro"]:
            assert forbidden not in source
    metadata = json.loads((REPO_ROOT / "notebooks" / NAME).read_text(encoding="utf-8"))["metadata"]
    assert metadata["colab"]["gpuType"] == "T4"


def test_the_key_cell_follows_the_install_cell_and_never_stops_the_local_part(participant_cells):
    """Contract 2 point 6 puts ensure_api_key right after the install cell. This lab
    is the self-hosted lab, so a missing key must cost the comparison, not the lab."""
    ids = [cell["id"] for cell in participant_cells]
    assert ids.index("key") == ids.index("install") + 2          # install, key-why, key
    key_source = source_of(cell_by_id(participant_cells, "key"))
    assert "utils.ensure_api_key(IN_COLAB)" in key_source
    assert "assert" not in key_source
    hosted_source = source_of(cell_by_id(participant_cells, "hosted-todo"))
    assert hosted_source.startswith("assert key_ok")


# ---------------------------------------------------------------------------
# What this lab promises
# ---------------------------------------------------------------------------


def test_the_pull_is_a_separate_idempotent_cell_that_records_its_own_time(participant_cells):
    pull_source = source_of(cell_by_id(participant_cells, "pull"))
    assert pull_source.startswith("# PULL CELL")
    assert "ollama_utils.ensure_model(MODEL_NAME)" in pull_source      # skips when already there
    assert '"02_pull"' in pull_source                                   # pull time saved apart from run time
    header = source_of(participant_cells[0])
    assert "day before" in header


def test_the_model_pinned_in_the_notebook_is_the_one_the_endpoint_uses(participant_cells):
    settings = source_of(cell_by_id(participant_cells, "settings"))
    assert 'MODEL_NAME = "llama3.2:1b"' in settings
    assert 'os.environ["OLLAMA_MODEL"] = MODEL_NAME' in settings
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    assert "get_endpoint(\"local\")" in sources


def test_ollama_comes_from_the_shared_helper_not_a_second_install_cell(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    assert "ollama_utils.ensure_server(IN_COLAB" in sources
    assert "install.sh" not in sources
    assert "curl" not in sources


def test_the_framing_is_self_hosted_versus_vendor_api(participant_cells):
    header = source_of(participant_cells[0])
    assert "Self-hosted versus vendor API" in header
    assert "Azure VM" in header
    assert "not laptop versus cloud" in header


def test_both_apis_are_shown_raw_http_and_the_endpoint_module(participant_cells):
    raw_source = source_of(cell_by_id(participant_cells, "raw"))
    assert "/v1/chat/completions" in raw_source and "requests.post" in raw_source
    endpoint_source = source_of(cell_by_id(participant_cells, "endpoint"))
    assert 'get_endpoint("local")' in endpoint_source


def test_the_comparison_sends_the_same_messages_to_both_endpoints(solution_cells):
    local_source = source_of(cell_by_id(solution_cells, "ticket"))
    hosted_source = source_of(cell_by_id(solution_cells, "hosted-todo"))
    call = "chat(messages=ticket_messages, temperature=0.0, max_tokens=300, timeout=600)"
    assert f"local_llm.{call}" in local_source
    assert f"hosted_llm.{call}" in hosted_source
    assert 'get_endpoint("hosted")' in hosted_source


def test_milestones_are_saved_and_reloaded(participant_cells):
    sources = "\n".join(source_of(cell) for cell in participant_cells if cell["cell_type"] == "code")
    for name in ["02_pull", "02_speed", "02_parameter_runs", "02_ticket_local", "02_ticket_hosted", "02_comparison"]:
        assert f'"{name}"' in sources, name
    for name in ["02_speed", "02_ticket_local"]:
        assert f'utils.load_json(CHECKPOINT_DIR, "{name}", default=None)' in sources, name


def test_no_version_touches_the_facilitator_answer_key(participant_cells, solution_cells):
    for cell in participant_cells + solution_cells:
        assert "planted_problems" not in source_of(cell)
        assert "plant_problems" not in source_of(cell)


# ---------------------------------------------------------------------------
# The solution's retained output is a real run
# ---------------------------------------------------------------------------


def test_solution_outputs_are_retained_and_error_free(solution_cells):
    for cell in solution_cells:
        if cell["cell_type"] == "code":
            assert cell["outputs"] != [], f"solution cell {cell['id']} has no output"
            for output in cell["outputs"]:
                assert output["output_type"] != "error", f"solution cell {cell['id']} ended in an error"
                assert output["output_type"] != "execute_result", f"solution cell {cell['id']} leaks a bare value"


def test_solution_prints_the_declared_result(solution_cells):
    printed = printed_by(solution_cells[-1])
    assert "LOCAL INFERENCE READY" in printed
    assert "tokens per second" in printed
    assert "pull          :" in printed
    card = printed_by(cell_by_id(solution_cells, "card"))
    assert "1.2B" in card and "Q8_0" in card
    raw = printed_by(cell_by_id(solution_cells, "raw"))
    assert '"usage"' in raw and '"finish_reason"' in raw


def test_solution_shows_the_capped_reply_cut_off(solution_cells):
    printed = printed_by(cell_by_id(solution_cells, "params-todo"))
    assert "finish_reason=length" in printed
    assert "=== capped" in printed and "=== creative" in printed and "=== repeatable" in printed
