# Skills map

One row per lab: the skill it teaches, how you check it landed, and what
downstream consumes it. If a lab has no row here, it is reference material
rather than part of the ladder.

This file and the notebooks' own header blocks are kept in step by
`tests/test_skills_map.py` — the skill sentence below must appear verbatim in
the notebook, and every "Feeds" target must be a real session or file.

## Day 3 · S16 · Vision

The two labs are one ladder, in order. Everything else in the vision section is
reference.

| Lab | Skill | You will know it landed when | Feeds |
|---|---|---|---|
| `08a_vision_basics` | Recognise that a vision model which cannot read a field returns a confident, well-formed, wrong value rather than an error — and know that telling it to flag uncertainty does not fix it. | They can answer *"why is `PTW-48715` worse than a blank field?"* | `09a_vision_review_rule`, S29 governance pack template 3 |
| `09a_vision_review_rule` | Decide, field by field, what a model may write into a system of record unchecked — and what must go to a person — by measuring it against documents you already know the answers to. | They can finish, with their own numbers: *"A model may write ___ unchecked. A person must see ___. That costs ___ reviews, and ___ wrong values still get through."* | S27 deployment checklist row 3, S29 governance pack template 4 |

## Day 4 · S22 · MCP

| Lab | Skill | You will know it landed when | Feeds |
|---|---|---|---|
| `11a_mcp_basics` | Tell what a model is allowed to do by looking at how its tool server was started — not at the model, the prompt or the client — and show that the same server file offers different tools depending on that one setting. | They can answer *"where is the write actually stopped?"* and *"what could a cleverer prompt do about it?"* | S24 blast-radius sheet, S26, S29 governance pack template 4 |

`11b_mcp_live` is the fuller version — two servers written from scratch, the
inspector, a gated client — and stays as reference. 11a is the rung.

### What the ladder deliberately leaves out

`08`, `09`, `10` and `08b` are **not** on it. They were built as a full
comparison bench — two model arms, four degradation tiers, F1 scoring, image
quality measurement — and that is the right shape for reference material and the
wrong shape for a room of IT practitioners meeting vision for the first time.
They stay in the repo and are still correct; they are just not what you teach.

### The measurements these labs rest on

All 2026-09-30, `gpt-4.1-mini`, temperature 0, and reproduced at least three
times each. If a number below stops holding, the lab's text is wrong and should
be changed rather than explained away.

| Claim | Measured |
|---|---|
| A clean scan reads perfectly | 6 of 6 fields correct |
| A poor photograph fails silently | 5 of 6 wrong, **0 flagged** |
| "Say NOT_LEGIBLE if unsure" changes nothing | 5 of 6 still wrong, still 0 flagged |
| "Assume you cannot read" works | 6 of 6 refused, 3 runs out of 3 |
| …and has not become refuse-everything | still 6 of 6 correct on the clean scan |
| A *decent* phone photo still fails | 8 of 60 fields wrong over ten forms |
| The errors are all identifiers | permit 4, equipment 4, work order 0, site 0, discipline 0, date 0 |

That last row is the one to say out loud: the model reads **words** reliably and
misreads **codes**, because a code has no redundancy and a word does.
