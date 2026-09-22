# Cost model — Day 1 S4 companion to the architecture spec

**Files:** `facilitator/cost_model.xlsx` (the sheet groups fill in),
this note (every formula, every assumption, every source), and
`scripts/build_cost_model.py` (regenerates the sheet and prints the
worked numbers; standard library only).

**What it answers.** Token and request volume in, money out, for two
ways of running the same model call: a vendor API (direct, or through
your own cloud tenant) and a model you host on a VM you control. It
also tells you the volume at which the two cost the same, and how much
of a self-hosted VM would sit idle.

**What it does not answer.** Whether to host. Cost is one row of the
decision matrix (`facilitator/decision_matrix_template.md`). Data
residency, latency and who is on call at 02:00 are the others.

## How to use it in the lab (10 minutes of the 90)

1. Open the workbook. Yellow cells are inputs. Everything else is a
   formula — if you type over a white cell you have broken the sheet.
2. `Inputs`: put in your use case's volume and token counts. Section 7
   of the architecture spec asks for exactly these numbers.
3. `Self-hosted`: pick a VM from the `Sources` sheet, put in its price,
   and put in *your* ops hours and hourly rate. The defaults are
   placeholders and are labelled as such.
4. `Summary`: copy the four numbers it shows into spec section 7.
   Set the "compare against API row" to the model that actually passes
   your quality bar, not the cheapest one.
5. Say out loud what would have to change for the other option to win.
   That sentence goes in the spec too.

## The sheets

| Sheet | Holds | Editable |
|---|---|---|
| `Inputs` | volume, tokens per request, cache share, months | yes (yellow) |
| `API options` | one row per vendor model: list prices and the monthly cost at your volume | the prices (yellow); the costs are formulas |
| `Self-hosted` | VM price, hours, capacity, availability minimum, ops labour, one-off | yes (yellow) |
| `Summary` | cheapest API, self-hosted total, break-even volume | the compare row only |
| `Sources` | where every price came from, when it was read, how sure we are | update when you re-verify |

## Every formula

Cell references are to the workbook. `Inputs!B15` means sheet
`Inputs`, cell `B15`.

**Volume**

| Quantity | Formula | Cell |
|---|---|---|
| Requests per month | requests per working day × working days | `Inputs!B15 = B5*B6` |
| Input tokens per month | requests per month × input tokens per request | `Inputs!B16 = B15*B9` |
| Output tokens per month | requests per month × output tokens per request | `Inputs!B17 = B15*B10` |
| Peak requests per hour | requests per day ÷ working hours × peak factor | `Inputs!B18 = B5/B7*B8` |

The monthly totals size the bill. The peak hour sizes the VM. Keep
them apart: a desk that takes 300 tickets a day takes 110 of them in
the hour after a long weekend.

**Vendor API, per model row**

| Quantity | Formula |
|---|---|
| $ per month | (input tokens × (1 − cache share) × input price + input tokens × cache share × cached price + output tokens × output price) ÷ 1,000,000 |
| $ per month, batch | $ per month × (1 − batch discount); shown as `-` when the vendor has no batch tier |
| $ per 1,000 requests | $ per month ÷ requests per month × 1,000 |
| $ total | $ per month × months |

Prices are per million tokens, which is why the division by a million.
A vendor with no published cache discount (Gemini) has its cached
price set equal to its input price, so the cache share changes nothing
for that row.

**Self-hosted**

| Quantity | Formula | Cell |
|---|---|---|
| VMs needed for the peak hour | ROUNDUP(peak requests per hour ÷ (capacity per VM per hour × utilisation ceiling)) | `'Self-hosted'!B15` |
| VMs actually run | MAX(VMs needed, minimum for availability) | `B16` |
| Compute $ per month | VMs run × $ per hour × hours per month | `B17` |
| Ops labour $ per month | ops hours per month × loaded hourly rate | `B18` |
| Self-hosted $ per month | compute + ops + storage | `B19` |
| $ per 1,000 requests | $ per month ÷ requests per month × 1,000 | `B20` |
| $ total | $ per month × months + one-off cost | `B21` |
| Idle share | 1 − requests per month ÷ (VMs run × capacity per hour × hours per month) | `B22` |

Self-hosted cost is a step function: it does not move with volume
until the peak hour needs one more VM. That is the whole shape of the
argument, and it is why the break-even is so far to the right at
service-desk volumes.

**Break-even**

| Quantity | Formula |
|---|---|
| Requests per month where both cost the same | self-hosted $ per month ÷ (API $ per 1,000 requests ÷ 1,000) for the chosen API row |
| Your volume as a share of break-even | requests per month ÷ break-even |

Below the break-even the API is cheaper on money alone. Note it holds
the VM count fixed; past the next VM step it moves further right.

## Assumptions and where they come from

| Input | Default (scenario A) | Basis |
|---|---|---|
| Requests per working day | 300 | Invented desk. Not OQ's number — put in yours |
| Working days per month | 22 | |
| Working hours per day | 8 | |
| Peak factor | 3.0 | Ordinary for a service desk; the busiest hour is the first one of the week |
| Input tokens per request | 330 | **Measured.** `dataset_utils.SYSTEM_PROMPT` is 250 Llama 3.2 tokens; ticket text across all 600 corpus tickets: mean 72, median 58, p95 211, max 453 |
| Output tokens per request | 60 | **Measured.** The JSON record on the held-out 20: mean 57, max 64 |
| Cache share of input | 0.75 | The 250-token system prompt is identical on every call; 250 ÷ 330 ≈ 0.76. Vendors bill a cache hit at 10% of the input price (OpenAI, Anthropic); set 0 if unsure |
| Months | 12 | |
| VM | NV12ads A10 v5, Linux, UAE North, $1.30/h | **Azure retail price API, 2026-09-22.** The cheapest GPU SKU offered in a Gulf region. A T4 is cheaper ($0.526/h) but only outside the region (Sources S6) |
| Hours per month | 730 | Always on. A VM stopped at night still pays for its disk and does not answer tickets |
| Minimum VMs for availability | 1 | One VM is down when it patches. Put 2 if that matters |
| Capacity per VM per hour | 3,000 | **Measured then discounted.** A Colab T4 served `llama3.2:1b` at a median 0.8 s per ticket, one at a time (about 4,500 an hour). 3,000 leaves room for a 3B model and no batching. Measure yours with notebook 03 |
| Utilisation ceiling | 0.6 | Queues grow without bound above it (Day 2 S8) |
| Ops hours per month | 8 | **Placeholder.** Patching, model updates, monitoring, on-call. The Ollama release that dropped LoRA adapters (0.34) is what "model updates" looks like in practice |
| Loaded hourly rate | $60 | **Placeholder.** Use your finance team's number |
| One-off | $25 | The fine-tune took 7 minutes on a free T4; two hours of A10 is $2.60; the rest is testing |
| Storage | $5 | Disk for the model and a month of logs |

## Worked example A — the Day 2 task

Output of `python scripts/build_cost_model.py` on 2026-09-22 (the
same numbers the sheet shows; verified by recalculating the workbook
in both Excel 16 and LibreOffice):

```
Scenario A - service desk ticket to structured record (the Day 2 task)
  300 requests/day x 22 days = 6,600 requests/month
  330 in + 60 out tokens/request, 75% of input cached
  tokens/month: 2.18 M in, 0.40 M out
  peak: 112 requests/hour

  API option                                         $/month     batch  $/1000 req  12 months
  OpenAI gpt-5.4-mini                                   2.31      1.16      0.3504      27.75
  OpenAI gpt-5.4                                        7.71      3.85      1.1681      92.52
  OpenAI gpt-5.6-luna                                   0.62      0.31      0.0935       7.40
  OpenAI gpt-5.6-terra                                  6.17      3.08      0.9345      74.01
  Anthropic Claude Haiku 4.5                            2.69      1.34      0.4073      32.25
  Anthropic Claude Sonnet 5                             5.38      2.69      0.8145      64.51
  Anthropic Claude Opus 5                              13.44      6.72      2.0362     161.27
  Google Gemini 3.8 Flash (promo to 2026-12-31)         3.12         -      0.4725      37.42
  Google Gemini 3.1 Pro (<=200k context)                9.11         -      1.3800     109.30
  Azure OpenAI gpt-5.4-mini, Global Standard            2.31      1.16      0.3504      27.75
  Azure OpenAI gpt-5.4-mini, Data Zone (list x1.10 - VERIFY)      2.54         -      0.3855      30.53

  Self-hosted: Azure NV12ads A10 v5, Linux, UAE North (1x A10 24 GB)
    VMs needed for peak 1, VMs run 1 (HA minimum 1)
    compute $949.00 + ops $480.00 + storage $5.00 = $1,434.00/month; $217.2727 per 1000 requests
    12 months incl. one-off $25: $17,233.00; the VM is idle 100% of the time

  Cheapest API: OpenAI gpt-5.6-luna at $0.62/month
  Break-even against Claude Sonnet 5: 1,760,589 requests/month (you have 6,600)
```

(The sheet shows the idle share as 99.7%; the text report rounds.)

What the room should take from it:

- At service-desk volume the vendor bill is **pocket money**: under
  $14 a month for the most expensive model on the list. Nobody will
  choose on token price here.
- The self-hosted line is **$1,434 a month, of which a third is
  people**, and the GPU sits idle 99.7% of the time. It would cost the
  same at ten times the volume.
- Break-even against Sonnet 5 is **1.76 million tickets a month**.
  No service desk gets there.
- So if this use case is hosted, it is hosted because the ticket text
  must not leave the tenant or the country, or because the desk tool
  cannot reach the internet, or because the team wants to own the
  model's behaviour. Those are decision-matrix rows, and they are
  legitimate. Cost is not the reason, and a spec that says it is will
  not survive S5.
- The honest comparison for "buy" is **through your own tenant**:
  Azure OpenAI in a Data Zone, or Claude in Microsoft Foundry, which
  bills the same per-token rates on the Azure invoice. Direct vendor
  keys are for the lab.

## Worked example B — a retrieval assistant at ten times the volume

Same sheet, different inputs (`--scenario procedure_qa`): 4,000
requests a day, 3,500 input tokens (question plus three retrieved
chunks), 250 output tokens, 15% cached, two VMs minimum, 600
requests per hour per VM because the prompts are long.

```
  tokens/month: 308.00 M in, 22.00 M out
  peak: 1,200 requests/hour

  OpenAI gpt-5.4-mini                                 298.81    149.41      3.3956    3585.78
  OpenAI gpt-5.6-luna                                  79.68     39.84      0.9055     956.21
  Anthropic Claude Haiku 4.5                          376.42    188.21      4.2775    4517.04
  Anthropic Claude Sonnet 5                           752.84    376.42      8.5550    9034.08
  Anthropic Claude Opus 5                            1882.10    941.05     21.3875   22585.20
  Google Gemini 3.8 Flash (promo to 2026-12-31)       313.50         -      3.5625    3762.00

  Self-hosted: VMs needed for peak 4, VMs run 4 (HA minimum 2)
    compute $3,796.00 + ops $960.00 + storage $20.00 = $4,776.00/month; $54.2727 per 1000 requests
    12 months incl. one-off $200: $57,512.00; the VM is idle 95% of the time

  Break-even against Claude Sonnet 5: 558,270 requests/month (you have 88,000)
```

Ten times the requests and ten times the tokens per request, and the
API is still six times cheaper than four A10s. Long prompts hurt the
self-hosted side too, because they cut the requests per hour a VM can
serve (which is the same lesson as notebook 03). The self-hosted case
still rests on residency and control.

Two inputs move this picture a lot, and both are in yellow: the
requests per hour per VM (serving with batching on a bigger GPU can
multiply it) and the ops hours. Change them and watch the break-even.

## Sources

All verified 2026-09-22. Prices change monthly and the sheet has a
column for the date; **re-verify the week before the room** and update
the yellow cells and the `Sources` sheet together.

| Id | Item | Source | How sure |
|---|---|---|---|
| S1 | OpenAI list prices per 1M tokens: gpt-5.4-mini $0.75 in / $0.075 cached / $4.50 out; gpt-5.4 $2.50 / $0.25 / $15; gpt-5.6-luna $0.20 / $0.02 / $1.20; gpt-5.6-terra $2 / $0.20 / $12; Batch API −50%; fine-tuning gpt-4.1-mini $5 per 1M training tokens | https://developers.openai.com/api/docs/pricing | primary vendor page |
| S2 | Anthropic per 1M tokens: Haiku 4.5 $1 / $5; Sonnet 5 $2 / $10; Opus 5 $5 / $25; cache hit 0.1× input; Batch −50%; Claude in Microsoft Foundry at the same rates via Azure Marketplace; US-only inference ×1.1 | https://platform.claude.com/docs/en/about-claude/pricing | primary vendor page |
| S3 | Gemini paid tier: 3.8 Flash $0.75 / $3.75 (promotional to 2026-12-31, then $1.50 / $7.50); 3.1 Pro $2 / $12 up to 200k context; free tier content may be used for training | https://ai.google.dev/gemini-api/docs/pricing | primary vendor page |
| S4 | Azure OpenAI pay-as-you-go: Global Standard equals OpenAI list; Data Zone about +10%; Regional higher | https://azure.microsoft.com/en-us/pricing/details/azure-openai/ (prices only render in the interactive calculator); numbers from https://www.cloudzero.com/blog/azure-openai-pricing/ updated 2026-09-04 | **secondary** — Ritesh: read UAE North / EU Data Zone from the Azure calculator before the room and overwrite row 11 |
| S5 | Azure NV12ads A10 v5 Linux: $1.30/h UAE North, $0.91/h East US. NV36ads A10 v5: $4.576/h UAE North, $3.20/h East US | Azure retail prices API, `armSkuName eq 'Standard_NV12ads_A10_v5'` | primary (Microsoft's price API) |
| S6 | Azure NC4as T4 v3 Linux: $0.526/h East US, $0.658/h West Europe; **no rows for UAE North, UAE Central or Qatar Central** | Azure retail prices API, `armSkuName eq 'Standard_NC4as_T4_v3'` | primary |
| S7 | Azure NC24ads A100 v4 Linux: $3.673/h East US, $4.775/h West Europe; not in the Gulf regions | Azure retail prices API | primary |
| S8 | Azure D4s v5 Linux, UAE North: $0.235/h (the app tier; not a serving option for a model) | Azure retail prices API | primary |
| S9 | AWS g6.xlarge (L4) $0.8048/h, g5.xlarge (A10G) $1.006/h, us-east-1 | https://www.thundercompute.com/blog/ec2-gpu-instances (Sept 2026) | secondary |
| S10 | Tokens per ticket | measured on `data/eval/heldout_20.jsonl` and `corpus/tickets/tickets_raw.jsonl` with the Llama 3.2 tokenizer | measured |
| S11 | Requests per hour per VM | `docs/timing_log.md`, notebook 06 on a Colab T4, 2026-09-21: median 0.8 s per ticket | measured, then discounted |
| S12 | Ops hours and hourly rate | none — placeholders | assumption |

Not modelled, on purpose: network egress, private endpoints, support
plans, VAT, currency, volume discounts, reserved-instance pricing, a
vendor changing its price mid-year, and the cost of a wrong answer.
Each is a line a group can add if it matters to their case.

## Regenerating and testing

```
python scripts/build_cost_model.py                      # rewrites facilitator/cost_model.xlsx, prints scenario A
python scripts/build_cost_model.py --scenario procedure_qa --out /tmp/b.xlsx
python -m pytest tests/test_cost_model.py -v
```

The tests check the Python arithmetic against hand-worked numbers,
check the workbook's formulas reference the cells this note says they
do, check the committed workbook is the script's output, and, when
Microsoft Excel is installed, open the workbook, recalculate it and
compare every derived cell with the Python numbers (both scenarios).
The committed workbook was also recalculated with LibreOffice 
headless on 2026-09-22 with identical results.

The workbook is written by the script as plain XML in a zip — no
spreadsheet library, because the repo's dependency list is frozen. If
you edit prices, edit `PRICES` and `SOURCES` in the script and rerun;
do not hand-edit the .xlsx, the test will fail.
