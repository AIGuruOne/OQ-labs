# 1. AI system registration record (8 min)

**Why this exists.** You cannot govern, monitor or switch off a
system nobody has written down. Every framework the pack draws on
starts here: the NIST AI RMF's GOVERN function asks for an inventory
of AI systems with their risks and owners [S1], ISO/IEC 42001 makes
the same inventory the base of its management system [S3], and Oman's
2025 AI policy asks for accountable ownership of every deployed system
[S6]. For an engineer the useful version is narrower: one page that
says what the thing is, who is paged, what it can touch, and what the
worst plausible wrong output does. The Day 3 demonstration is the
test case: a wrong extraction was indexed and cited, and the first
question anyone asked was "whose system is this?" This record is the
answer, and it is the one document a manager reads before saying yes
to a pilot.

**Paste from:** spec §0 (cover), §1 (the job), §9 (ownership). New
writing: the autonomy level, the "if it is wrong" lines, the review
date.

**Done when:** every cell is filled or says OPEN with a name and a
date; the autonomy level and the risk tier are circled, not described.

---

## 1.1 Identity

| | |
|---|---|
| System name (as people will call it) | |
| System id (invented convention: `AIS-` + 3 digits, e.g. `AIS-001`) | |
| Version of this record, date | v0.1, 2026-10-01 |
| Use case brief (1–5) | |
| One-sentence job (spec §1, verbatim) | |
| Status | design / shadow / pilot / production / retired |
| Go-live date (planned or actual) | |
| Next review date (at most 6 months after go-live) | |

## 1.2 People

| Role | Name | How reached |
|---|---|---|
| Owner (the person paged; spec §9) | | |
| Deputy | | |
| Business owner (whose process changes) | | |
| Data owner (signs template 2) | | |
| Security contact (signs templates 4, 5) | | |
| Data protection officer, if personal data is involved [S5] | | |

## 1.3 What it touches

| | |
|---|---|
| Inputs (spec §1): what arrives, from where | |
| Outputs (spec §1): what leaves, to whom | |
| Systems it READS (name each; e.g. `Tavrona ERP` equipment master) | |
| Systems it WRITES to (name each; each needs a row in template 4) | |
| Knowledge base / index it reads, if any | |
| Knowledge base / index it WRITES to, if any (a write; template 4) | |
| Model(s) and endpoint name (`local` / `hosted` / `tuned`, spec §4) | |
| Hosting: self-hosted VM in tenant / vendor through tenant / vendor direct (template 2) | |
| Users: who sees the output, how many | |

## 1.4 Autonomy level (circle one)

| Level | Meaning | Example from the week |
|---|---|---|
| **L0 informs** | Output is shown to a person; nothing changes until they act | Similar-ticket panel (brief 5) |
| **L1 proposes** | Output pre-fills something a person confirms or edits, item by item | Triage record in the desk tool (brief 1) |
| **L2 acts with approval** | The system prepares an action; a named approver must approve before it executes | Draft work order behind the approval interrupt (brief 4) |
| **L3 acts autonomously** | Executes without a human per item | **Not built this week.** If you circle L3, template 4 must say why and template 8 must sample it weekly |

> Level: ___   Why this level and not the one below:
>

## 1.5 If it is wrong

Write three lines. The third is the Day 3 case: what happens if a
confident wrong output is *stored* and reused later.

| Case | What happens, concretely | Who notices, and how long after |
|---|---|---|
| A wrong output is shown to a person once | | |
| A wrong output is acted on (a write, a routing, a permit decision) | | |
| A wrong output is stored (index, equipment master, training data) and reused | | |

## 1.6 Risk tier (circle one)

| Tier | Condition | What it obliges |
|---|---|---|
| **T1** | Worst plausible wrong output costs time or money and is visible to a person before it takes effect | Templates 1–8 filled; weekly sample (template 8) |
| **T2** | A wrong output can reach a system of record, a knowledge base, or a customer without a person in between | T1 plus: approval gate tested (template 4), shadow period before pilot (template 3), incident runbook rehearsed once (template 6) |
| **T3** | A wrong output can affect plant operation, safety, permits, or a person's rights | **Stop.** Nothing in this week is designed for T3. Talk to HSE and the OT owner before writing anything else |

> Tier: ___   The wrong output that put it there:
>

## 1.7 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Business owner | | |

Sources: [S1] NIST AI RMF 1.0, GOVERN. [S3] ISO/IEC 42001:2023.
[S6] Oman MTCIT AI policy, 2025. [S5] Oman PDPL, for the DPO row.
