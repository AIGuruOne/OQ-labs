# OQ Agent — one job, run two ways

```bash
uvicorn apps.oq_agent.main:app --port 8400     # then open http://127.0.0.1:8400
```

One hosted API key. **No GPU, no Ollama, no local model, no new dependency.**

## Why it exists

"Nodes and edges" lands as jargon with an IT room. This shows the thing before naming
it: the same job run twice, once as a plain loop and once with the order written down
and the one dangerous step held for a person.

The job is a picnic on purpose. Nobody argues about a picnic, so the argument stays on
the mechanism.

## The demo, in four clicks

1. **Run it plain.** The invite is sent. Nobody was asked.
2. **Run it plain again.** Same order, same send. Then ask the room: *which of those
   three calls did you decide?* The answer is none.
3. **Run it with a gate.** It stops before the write and shows the exact call.
4. **Approve.** Now it sends.

Then tick **break the forecast** and run each again: the plain loop gives up sensibly
(current models do), and the gated one stops at a rule you wrote.

## The two numbers that are the lesson

The header of each run counts who decided each step:

| | decided by the model | decided by code |
|---|---|---|
| plain | **4** | 0 |
| gated | **1** | 3 |

That inversion is the point, and it is the sentence to say out loud:

> The model is still doing the thinking. It is doing it in **one** place instead of
> four, and you chose which one.

Draw those four boxes on a whiteboard afterwards, put the gate before the third, and
say: *that drawing is what people mean by a graph.* The word arrives after the need
for it, not before.

## Measured, not assumed

`gpt-4.1-mini`, temperature 0, 2026-09-30:

- **Happy path, three identical runs: the invite was sent every time, nobody asked.**
  Same call order all three times.
- **Forecast broken: the plain loop did NOT spin.** It retried twice, stopped on its
  own and explained itself. If you have seen a demo claiming a plain loop loops
  forever on a failing tool, it does not, with this model. The danger is not that it
  misbehaves - it is that it behaved perfectly and you had no way to know it would.
- The model also passed `"date": "2024-10-10"` to both read tools while answering about
  2026. Nothing caught it, because nothing was checking. Worth pointing at.

## Files

| Path | What it is |
|---|---|
| `agent.py` | three mock tools, the plain loop (26 lines), the gated version |
| `main.py` | FastAPI: `/run`, `/decide`, `/reset`, `/health` |
| `static/index.html` | the page. One file, no build step, no CDN |

Nothing here touches a real calendar, mail or network service. The three tools are
dictionaries.
