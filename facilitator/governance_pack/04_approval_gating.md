# 4. Human-in-the-loop and approval gating policy (12 min)

**Why this exists.** The MCP specification says it plainly: there
should always be a human in the loop with the ability to deny a tool
invocation, clients should prompt for confirmation on sensitive
operations and show the tool's inputs before calling, and tool
annotations such as `readOnlyHint` and `destructiveHint` are hints
that must be treated as untrusted unless the server is trusted [S9].
That is a protocol saying what a policy should say. Day 4 S24 built
the pattern: the agent loop stops before a write, saves its state,
shows a person the proposed action with the evidence that produced
it, and resumes only on an explicit decision. Day 5 S26 put the same
gate inside the ERP MCP server: the one write tool refuses without
an approval. This template records which actions are gated, by whom,
what the approver must see, and where in the code the gate is, so
"we have a human in the loop" is a line in a file rather than a
sentence in a meeting. The EU AI Act's human-oversight article is the
most concrete public statement of what an overseer must be able to
do: understand the system's limits, resist over-relying on it,
interpret its output, decide not to use it, and stop it [S4, Art. 14].
Not law in Oman; a good checklist anywhere.

**Paste from:** spec §5 (tools: name, read or write, approval), §8
(wrong answer: who sees it; kill switch). New writing: the approver
table, the "what the approver sees" list, the gate location and its
test.

**Done when:** every write has a row with an approver role, a gate
location and a test date; the "never automated" list has at least one
line; the kill switch has a name and a time.

---

## 4.1 Action classes

| Class | Definition | Gate |
|---|---|---|
| **R** read | Reads a system, an index or a file; no side effect | None. Logged (template 5) |
| **W1** reversible write, seen by a person first | Pre-fills a form, drafts a record, proposes a queue; a person confirms or edits item by item before it takes effect | Confirmation by the user of the output |
| **W2** write to a system of record, an index, or a message to a person | Creates or changes a work order, an equipment record, a knowledge-base entry, sends a notification | **Approval interrupt** with a named approver role; decision logged with reason |
| **X** never automated | Listed explicitly; the system may draft, never execute | Not exposed as a tool at all |

## 4.2 The tool table (every tool, every write)

One row per tool the model can call, and one row per write that
happens outside a tool (e.g. "the confirmed record is written by the
desk tool"). The annotation column is what the MCP server declares;
the class column is what you decide. They must agree, and the class
wins.

| Tool or write | System | MCP annotations declared (`readOnlyHint`, `destructiveHint`, `idempotentHint`) | Class (R / W1 / W2 / X) | Approver role | Gate location (agent loop interrupt / MCP server refuses without approval / downstream form) | Tested on (date), how |
|---|---|---|---|---|---|---|
| | | | | | | |
| | | | | | | |
| | | | | | | |
| Adding an item to the index / knowledge base | | | W2 | | | |

## 4.3 What the approver sees, every time

Tick the ones the interface shows. All five are required for a W2
gate; the Day 3 case failed on the fourth.

| The approver sees | Shown? | Where (screen, message, notebook cell) |
|---|---|---|
| The exact action and its exact arguments (the JSON that will be sent, not a summary) | | |
| The evidence: the tool calls and retrieved sources that produced it, with ids (`chunk_id`, `doc_id`, ticket id) | | |
| The model and version that produced it (template 7 fingerprint) | | |
| The score line: confidence, and the **invented / uncited count** for this item; an item that invents anything is never presented as auto-acceptable | | |
| A reject button that requires a reason, and a stop button that ends the run [S4, Art. 14(4)(e)] | | |

## 4.4 Who may approve, and what approving commits them to

| Approver role | Named people (at least two, for cover) | May approve | May NOT approve | Approving means they have checked |
|---|---|---|---|---|
| | | | | |
| | | | | |

## 4.5 Never automated

> Actions the system may draft but never execute, however good the
> eval gets (e.g. closing a ticket, changing a permit, writing to the
> equipment master without a person, contacting a requester):
>

## 4.6 Batch or auto-approval

Groups will be tempted to "let it do the obvious ones" (S25). Write
the condition under which that is even discussed, or write NEVER.

| | |
|---|---|
| Condition (e.g. after N weeks of shadow, rejection rate below X% on a weekly sample of at least 100, and only class W1) | |
| Who decides, and where the decision is recorded (template 7) | |
| What is sampled weekly afterwards (template 8) | |

## 4.7 Injection and prompt-carried instructions

| | |
|---|---|
| Inputs that can carry instructions (tickets, documents, tool results, images with text) | |
| What the loop does with them (data only; never system text; tool calls validated against the class table, not the model's request) | |
| The injection test run (template 3.3), date, result | |

## 4.8 Kill switch and step budget

| | |
|---|---|
| Who can stop the system, how, in how many seconds (spec §8) | |
| Step budget and token budget per item, and what happens when hit (stops, logs, no partial write) | |
| Rate limit per caller on write tools (the MCP spec requires servers to rate-limit tool invocations [S9]) | |

## 4.9 Sign-off

| Who | Name | Date |
|---|---|---|
| Owner | | |
| Security | | |
| Business owner of the system being written to | | |

Sources: [S9] MCP specification 2026-07-28, Tools: user interaction
model, annotations, security considerations. [S4] EU AI Act Art. 14.
[S7] OWASP LLM Top 10 2025, LLM06 excessive agency. [S8] OWASP
Agentic Top 10 2026, ASI02 tool misuse, ASI03 identity and privilege
abuse, ASI09 human agent trust exploitation. [S2] NIST AI 600-1,
section 2.7 human-AI configuration.
