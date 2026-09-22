# Build, buy or host — decision matrix (Day 1 S3)

**Time:** the S3 talk is 35 minutes. Budget 12 of them for filling this
in for your capstone use case, at the table, in pencil. You will
revise the cost row in S4 with real numbers from the cost model, and
the quality row on Day 2 and Day 4 with real eval numbers.

**Output:** one page a manager can read in three minutes: the gates,
the scored table, the choice, and the sentence that says what would
flip it.

---

## Step 0 — the gates (2 minutes)

Answer before scoring anything. A "no" removes options; it does not
lower a score. Scores cannot buy back a failed gate.

| Gate | Question | If NO, remove |
|---|---|---|
| G1 | May this data be processed by a vendor at all, under a data processing agreement, even inside your own cloud tenant? | A and B |
| G2 | May this data leave the country / your cloud region? | A; and B unless the vendor offers a regional or data-zone deployment you have confirmed |
| G3 | Can the system reach the internet or the vendor endpoint from where it will run? | A, B |
| G4 | Is there measured evidence that a small open-weights model reaches the quality bar (or can, with tuning)? | C and D until you have the evidence — Day 2 S12 produces it |
| G5 | Is there a team that will patch, monitor and be on call for a GPU VM after the week? | C, D |

Write the answers down with who said so. "The data owner said yes on
2026-09-27" is a fact. "Probably fine" is not.

## The four options

| | Option | What it means in practice |
|---|---|---|
| **A** | **Buy, direct** | A vendor API key (OpenAI, Anthropic, Google). Fastest. Data goes to the vendor under their DPA, routed globally unless you pay for a region |
| **B** | **Buy, through your tenant** | The same models inside your cloud subscription: Azure OpenAI (Global, Data Zone or Regional), Claude in Microsoft Foundry, Bedrock. Same tokens prices or slightly more; your IAM, your network, your invoice |
| **C** | **Host, as-is** | An open-weights model (Llama, Qwen, Mistral) on a VM you control, served by Ollama or vLLM behind the same OpenAI-compatible API. Nothing leaves the VM |
| **D** | **Host, fine-tuned** | C plus an adapter you trained on your own examples — the Day 2 lab. The model learns your format and your house conventions. You now own a model, not just a server |

"Build from scratch" is not an option in this room. Nobody here trains
a foundation model, and the week does not pretend otherwise.

## The criteria and how to score them

Score each option 1, 3 or 5 (2 and 4 if you must). The guidance says
what each score means so two groups scoring the same case land close.
Weights must add to 100; the defaults suit an internal IT integration
and you should change them, out loud, for your case.

| # | Criterion | Weight | Score 1 | Score 3 | Score 5 |
|---|---|---|---|---|---|
| 1 | **Data residency and classification** — where the prompt text and outputs physically go | 20 | Leaves the country to a vendor's global pool | Stays with a vendor in a region or data zone you chose, under a DPA | Never leaves a VM in your subscription |
| 2 | **Quality evidence** — measured on your eval set, not on a demo | 20 | No measurement, or measured and fails the bar | Measured on 20+ items, passes format, misses on content | Measured, passes both, and the misses are understood |
| 3 | **Cost at 12 months** — from the cost model, including people | 10 | More than 5× the cheapest viable option | Within 2× | The cheapest viable option |
| 4 | **Latency and availability** — against the use case's real need | 10 | Depends on a path you do not control and the use case is interactive | Acceptable; a vendor outage or a VM patch stops the service for an hour | Meets the need with a fallback you tested |
| 5 | **Operational ownership** — who runs it on 2 January | 15 | Needs skills nobody in the team has and nobody is hiring | The team can run it with a runbook and some learning | Nothing to run, or the team already runs this kind of thing |
| 6 | **Integration fit** — IAM, network, logging, the tools it must talk to | 10 | Needs a new network path, a new identity, a new log pipeline | Fits with one of those changed | Drops into what exists |
| 7 | **Lock-in and exit** — cost of moving to another model in a year | 5 | Prompts, formats and evals would all need redoing | A week of work | Swap the endpoint, rerun the eval |
| 8 | **Time to first value** — a pilot in front of a real user | 10 | Months (procurement, GPU quota, training) | Weeks | Days |

Notes for scoring honestly:

- Criterion 2 is where groups cheat. Score it 1 until you have a
  number from `run_eval.py` or a comparable measurement. The week
  gives you one on Day 2 (S12) and Day 4 (S19).
- Criterion 5: fine-tuning adds retraining to the ops list. Every time
  the queue list or the schema changes, someone rebuilds the dataset
  and retrains. Score D lower than C on this row unless that someone
  exists.
- Criterion 3 comes from `facilitator/cost_model.xlsx`, with the ops
  labour line filled in. A cost row with no people in it is wrong.

## The scoring table

Copy this, fill it in, keep the arithmetic visible.

| # | Criterion | Weight | A direct | B tenant | C host | D host+tune |
|---|---|---|---|---|---|---|
| 1 | Data residency | | | | | |
| 2 | Quality evidence | | | | | |
| 3 | Cost at 12 months | | | | | |
| 4 | Latency and availability | | | | | |
| 5 | Operational ownership | | | | | |
| 6 | Integration fit | | | | | |
| 7 | Lock-in and exit | | | | | |
| 8 | Time to first value | | | | | |
| | **Weighted total** (Σ weight × score) | 100 | | | | |
| | **Removed by a gate?** | | | | | |

## Defending it (the part the manager reads)

Five sentences, in this order:

1. **The choice:** "We chose B, buy through the tenant."
2. **The gates:** "Nothing was removed; the data owner confirmed
   internal ticket text may be processed inside our Azure subscription
   with a data-zone deployment."
3. **What decided it:** "Residency and ops ownership. A vendor in our
   tenant scores 4 on residency and 5 on ops; hosting scores 5 and 2."
4. **What it cost to not choose the runner-up:** "A scored 50 points
   lower only on residency; C and D lost 100+ points on quality
   evidence and ops."
5. **What would flip it:** "If the data owner withdraws consent for
   any vendor processing, D wins by 5 points and we need a named
   owner for the VM before we start."

If you cannot write sentence 5, you have not understood your own
table.

---

## Worked example — the service desk ticket triage (use case brief 1)

**Scenario (invented).** An IT service desk at a seven-site company
takes about 300 tickets a working day by portal, email and phone. A
desk agent reads each one and fills in seven fields (category, system,
asset, urgency, impact, requested action, queue) before it is routed.
Median time to first triage is 40 minutes; on Sunday mornings it is
three hours. The use case: a model proposes the seven-field record
from the ticket text; an agent confirms or corrects; the ticket routes.
Ticket text contains employee first names, internal system names,
occasionally a pasted password, and is classified *internal*.

**Gates.**

| Gate | Answer | Source |
|---|---|---|
| G1 vendor processing at all | Yes, inside our tenant, under the existing cloud DPA | data owner (invented), 2026-09-27 |
| G2 may leave the region | No — must stay in a region or data zone we chose | same |
| G3 reach the endpoint | Yes; the desk tool runs in the same subscription | integration architect |
| G4 small-model evidence | Yes, from this week: tuned 1B on the held-out 20 is 20/20 schema-valid, routing 16/20, requested action 16/20, whole record 4/20; untuned 1B is routing 7/20, whole record 2/20; gpt-4o-mini class hosted model was 20/20 schema, whole record 6/20 | `checkpoints/adapter_prebaked/README.md`, `facilitator/prebaked_outputs/eval/` |
| G5 someone to run a VM | One platform engineer, part-time, no GPU experience | team lead |

G2 removes A (direct, global routing). Nothing else removed. B stays
because a data-zone deployment exists for the model family; it must
be confirmed for the specific model before go-live.

**Scores.** Weights as default.

| # | Criterion | W | A direct | B tenant | C host | D host+tune | Why |
|---|---|---|---|---|---|---|---|
| 1 | Data residency | 20 | 2 | 4 | 5 | 5 | A is global routing; B is a data zone we chose; C/D never leave the VM |
| 2 | Quality evidence | 20 | 4 | 4 | 1 | 3 | Hosted models: 20/20 format, 6/20 whole record. Untuned 1B copies the prompt's example asset tag into every ticket. Tuned: house conventions learned (routing 16/20) but whole record still 4/20 and urgency 7/20 |
| 3 | Cost at 12 months | 10 | 5 | 5 | 2 | 2 | Cost model A: $28–$65 a year on the API; $17,233 self-hosted, a third of it people |
| 4 | Latency and availability | 10 | 3 | 4 | 3 | 3 | Triage is asynchronous, so all pass; A adds an internet dependency; one VM is down when it patches |
| 5 | Operational ownership | 15 | 5 | 5 | 2 | 1 | D adds retraining whenever a queue is renamed |
| 6 | Integration fit | 10 | 4 | 5 | 4 | 4 | All speak the same `/v1/chat/completions`; B shares IAM and network with the desk tool |
| 7 | Lock-in and exit | 5 | 3 | 3 | 5 | 4 | The adapter is tied to one base model version (Ollama 0.34 dropped adapter support this month, which is what lock-in to a serving stack looks like) |
| 8 | Time to first value | 10 | 5 | 4 | 3 | 2 | B needs a tenant deployment approved; D needs a labelled set and a retrain cycle |
| | **Weighted total** | 100 | **380** | **430** | **295** | **305** | |
| | Removed by a gate? | | **yes, G2** | no | no | no | |

Arithmetic for B, so it can be checked: 4×20 + 4×20 + 5×10 + 4×10 +
5×15 + 5×10 + 3×5 + 4×10 = 80 + 80 + 50 + 40 + 75 + 50 + 15 + 40 = 430.

**The five sentences.**

1. We chose **B: buy through the tenant** — the same model family,
   deployed in our Azure subscription in a data zone we pick.
2. Gate G2 removed the direct vendor key: ticket text may not be
   routed globally. Nothing else was removed.
3. Residency and ownership decided it. In our tenant the data stays in
   a region we chose and there is nothing for us to patch; hosting
   scores better on residency but costs us an owner we do not have.
4. Hosting lost mainly on quality evidence and ops: the tuned small
   model learns our routing conventions well (16/20) but is still
   wrong on the whole record four times in five, and a GPU VM plus
   retraining is a job nobody has.
5. **What flips it:** if the data owner rules that ticket text may not
   be processed by any vendor (G1 = no), A and B fall away and D wins
   over C on the quality row — provided the platform engineer is
   named as owner and the Day 2 eval numbers hold on 200 tickets, not
   20. Even without G1 failing, reweighting for a stricter data
   owner (residency 30, ops 10, time to value 5, vendor options
   scored 1 on residency because no in-country deployment exists for
   the model) puts D ahead of B, 340 to 335 — that is how close it is.

**What the capstone group does with this.** Builds D anyway — that is
the lab — and reports it as the residency-driven alternative, with
its eval numbers beside B's. A spec that shows both, and says which
gate chooses between them, is a deployable spec. One that hides the
cheaper option is not.
