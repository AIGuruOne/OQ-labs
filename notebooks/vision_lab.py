"""Helpers for the vision labs 08a and 09a.

Everything mechanical lives here so the notebooks stay at one idea per cell:
drawing the work orders, photographing them, calling the model, and counting.
A participant never needs to read this file - but nothing here is hidden either,
and every number a notebook prints comes from a function you can open.

Synthetic throughout: invented equipment tags, site codes and permit numbers,
using the same systems as the ticket corpus. No real OQ material.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from dataclasses import dataclass

# ---------------------------------------------------------------- the forms

FIELDS = [("Work order", "work_order"), ("Equipment", "equipment"), ("Site", "site"),
          ("Permit", "permit"), ("Discipline", "discipline"), ("Sign-off date", "signoff_date")]
FIELD_KEYS = [k for _, k in FIELDS]

SITES = ["MRB", "SHZ", "KTF", "TMQ", "WQR"]
DISCIPLINES = ["Mechanical", "Electrical", "Instrument", "Rotating"]


def form_truth(n: int) -> dict:
    """What is printed on form n. Deterministic, so the answer key never moves."""
    return {
        "work_order": f"WO-11{8300 + n * 37:04d}",
        "equipment": f"P-1{200 + n * 13}{'AB'[n % 2]}",
        "site": SITES[n % len(SITES)],
        "permit": f"PTW-{48200 + n * 411:05d}",
        "discipline": DISCIPLINES[n % len(DISCIPLINES)],
        "signoff_date": f"2026-0{8 + n % 2}-{(n * 3) % 27 + 1:02d}",
    }


def _font(size: int):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_form(truth: dict):
    """Draw one maintenance work order as a clean page."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (840, 560), "white")
    d = ImageDraw.Draw(im)
    d.text((40, 28), "MAINTENANCE WORK ORDER", fill="black", font=_font(26))
    d.line((40, 66, 800, 66), fill="black", width=3)
    y = 96
    for label, key in FIELDS:
        d.text((44, y), label, fill="#333333", font=_font(19))
        d.line((250, y + 26, 560, y + 26), fill="#999999", width=1)
        d.text((256, y), truth[key], fill="black", font=_font(19))
        y += 46
    d.text((44, y + 16), "READINGS", fill="#333333", font=_font(19))
    y += 48
    for x, c in zip([44, 240, 420, 600], ["Point", "Before", "After", "Unit"]):
        d.text((x, y), c, fill="#333333", font=_font(16))
    y += 24
    for point, before, after in [("TP-1", "4.6", "2.1"), ("TP-2", "5.2", "2.4")]:
        d.line((40, y - 4, 800, y - 4), fill="#cccccc", width=1)
        for x, v in zip([44, 240, 420, 600], [point, before, after, "mm/s"]):
            d.text((x, y), v, fill="black", font=_font(16))
        y += 28
    return im


# How a page degrades between a scanner and a phone in a dim plant room.
# Measured 2026-09-30 with gpt-4.1-mini: "clean" and "decent" are read perfectly,
# "poor" is where it starts returning confident wrong values.
PHOTO_LEVELS = {
    "clean":  dict(blur=0.0, scale=1.00, quality=92, note="flatbed scanner, straight on"),
    "decent": dict(blur=1.0, scale=0.60, quality=60, note="phone photo in good light"),
    # measured 2026-09-30, ten forms, plain prompt, gpt-4.1-mini:
    #   decent -> 11 of 60 wrong   field -> 31 of 60   poor -> 51 of 60
    "poor":   dict(blur=1.6, scale=0.45, quality=40, note="phone photo, dim, held too far back"),
    "field":  dict(blur=1.3, scale=0.52, quality=50, note="a normal photo from the field"),
}


def photograph(image, level: str = "clean") -> bytes:
    """Make a drawn page look like a photograph of a printout. Returns JPEG bytes."""
    from PIL import ImageFilter
    spec = PHOTO_LEVELS[level]
    im = image.convert("L")
    if spec["scale"] != 1.0:
        im = im.resize((int(im.width * spec["scale"]), int(im.height * spec["scale"])))
    if spec["blur"]:
        im = im.filter(ImageFilter.GaussianBlur(spec["blur"]))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=spec["quality"])
    return buf.getvalue()


def make_forms(n: int = 10, level: str = "decent") -> tuple[list[bytes], list[dict]]:
    """n photographed work orders, and the answer key for each.

    "decent" is the default because it is the honest case: a phone photo taken in
    good light, the kind anyone would send without apologising for it. Measured
    2026-09-30 over ten forms with gpt-4.1-mini and the plain prompt, it still gets
    11 of 60 fields wrong - and almost all of them are identifiers.
    """
    truths = [form_truth(i) for i in range(n)]
    images = [photograph(draw_form(t), level) for t in truths]
    return images, truths


def show(jpeg_bytes: bytes):
    """Display a photograph in the notebook."""
    from PIL import Image
    return Image.open(io.BytesIO(jpeg_bytes))


# ---------------------------------------------------------------- the model

MODEL = os.environ.get("OQ_VISION_MODEL", "gpt-4.1-mini")
KEYS = ", ".join(FIELD_KEYS)

# The three prompts from lab 08a, kept here so 09a uses exactly the one 08a landed on.
PROMPTS = {
    "plain": f"Read this maintenance work order and return ONLY JSON with exactly these keys: {KEYS}.",
    "soft": (f"Read this maintenance work order and return ONLY JSON with exactly these keys: {KEYS}.\n"
             "Only report a value you can actually READ in the image, character by character.\n"
             'If a value is blurred, cut off, or you are guessing any character, write "NOT_LEGIBLE".\n'
             "A wrong value is far worse than NOT_LEGIBLE."),
    # This exact wording was measured on 2026-09-30, three runs: it refused all six
    # fields on a poor photograph every time, and still read all six correctly on a
    # clean scan. Rule 1 is the one that does the work - without it the model tries.
    "careful": ("You are transcribing a photograph of a maintenance work order.\n\n"
                f"Return ONLY JSON with exactly these keys: {KEYS}.\n\n"
                "RULES:\n"
                "1. This photograph is low resolution. Assume you CANNOT read most of it.\n"
                "2. For each field ask: can I make out every single character with certainty?\n"
                '3. If the answer is no for ANY character, the value is exactly "NOT_LEGIBLE".\n'
                "4. Identifiers (work order, equipment tag, permit, dates) are the ones to be\n"
                "   strictest about: a plausible-looking wrong identifier is the worst output.\n"
                '5. Never reconstruct a value from its expected format. "It looks like a permit\n'
                '   number" is not reading it. When in doubt, "NOT_LEGIBLE".'),
}


def _client():
    from openai import OpenAI
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(timeout=120, default_headers={"Accept-Encoding": "gzip"})


def read_form(jpeg_bytes: bytes, prompt: str | None = None) -> dict:
    """Ask the model to read one form. Returns the JSON it produced."""
    text = PROMPTS.get(prompt or "plain", prompt or PROMPTS["plain"])
    b64 = base64.b64encode(jpeg_bytes).decode()
    reply = _client().chat.completions.create(
        model=MODEL, temperature=0, max_tokens=400,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]
    ).choices[0].message.content
    match = re.search(r"\{.*\}", reply, re.S)
    return json.loads(match.group()) if match else {}


def read_all(images: list[bytes], prompt: str | None = None) -> list[dict]:
    """Read every form. One model call each, in order, so the cost is obvious."""
    return [read_form(img, prompt) for img in images]


# ---------------------------------------------------------------- counting

def _value(answer: dict, key: str) -> str:
    return str(answer.get(key, "")).strip()


def is_wrong(answer: dict, truth: dict, key: str) -> bool:
    """Wrong means a value that is neither correct nor an admission of not knowing.

    Case and surrounding space are ignored: a model writing "instrument" where the
    form says "Instrument" has read the form correctly, and counting that as an error
    would bury the ones that matter - a permit number with a digit missing.
    """
    got = _value(answer, key)
    if "NOT_LEGIBLE" in got.upper():
        return False                      # refusing is not being wrong
    return got.casefold() != truth[key].casefold()


def count_wrong(answers: list[dict], truths: list[dict]) -> str:
    total = len(answers) * len(FIELD_KEYS)
    wrong = sum(is_wrong(a, t, k) for a, t in zip(answers, truths) for k in FIELD_KEYS)
    refused = sum("NOT_LEGIBLE" in _value(a, k).upper()
                  for a in answers for k in FIELD_KEYS)
    line = f"{wrong} of {total} fields wrong"
    if refused:
        line += f", {refused} refused as NOT_LEGIBLE"
    return line


def by_field(answers: list[dict], truths: list[dict]) -> str:
    """Which fields go wrong, worst first. Errors are never spread evenly."""
    counts = {k: sum(is_wrong(a, t, k) for a, t in zip(answers, truths)) for k in FIELD_KEYS}
    width = max(len(k) for k in FIELD_KEYS)
    lines = [f"{'field'.ljust(width)}  wrong  of {len(answers)}"]
    for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        bar = "#" * n
        lines.append(f"{key.ljust(width)}  {n:>5}  {bar}")
    return "\n".join(lines)


def cost(checked_by_a_person: list[str], answers: list[dict], truths: list[dict]) -> str:
    """What your rule costs, and what it still lets through.

    The second number is the one that matters: a rule that routes some fields to a
    person always leaves the rest unchecked, and some of those are wrong.
    """
    unknown = [k for k in checked_by_a_person if k not in FIELD_KEYS]
    if unknown:
        return f"not a field on this form: {unknown}. Choose from {FIELD_KEYS}"
    n_forms, n_fields = len(answers), len(FIELD_KEYS)
    reviewed = len(checked_by_a_person) * n_forms
    total = n_forms * n_fields
    leaked = [(i, k) for i, (a, t) in enumerate(zip(answers, truths))
              for k in FIELD_KEYS if k not in checked_by_a_person and is_wrong(a, t, k)]
    out = [f"{reviewed} of {total} fields go to a person  ({reviewed / total:.0%})",
           f"{total - reviewed} go straight through"]
    if leaked:
        out.append(f"and {len(leaked)} wrong value(s) went through unchecked:")
        for i, k in leaked[:5]:
            out.append(f"    form {i + 1}  {k}: model said {_value(answers[i], k)!r}, "
                       f"form says {truths[i][k]!r}")
    else:
        out.append("no wrong value reached the system of record")
    return "\n".join(out)


def capstone_sentence(checked_by_a_person: list[str], answers, truths, use_case: str = "your use case") -> str:
    """The sentence to carry into S27 and S29."""
    unchecked = [k for k in FIELD_KEYS if k not in checked_by_a_person]
    n_forms = len(answers)
    reviewed = len(checked_by_a_person) * n_forms
    total = n_forms * len(FIELD_KEYS)
    leaked = sum(1 for a, t in zip(answers, truths)
                 for k in FIELD_KEYS if k not in checked_by_a_person and is_wrong(a, t, k))
    return (f"For {use_case}, a model may write {', '.join(unchecked) or '(nothing)'} unchecked.\n"
            f"A person must see {', '.join(checked_by_a_person) or '(nothing)'}.\n"
            f"That costs {reviewed} reviews per {total} fields, about 1 in "
            f"{round(total / reviewed) if reviewed else 0}.\n"
            f"Residual risk: {leaked} wrong value(s) per {n_forms} forms still reach the "
            f"system of record.")


def compare_one(answer: dict, truth: dict) -> str:
    """One form, side by side with the answer key. Used by lab 08a."""
    width = max(len(label) for label, _ in FIELDS)
    lines = [f"{'field'.ljust(width)}  {'on the form'.ljust(16)}{'model read'.ljust(16)}"]
    for label, key in FIELDS:
        got = _value(answer, key) or "-"
        if "NOT_LEGIBLE" in got.upper():
            mark = "refused"
        elif got.casefold() == truth[key].casefold():
            mark = "ok"
        else:
            mark = "WRONG"
        lines.append(f"{label.ljust(width)}  {truth[key].ljust(16)}{got.ljust(16)}{mark}")
    wrong = sum(is_wrong(answer, truth, k) for k in FIELD_KEYS)
    refused = sum("NOT_LEGIBLE" in _value(answer, k).upper() for k in FIELD_KEYS)
    lines.append(f"=> {len(FIELD_KEYS) - wrong - refused} correct, {wrong} wrong, {refused} refused")
    return "\n".join(lines)
