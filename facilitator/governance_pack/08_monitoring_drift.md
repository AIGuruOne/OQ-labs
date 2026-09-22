# 8. Ongoing monitoring and drift (8 min)

**Why this exists.** The eval number is true on the day it was
measured. After that the inputs move (a new system name in tickets, a
new queue, a procedure revised, a camera changed), the vendor updates
the model under the same name, the index grows, and the people using
the output start trusting it more than the number justifies. None of
that produces an error. It produces a slow slide in the weekly sample,
which is why the weekly sample exists. The CISA data-security guidance
names data drift as one of its three risk areas and asks for ongoing
monitoring of it [S11]; the NCSC/CISA guidelines put monitoring under
secure operation [S10]; the NIST AI RMF's MEASURE and MANAGE functions
are this template in framework language [S1]. For an engineer: a
dashboard with six numbers, a threshold on each, and the name of the
runbook each threshold starts. Nothing here needs a data scientist.
It needs someone to look at the numbers every week and to know what to
do when one moves.

**Paste from:** spec §6 (human review, retrain trigger), §7 (latency
target, cost cap). New writing: the drift signals, the thresholds and
what each one starts.

**Done when:** each signal has a threshold and a runbook; the weekly
review has a name, a day and a duration; the first review has
happened.

---

## 8.1 The weekly numbers

| Signal | How it is computed | Threshold | When crossed, start | Owner |
|---|---|---|---|---|
| Format rate (schema-valid, citation present) on all traffic | from `llm_call.validation` | below ___ % for a week | template 6 SEV3 review; template 7 if a change preceded it | |
| **Invented / uncited count** on the weekly sample | rubric or `score_extraction.py` on the sample | above 0 | template 6 runbook 6.4 (check what entered the index) | |
| Accuracy on the weekly human-scored sample (per field or per answer; counts, not %) | the same rubric as template 3, n = ___ | below the pilot bar for 2 consecutive weeks | template 7 retrain / rebuild | |
| Gate signals: approval rejection rate, refusal rate | from `tool_call.approval` and the refusal reason | rejection above ___ % or below ___ % (a rate near 0 means the approver stopped reading) | approver check-in; sample size up | |
| Latency p95 and error rate | from `llm_call.seconds`, `tool_call.status` | above the spec §7 target | existing on-call | |
| Cost per month to date | from `cost_estimate` sums | above ___ % of the cap by mid-month | cost cap action (spec §7) | |

## 8.2 Drift signals (the inputs, not the outputs)

| Signal | How it is computed | Threshold | When crossed, start |
|---|---|---|---|
| Input length distribution (tokens per item) against the eval set's | median and p95 per week vs. the eval set | p95 more than ___ % above | check truncation; sample the long ones |
| Unseen values: new system names, queues, tags, document families in inputs | count of values not in the training / index vocabulary | more than ___ new per week | label them; template 7 (dataset or index rebuild) |
| Index freshness: age of the newest and oldest document; documents withdrawn but still indexed | from `index_write` | older than the freshness rule in spec §5 | index rebuild (template 7) |
| Vendor model change (hosted only): version string or a canary prompt's answer changed | the vendor's version field; a fixed canary set of 5 prompts run daily | any change | re-run template 3.1 before the day ends |
| Automation bias: the share of proposals confirmed without an edit, by user | from the downstream tool's confirm/edit event | above ___ % for a user for 2 weeks | that user's sample doubled; approver check-in (template 4.4) |

## 8.3 The weekly review

| | |
|---|---|
| Who, which day, how long (target: 30 minutes) | |
| Sample size and how it is drawn (random across users and sites, not the easy ones) | |
| Where the numbers are written (one row per week; the same file as 7.3 is fine) | |
| Who is told when a threshold is crossed, and how | |
| Quarterly: the eval set refreshed with recent hard cases (template 3.2), the pack re-read | |

## 8.4 First month log

| Week | Format | Invented | Sample accuracy (n) | Rejection % | p95 s | Cost to date | Notes / actions started |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |

## 8.5 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Business owner | | |

Sources: [S11] CISA and partners, AI data security best practices
(data drift). [S10] NCSC/CISA secure AI system development, "secure
operation and maintenance: logging and monitoring". [S1] NIST AI RMF
1.0, MEASURE and MANAGE. [S4] EU AI Act Art. 14(4)(b) on automation
bias, as the checklist item behind 8.2's last row.
