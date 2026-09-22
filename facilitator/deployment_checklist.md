# Deployment checklist (Day 5, 13:15 final polish, 30 minutes)

**Who:** each capstone group, on its own build. **Output:** this page,
ticked, with the verdict at the bottom filled in, shown in S30.

Tick an item only after doing the check in the right-hand column
against what you actually built, not what you plan to build. An item you
cannot tick is fine: write the gap and its owner in the last column.
A gap nobody owns is the only wrong answer.

`<OUT>` = the folder you pass as `--out` (on Colab, your Drive folder).
`<uc>` = your use-case module, e.g. `capstone.my_usecase`.

## A. It runs (6 min)

| # | Check | How | Done / gap + owner |
|---|---|---|---|
| A1 | Runs from a cold start with one command | `python -m capstone.run status --usecase <uc> --out <OUT>`: no traceback | |
| A2 | You know which of your pieces are FALLBACK, and why | the `index` and `adapter` rows of that output | |
| A3 | Your demo input works | `python -m capstone.run ticket ... --usecase <uc>` on the input you will show | |
| A4 | The model can change without your code changing | the same command with `--endpoint` set to a second endpoint | |
| A5 | It survives a missing service | the same command with `--no-services`: it still answers, and says the lookup was unavailable | |

## B. There is a number (6 min)

| # | Check | How | Done / gap + owner |
|---|---|---|---|
| B1 | Measured on data it did not train on | `python -m capstone.run eval --usecase <uc> --out <OUT>` (held-out 20; brief 2/3: your Day 3 set) | |
| B2 | Compared with something | `python scripts/run_eval.py --compare <yours>_summary.json <baseline>_summary.json` | |
| B3 | You can say what the number does NOT show | the "READ THIS BEFORE QUOTING" block: n = 20, one ticket = 5 points, thin classes | |
| B4 | The field or case it gets wrong most is named | the per-field and per-ticket rows | |

## C. A wrong answer has a path (6 min)

| # | Check | How | Done / gap + owner |
|---|---|---|---|
| C1 | A malformed or invented output is caught | your `check_output`; find one ticket in B1 where it fired (`validation.valid: false` in `<OUT>/audit/llm_call.jsonl`) | |
| C2 | A caught output is never applied | read your `decide()`: every branch proposes, refuses or asks. Nothing writes | |
| C3 | Any write needs a named person | brief 3/4: the approval form and the approver list (`OQ_MCP_APPROVERS`); others: write "no writes" | |
| C4 | Text inside the input is not obeyed | brief 2/4: the injection ticket or document, run once, result noted | |

## D. It is logged and costed (5 min)

| # | Check | How | Done / gap + owner |
|---|---|---|---|
| D1 | Every model call has an audit line | line count of `<OUT>/audit/llm_call.jsonl` = calls made | |
| D2 | A line says which model, prompt version and context produced it | one line: `model_fingerprint`, `prompt_version`, `context_ids` filled | |
| D3 | Tool calls join the model call | a `tool_call.jsonl` line with the same `trace_id` (if you look anything up) | |
| D4 | The cost cap is set to a number someone chose | `COST_CAP_USD_PER_MONTH` and the price in your use-case file, with where they came from | |

## E. Someone can take it over (5 min)

| # | Check | How | Done / gap + owner |
|---|---|---|---|
| E1 | A named owner after this week | governance template 1 | |
| E2 | Data classification and where data goes | governance template 2 | |
| E3 | Rollback in one sentence | "set ENDPOINT / MY_ADAPTER_DIR / MY_INDEX back to ..." (template 7) | |
| E4 | The gaps above have owners | the right-hand column of this page | |
| E5 | What is NOT built is written down | `facilitator/production_engineering_handout.md` section 2: which apply to you | |

## Verdict (2 min)

- [ ] **Handover-ready**: every item in A-D ticked; E filled in.
- [ ] **Handover-ready with named gaps**: A ticked; every other gap has an owner and a date.
- [ ] **Not yet**: say which letter, and what it would take.

The verdict is what you say first in S30.
