# 6. Incident and failure response (12 min)

**Why this exists.** An AI incident is not an outage. The service is
up, the latency is fine, and a confidently wrong output has been
acted on, stored or sent. The usual on-call playbook has no step for
"find every place this output went". NIST's generative AI profile
lists incident disclosure and response among the actions it expects
[S2, A.1.8]; the NCSC/CISA guidelines put incident management under
secure deployment [S10]; and if personal data was involved, Oman's
PDPL sets a notification clock that the DPO owns, reported as 72 hours
in the executive regulations [S5, VERIFY with the DPO]. The case this
template is built around is the Day 3 one: an extraction with a wrong
tag entered the knowledge base, was retrieved, and was cited as fact.
Handling it is four moves, in order: contain (quarantine the chunk),
trace (the blast-radius query from template 5), correct (re-extract
with a person), and prevent (change the rule that let it in, through
template 7). Everything below is those four moves with names on them.

**Paste from:** spec §8 (wrong answer, model down, kill switch). New
writing: the severity table, the roles, the knowledge-base runbook.

**Done when:** each severity has an owner and a clock; the
knowledge-base runbook has been walked through once, on the lab
index, with the times written in.

---

## 6.1 What counts as an incident here

| Severity | Definition | First response within | Owner |
|---|---|---|---|
| **SEV1** | A wrong output was acted on in the real world (a work order raised, a permit decision influenced, a record changed), **or** data left where template 2 says it may not go | 1 hour | |
| **SEV2** | A wrong output reached a system of record, an index, or a person outside the team, but has not (yet) been acted on. The Day 3 case is SEV2 until someone acts on the answer | 4 hours | |
| **SEV3** | A wrong output was caught by the person or the gate before it took effect. Counted, not paged; the count is a template 8 signal | next weekly review | |
| **Availability** | Model down, tool down, budget exhausted. Handled by the normal on-call playbook; the AI-specific part is only "did anything get half-written?" | as per existing playbook | |

## 6.2 Roles for the first hour

| Role | Name (and deputy) | Does |
|---|---|---|
| Incident lead (usually the owner from template 1) | | Declares severity, runs the checklist below, writes the record |
| Operator with the kill switch (template 4.8) | | Stops the system if SEV1, or if the cause is unknown |
| Data owner / DPO, if personal data | | Decides on notification; owns the 72-hour clock [S5] |
| Business owner of the affected system | | Decides what to do with the acted-on outputs (reverse, re-check, inform) |

## 6.3 The first-hour checklist (any severity)

| Step | Do | Done (time) |
|---|---|---|
| 1 | Stop the bleeding: kill switch (SEV1), or disable the write / the index insert path only (SEV2) | |
| 2 | Freeze the evidence: copy the log lines for the `trace_id`s involved; note model fingerprint, prompt version, index build id (template 7) | |
| 3 | Find the blast radius: template 5.3 query 2 for a bad chunk; query 1 for a bad output. Write down the count and the recipients | |
| 4 | Tell the recipients what was wrong and what to do (a one-line message, approved by the business owner) | |
| 5 | Decide: keep it stopped, or restart with the gate tightened (template 4) | |
| 6 | Open the incident record (6.6) | |

## 6.4 Runbook: a confidently wrong extraction is in the knowledge base

The Day 3 case, step by step. Walk it through once on the lab index
before go-live and record the minutes.

| Step | Do | Tool / query | Minutes (rehearsal) |
|---|---|---|---|
| Contain | Quarantine the chunk: `index_write` with `action: "quarantine"` so it is excluded from search but not deleted (it is evidence) | | |
| Trace | Blast-radius query (template 5.3): every answer whose `context_ids` held the `chunk_id`, and who received each | | |
| Widen | Same `produced_by` fingerprint and same `score_line` pattern: were other chunks produced the same way with an invented count above 0? Quarantine those too | | |
| Correct | Re-extract with a person checking against the source image; write the corrected chunk with `produced_by: "human"` and the approval line | | |
| Verify | Re-run the retrieval eval (golden answers, adversarial set) and the affected question by hand; the wrong tag must no longer appear | | |
| Prevent | Which rule let it in? (No invented-count rule; no approval on index writes; the confidence floor too low.) Change it through template 7 and record the new eval | | |
| Close | Incident record complete; the recipients told the corrected answer | | |

## 6.5 Other failure cases (one line each: who sees it, what they get, what is written)

| Case | Who sees it first | What the caller gets | What is logged |
|---|---|---|---|
| Model returns invalid output | | | |
| Model returns valid output that is wrong (caught at the gate) | | | |
| Approver approves a wrong action | | | |
| Injection succeeds in changing an argument (caught or not) | | | |
| Tool returns an error mid-run; partial state | | | |
| Budget (steps, tokens, money) exhausted | | | |
| Vendor outage / VM down for more than an hour | | | |

## 6.6 The incident record (one per incident, kept with the pack)

| | |
|---|---|
| Incident id, date, severity | |
| What was wrong, in one sentence, with the `item_id` / `chunk_id` | |
| Model fingerprint, prompt version, index build id at the time | |
| Blast radius: count of outputs and recipients | |
| Acted on? By whom? Reversed? | |
| Root cause: which template-4 rule or template-3 test was missing | |
| Prevention: the template 7 change, and its re-eval result | |
| Personal data involved? Notification made? (DPO) [S5] | |
| Time to contain, time to close | |

## 6.7 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Business owner | | |

Sources: [S2] NIST AI 600-1, A.1.8 incident disclosure; section 2.2
confabulation. [S10] NCSC/CISA secure AI system development, "secure
deployment: developing incident management processes". [S5] Oman PDPL
and executive regulations (breach notification; verify the clock with
the DPO). [S8] OWASP Agentic Top 10 2026, ASI06 memory and context
poisoning, ASI08 cascading failures. [S7] OWASP LLM Top 10 2025, LLM08
vector and embedding weaknesses.
