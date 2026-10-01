# OQ Agent — one job, run two ways

```bash
uvicorn apps.oq_agent.main:app --port 8400     # then open http://127.0.0.1:8400
```

One hosted API key. **No GPU, no Ollama, no local model, no new dependency.**

## Why it exists

Two things land as jargon with an IT room, and the second one is worse:

1. "Nodes and edges" is a word for a picture nobody has seen yet.
2. **People believe the model calls the tool itself.** They picture it reaching out
   and sending the invite. Until that is fixed, every sentence about gates, approvals
   and audit is being heard by someone who thinks the model is the one acting.

So the page answers "who did that?" before it answers anything else. One sentence,
across the top:

> The model never runs a tool. It reads text and writes text. When it "calls a tool"
> it writes text **naming** one. Your program reads that text, decides whether to
> obey, and runs the function itself.

The job is a picnic on purpose. Nobody argues about a picnic, so the argument stays on
the mechanism.

## The picture: two columns and a line

Every step lands in one of two columns, and there are three actors:

| | | |
|---|---|---|
| **person** | left column | starts it, and says yes or no. Nothing here starts itself. |
| **your program** | left column | runs every function. **The only actor that touches the world.** |
| **the model** | right column | reads text, writes text. Runs nothing, ever. |

The line down the middle is labelled **ONLY TEXT CROSSES THIS LINE**, and it stays on
screen while you scroll. Each model box shows the literal text that came back, so the
room can see that a "tool call" is this:

```json
{"tool_calls": [
  {"function": {"name": "send_invite", "arguments": "{\"date\":\"2026-10-10\", ...}"}}
]}
```

That is all the model did. Note that `arguments` is a **string** — characters someone
still has to parse before anything can happen.

Every tool call is therefore **two steps**, never one:

| step | column | what |
|---|---|---|
| n | right | the model **asks for** `send_invite`, in text |
| n+1 | left | your program **runs** `send_invite`, and the invite goes out |

Collapsing those two into a single row labelled "model: send_invite" is exactly what
made the room believe the model acts. Do not do it on a slide either.

## The demo, in five clicks

1. **Run it plain.** The invite is sent. Nobody was asked. Ask the room to *point at
   the step where it was sent* — it is in the left column, and it is your code.
2. **Untick "run what the model asks for" and run it plain again.** The model asks for
   exactly the same things. Nothing runs. Your program just skipped them. The model's
   final answer says it "couldn't access" the data: it cannot tell a refusal from a
   failure, because both come back as text.
3. **Run it with a gate.** Count the boxes in the model's column: one. It stops before
   the write and shows the exact call.
4. **Approve.** A person step appears, then your program runs it.
5. Tick **break the forecast** and run each again: the plain loop gives up sensibly
   (current models do), and the gated one stops at a rule you wrote.

## The tally under every run

| | person | your program | the model | functions run **by the model** |
|---|---|---|---|---|
| plain | 1 | 6 | 3 (all text) | **0** of 3 |
| plain, not obeying | 1 | 4 | 2 (all text) | **0** of 0 |
| gated, then approved | 2 | 5 | 1 (all text) | **0** of 3 |

(Read off live runs, `gpt-4.1-mini`, 2026-10-01. The model's step count can vary by one
if it asks for the two read tools in separate turns.)

The last column is zero in every row of every run, and it always will be. That is the
point. The middle inversion — 3 model boxes down to 1 — is the second point:

> The model is still doing the thinking. It is doing it in **one** place instead of
> three, and you chose which one.

Draw those boxes on a whiteboard afterwards, put the gate before the write, and say:
*that drawing is what people mean by a graph.* The word arrives after the need for it,
not before.

## Measured, not assumed

`gpt-4.1-mini`, temperature 0, 2026-09-30:

- **Happy path, three identical runs: the invite was sent every time, nobody asked.**
  Same call order all three times.
- **Forecast broken: the plain loop did NOT spin.** It retried twice, stopped on its
  own and explained itself. If you have seen a demo claiming a plain loop loops
  forever on a failing tool, it does not, with this model. The danger is not that it
  misbehaves - it is that it behaved perfectly and you had no way to know it would.
- The model also passed `"date": "2024-10-10"` to both read tools while answering about
  2026 (it has also said 2023). Nothing caught it, because nothing was checking. Worth
  pointing at — and note which column that wrong value was *used* in.
- **Declining to obey, three runs:** the model asked for the same tools, nothing ran,
  nothing was sent, and its closing answer blamed the data being unavailable. It has
  no way to tell "your program refused" from "the service was down".

## Files

| Path | What it is |
|---|---|
| `agent.py` | three mock tools, the plain loop, the gated version. Every step records its actor |
| `main.py` | FastAPI: `/run`, `/decide`, `/reset`, `/health` |
| `static/index.html` | the page. One file, no build step, no CDN |

Nothing here touches a real calendar, mail or network service. The three tools are
dictionaries.
