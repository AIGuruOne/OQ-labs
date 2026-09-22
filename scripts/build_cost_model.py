"""Build facilitator/cost_model.xlsx (Day 1 S4) and print the worked numbers.

    python scripts/build_cost_model.py                       # write the workbook, print scenario A
    python scripts/build_cost_model.py --scenario procedure_qa
    python scripts/build_cost_model.py --out /tmp/x.xlsx --no-print

Standard library only, on purpose: it must run on a participant laptop
with nothing but Python, and the repo's dependency list is frozen. The
.xlsx is written as the zip-of-XML it really is, with LIVE formulas -
open it in Excel or LibreOffice and every number recalculates from the
yellow input cells.

The same arithmetic is done a second time here in plain Python
(`compute`) so the printed numbers and the spreadsheet can be checked
against each other (`tests/test_cost_model.py` does that through Excel
when Excel is installed).

Every price in PRICES carries the source it was read from and the date.
The prices are the ONLY thing in this file that go stale; update the
table, rerun, commit the workbook.
"""

import argparse
import json
import math
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "facilitator" / "cost_model.xlsx"
VERIFIED = "2026-09-22"

# ---------------------------------------------------------------------------
# Scenarios: the editable assumptions. Scenario A is the locked fine-tune
# task and its token counts are MEASURED on this repo's data with the
# Llama 3.2 tokenizer (system prompt 250 tokens, ticket mean 72 / p95 211,
# reply mean 57). Everything else is an invented desk - edit freely.
# ---------------------------------------------------------------------------

SCENARIOS = {
    "ticket": {
        "title": "A - service desk ticket to structured record (the Day 2 task)",
        "requests_per_day": 300,          # tickets a working day, invented desk
        "working_days": 22,
        "working_hours": 8,
        "peak_factor": 3.0,               # the busiest hour is 3x the average hour
        "input_tokens": 330,              # 250 system prompt + ~80 ticket (measured)
        "output_tokens": 60,              # one JSON record (measured mean 57)
        "cache_share": 0.75,              # the 250-token system prompt is identical every call
        "months": 12,
        "vm_sku": "Azure NV12ads A10 v5, Linux, UAE North (1x A10 24 GB)",
        "vm_hourly": 1.30,
        "vm_hours_month": 730,
        "vm_count_ha": 1,                 # 2 for a failover pair
        "vm_capacity_per_hour": 3000,     # sustained requests/hour ONE VM can serve (see note)
        "vm_utilisation": 0.6,            # never plan above 60% of capacity
        "ops_hours_month": 8,             # patching, monitoring, on-call - YOUR number
        "ops_hourly_rate": 60,            # loaded cost of an engineer hour - YOUR number
        "one_off_cost": 25,               # fine-tune + setup: 2 h of A10 + a day of testing credits
        "storage_month": 5,
        "compare_api_row": 6,             # which API row the break-even uses (1-based, see table)
    },
    "procedure_qa": {
        "title": "B - HSE procedure assistant with retrieval (long prompts, many users)",
        "requests_per_day": 4000,
        "working_days": 22,
        "working_hours": 10,
        "peak_factor": 3.0,
        "input_tokens": 3500,             # question + 3 retrieved chunks + instructions
        "output_tokens": 250,
        "cache_share": 0.15,              # only the instructions repeat
        "months": 12,
        "vm_sku": "Azure NV12ads A10 v5, Linux, UAE North (1x A10 24 GB)",
        "vm_hourly": 1.30,
        "vm_hours_month": 730,
        "vm_count_ha": 2,
        "vm_capacity_per_hour": 600,      # long prompts: far fewer per hour
        "vm_utilisation": 0.6,
        "ops_hours_month": 16,
        "ops_hourly_rate": 60,
        "one_off_cost": 200,
        "storage_month": 20,
        "compare_api_row": 6,
    },
}

# (provider, model, input $/MTok, cached-input $/MTok, output $/MTok, batch discount, source id)
PRICES = [
    ("OpenAI", "gpt-5.4-mini", 0.75, 0.075, 4.50, 0.5, "S1"),
    ("OpenAI", "gpt-5.4", 2.50, 0.25, 15.00, 0.5, "S1"),
    ("OpenAI", "gpt-5.6-luna", 0.20, 0.02, 1.20, 0.5, "S1"),
    ("OpenAI", "gpt-5.6-terra", 2.00, 0.20, 12.00, 0.5, "S1"),
    ("Anthropic", "Claude Haiku 4.5", 1.00, 0.10, 5.00, 0.5, "S2"),
    ("Anthropic", "Claude Sonnet 5", 2.00, 0.20, 10.00, 0.5, "S2"),
    ("Anthropic", "Claude Opus 5", 5.00, 0.50, 25.00, 0.5, "S2"),
    ("Google", "Gemini 3.8 Flash (promo to 2026-12-31)", 0.75, None, 3.75, None, "S3"),
    ("Google", "Gemini 3.1 Pro (<=200k context)", 2.00, None, 12.00, None, "S3"),
    ("Azure OpenAI", "gpt-5.4-mini, Global Standard", 0.75, 0.075, 4.50, 0.5, "S4"),
    ("Azure OpenAI", "gpt-5.4-mini, Data Zone (list x1.10 - VERIFY)", 0.825, 0.0825, 4.95, None, "S4"),
]

SOURCES = [
    ("S1", "OpenAI API list prices, per 1M tokens; cached input; Batch API -50%",
     "https://developers.openai.com/api/docs/pricing", VERIFIED, "primary (vendor page)",
     "gpt-5.4-mini $0.75 / $0.075 cached / $4.50; gpt-5.4 $2.50 / $0.25 / $15; "
     "gpt-5.6-luna $0.20 / $0.02 / $1.20; gpt-5.6-terra $2 / $0.20 / $12. Fine-tuning gpt-4.1-mini: "
     "$5 per 1M training tokens, then $0.80 in / $3.20 out."),
    ("S2", "Anthropic Claude API prices, per 1M tokens; cache hit = 0.1x input; Batch -50%",
     "https://platform.claude.com/docs/en/about-claude/pricing", VERIFIED, "primary (vendor page)",
     "Haiku 4.5 $1 / $5; Sonnet 5 $2 / $10 (introductory price made permanent); Opus 5 $5 / $25. "
     "Claude in Microsoft Foundry bills the SAME per-token rates through the Azure Marketplace "
     "(Claude Consumption Units); US-only inference is x1.1."),
    ("S3", "Google Gemini API paid tier, per 1M tokens",
     "https://ai.google.dev/gemini-api/docs/pricing", VERIFIED, "primary (vendor page)",
     "Gemini 3.8 Flash $0.75 / $3.75 is promotional until 2026-12-31, then $1.50 / $7.50. "
     "Gemini 3.1 Pro $2 / $12 up to 200k context. Free tier exists but Google may train on it - "
     "not for company data."),
    ("S4", "Azure OpenAI Service, pay-as-you-go",
     "https://azure.microsoft.com/en-us/pricing/details/azure-openai/", VERIFIED,
     "SECONDARY for the numbers - the Microsoft page renders prices only in the interactive "
     "calculator. Global Standard matches OpenAI list per cloudzero.com/blog/azure-openai-pricing "
     "(updated 2026-09-04), which also reports Data Zone at about +10%. Regional (UAE North) is "
     "higher again and was not obtainable in writing.",
     "RITESH: open the Azure calculator for UAE North / EU Data Zone before the room and overwrite "
     "row 11 of the API table."),
    ("S5", "Azure VM NV12ads A10 v5 (1x A10 24 GB, 12 vCPU), Linux, pay-as-you-go, UAE North",
     "https://prices.azure.com/api/retail/prices?$filter=armSkuName eq 'Standard_NV12ads_A10_v5'",
     VERIFIED, "primary (Azure retail prices API)",
     "$1.30/h UAE North; $0.91/h East US. NV36ads A10 v5 (whole A10): $4.576/h UAE North, "
     "$3.20/h East US. Spot and 1-/3-year reservations are cheaper but not for a first deployment."),
    ("S6", "Azure VM NC4as T4 v3 (1x T4 16 GB, 4 vCPU), Linux, pay-as-you-go",
     "https://prices.azure.com/api/retail/prices?$filter=armSkuName eq 'Standard_NC4as_T4_v3'",
     VERIFIED, "primary (Azure retail prices API)",
     "$0.526/h East US, $0.658/h West Europe. NOT offered in UAE North / UAE Central / Qatar "
     "Central (the API returns no rows) - a T4 means the data leaves the region."),
    ("S7", "Azure VM NC24ads A100 v4 (1x A100 80 GB), Linux, pay-as-you-go",
     "https://prices.azure.com/api/retail/prices?$filter=armSkuName eq 'Standard_NC24ads_A100_v4'",
     VERIFIED, "primary (Azure retail prices API)",
     "$3.673/h East US, $4.775/h West Europe. Not offered in the Gulf regions. Only needed for "
     "models of 30B+ parameters or heavy concurrency."),
    ("S8", "Azure VM D4s v5 (4 vCPU, 16 GB, no GPU), Linux, UAE North - the app / API layer",
     "https://prices.azure.com/api/retail/prices?$filter=armSkuName eq 'Standard_D4s_v5'",
     VERIFIED, "primary (Azure retail prices API)",
     "$0.235/h UAE North. A small model (1B-3B) also RUNS on this, slowly: the build machine's "
     "CPU takes 3-4 s a ticket; two Colab CPU cores exceeded 120 s. Not a serving option."),
    ("S9", "AWS EC2 GPU instances, on-demand, us-east-1",
     "https://www.thundercompute.com/blog/ec2-gpu-instances", VERIFIED, "secondary (Sept 2026 roundup)",
     "g6.xlarge (1x L4 24 GB) $0.8048/h; g5.xlarge (1x A10G 24 GB) $1.006/h. AWS has a Bahrain "
     "and a UAE region; their prices were not checked."),
    ("S10", "Tokens per ticket - MEASURED on this repo",
     "data/eval/heldout_20.jsonl + corpus/tickets/tickets_raw.jsonl, Llama 3.2 tokenizer",
     VERIFIED, "measured",
     "System prompt 250 tokens. Ticket text: mean 72, median 58, p95 211, max 453 over all 600. "
     "JSON reply: mean 57, max 64. Scenario A uses 330 in / 60 out."),
    ("S11", "Throughput of one GPU VM - MEASURED on a Colab T4, extrapolated",
     "docs/timing_log.md (notebook 06 T4 run, 2026-09-21)", VERIFIED, "measured + assumption",
     "Ollama 0.12.10, llama3.2:1b, 100% in GPU memory: median 0.8 s per ticket, one request at a "
     "time = ~4,500 tickets/hour sequential. Scenario A plans 3,000/h on an A10 to allow for a 3B "
     "model and no batching. Measure YOUR number with notebook 03 before you defend it."),
    ("S12", "Ops labour and one-off costs",
     "assumption - no source", VERIFIED, "assumption",
     "The ops hours and hourly rate are placeholders. They are the largest self-hosted line at "
     "low volume; replace them with your own before showing anyone a total."),
]

# ---------------------------------------------------------------------------
# The arithmetic, in Python. Mirrors the spreadsheet formulas one for one.
# ---------------------------------------------------------------------------


def compute(s):
    """Return every number the workbook shows, as a dict, for scenario dict `s`."""
    out = {}
    out["requests_month"] = s["requests_per_day"] * s["working_days"]
    out["input_tokens_month"] = out["requests_month"] * s["input_tokens"]
    out["output_tokens_month"] = out["requests_month"] * s["output_tokens"]
    out["peak_requests_hour"] = s["requests_per_day"] / s["working_hours"] * s["peak_factor"]

    api = []
    for provider, model, p_in, p_cached, p_out, batch, src in PRICES:
        cached_price = p_in if p_cached is None else p_cached
        uncached_tokens = out["input_tokens_month"] * (1 - s["cache_share"])
        cached_tokens = out["input_tokens_month"] * s["cache_share"]
        monthly = (uncached_tokens * p_in + cached_tokens * cached_price
                   + out["output_tokens_month"] * p_out) / 1_000_000
        monthly_batch = monthly * (1 - batch) if batch else None
        per_1000 = monthly / out["requests_month"] * 1000
        api.append({
            "provider": provider, "model": model, "monthly": monthly,
            "monthly_batch": monthly_batch, "per_1000": per_1000,
            "total": monthly * s["months"],
        })
    out["api"] = api

    vms_needed = math.ceil(out["peak_requests_hour"] / (s["vm_capacity_per_hour"] * s["vm_utilisation"]))
    vms_run = max(vms_needed, s["vm_count_ha"])
    compute_month = vms_run * s["vm_hourly"] * s["vm_hours_month"]
    ops_month = s["ops_hours_month"] * s["ops_hourly_rate"]
    self_month = compute_month + ops_month + s["storage_month"]
    out.update({
        "vms_needed": vms_needed, "vms_run": vms_run,
        "compute_month": compute_month, "ops_month": ops_month,
        "self_month": self_month,
        "self_per_1000": self_month / out["requests_month"] * 1000,
        "self_total": self_month * s["months"] + s["one_off_cost"],
        "idle_share": 1 - out["requests_month"] / (vms_run * s["vm_capacity_per_hour"] * s["vm_hours_month"]),
    })
    row = api[s["compare_api_row"] - 1]
    out["compare_model"] = row["model"]
    out["breakeven_requests_month"] = self_month / (row["per_1000"] / 1000)
    out["cheapest_api"] = min(api, key=lambda r: r["monthly"])
    return out


def print_report(s, r):
    """The worked example, as text. Same numbers as the workbook."""
    print(f"Scenario {s['title']}")
    print(f"  {s['requests_per_day']} requests/day x {s['working_days']} days = {r['requests_month']:,} requests/month")
    print(f"  {s['input_tokens']} in + {s['output_tokens']} out tokens/request, {s['cache_share']:.0%} of input cached")
    print(f"  tokens/month: {r['input_tokens_month']/1e6:.2f} M in, {r['output_tokens_month']/1e6:.2f} M out")
    print(f"  peak: {r['peak_requests_hour']:,.0f} requests/hour")
    print()
    print(f"  {'API option':<48} {'$/month':>9} {'batch':>9} {'$/1000 req':>11} {'12 months':>10}")
    for a in r["api"]:
        batch = f"{a['monthly_batch']:9.2f}" if a["monthly_batch"] is not None else "        -"
        print(f"  {a['provider'] + ' ' + a['model']:<48} {a['monthly']:9.2f} {batch} {a['per_1000']:11.4f} {a['total']:10.2f}")
    print()
    print(f"  Self-hosted: {s['vm_sku']}")
    print(f"    VMs needed for peak {r['vms_needed']}, VMs run {r['vms_run']} (HA minimum {s['vm_count_ha']})")
    print(f"    compute ${r['compute_month']:,.2f} + ops ${r['ops_month']:,.2f} + storage ${s['storage_month']:,.2f}"
          f" = ${r['self_month']:,.2f}/month; ${r['self_per_1000']:.4f} per 1000 requests")
    print(f"    {s['months']} months incl. one-off ${s['one_off_cost']}: ${r['self_total']:,.2f};"
          f" the VM is idle {r['idle_share']:.0%} of the time")
    print()
    c = r["cheapest_api"]
    print(f"  Cheapest API: {c['provider']} {c['model']} at ${c['monthly']:,.2f}/month")
    print(f"  Break-even against {r['compare_model']}: {r['breakeven_requests_month']:,.0f} requests/month"
          f" (you have {r['requests_month']:,})")


# ---------------------------------------------------------------------------
# A minimal .xlsx writer. Cells are (ref, kind, value): kind is "s" string,
# "n" number, "f" formula. Style ids: 0 plain, 1 input (yellow), 2 money,
# 3 bold, 4 percent, 5 wrapped text.
# ---------------------------------------------------------------------------


def col_letter(n):
    """1 -> A, 27 -> AA."""
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


class Sheet:
    def __init__(self, name):
        self.name = name
        self.cells = []          # (row, col, kind, value, style)
        self.widths = {}         # col -> width

    def put(self, row, col, value, style=0):
        if value is None:
            return
        if isinstance(value, str) and value.startswith("="):
            # "=B5*B6" is a formula; "= requests x days" is prose and a bug
            if value.startswith("= "):
                raise ValueError(f"prose that looks like a formula at {self.ref(row, col)}: {value!r}")
            self.cells.append((row, col, "f", value[1:], style))
        elif isinstance(value, (int, float)):
            self.cells.append((row, col, "n", value, style))
        else:
            self.cells.append((row, col, "s", str(value), style))

    def ref(self, row, col):
        return f"{col_letter(col)}{row}"

    def xml(self):
        rows = {}
        for row, col, kind, value, style in self.cells:
            rows.setdefault(row, []).append((col, kind, value, style))
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">']
        if self.widths:
            parts.append("<cols>")
            for col, width in sorted(self.widths.items()):
                parts.append(f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>')
            parts.append("</cols>")
        parts.append("<sheetData>")
        for row in sorted(rows):
            parts.append(f'<row r="{row}">')
            for col, kind, value, style in sorted(rows[row]):
                ref = self.ref(row, col)
                st = f' s="{style}"' if style else ""
                if kind == "s":
                    parts.append(f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>')
                elif kind == "n":
                    parts.append(f'<c r="{ref}"{st}><v>{value}</v></c>')
                else:
                    parts.append(f'<c r="{ref}"{st}><f>{escape(value)}</f></c>')
            parts.append("</row>")
        parts.append("</sheetData></worksheet>")
        return "".join(parts)


STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2">
<numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/>
<numFmt numFmtId="165" formatCode="0.0%"/>
</numFmts>
<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2AB"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="6">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/>
<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

INPUT, MONEY, BOLD, PCT, WRAP = 1, 2, 3, 4, 5


def write_xlsx(path, sheets):
    """Zip the sheets into a valid .xlsx. fullCalcOnLoad makes Excel/LibreOffice recalculate on open."""
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                     '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
                     '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                     '<Default Extension="xml" ContentType="application/xml"/>',
                     '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
                     '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    workbook = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for i, sheet in enumerate(sheets, start=1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        workbook.append(f'<sheet name="{escape(sheet.name)}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    n = len(sheets)
    rels.append(f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    rels.append("</Relationships>")
    workbook.append('</sheets><calcPr fullCalcOnLoad="1"/></workbook>')
    content_types.append("</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 '</Relationships>')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "".join(content_types))
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", "".join(workbook))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        z.writestr("xl/styles.xml", STYLES_XML)
        for i, sheet in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet.xml())


# ---------------------------------------------------------------------------
# Laying out the workbook. Cell addresses are recorded in CELLS so the test
# can read the same cells back from Excel and compare with compute().
# ---------------------------------------------------------------------------

CELLS = {}  # name -> "Sheet!A1"


def build_workbook(s):
    inputs = Sheet("Inputs")
    inputs.widths = {1: 44, 2: 16, 3: 70}
    inputs.put(1, 1, "COST MODEL - Day 1 S4. Yellow cells are inputs; everything else is a formula.", BOLD)
    inputs.put(2, 1, f"Scenario: {s['title']}")
    inputs.put(3, 1, "Prices and their sources: sheet 'Sources'. Formulas explained: facilitator/cost_model.md")

    rows = [
        # row, label, key, style, note
        (5, "Requests per working day", "requests_per_day", INPUT, "One request = one model call. A chat turn or an agent step is a request each."),
        (6, "Working days per month", "working_days", INPUT, ""),
        (7, "Working hours per day", "working_hours", INPUT, "Hours the requests are spread over."),
        (8, "Peak factor (busiest hour / average hour)", "peak_factor", INPUT, "3 is normal for a service desk: Sunday 08:00 after a long weekend."),
        (9, "Input tokens per request", "input_tokens", INPUT, "Prompt + context + the user's text. Scenario A: MEASURED, 250 system + ~80 ticket (Sources S10)."),
        (10, "Output tokens per request", "output_tokens", INPUT, "Scenario A: one JSON record, measured mean 57."),
        (11, "Share of input tokens served from cache", "cache_share", INPUT, "The part of the prompt that is identical every call (system prompt, tool list). 0 if unsure."),
        (12, "Months to total over", "months", INPUT, ""),
    ]
    for row, label, key, style, note in rows:
        inputs.put(row, 1, label)
        inputs.put(row, 2, s[key], style)
        inputs.put(row, 3, note)
        CELLS[key] = f"Inputs!B{row}"

    inputs.put(14, 1, "Derived", BOLD)
    inputs.put(15, 1, "Requests per month")
    inputs.put(15, 2, "=B5*B6")
    inputs.put(15, 3, "Formula: requests/day x working days")
    inputs.put(16, 1, "Input tokens per month")
    inputs.put(16, 2, "=B15*B9")
    inputs.put(17, 1, "Output tokens per month")
    inputs.put(17, 2, "=B15*B10")
    inputs.put(18, 1, "Peak requests per hour")
    inputs.put(18, 2, "=B5/B7*B8")
    inputs.put(18, 3, "Formula: requests/day / working hours x peak factor. This sizes the VM, the monthly total sizes the bill.")
    CELLS.update({"requests_month": "Inputs!B15", "input_tokens_month": "Inputs!B16",
                  "output_tokens_month": "Inputs!B17", "peak_requests_hour": "Inputs!B18"})

    # --- API options -------------------------------------------------------
    api = Sheet("API options")
    api.widths = {1: 14, 2: 46, 3: 12, 4: 14, 5: 12, 6: 10, 7: 8, 8: 14, 9: 14, 10: 14, 11: 14}
    api.put(1, 1, "VENDOR API COST. Prices are per 1M tokens (yellow = editable, see Sources). Costs are formulas.", BOLD)
    headers = ["Provider", "Model", "Input $/MTok", "Cached input $/MTok", "Output $/MTok", "Batch discount", "Source",
               "$ / month", "$ / month, batch", "$ / 1000 requests", "$ total (months)"]
    for c, h in enumerate(headers, start=1):
        api.put(3, c, h, BOLD)
    api.put(2, 8, "Formula: (uncached in x price + cached in x cached price + out x price) / 1e6", WRAP)
    first = 4
    for i, (provider, model, p_in, p_cached, p_out, batch, src) in enumerate(PRICES):
        r = first + i
        api.put(r, 1, provider)
        api.put(r, 2, model)
        api.put(r, 3, p_in, INPUT)
        api.put(r, 4, p_cached if p_cached is not None else p_in, INPUT)
        api.put(r, 5, p_out, INPUT)
        api.put(r, 6, batch if batch is not None else 0, INPUT)
        api.put(r, 7, src)
        api.put(r, 8, f"=(Inputs!$B$16*(1-Inputs!$B$11)*C{r}+Inputs!$B$16*Inputs!$B$11*D{r}+Inputs!$B$17*E{r})/1000000", MONEY)
        api.put(r, 9, f'=IF(F{r}>0,H{r}*(1-F{r}),"-")', MONEY)
        api.put(r, 10, f"=H{r}/Inputs!$B$15*1000", MONEY)
        api.put(r, 11, f"=H{r}*Inputs!$B$12", MONEY)
        CELLS[f"api_{i}_monthly"] = f"'API options'!H{r}"
        CELLS[f"api_{i}_per_1000"] = f"'API options'!J{r}"
        CELLS[f"api_{i}_total"] = f"'API options'!K{r}"
    last = first + len(PRICES) - 1
    api.put(last + 2, 1, "Row numbers used by Summary!B12 (compare row): 1 = first model row, in table order.")
    api.put(last + 3, 1, "A cached-input price equal to the input price means the vendor publishes no cache discount (Gemini).")
    api.put(last + 4, 1, "Prices EXCLUDE: fine-tuning a vendor model, image input, tool-call overhead tokens, egress, support plans.")

    # --- Self-hosted -------------------------------------------------------
    sh = Sheet("Self-hosted")
    sh.widths = {1: 46, 2: 18, 3: 72}
    sh.put(1, 1, "SELF-HOSTED COST. An open-weights model on a VM you control (Ollama / vLLM). Yellow = inputs.", BOLD)
    srows = [
        (3, "VM SKU (text, for the record)", "vm_sku", INPUT, "Sources S5-S8 list the SKUs checked. Gulf regions have A10s; T4 and A100 mean leaving the region."),
        (4, "VM price, $ per hour, pay-as-you-go", "vm_hourly", INPUT, "Linux. Reserved 1-year is roughly 30-40% less; check the calculator."),
        (5, "Hours per month the VM runs", "vm_hours_month", INPUT, "730 = always on. A VM that stops at night still pays for its disk."),
        (6, "Minimum VMs for availability", "vm_count_ha", INPUT, "1 = one VM, and the service is down when it patches. 2 = a pair."),
        (7, "Sustained requests per hour ONE VM serves", "vm_capacity_per_hour", INPUT, "MEASURE this with notebook 03 for your model and prompt length (Sources S11)."),
        (8, "Utilisation ceiling", "vm_utilisation", INPUT, "Plan at 60%. Queues explode above that - Day 2 S8 shows why."),
        (9, "Ops hours per month", "ops_hours_month", INPUT, "Patching, model updates, monitoring, on-call. YOUR number (Sources S12)."),
        (10, "Loaded cost per engineer hour, $", "ops_hourly_rate", INPUT, "YOUR number."),
        (11, "One-off cost, $ (fine-tune, setup)", "one_off_cost", INPUT, "The Day 2 fine-tune took 7 minutes on a free T4; 2 h of A10 is $2.60."),
        (12, "Storage, logs, backups, $ per month", "storage_month", INPUT, ""),
    ]
    for row, label, key, style, note in srows:
        sh.put(row, 1, label)
        sh.put(row, 2, s[key], style)
        sh.put(row, 3, note)
        CELLS[key] = f"'Self-hosted'!B{row}"
    sh.put(14, 1, "Derived", BOLD)
    sh.put(15, 1, "VMs needed for the peak hour")
    sh.put(15, 2, "=ROUNDUP(Inputs!B18/(B7*B8),0)")
    sh.put(15, 3, "Formula: peak requests/hour / (capacity x utilisation), rounded up")
    sh.put(16, 1, "VMs actually run")
    sh.put(16, 2, "=MAX(B15,B6)")
    sh.put(16, 3, "Formula: the larger of 'needed for peak' and 'minimum for availability'")
    sh.put(17, 1, "Compute, $ per month")
    sh.put(17, 2, "=B16*B4*B5", MONEY)
    sh.put(17, 3, "Formula: VMs x $/hour x hours")
    sh.put(18, 1, "Ops labour, $ per month")
    sh.put(18, 2, "=B9*B10", MONEY)
    sh.put(19, 1, "Self-hosted total, $ per month")
    sh.put(19, 2, "=B17+B18+B12", MONEY)
    sh.put(19, 3, "Formula: compute + ops + storage. Note it does NOT change with volume until you add a VM.")
    sh.put(20, 1, "$ per 1000 requests")
    sh.put(20, 2, "=B19/Inputs!B15*1000", MONEY)
    sh.put(21, 1, "$ total over the months, incl. one-off")
    sh.put(21, 2, "=B19*Inputs!B12+B11", MONEY)
    sh.put(22, 1, "Share of the time the VMs sit idle")
    sh.put(22, 2, "=1-Inputs!B15/(B16*B7*B5)", PCT)
    sh.put(22, 3, "Formula: 1 - requests/month / (VMs x capacity x hours). High = you are paying for a car park.")
    CELLS.update({"vms_needed": "'Self-hosted'!B15", "vms_run": "'Self-hosted'!B16",
                  "compute_month": "'Self-hosted'!B17", "ops_month": "'Self-hosted'!B18",
                  "self_month": "'Self-hosted'!B19", "self_per_1000": "'Self-hosted'!B20",
                  "self_total": "'Self-hosted'!B21", "idle_share": "'Self-hosted'!B22"})

    # --- Summary -----------------------------------------------------------
    su = Sheet("Summary")
    su.widths = {1: 46, 2: 22, 3: 60}
    su.put(1, 1, "SUMMARY - what to put in the architecture spec (section 7)", BOLD)
    su.put(3, 1, "Requests per month")
    su.put(3, 2, "=Inputs!B15")
    su.put(4, 1, "Cheapest API option, $ per month")
    su.put(4, 2, f"=MIN('API options'!H{first}:H{last})", MONEY)
    su.put(5, 1, "Cheapest API option, which")
    su.put(5, 2, f"=INDEX('API options'!B{first}:B{last},MATCH(B4,'API options'!H{first}:H{last},0))")
    su.put(6, 1, "Self-hosted, $ per month")
    su.put(6, 2, "='Self-hosted'!B19", MONEY)
    su.put(7, 1, "Self-hosted, $ total incl. one-off")
    su.put(7, 2, "='Self-hosted'!B21", MONEY)
    su.put(8, 1, "Self-hosted VMs run / idle share")
    su.put(8, 2, "='Self-hosted'!B16")
    su.put(8, 3, "='Self-hosted'!B22", PCT)
    su.put(10, 1, "Break-even", BOLD)
    su.put(11, 1, "Compare self-hosted against API row number")
    su.put(11, 2, s["compare_api_row"], INPUT)
    su.put(11, 3, "1 = first row of the API table. Pick the model that actually passes your quality bar, not the cheapest.")
    su.put(12, 1, "That model")
    su.put(12, 2, f"=INDEX('API options'!B{first}:B{last},B11)")
    su.put(13, 1, "Its $ per month at your volume")
    su.put(13, 2, f"=INDEX('API options'!H{first}:H{last},B11)", MONEY)
    su.put(14, 1, "Requests per month where self-hosting costs the same")
    su.put(14, 2, f"='Self-hosted'!B19/(INDEX('API options'!J{first}:J{last},B11)/1000)")
    su.put(14, 3, "Formula: self-hosted $/month / API $/request. Below this volume the API is cheaper on money alone.")
    su.put(15, 1, "Your volume as a share of break-even")
    su.put(15, 2, "=B3/B14", PCT)
    su.put(17, 1, "Cost is one row of the decision matrix, not the decision. Data residency, latency and who owns it at 02:00 are the others.", WRAP)
    CELLS.update({"cheapest_api_monthly": "Summary!B4", "cheapest_api_model": "Summary!B5",
                  "compare_model": "Summary!B12", "compare_monthly": "Summary!B13",
                  "breakeven_requests_month": "Summary!B14"})

    # --- Sources -----------------------------------------------------------
    so = Sheet("Sources")
    so.widths = {1: 6, 2: 50, 3: 60, 4: 12, 5: 28, 6: 90}
    so.put(1, 1, f"SOURCES - every price above, where it was read and when. All verified {VERIFIED}. Prices change monthly; re-verify before the room.", BOLD)
    for c, h in enumerate(["Id", "Item", "Source", "Verified", "How", "Detail / caveat"], start=1):
        so.put(2, c, h, BOLD)
    for i, row in enumerate(SOURCES):
        r = 3 + i
        for c, v in enumerate(row, start=1):
            so.put(r, c, v, WRAP if c in (2, 3, 6) else 0)
    so.put(3 + len(SOURCES) + 1, 2, "Not modelled: network egress, private endpoints, support plans, currency (all USD), VAT, volume discounts, reserved instances, "
                                     "a vendor's price change mid-year, the cost of a wrong answer.", WRAP)

    return [inputs, api, sh, su, so]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="ticket")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="where to write the .xlsx")
    parser.add_argument("--no-print", action="store_true", help="write the workbook only")
    parser.add_argument("--json", action="store_true", help="print compute() as JSON instead of the report")
    args = parser.parse_args()

    scenario = SCENARIOS[args.scenario]
    sheets = build_workbook(scenario)
    write_xlsx(args.out, sheets)
    result = compute(scenario)
    if args.json:
        print(json.dumps({"cells": CELLS, "result": result}, indent=2, default=str))
    elif not args.no_print:
        print(f"wrote {args.out}")
        print()
        print_report(scenario, result)


if __name__ == "__main__":
    main()
