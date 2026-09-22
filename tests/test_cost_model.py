"""Tests for scripts/build_cost_model.py and facilitator/cost_model.xlsx.

    python -m pytest tests/test_cost_model.py -v

Three layers:
1. The Python arithmetic (`compute`) against hand-worked numbers.
2. The workbook is a valid .xlsx whose formulas reference the cells the
   script says they do, and the committed file matches the script.
3. If Microsoft Excel is installed (Windows, COM), the workbook is opened,
   recalculated, and every derived cell is compared with `compute()`.
   Skipped elsewhere - layer 2 still proves the formulas are wired.
"""

import json
import math
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_cost_model as cm  # noqa: E402

WORKBOOK = REPO_ROOT / "facilitator" / "cost_model.xlsx"
TICKET = cm.SCENARIOS["ticket"]


# ---------------------------------------------------------------------------
# 1. arithmetic
# ---------------------------------------------------------------------------


def test_scenario_a_hand_worked():
    r = cm.compute(TICKET)
    assert r["requests_month"] == 300 * 22 == 6600
    assert r["input_tokens_month"] == 6600 * 330
    assert r["output_tokens_month"] == 6600 * 60
    assert r["peak_requests_hour"] == pytest.approx(300 / 8 * 3)
    # gpt-5.4-mini, first row: 75% of input at the cached price
    uncached = 6600 * 330 * 0.25 * 0.75
    cached = 6600 * 330 * 0.75 * 0.075
    out = 6600 * 60 * 4.50
    assert r["api"][0]["monthly"] == pytest.approx((uncached + cached + out) / 1e6)
    assert r["api"][0]["monthly_batch"] == pytest.approx(r["api"][0]["monthly"] / 2)
    # self-hosted: one VM, 730 h
    assert r["vms_needed"] == 1
    assert r["compute_month"] == pytest.approx(1.30 * 730)
    assert r["self_month"] == pytest.approx(1.30 * 730 + 8 * 60 + 5)
    assert r["self_total"] == pytest.approx(r["self_month"] * 12 + 25)
    assert r["breakeven_requests_month"] == pytest.approx(r["self_month"] / (r["api"][5]["per_1000"] / 1000))
    assert r["compare_model"] == "Claude Sonnet 5"


def test_peak_sizing_adds_vms():
    s = dict(TICKET, requests_per_day=300 * 200)  # 60,000 a day
    r = cm.compute(s)
    assert r["peak_requests_hour"] == pytest.approx(22500)
    assert r["vms_needed"] == math.ceil(22500 / (3000 * 0.6)) == 13
    assert r["vms_run"] == 13
    assert r["compute_month"] == pytest.approx(13 * 1.30 * 730)


def test_no_cache_discount_uses_input_price():
    # Gemini rows carry None for cached price: cached tokens cost the input price.
    r = cm.compute(dict(TICKET, cache_share=1.0))
    gemini = r["api"][7]
    expected = (6600 * 330 * 0.75 + 6600 * 60 * 3.75) / 1e6
    assert gemini["monthly"] == pytest.approx(expected)
    assert gemini["monthly_batch"] is None


def test_every_price_has_a_source():
    ids = {row[0] for row in cm.SOURCES}
    for row in cm.PRICES:
        assert row[6] in ids, row


# ---------------------------------------------------------------------------
# 2. workbook structure
# ---------------------------------------------------------------------------


def read_sheets(path):
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/"))
        return {n: z.read(n).decode("utf-8") for n in names}, z.namelist()


def test_workbook_is_valid_zip_with_five_sheets(tmp_path):
    out = tmp_path / "cm.xlsx"
    cm.write_xlsx(out, cm.build_workbook(TICKET))
    sheets, names = read_sheets(out)
    assert "[Content_Types].xml" in names and "xl/workbook.xml" in names and "xl/styles.xml" in names
    assert len(sheets) == 5
    assert zipfile.ZipFile(out).testzip() is None


def test_formulas_reference_input_cells(tmp_path):
    out = tmp_path / "cm.xlsx"
    cm.CELLS.clear()
    cm.write_xlsx(out, cm.build_workbook(TICKET))
    sheets, _ = read_sheets(out)
    inputs, api, self_hosted, summary, sources = (sheets[k] for k in sorted(sheets))
    formulas = re.findall(r"<f>(.*?)</f>", api)
    assert len(formulas) == 4 * len(cm.PRICES)
    # every API cost formula reads the derived token cells and the cache share
    for f in formulas[0::4]:
        assert "Inputs!$B$16" in f and "Inputs!$B$17" in f and "Inputs!$B$11" in f
    assert "ROUNDUP(Inputs!B18" in self_hosted
    assert "MAX(B15,B6)" in self_hosted
    assert "INDEX(" in summary and "MATCH(" in summary
    # the source ids in the API table exist on the Sources sheet
    for row in cm.PRICES:
        assert f">{row[6]}<" in sources
    assert "fullCalcOnLoad" in zipfile.ZipFile(out).read("xl/workbook.xml").decode()


def test_committed_workbook_matches_script(tmp_path):
    """facilitator/cost_model.xlsx is generated. Rebuild if this fails."""
    assert WORKBOOK.exists(), "run: python scripts/build_cost_model.py"
    out = tmp_path / "cm.xlsx"
    cm.write_xlsx(out, cm.build_workbook(TICKET))
    fresh, _ = read_sheets(out)
    committed, _ = read_sheets(WORKBOOK)
    assert fresh == committed


# ---------------------------------------------------------------------------
# 3. Excel recalculation (Windows + Excel only)
# ---------------------------------------------------------------------------

PS_READ = r"""
$ErrorActionPreference = 'Stop'
$path = $args[0]
$cells = Get-Content $args[1] | ConvertFrom-Json
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {
  $wb = $excel.Workbooks.Open($path, 0, $true)
  $excel.CalculateFull()
  $out = @{}
  foreach ($p in $cells.PSObject.Properties) {
    $ref = $p.Value -replace "'", ""
    $sheetName, $addr = $ref -split '!'
    $out[$p.Name] = $wb.Worksheets.Item($sheetName).Range($addr).Value2
  }
  $wb.Close($false)
  $out | ConvertTo-Json -Compress
} finally {
  $excel.Quit()
  [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
}
"""


def excel_available():
    if sys.platform != "win32":
        return False
    probe = "try { $x = New-Object -ComObject Excel.Application; $x.Quit(); 'yes' } catch { 'no' }"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", probe], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.stdout.strip() == "yes"


@pytest.mark.skipif(not excel_available(), reason="Microsoft Excel (COM) not available")
@pytest.mark.parametrize("scenario_name", sorted(cm.SCENARIOS))
def test_excel_recalculates_to_the_python_numbers(tmp_path, scenario_name):
    scenario = cm.SCENARIOS[scenario_name]
    out = tmp_path / f"{scenario_name}.xlsx"
    cm.CELLS.clear()
    cm.write_xlsx(out, cm.build_workbook(scenario))
    expected = cm.compute(scenario)
    cells_file = tmp_path / "cells.json"
    cells_file.write_text(json.dumps(cm.CELLS))
    script = tmp_path / "read.ps1"
    script.write_text(PS_READ)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                        str(out), str(cells_file)], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout.strip().splitlines()[-1])

    scalar_keys = ["requests_month", "input_tokens_month", "output_tokens_month", "peak_requests_hour",
                   "vms_needed", "vms_run", "compute_month", "ops_month", "self_month", "self_per_1000",
                   "self_total", "idle_share", "breakeven_requests_month"]
    for key in scalar_keys:
        assert got[key] == pytest.approx(expected[key], rel=1e-9), key
    for i, row in enumerate(expected["api"]):
        assert got[f"api_{i}_monthly"] == pytest.approx(row["monthly"], rel=1e-9), row["model"]
        assert got[f"api_{i}_per_1000"] == pytest.approx(row["per_1000"], rel=1e-9), row["model"]
        assert got[f"api_{i}_total"] == pytest.approx(row["total"], rel=1e-9), row["model"]
    assert got["cheapest_api_monthly"] == pytest.approx(expected["cheapest_api"]["monthly"], rel=1e-9)
    assert got["cheapest_api_model"] == expected["cheapest_api"]["model"]
    assert got["compare_model"] == expected["compare_model"]
    # the input cells round-trip too (they are what a participant edits)
    for key in ["requests_per_day", "input_tokens", "cache_share", "vm_hourly", "ops_hours_month"]:
        assert got[key] == pytest.approx(scenario[key])
