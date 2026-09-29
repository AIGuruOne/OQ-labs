# OQ Vision — what a model does when it cannot quite read the page

```bash
uvicorn apps.oq_vision.main:app --port 8300      # then open http://127.0.0.1:8300
```

**One hosted API key. No GPU, no Ollama, no local model, no new dependency.** The three
photographs are pre-rendered and committed, so the app imports no Pillow either.

## The demo, in three clicks

Select **Poor photo**, then press the buttons left to right.

1. **Just read it** — five of six fields come back **wrong**, with no error. `PTW-48213`
   returns as `PTW-48715`: same prefix, same length, different number. Valid JSON,
   right shapes, no warning, no confidence score. Everything a normal pipeline checks
   would pass.
2. **"Say NOT_LEGIBLE if unsure"** — the fix everybody writes first. It reads as
   careful and it **changes nothing**: still five of six wrong. This is the most
   useful click in the demo. A polite instruction is not a control.
3. **Assume you cannot** — refusal becomes the default and identifiers are named as
   the highest risk. Now six of six come back `NOT_LEGIBLE`.

Then select **Clean scan** and press **Assume you cannot** again: all six still read
correctly. The strict prompt has not just become a refuse-everything machine.

## Measured, not asserted

gpt-4.1-mini, temperature 0, three runs each on the poor photograph:

| prompt | refused | wrong |
|---|---|---|
| plain | 0 | 5 |
| "say NOT_LEGIBLE if unsure" | 0 | 5 |
| "assume you cannot read" | 6 | 0 |

Stable across all three runs in both directions. Also measured: **gpt-4o-mini refuses
far less reliably** — it still guessed four of six under the strict prompt. Set
`OQ_VISION_MODEL=gpt-4o-mini` to show that, and the lesson gets harder: the prompt fix
is model-dependent.

## What it is for

Notebooks 08, 09 and 10 teach vision with two model arms and a scoring harness, and
most of their cells are machinery. This is the same lesson with the machinery removed,
for a room that does not do computer vision and should not have to.

`notebooks/08a_vision_basics.ipynb` is the same demo as a 15-minute notebook, for
people to run themselves afterwards.

## Files

| Path | What it is |
|---|---|
| `forms.py` | draws the work order and the three photographs. Needs Pillow; run once with `python -m apps.oq_vision.forms` |
| `main.py` | FastAPI: `/read`, `/health`. No Pillow at runtime |
| `static/level_*.jpg` | the three photographs, committed so the demo is byte-identical every time |
| `static/index.html` | the page. One file, no build step, no CDN |
