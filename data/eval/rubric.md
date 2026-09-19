# Scoring rubric: ticket to structured record

> **STATUS: DRAFT - awaiting sign-off by Ritesh.** The eval rubric is a
> raise-with-Ritesh item (BUILD_SPEC.md section 16). Nothing here is
> final until the sign-off block at the bottom is filled in. The
> harness already implements this draft, so a change here is a change
> in `scripts/eval_scoring.py` too.

Used in Day 2 S12 (base vs tuned) and Day 4 S19 (base / tuned /
base + retrieval). Same 20 tickets, same rules, both days.

**Design target: 15 minutes of reading results, not 40 minutes of
debate.** So the machine scores everything it honestly can, people
judge exactly two things, and both human steps have a fixed sample
size, a fixed question and a clock.

```
python scripts/run_eval.py --dataset data/eval/heldout_20.jsonl --endpoint local
```

---

## Part 1 - what the machine scores (no discussion needed)

Four measurements. They are reported separately and **never averaged
into one score**: a model that writes perfect JSON with wrong content
and a model that writes correct content inside a code fence fail in
different ways, and you fix them in different ways.

| # | Measurement | Rule | Report section |
|---|---|---|---|
| 1 | **Format** - schema-valid rate | `json.loads(reply)` works on the raw reply **and** the object passes `data/finetune/ticket_schema.json`. JSON wrapped in a code fence or in prose is *repaired and its content scored*, but it **fails format**: your integration would have crashed on it | 1 |
| 2 | **Fields** - per-field accuracy | Six fields by exact match, one by similarity (table below). An unreadable reply is wrong on every field; the "of readable" column shows the same thing without the format failures, so the two causes can be told apart | 2 |
| 3 | **Record** - whole-record match | All six exact-match fields right on the same ticket. `requested_action` is not included - it is not an exact-match field | 3 |
| 4 | **Invented values** | A count, never part of any accuracy: a value outside the allowed list (`"urgent"`, `"helpdesk"`), a key the schema does not have (`"notes"`), an asset tag whose digits appear nowhere in the ticket. A *wrong but real* value (`high` for `medium`) is an accuracy miss, not an invention. `null` in an enum field is a schema problem, not an invention | 4 |

### Field by field

| Field | Scored by | Detail |
|---|---|---|
| `category` | exact | case-sensitive: `"Access"` is wrong (and schema-invalid) |
| `affected_system` | exact on the **name** | case, spaces and punctuation ignored: `Auto Cad` = `AutoCAD`, `TEAMS` = `Teams`. `Tavrona` is **not** `Tavrona ERP`; `null` is not `"null"` |
| `asset_tag` | exact | `LAP-04412` form only. `lap-04412` is wrong: normalising the tag is part of the task |
| `urgency` | exact, then **H1** | misses are also reported by direction and size (+1 = one level too high) |
| `impact` | exact | |
| `routing_queue` | exact | one of the eight queues. The frozen schema allows any string here, so an unknown queue passes format and is caught as an *invented value* instead |
| `requested_action` | similarity, then **H2** | see below |

### `requested_action` - the one generative field

- **Measure:** word-set Jaccard similarity between the model's clause
  and the label's clause - shared words divided by all words, case
  and punctuation ignored. It is `dataset_utils.text_similarity`, the
  same measure the morning's near-duplicate check uses, so the room
  has already seen it. (Token-F1 is a monotone transform of it,
  `F1 = 2J / (1 + J)`, so it would rank answers identically.)
- **A match** is similarity **>= 0.50**. Calibrated on 40 real replies
  (llama3.2:3b and gpt-4o-mini on the held-out 20, 2026-09-20): every
  pair at or above 0.50 named the same action on the same object -
  there were no false matches.
- **Its limits, stated in the harness output too:** it compares words,
  not meaning, and the labels are written in one house style.
  `Reset password` vs `Reset the user's MyPortal password` scores 0.33
  though a desk agent would do the same thing. `Do not reset the
  password` vs `Reset the password` scores 0.60. So the match rate is
  a **floor** that rewards house wording; a fine-tuned model is
  expected to jump on it *partly because it learned the wording*.
  That is a real result (consistent phrasing is what a downstream
  system wants), but it is not the same as "understands better". H2
  exists to keep that honest.

### Per-class scores and the small-sample warning

The report prints per-class **counts** for category, urgency and
impact - never percentages - and flags every class with fewer than 5
tickets as `thin`. With 20 tickets, one ticket is 5 percentage points;
most classes in the held-out set have 1 to 4 tickets. The harness
says this in its own output ("READ THIS BEFORE QUOTING A NUMBER") so
that nobody has to discover it. A class with **no** tickets in the
dataset is still listed, as `NOT TESTED`. `val.jsonl` is worse than
the held-out set for the rare classes: once its planted problems are
cleaned out it has no `critical` and no `enterprise` ticket at all
(the held-out 20 has 2 and 1). No file in this repo can prove
rare-class quality, and the honest statement to the room is exactly
that.

---

## Part 2 - what people judge (exactly two things)

Both steps use tickets **the harness picks**, so every group reads the
same ones. Human verdicts are reported **next to** the machine number.
They never change it: recomputed accuracies cannot be compared between
groups, or between Day 2 and Day 4.

### H1 - urgency: is the miss a wrong answer or a defensible one?

`urgency` is where reasonable people disagree. The rule is written
down (`corpus/README.md`, "Labelling rules"):

| Level | The ticket states ... |
|---|---|
| `critical` | work blocked across a site or the enterprise |
| `high` | a user or team cannot work at all; or a same-day deadline; or degraded service across a site / enterprise |
| `medium` | degraded but workable; or a request with a needed-by date |
| `low` | a request with no time pressure; anything the user says can wait |

Tone never counts. `URGENT!!!` with no stated effect changes nothing.

**Step 1 - the pattern (2 minutes, no ticket reading).** If report
section 6 prints `PATTERN: the model over-escalates` (or
under-escalates), at least two thirds of the misses go the same way.
That is **one** disagreement about the convention, not a dozen about
tickets. The only question for the room: *the model has never been
told this convention - the prompt says "judge by the stated business
effect" and nothing else. Whose job is it to tell it: the prompt, or
the training data?* Write down the answer and move on.

**Step 2 - the tickets marked `*` (at most 3, 90 seconds each).** The
harness marks the misses furthest from the label. For each one:

1. One person reads aloud the sentence in the ticket that states the
   business effect - or says "none stated".
2. Hold that sentence against the table above.
3. Vote once, majority wins, no second round:

| Verdict | Meaning |
|---|---|
| **LABEL STANDS** | The rule gives the label's answer. The model is wrong |
| **MODEL DEFENSIBLE** | The rule supports both readings. Name the ambiguous phrase |
| **LABEL WRONG** | The rule clearly gives the model's answer. Note the ticket id for Utkarsh. **Do not edit the data in the room** |

Record three tallies. Report as: *"urgency 13/20; of 3 misses
reviewed: 2 label stands, 1 defensible."*

### H2 - requested_action: would the desk agent start the right work?

The harness lists at most 5 clauses that scored below 0.50, spread
evenly across the misses. For each, 30 seconds, one question:

> Given **only this clause and the routing queue**, would a desk agent
> start the right work on the ticket's **first** problem?

**YES** or **NO**. No "partly".

- Typical NO: a bare verb (`RESET`, `GRANT`); the wrong remedy
  (`Reboot` for a laptop that will not power on); an asset tag that is
  not in the ticket; the ticket's second problem instead of its first.
- Typical YES: the same action in other words (`Resolve microphone
  issue in TEAMS` for `Fix the user's microphone in Teams`).

Report as: *"requested_action 6/20 matched by machine; of 5 misses
read, 4 were adequate."* If most of the sample is adequate, the low
match rate is wording, not understanding - say so.

---

## The 15 minutes

| Min | Do | Look at |
|---|---|---|
| 0 - 4 | Read report sections 1 to 5, and the warning block. One sentence per measurement: format, fields, record, invented | the report |
| 4 - 6 | H1 step 1: the pattern | section 6 |
| 6 - 10 | H1 step 2: the `*` tickets | section 6 + ticket text |
| 10 - 13 | H2: the five clauses | section 7 |
| 13 - 15 | One conclusion per group: *what would you fix first, and with which tool - prompt, tuning, retrieval, or a validator?* | - |

### Tally sheet (one per group)

```
run label: ____________        schema-valid __/20     whole record __/20     invented __

H1 pattern:  over / under / mixed / none      whose job: prompt / training data
H1 tickets:  label stands __   model defensible __   label wrong __   (ids: ______________)
H2 clauses:  adequate __ of __
fix first:   ________________________________  with: prompt / tuning / retrieval / validator
```

### Not allowed in the room

- Re-labelling tickets, or re-computing accuracy after a vote.
- One blended "quality score". Four measurements stay four.
- Quoting a per-class percentage. Counts only; `thin` means anecdote.
- Reading a 5-point difference between two runs as a finding. It is
  one ticket.

---

## Calibration: what real runs looked like (2026-09-20)

Held-out 20, temperature 0, JSON mode off. Full outputs are in
`facilitator/prebaked_outputs/eval/`.

| | llama3.2:3b (Ollama) | gpt-4o-mini (hosted) |
|---|---|---|
| schema-valid | 17/20 (3 x `impact: null`) | 20/20 |
| category | 14/20 | 19/20 |
| affected_system | 15/20 | 15/20 |
| asset_tag | 20/20 | 20/20 |
| urgency | 13/20 (mixed direction) | **8/20 - all 12 misses over-escalate** |
| impact | 14/20 | 19/20 |
| routing_queue | 8/20 | 17/20 |
| requested_action (>= 0.50) | 2/20, mean 0.14 | 6/20, mean 0.38 |
| whole record | 2/20 | 6/20 |
| invented values | 1 (copied the prompt's example tag `LAP-04412` into an action) | 0 |

Both untuned models already write clean JSON on this prompt, so on
Day 2 the tuned model's visible wins will be the *house conventions* -
urgency levels, queue names, clause wording - more than raw format.

---

## Sign-off (Ritesh)

Decisions this draft makes that need a yes or a change:

| # | Decision | Default in this draft |
|---|---|---|
| 1 | Fenced or prose-wrapped JSON fails **format** but its content is still scored | yes |
| 2 | `affected_system` ignores case, spacing and punctuation; nothing looser | yes |
| 3 | `requested_action`: word-set Jaccard, match at >= 0.50, reported as a floor | yes |
| 4 | Whole-record match uses the six exact fields only | yes |
| 5 | `null` in an enum field is a schema problem, not an invented value | yes |
| 6 | H1 reads at most 3 tickets, H2 at most 5; votes never change machine numbers | yes |
| 7 | JSON mode is **off** by default (`--json-mode` turns it on as a talking point) | yes |
| 8 | **Open question.** The system prompt does not define the four urgency levels, so untuned models are scored against a convention they were never shown (gpt-4o-mini: 8/20, every miss an over-escalation). Option A: keep it - it *is* the lesson, tuning teaches the house convention, and H1 step 1 makes the point in two minutes. Option B: add the four definitions to `SYSTEM_PROMPT` - fairer to the base model, but it means rebuilding the dataset, the adapter and every eval table | A (recommended: B costs a full rebuild inside the freeze week and removes the clearest win tuning has) |

```
Signed off by: ____________________   Date: __________   Changes required: ______________________
```
