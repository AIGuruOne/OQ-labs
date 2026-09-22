# Architecture spec — template (Day 1 S4, 90-minute lab)

**Who fills it in:** a capstone group of 2–3, at the table, for the
use case brief it picked. One person types; the other two answer.

**Time:** 75 minutes of writing in the boxes below, in the order
given; the minutes beside each section add to 75. The other 15 are for
the cost model (`facilitator/cost_model.xlsx`, needed in section 7)
and for arguing. If a section is running over, write "OPEN" and move
on — section 10 collects those.

**The bar:** every prompt gets one line, sometimes two. A line that
starts with "we will decide later" is fine if it also says who decides
and by when. A line that starts with "the model will" and has no
number in it is a wish, not a spec.

**How it is used:** reviewed by another group in S5 with
`facilitator/spec_review_checklist.md`. Revised on Day 2 evening with
the eval numbers. Filled into the governance pack on Day 5. A group's
spec is the first thing they show on Thursday.

A filled example: `facilitator/examples/architecture_spec_brief1_filled.md`.

---

## 0. Cover (2 min)

| | |
|---|---|
| Group | |
| Use case brief | (number and name from `facilitator/use_case_briefs.md`) |
| Version and date | v0.1, 2026-09-27 |
| Owner after the week (name in principle) | |

## 1. The job (8 min)

- **One sentence.** "When ___ happens, the system takes ___ and
  produces ___, so that ___ can ___." No adjectives.
  >
- **Input.** What exactly arrives: a ticket body, a photo, a question.
  Its size range. Who or what sends it.
  >
- **Output.** What exactly leaves: a JSON record, an answer with
  citations, a draft work order. Who or what receives it. What they
  do with it in the next five minutes.
  >
- **Today.** How this is done now, by whom, and how long it takes.
  The number you are trying to move.
  >
- **Not in scope.** Two things a reader might assume this does that it
  does not.
  >

## 2. The decision (5 min)

Paste from the S3 decision matrix.

- **Option chosen** (A direct / B tenant / C host / D host and tune)
  and the weighted totals of all four.
  >
- **Gates.** Which of G1–G5 removed an option, and who answered them.
  >
- **What flips it.** The one sentence from the matrix.
  >

## 3. Data (10 min)

- **What goes into a prompt.** List the fields, verbatim from the
  source system. Mark each one *needed* or *nice to have*.
  >
- **Classification.** Public / internal / confidential / personal data
  — of the prompt, and separately of the output. Who classified it.
  >
- **Must never enter a prompt.** Fields, patterns (passwords, national
  ids), whole document families. And the mechanism that stops them,
  not just the intention.
  >
- **Where the text is stored after the call.** Prompts, outputs and
  logs: where, for how long, who can read them.
  >
- **Training or index data, if any.** Where it comes from, how many
  items, how it is refreshed, and the quality checks it passes before
  use (duplicates, leakage, schema, coverage, imbalance).
  >

## 4. Model and serving (10 min)

- **Model.** Name, size, version or date. Why this one and not the
  next size up or down.
  >
- **Where it runs.** Vendor deployment (which region or data zone) or
  VM (SKU, region, count). For a VM: what serves it (Ollama, vLLM),
  which version, and who upgrades it.
  >
- **Endpoint.** The `config/endpoints.py` name (`local`, `hosted`,
  `tuned`) the integration calls, and the fact that swapping it needs
  no code change.
  >
- **Context budget.** Maximum input tokens you will send, and what is
  dropped first when a request is bigger.
  >
- **Output contract.** The schema (or the format) and where it is
  validated. What the caller receives when validation fails.
  >
- **Timeout, retry, fallback.** Seconds before you give up; how many
  retries; what answers when the model is down.
  >

## 5. Retrieval and tools (8 min — write "none" and skip if none)

- **Sources.** Which document families or tables the index holds, and
  which it must not.
  >
- **Freshness.** What triggers a rebuild, and how the answer shows its
  index date.
  >
- **Per request.** How many chunks (k), the context cap in tokens, the
  confidence floor below which you refuse.
  >
- **Tools.** One line per tool: name, read or write, what approval a
  write needs, what the tool returns on error.
  >
- **Untrusted text.** Which inputs can contain instructions to the
  model (documents, tickets, tool results) and what you do about it.
  >

## 6. Quality (10 min)

- **Correct means.** Per output field or per answer: exact match,
  similarity above a threshold, cited from the right source, a human
  agrees. Name the rubric if one exists.
  >
- **Eval set.** How many items, where they came from, and the proof
  they were never in training or in the index.
  >
- **Targets.** The numbers you must reach for a pilot, per
  measurement, and the number you have today. Keep format, per-field
  accuracy, whole-record accuracy and invented values as separate
  lines — never one blended score.
  >
- **Human review.** What sample a person checks, how often, and what
  they do with a miss.
  >
- **Retrain or rebuild trigger.** The number that, when it drops
  below X on the weekly sample, starts the retrain or rebuild runbook.
  >

## 7. Cost and capacity (7 min — from the cost model)

| From the sheet | Value |
|---|---|
| Requests per month | |
| Input / output tokens per request | |
| Vendor API $ per month (chosen model) | |
| Self-hosted $ per month (with ops labour) | |
| Break-even requests per month | |
| Peak requests per hour | |
| VMs needed at peak, if hosting | |

- **Latency target.** p95 seconds, and where it was measured (or
  "not yet: notebook 03 on Day 2").
  >
- **Cost cap.** The monthly figure at which the service stops or
  degrades, and what degrading means.
  >

## 8. Failure and control (8 min)

- **Wrong answer.** Who sees it before it has an effect. If nobody:
  say so, and say why that is acceptable.
  >
- **Model down.** What the caller gets, and how long the business can
  live with it.
  >
- **Audit log.** The fields written per call (at least: timestamp,
  caller, input hash, model and version, output, validation result,
  tokens, seconds).
  >
- **Kill switch.** Who can turn it off, how, and how fast.
  >
- **Rollback.** How you return to the previous model or index, and how
  long it takes.
  >

## 9. Ownership and rollout (5 min)

- **Owner.** Name and role. The person who is paged.
  >
- **Pilot.** Which users, how many, for how long, measured on what.
  >
- **First 30 days.** The three things that happen after go-live.
  >
- **Sign-offs needed before pilot.** Data owner, security, the team
  whose process changes.
  >

## 10. Open questions (2 min)

Everything marked OPEN above, each with a name and a date.

| # | Question | Who | By when |
|---|---|---|---|
| | | | |
