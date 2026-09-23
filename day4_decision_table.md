# S20 · The agent stack as a decision table

**Day 4 · 09:10 to 09:35 · 25 min · Talk · Owner: Preety**

**Follows** S19, which ended with a table on screen. **Hands off to** S21, MCP.
**Artifact:** the decision table in section 3. It goes in the take-away pack and gets filled in during the capstone. Everything else in this file is how to deliver it.

---

## Why this session exists

By 09:10 the room has built four things that work: a tuned model, a retrieval pipeline, a vision extractor, and as of forty minutes ago a table that says which of the first two to reach for. Every one of those is a **single call**. Something goes in, something comes back, and a person reads it.

The rest of Day 4 is about calls that do not come back straight away: a model that looks something up in a live system, decides what to do next, and keeps going until it is finished. That is a large step, and the standard way it gets taken is badly — somebody reads that agents are the frontier, wires a loop around an LLM, and ships a system nobody can test, price or explain to an auditor.

So this session does not teach agents. It teaches **where the agent line is, and how to tell whether you have crossed it on purpose.** The stack has rungs. Each rung buys a capability and costs you determinism. The table says when to climb and, more usefully, when to stop.

There is no notebook. The labs come after: S23 builds the graph, S24 puts controls on it.

---

## Timing spine

| Min | Beat | Leaves the room with |
|---|---|---|
| 0:00 to 3:00 | From S19's table to this one | The question: same call, or more than one? |
| 3:00 to 8:00 | The seven rungs | A shared vocabulary. Workflow and agent stop being synonyms |
| 8:00 to 15:00 | The decision table, read row by row | The artifact |
| 15:00 to 19:00 | What a rung costs | Why the answer is usually "one rung lower" |
| 19:00 to 23:00 | Four questions, and when to stop climbing | A test they can run on their own capstone |
| 23:00 to 25:00 | Write it down, handoff | Three lines per group, and the question S21 answers |

Runs long? Cut the cost section to the determinism row and keep the write-down. The write-down is what makes S23 and S24 land on something they chose rather than something we assigned.

---

## 1. From S19's table to this one (3 min)

Put the S19 output back on screen. It read symptom to fix:

> Wrong shape → behaviour → constrain the decoder, tune if it persists.
> Right shape, wrong number → knowledge → retrieval.
> Right since the procedure changed → staleness → re-index.

Every fix in that table is still one call to a model. The prompt got better, the shape got constrained, the context got richer, but the architecture never changed: **request in, answer out, and a human decides what happens next.**

Say the line that opens the session:

> Everything you have built this week answers a question. Nothing you have built has done anything. Today is about the second one, and the gap between them is where most enterprise AI projects are lost.

The three things that push you off a single call, and only these three:

1. **The model needs a fact that lives in a system, not a document.** Retrieval reads your corpus. It does not know whether ticket 4471 is still open.
2. **The work has more than one step, and a later step depends on what an earlier step found.**
3. **Something has to change** — a ticket updated, a work order raised, a mail sent.

If none of those three is true, the rest of today is architecture you do not need. That is a legitimate answer and some capstones will land on it.

---

## 2. The rungs (5 min)

Seven rungs. The room already lives on the first three. Draw this once, keep it visible for the rest of the day.

| # | Rung | What it adds | Who decides what happens next | Calls per request |
|---|---|---|---|---|
| 0 | **One prompt** | nothing. The baseline | you | 1 |
| 1 | **Constrained call** — JSON schema, enum, strict decode | a shape your code can parse without a regex | you | 1 |
| 2 | **Grounded call** — retrieval in the prompt | facts the weights never had | you | 1, plus retrieval |
| 3 | **Tool call, one hop** — the model reads a live system | current state: an open ticket, a stock level, a run hour | you choose the moment, the model chooses the arguments | 2 |
| 4 | **Workflow** — several steps, fixed order, written by you | multi-step work you can draw on a whiteboard | **you**, in code | fixed and known |
| 5 | **Agent** — the model runs its own loop until done | steps you cannot draw in advance, because the branch depends on what it finds | **the model** | unbounded until you cap it |
| 6 | **Multiple agents** — sub-tasks with their own context | parallel or genuinely separate sub-problems | the model, twice over | worse than you think |

**The line is between 4 and 5, and it is one question: who decides the next step.**

A workflow is code you wrote, with model calls in it. You can read it, draw it, unit-test each branch, and predict what it will do on Monday. An agent is a loop where the model chooses the next action from a set of tools and keeps choosing until it decides it is finished. That is the whole difference. Not sophistication, not frameworks, not how many tools — **who holds control flow.**

Two corrections worth making out loud, because the room will have read otherwise:

- **A prompt chain is not an agent.** Extract, then classify, then draft: three calls in a fixed order is rung 4. It is often the right answer, and nobody should apologise for shipping it.
- **A tool is not an agent either.** One model call that reads the ticket system and answers is rung 3. Enormous value, small blast radius, a full afternoon's worth of capstone.

Rung 6 gets one sentence today: it is the right answer far less often than the writing suggests, it multiplies cost, and it makes traces unreadable. S23 will show a graph with one loop, not five agents.

---

## 3. The decision table

This is the artifact. Read it row by row — it is the seven minutes the session exists for. Each row is a thing you cannot do, the lowest rung that fixes it, and the reason not to go higher.

| What you cannot do today | Lowest rung that fixes it | Do not reach higher, because |
|---|---|---|
| Parse the output reliably | **1** constrain the decoder | A loop will not fix a shape problem. S19 settled this |
| Answer from the plant's documents | **2** retrieval | Tools are for live systems. A PDF is not a live system |
| Say whether ticket 4471 is still open | **3** one tool call, read-only | Nothing here needs a loop. One hop, you parse, you answer |
| Answer over both documents and live state | **3** two tools, one hop each | Still one hop if you know both are needed. Do not let the model discover that |
| Run the same four steps on every ticket | **4** workflow | You can draw it, so write it. An agent will rediscover your flowchart on every call, slowly, at a price |
| Branch on a classification the model makes | **4** workflow with a switch | A branch you can enumerate is an `if`, not autonomy |
| Handle a request where step three depends on what step two found, and you cannot list the cases | **5** agent | This is the real threshold. If you can list the cases, you are at rung 4 |
| Keep going until a goal is met, with an unknown number of steps | **5** agent, with a hard cap | The cap is not optional. See S24 |
| Change something in a system of record | **the rung you already need, plus a gate** | Writing is not a rung. It is a control question, and it applies at every rung |
| Handle two unrelated sub-problems that do not share context | **6** consider it, then usually do not | Try one agent with more tools first. Measure before you split |

Deliver it with three claims:

**First: climb one rung at a time, and name the failure before you build.** "We need an agent" is not a requirement. "A single grounded call cannot tell us whether the work order it cites is still open" is a requirement, and it buys you rung 3, not rung 5.

**Second: if you can draw the flowchart, build the flowchart.** This is the sentence to repeat. Most systems sold internally as agents are workflows whose authors did not want to write the switch statement. The workflow is cheaper, faster, deterministic, testable branch by branch, and it does not change its mind in production.

**Third: writing is orthogonal.** There is no rung at which a write becomes safe. A rung-3 tool that closes tickets can do more damage in an afternoon than a rung-5 agent that only reads. Separate the two questions: *how much autonomy does this need*, and *what can it touch*. They are decided independently and S24 is the second one.

---

## 4. What a rung costs (4 min)

Each rung up is paid for in four currencies, and only one of them shows up in the demo.

| Rung | Latency | Cost per request | Determinism | The new failure mode it introduces |
|---|---|---|---|---|
| 1 constrained | unchanged | unchanged | high | valid shape, invented contents |
| 2 grounded | plus retrieval, plus a longer prompt | plus the passages, every call | high | the wrong passage, confidently used. Retrieval always returns something |
| 3 one tool hop | roughly double | roughly double | high | wrong arguments, and a tool error the prompt never mentioned |
| 4 workflow | the sum of its steps | the sum of its steps | **still high** | a bad step-two output carried silently into step five |
| 5 agent | unpredictable by construction | unpredictable by construction | **low** | loops, repetition, a run that costs 40x the median and nobody notices until the invoice |
| 6 multi-agent | worse | several times worse | lowest | context lost between agents, duplicated work, a trace nobody can review |

Two things to land:

**Determinism falls off a cliff between 4 and 5, and that is the cliff that matters to your auditor.** A workflow that failed can be replayed. An agent run is a path through a space you did not enumerate; reproducing it needs the whole trace, which means you must have stored the whole trace. That is a logging requirement you inherit the moment you cross the line, and it is why S24 exists.

**The median is not the problem. The tail is.** Agent runs have a long tail — the run that takes 60 steps instead of 6. Price rung 5 at its p95, not its average, or the pilot looks affordable and the rollout does not.

---

## 5. Four questions, and when to stop (4 min)

Four questions to run over any capstone design. They take a minute each and they settle most arguments.

**1. Can I draw the flowchart?**
Yes → rung 4. Write it. No, because the branches depend on what is found and I cannot list them → rung 5.

**2. Does it need to act, or only to answer?**
Only answer → nothing writes, and the review burden drops by an order of magnitude. Act → the gate question, and S24.

**3. If it is wrong, who finds out and when?**
A person reading the answer, immediately → you can afford more autonomy. A system three weeks later, at an audit → you can afford much less. This question, not the technology, sets your rung ceiling.

**4. How does it know it is finished?**
If the only answer is "the model says so", you have no termination condition. Every rung-5 design needs three caps written down before it is built: **steps, money, wall clock.** An agent without a cap is not a design, it is an outage waiting for a Thursday.

### Stop climbing when

- The rung below has not actually failed, only felt unsophisticated.
- You cannot describe the new failure mode you are taking on.
- There is no end-to-end eval. At rung 4 and above, unit tests on each step tell you nothing about the system; you need a set of real requests with known-good outcomes, or you cannot distinguish a regression from a bad day. This is the same discipline as the adversarial set from Day 3, applied to behaviour instead of retrieval.
- Nothing logs the trace.
- The thing it would write to has no undo.

---

## 6. Write it down (2 min)

Before the break, each group writes three lines. They come back to these in S23, and again at the Day 4 close when the integration mapping worksheet asks for them.

1. **The rung our capstone needs**, as a number.
2. **The failure of the rung below that justifies it**, in one sentence, concrete.
3. **The thing that would make us climb down a rung.**

Third line is the one that matters. A group that cannot write it has not made a decision, it has made a purchase.

---

## Handoff to S21

Rung 3 and above need tools, and a tool is not a clever prompt — it is a real connection to a real system, with auth, a schema, errors, rate limits and an owner. Every one of the five capstone use cases will want three or four.

The question S20 leaves open and S21 answers:

> You need a model to read your ticket system, your ERP and your document store. That is three integrations, per project, per framework, maintained by you forever. What if the connection were a protocol instead?

That is MCP. Straight into S21.

---

## What to take away

- **The stack is rungs, not a leap.** Constrained, grounded, one tool hop, workflow, agent, multi-agent. Name your rung. "We're building an agent" is not an architecture.
- **The line between workflow and agent is who decides the next step.** If you can draw the flowchart, write the flowchart. Most shipped agents should have been workflows.
- **Climb for a named failure.** One rung at a time, and say out loud what the rung below could not do.
- **Determinism is the currency you spend.** It falls off a cliff at rung 5, it is what your auditor asks about, and it is what makes an incident reproducible.
- **Autonomy and authority are separate decisions.** How many steps it takes on its own, and what it is allowed to change. Deciding them together is how a demo becomes an incident.
- **Every rung-5 design carries three caps and a trace.** Steps, money, wall clock, and a log you could hand to someone else on Monday.

---

## Facilitator notes

**Cut order if the clock slips.** Section 4 to just the determinism row. Then section 5 to questions 1 and 4. Never cut the decision table or the write-down — they are what S23, S24 and the close all build on.

**Questions this reliably draws:**

- *"Which framework?"* Not this session. The table is framework-neutral on purpose and every row survives a framework change. S23 picks one and says why.
- *"Isn't everyone shipping agents?"* Everyone is shipping the word. Ask what decides the next step in the system being described; roughly half the time the honest answer is rung 4, and the room works this out faster than we can tell them.
- *"Can we start at rung 5 and simplify later?"* You can, and nobody ever does, because by the time it works nobody wants to touch it. Simplification is a project that gets scheduled after the project that never finishes.
- *"How many tools is too many for one agent?"* Symptom, not a number: when the model starts picking the wrong tool, you have either too many or badly named ones. Fix the descriptions before splitting the agent.
- *"Where does the tuned model from Day 2 sit?"* Orthogonal again — rungs describe control flow, tuning describes the model at each node. A tuned model at rung 4 is a common and good answer.

**The one slide that carries the session** is the seven-rung table from section 2, with the line drawn between 4 and 5. If only one image survives to the deck, that is it.

**Adapt to the room.** Swap the examples in section 3 for the actual capstone briefs once they are settled — the rows are written generically here so they hold whichever five land, but the session is markedly better when row four names a group's own use case back at them.
