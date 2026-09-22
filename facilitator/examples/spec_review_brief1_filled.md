# Spec peer review — filled example (brief 1 spec, v0.1)

> `facilitator/spec_review_checklist.md` applied to
> `architecture_spec_brief1_filled.md` on 2026-09-22 by the build team,
> acting as the reviewing group, in the 25-minute clock. The answers
> below are what the checklist produced; the findings are real gaps in
> that spec. Authors of the real thing will have different gaps —
> the point is that the questions find them in 25 minutes.

Clock as run: 7 min reading, 12 min answering (finished all ten
groups with one minute spare), 4 min choosing, 2 min reading out.

## A. Is the job real? (section 1)

| # | Answer | Where |
|---|---|---|
| A1 | YES — ticket text in, seven-field record plus `valid` out | 1 |
| A2 | YES — 40 min median, 3 h after a weekend, 11% bounce-back | 1 |
| A3 | YES — the agent, within five minutes, on the pre-filled form | 1 |
| A4 | YES — the plugin and auto-routing are both things a reader assumes | 1 |

## B. Was the decision made, or assumed? (section 2)

| # | Answer | Where |
|---|---|---|
| B1 | YES — four totals, arithmetic in the matrix page | 2 |
| B2 | YES — G1 attributed to the data owner by name and date; G5 answered "partly", which is honest but is not an answer | 2 |
| B3 | YES — the DPA review completing is a this-year event | 2 |
| B4 | YES — $1,434 with 8 h × $60 of ops labour; but the ops hours are the cost model's placeholder, not the team's number | 7 |

## C. Will the data owner sign this? (section 3)

| # | Answer | Where |
|---|---|---|
| C1 | YES — internal + personal data; D is allowed for it | 3 |
| C2 | **NO** — pasted passwords: "OPEN — no mechanism yet". The intention is there, the mechanism is not | 3 |
| C3 | YES — hash, output, 90 days, platform engineering | 3, 8 |
| C4 | YES — log stores the hash, not the text. But the *output* `requested_action` is free text generated from the body; a pasted password could be echoed into it. Not addressed | 3, 8 |
| C5 | YES — 600 / 400 / 80 / 20, five named checks | 3 |

## D. Can this actually be run? (section 4)

| # | Answer | Where |
|---|---|---|
| D1 | YES — 1B, r=16, 3 epochs; 3B ruled out with a reason | 4 |
| D2 | **CAN'T TELL** — SKU, region and person are there, but the serving version is "a problem" and the fix (merge the adapter, serve on current Ollama or vLLM) is untested. As written, production runs on a pinned Ollama release that has since dropped the feature | 4 |
| D3 | YES — `get_endpoint("tuned")`, swap by `.env` | 4 |
| D4 | YES — 1,500-token cap, truncate the end, log it | 4 |
| D5 | YES — schema validated in the endpoint; `valid: false` and a blank form | 4 |
| D6 | YES — 20 s, one retry, blank form, paging rule with a number | 4 |

## E. Retrieval and tools (section 5)

| # | Answer | Where |
|---|---|---|
| E1–E3 | n/a — none | 5 |
| E4 | YES — ticket body named as untrusted, reaches the model as user content only, output is a validated record | 5 |

## F. Would you believe the quality number? (section 6)

| # | Answer | Where |
|---|---|---|
| F1 | YES — rubric named, per field | 6 |
| F2 | YES — 20, stratified, lookalike-free, enforced by a test | 6 |
| F3 | YES — four separate lines, plus per field | 6 |
| F4 | YES — routing 16/20 today against 80% target; plausible | 6 |
| F5 | **NO, and the spec knows it** — "too small for a pilot claim" is written down, and the 200-ticket shadow week is the answer. But the pilot target table already says "on 200 tickets" while every number in it is on 20 | 6, 9 |
| F6 | YES — 20 a week by the desk lead, misses become corrections | 6 |

## G. Does the money add up? (section 7)

| # | Answer | Where |
|---|---|---|
| G1 | YES — all seven | 7 |
| G2 | YES — idle 99.7% acknowledged; the reason for hosting is gate G1, stated | 2, 7 |
| G3 | YES — p95 < 5 s, measured on Day 2 S8 | 7 |
| G4 | YES — $1,600 and "a decision, not autoscaling" | 7 |

## H. What happens when it is wrong? (section 8)

| # | Answer | Where |
|---|---|---|
| H1 | YES — pre-filled, never submitted; urgency always the agent's | 8 |
| H2 | YES — twelve fields including adapter fingerprint | 8 |
| H3 | YES — webhook off, 30 seconds, two named people | 8 |
| H4 | YES — re-register the previous adapter, under five minutes, tested on Day 2 | 8 |

## I. Will it survive us leaving? (section 9)

| # | Answer | Where |
|---|---|---|
| I1 | **NO** — "in principle", manager has not agreed, no GPU experience. This is gate G5 answered "partly" and never resolved | 0, 2, 9 |
| I2 | YES — MRB desk, four agents, six weeks, four measures | 9 |
| I3 | YES — data owner, security, desk lead, the owner's manager | 9 |

## J. The manager's three questions

| # | One-line answer from the spec |
|---|---|
| J1 | $1,434 a month, almost all of it the VM and the engineer's time; saves agent minutes we have not yet measured (the shadow week measures them). Honest: at this volume a vendor would cost $5 a month, and the DPA review is what stands between us and that |
| J2 | A wrong queue or urgency pre-filled on the form — the agent sees it before it routes. Worst case we can name: a pasted password echoed into `requested_action` and stored in the log |
| J3 | Faisal, in principle. Nobody has agreed that in writing |

## Findings block

| # | Severity | Finding | Question |
|---|---|---|---|
| 1 | **BLOCKS** | There is no owner. "In principle" is not a name a manager will accept, and gate G5 was answered "partly" and carried through nine sections unresolved. Until someone whose job includes this VM says yes, this is a lab, not a deployment | I1, B2 |
| 2 | **BLOCKS** | The must-never-enter mechanism does not exist. The spec's own reason for choosing D over B is that ticket text contains pasted passwords; it then sends that text to the model unredacted and can echo it into a stored output field. The data owner will not sign section 3 as written | C2, C4 |
| 3 | **BEFORE PILOT** | The serving stack is not runnable as specified: the adapter needs an Ollama release that has since dropped adapter support. The merged-weights path is the right fix and it is untested. It must be tested before the pilot, not "on Day 5 S27" if Day 5 runs late | D2 |

Also noted, not in the top three: F5 — the pilot target table claims
200-ticket targets on 20-ticket evidence; write "target on the
200-ticket shadow week" as the column heading. B4 — the ops hours are
the cost model's placeholder; ask Faisal for his.

**The best thing about this spec:** section 8. A wrong answer cannot
reach a queue without an agent seeing it, urgency is explicitly the
agent's field because the eval says the model cannot be trusted with
it, and the model being down leaves the desk exactly where it is
today. That is what "deployment-ready" is supposed to mean, and it
should not be lost in revision.

## Timing note for the facilitator

Answering all 43 questions took 12 minutes for a spec the reviewers
had not seen before, with two people reading and one writing. A
three-person group with one reader-aloud will be slower; if groups
are not through section F by minute 15, tell them to skip to J and
do the findings — J alone finds two of the three above.
