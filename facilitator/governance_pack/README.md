# Governance and deployment pack (Day 5 S29, 30 minutes)

Eight templates an IT team fills in for one AI system and keeps using
after the week. Not policy essays: every template is a set of tables
and one-line prompts, most of which are pasted from the architecture
spec (`facilitator/architecture_spec_template.md`) the group already
wrote on Day 1 and revised on Day 2.

**Why it exists, in one paragraph.** On Day 3 the room watched a
vision model misread a diagram (two tags at low separation, the
known-bad case), watched that wrong extraction get indexed, then
watched a retrieval answer cite it as fact with a confident tone and a
citation. Nothing in that chain was broken: the model did what models
do, the index did what indexes do, the answer format did what it was
told. What was missing was a rule about what may enter a knowledge
base unchecked, a log that could find every answer that cited the bad
chunk, and someone whose job it was to pull it. These eight templates
are that rule, that log and that someone, written down for the system
each group is building.

## The eight templates

| # | File | Minutes | Answers the question | Mostly pasted from |
|---|---|---|---|---|
| 1 | `01_system_register.md` | 8 | What is this system, who owns it, what does it touch, what happens if it is wrong? | spec §0, §1, §9 |
| 2 | `02_data_classification.md` | 12 | What data goes where, and is a vendor model allowed to see it? Self-hosted VM versus vendor through the tenant versus vendor direct | spec §2, §3 |
| 3 | `03_evaluation_acceptance.md` | 12 | What number must it reach before real users see it, measured how, on what? | spec §6, the eval tables |
| 4 | `04_approval_gating.md` | 12 | Which actions need a human, which human, what do they see, and where in the code is the gate? | spec §5, §8 |
| 5 | `05_audit_logging.md` | 8 | What is written per model call, per tool call and per index write, so one bad output can be traced a month later? | spec §8 |
| 6 | `06_incident_response.md` | 12 | When it is wrong and someone acted on it, who does what in the first hour, including the case of a wrong extraction in the knowledge base? | spec §8 |
| 7 | `07_change_management.md` | 8 | What is versioned, what is re-run before a new version is promoted, how do you go back? | spec §4, §8 |
| 8 | `08_monitoring_drift.md` | 8 | What is looked at every week, and which number starts which runbook? | spec §6, §7 |

80 minutes for the whole pack when the spec is in front of you. Each
template says which spec sections to paste from; the new writing per
template is ten lines or fewer. A worked example, filled for brief 3
(nameplate and diagram capture) with the fill time recorded per
template: `examples/brief3_vision_capture_filled.md`.

`sources.md` lists every framework, regulation and vendor document the
templates cite, with the link, the date it was checked and how sure we
are. Templates cite them as `[S1]`..`[S14]`. Nothing is cited from
memory; a source that could not be opened is marked so.

## The 30-minute session: what is presented, what is taken away

The session is talk and template. Ritesh presents; the groups fill in
two things and take the rest away. Do not try to fill all eight in the
room.

| Minute | Who | Do |
|---|---|---|
| 0–5 | Ritesh | Replay the Day 3 moment on one slide: the known-bad diagram, the wrong tag, the index, the confident cited answer. Ask the room: which of the six deployment-ready points from the briefs would have stopped it? (Point 3, a defined path for a wrong answer, and point 5, every call logged.) |
| 5–15 | Ritesh | The eight templates, about a minute each, using the **filled brief 3 example**, not the blanks. For each: the one row that would have caught the Day 3 case. Template 4's tool table and template 5's tool-call line are the ones to show on screen, because the room wrote that exact audit line in S26 this morning. |
| 15–25 | Groups | Fill **template 1** (register) and the **tool table in template 4** for their own capstone. Both are needed for the showcase: the register names the owner, the tool table names the approval points. Paste, do not compose. |
| 25–28 | Ritesh | The take-away rule (below), and the two rows the showcase will ask about tomorrow afternoon: the classification table in template 2 and the rollback line in template 7. Both are pastes from spec §3 and §8. |
| 28–30 | Ritesh | The one sentence to leave with: a wrong answer that nobody can trace is a governance failure; a wrong answer that is caught, logged and pulled is the system working. |

**Take-away rule.** The owner named in template 1 finishes templates
2 to 8 for the real system, not the lab one, within two weeks of the
program, and the pack is reviewed with the data owner and security
before any pilot. The showcase (S30) checks that templates 1 and 4 are
filled and that templates 2 and 7 have their key rows; it does not
check the rest.

## How to fill one in

1. Have the group's architecture spec (v0.3, with the Day 2 numbers)
   open. Most answers are already in it.
2. Work top to bottom, one template at a time, one person typing.
3. A blank cell is allowed if it says OPEN and names who closes it. A
   blank cell with nothing in it is not.
4. Numbers come from a run (`run_eval.py`, `score_extraction.py`, the
   cost model). A number you cannot point at a file for is written as
   "not measured", never estimated.
5. If a template takes more than its minute budget, write OPEN in the
   remaining rows and move on. The pack is finished later; the
   showcase is tomorrow.

## What this pack is not

- Not a compliance programme. It is what an engineering team needs to
  run one system responsibly. An organisation-wide AI policy, an AI
  management system (ISO/IEC 42001 [S3]) or a regulatory filing would
  be built on top of packs like this, not instead of them.
- Not legal advice. Where a template touches Omani law (personal data,
  cross-border transfer, breach notification) it says what the law is
  called and where to read it [S5], and tells you to ask the data
  protection officer. It does not tell you what the law means for your
  case.
- Not specific to any real OQ system. Every example, site, system
  name and person in this folder is invented (BUILD_SPEC section 9).
