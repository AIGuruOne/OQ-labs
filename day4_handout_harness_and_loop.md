# Handout · The agent loop, and the harness around it

**OQ Advanced AI for IT · Day 4, S25.** Two pages to build from, one to fill in.
Nothing here is framework-specific, and everything here was on screen in labs 12, 13 and 14.

---

## 1. The loop

Every agent framework is this plus features. Write it once yourself before you adopt one: the
seams below are where your controls live, and a framework that hides a seam hides a control.

```python
def agent(task, tools, *, system, gate, caps, trace):
    messages = [system_message(system), user_message(task)]      # 1  context
    for step in range(caps.max_steps):                           # 2  termination
        caps.check()                                             # 3  budget
        reply = model(messages, tools=tools.schemas())           # 4  the model call
        messages += reply.output
        calls = [c for c in reply.output if c.is_tool_call]
        if not calls:
            return reply.text, trace                             # 5  the exit
        for call in calls:
            allowed, why = gate(call.name, call.args,            # 6  authority
                                tools[call.name].read_only)
            result = tools.call(call.name, call.args) if allowed else why   # 7  execution
            trace.append(step, call, allowed, result)            # 8  evidence
            messages.append(tool_result(call.id, fence(result))) # 9  observation
    return "(step cap reached)", trace
```

### The nine seams

| # | Seam | The decision it carries | Seen in | If you leave it to the framework |
|---|---|---|---|---|
| 1 | context | what is in the window, in what order, and what was dropped to fit | 12 | cost and behaviour drift with conversation length and nobody can say why |
| 2 | termination | the step cap. The only reason an agent stops when the model will not | 12, 13 | a loop with no end condition, which is an outage waiting for a Thursday |
| 3 | budget | money and wall clock, checked *before* the call that would spend them | 13 §6 | you learn the number from the invoice |
| 4 | the model call | which model, what temperature, whether the output is schema-constrained | 01, 11 | you cannot swap the model, and you find out at the upgrade |
| 5 | the exit | what "finished" means: no tool call is not the same as the job being done | 12 | success and giving up look identical in your logs |
| 6 | authority | which records, which states, how many writes, decided in a file by a person | 13 §5 | the prompt is your access control |
| 7 | execution | where the tool runs, whose credentials, timeouts, and the idempotency key | 13 §8 | the retry that writes twice |
| 8 | evidence | who asked, what was proposed, what was decided, what ran, what changed | 13 §10 | nothing to hand the auditor, and it cannot be added retrospectively |
| 9 | observation | what comes back in: truncation, and the fence that labels it as data | 14 §5 | untrusted text arrives looking exactly like your own instructions |

---

## 2. The harness

The loop is the part everyone writes. The harness is the part that decides whether you can run it
on a Tuesday against a system OQ depends on. Ten things, all of them ordinary engineering, none of
them shipped for you by a vendor.

| # | Component | What it is, concretely | Own it as |
|---|---|---|---|
| 1 | **context assembly** | the function that builds the window: system prompt, task, retrieved chunks, history, and what gets dropped first | code, tested |
| 2 | **tool surface** | the list of tools this session may call, written in *your* config, not inherited from whatever a server offers | config, version-pinned |
| 3 | **data scope** | which records the session can see at all. The store, the index, the folder, the connection | config, per session |
| 4 | **authority policy** | which writes are allowed, to what, in which states, how many | a file a person signs off |
| 5 | **caps** | steps, money, wall clock. Three caps, three places in the code | config, checked before the spend |
| 6 | **trace** | every call: who asked, proposed, decided, executed, changed | append-only, kept |
| 7 | **replay** | a saved run the system can fall back to, and that you can re-read six weeks later | files in the repo |
| 8 | **kill switch** | one variable that removes the write tools without a deploy | environment, documented |
| 9 | **eval set** | real requests with known-good outcomes, including the adversarial ones. Behaviour, not unit tests | a jsonl, run on every change |
| 10 | **idempotency** | the key that makes a repeated call safe, and the precondition that makes a stale one fail | in the tool contract |

**The test for whether you have a harness:** someone who was not in the room can re-run last
Tuesday's request, get the same trace, and say what the system was allowed to do at the time.

---

## 3. Injection: the order to build defences in

Ordered deliberately. Everything above the line holds whatever the text says; everything below it
is a rate, and rates have bad days.

1. **Write down every channel of untrusted text** the session reads. Tickets, notes, documents,
   scanned pages, email bodies, web pages, tool descriptions, memory. Most teams find more than they expected.
2. **Remove the capability.** If the session does not need to write, the write tool is not in the
   list. `SGP_DESK_READONLY=1` is stronger than any instruction, and it is cheaper.
3. **Scope the data.** The session sees the three records it is working on, not the queue. A record
   that is not there cannot be closed, copied or leaked.
4. **Scope the writes.** Which records, which states, how many, in a policy file. Refusals explain
   themselves, name the alternative, and are logged.
5. **Split the session** when it would otherwise hold all three of: untrusted content, something
   worth taking, and a way to send. Two sessions with different authority, and code on the seam.
--- everything above this line is a property; everything below is a rate ---
6. **Fence and label tool output**, and say in the system prompt that fenced content is data. Cheap,
   worth doing, and not a control.
7. **Screen the input** with a classifier if the volume justifies it. It catches the obvious ones.
8. **Alert on the shape of the traffic**: a write outside scope, a read of a record nobody asked
   about, a tool call to a third party carrying more text than the task needed.
9. **Keep an injection case in the eval set** and re-run it on every model upgrade, every prompt
   change and every new MCP server. This is how you find out that last month's defence stopped working.

Measured in S25 on the same queue, same model and same loop: undefended, the payload reached the
record on 1 of 3 runs. Under the structural controls it reached it on none of theirs — and not one
of them had to notice anything to stop it.

---

## 4. Fill this in for your capstone

Bring it to Day 5, S27.

**Untrusted text this system reads**

| Channel | Who can write to it | Does it reach the model | Fenced and labelled |
|---|---|---|---|
| | | | |

**What the session can reach**

| Records or documents in scope | Why that scope | Who set it, and where |
|---|---|---|
| | | |

**What could leave, and how**

| Outbound path (note, email, webhook, third-party tool) | Who can read the other end | Is it needed |
|---|---|---|
| | | |

**The three properties**

- Does one session hold untrusted content, valuable data and an outbound path at the same time?  yes / no
- If yes, where is the split going to be, and what is on the seam?
- Which control here is a property, and which is a rate?

**Tools this session may call** — the allowlist, in our config, with server versions pinned:

| Tool | Server and version | Read-only, verified by us | Why it is needed |
|---|---|---|---|
| | | | |
