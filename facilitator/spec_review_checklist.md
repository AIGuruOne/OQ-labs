# Spec peer review checklist (Day 1 S5, 25 minutes)

**Setup.** Groups swap specs in a ring (1 reviews 2, 2 reviews 3, ...
last reviews 1). The reviewing group answers the questions below
*in writing* on the spec itself, then tells the authors the three
findings that matter most. Authors listen and write; they do not
defend. Defence is for the revision this evening.

**Clock.**

| Minute | Do |
|---|---|
| 0–7 | Read the spec in silence. All of it. Do not start answering |
| 7–19 | Answer the questions. Every answer is YES / NO / CAN'T TELL plus the section number you looked in. CAN'T TELL is a finding: it means the spec does not say |
| 19–23 | Pick the three findings that would stop this being deployed, in order. Write them in the findings block |
| 23–25 | Read the three findings to the authors, one minute each, in order. No discussion |

**Severity.** Every finding gets one:

- **BLOCKS** — the pilot cannot start until this is answered (no
  owner, data may not be sent where the spec sends it, no eval).
- **BEFORE PILOT** — must be fixed before real users see it, but the
  build can continue.
- **NOTE** — would improve it; not a reason to stop.

A review with no BLOCKS on a first-draft spec was not read properly.
There is always one.

A filled example: `facilitator/examples/spec_review_brief1_filled.md`.

---

## The questions

Answer YES / NO / CAN'T TELL and the section you looked in.

### A. Is the job real? (spec section 1)

| # | Question | Answer | Where |
|---|---|---|---|
| A1 | Can you say, in one sentence, what arrives and what leaves — without reading the spec again? | | |
| A2 | Is there a number for how it is done today (minutes, tickets, errors)? | | |
| A3 | Does the output go to a person or system that will act on it within the day? | | |
| A4 | Are the two out-of-scope items things you would have assumed were in? | | |

### B. Was the decision made, or assumed? (section 2)

| # | Question | Answer | Where |
|---|---|---|---|
| B1 | Are all four options scored, with the arithmetic visible? | | |
| B2 | Is each gate answer attributed to a person, not "probably"? | | |
| B3 | Does the "what flips it" sentence name a condition that could actually happen this year? | | |
| B4 | Is the cost row filled from the cost model, with ops labour in it, and not from a guess? | | |

### C. Will the data owner sign this? (section 3)

| # | Question | Answer | Where |
|---|---|---|---|
| C1 | Is the classification of the *prompt text* stated, and is the option chosen in section 2 allowed for that classification? | | |
| C2 | Is there a *mechanism* (not an intention) that keeps the must-never-enter fields out? | | |
| C3 | Does the spec say where prompts and outputs are stored, for how long, and who can read them? | | |
| C4 | If the log stores the input text, is that consistent with C1? (It usually is not.) | | |
| C5 | For training or index data: is there a source, a count and a quality check named? | | |

### D. Can this actually be run? (section 4)

| # | Question | Answer | Where |
|---|---|---|---|
| D1 | Is the model named with a size and a version, and the next size up or down ruled out for a reason? | | |
| D2 | For a VM: SKU, region, serving software and its version, and the person who upgrades it? For a vendor: region or data zone? | | |
| D3 | Is the endpoint one of the `config/endpoints.py` names, so the model can be swapped by configuration? | | |
| D4 | Is there a maximum input size and a rule for what is cut when it is exceeded? | | |
| D5 | Is the output validated against a schema *before* the caller sees it, and is the failure case described? | | |
| D6 | Are timeout, retry count and the model-down answer all numbers or names, not "handled"? | | |

### E. Retrieval and tools, if any (section 5)

| # | Question | Answer | Where |
|---|---|---|---|
| E1 | Is there a list of what the index must NOT contain? | | |
| E2 | Does an answer show the date of the index it came from? | | |
| E3 | Is every write tool behind a named human approval, tested not described? | | |
| E4 | Does the spec name the inputs that can carry instructions to the model, and what happens to them? | | |

### F. Would you believe the quality number? (section 6)

| # | Question | Answer | Where |
|---|---|---|---|
| F1 | Is "correct" defined per field or per answer in a way a script could check? | | |
| F2 | Is the eval set's size stated, and is there proof it was never trained on or indexed? | | |
| F3 | Are format, field accuracy, whole-record accuracy and invented values reported as separate numbers? | | |
| F4 | Is the pilot target compared with a number that exists today, and is the gap plausible in the time given? | | |
| F5 | Is the eval set big enough for the claim? (20 items cannot support "80%": one ticket is 5 points.) | | |
| F6 | Does a human check a stated sample at a stated interval, and does a miss go somewhere? | | |

### G. Does the money add up? (section 7)

| # | Question | Answer | Where |
|---|---|---|---|
| G1 | Are the seven numbers from the cost model present? | | |
| G2 | If self-hosting: is the idle share acknowledged, and is the reason for hosting a gate or a criterion other than cost? | | |
| G3 | Is there a latency target with a place it was or will be measured? | | |
| G4 | Is there a cost cap and a defined behaviour when it is hit? | | |

### H. What happens when it is wrong? (section 8)

| # | Question | Answer | Where |
|---|---|---|---|
| H1 | Does a wrong output reach a person before it has an effect? If not, does the spec say why that is acceptable? | | |
| H2 | Is the audit log field list complete enough to reconstruct one call a month later? | | |
| H3 | Can a named person turn it off, and is "how fast" a number? | | |
| H4 | Is rollback a procedure with a duration, not a word? | | |

### I. Will it survive us leaving? (section 9)

| # | Question | Answer | Where |
|---|---|---|---|
| I1 | Is the owner a named person whose job includes being paged for this? | | |
| I2 | Are the pilot users, count, duration and success measure all stated? | | |
| I3 | Are the sign-offs named as roles that exist in the company? | | |

### J. The manager's three questions

Answer as the manager would ask them. If the spec does not let you
answer in one line each, that is a finding.

| # | Question | Your one-line answer from the spec |
|---|---|---|
| J1 | What does it cost a month, and what does it save? | |
| J2 | What is the worst thing it can do, and who catches it? | |
| J3 | Who do I call when it breaks on a Friday? | |

---

## Findings block

Write on the spec. Three findings, most severe first. One sentence
each: what is missing or wrong, and which question above found it.

| # | Severity | Finding | Question |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |

Then, in one line: **the best thing about this spec** — the part the
authors should not lose in revision.

## For the authors, this evening

Revise sections the findings point at. Re-answer the three findings'
questions yourself. Version becomes v0.2. The Day 2 eval numbers go
into section 6 tomorrow afternoon; that is v0.3.
