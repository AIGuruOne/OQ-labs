"""Two work order forms, identical except for one field.

The whole vision lesson rests on this pair: the same form, once with a permit
number printed on it and once with that line left blank. Everything else - the
equipment tag, the site, the dates, the readings - is identical.

Synthetic. Invented equipment tags and site codes, no real OQ material.
"""
from __future__ import annotations

import io
from pathlib import Path

# Pillow is imported inside the rendering functions, not here: main.py needs the
# constants below (FIELDS, TRUTH, LEVELS) and must not require Pillow to serve a
# pre-rendered image. requirements.txt does not pin Pillow, on purpose.

# What is actually on the complete form. The blank one is the same, except the
# permit line has nothing after the colon - so its truthful answer is None.
TRUTH = {
    "work_order": "WO-118305",
    "equipment": "P-1204A",
    "site": "MRB",
    "permit": "PTW-48213",
    "discipline": "Mechanical",
    "signoff_date": "2026-09-14",
}
BLANK_FIELD = "permit"

FIELDS = [("Work order", "work_order"), ("Equipment", "equipment"), ("Site", "site"),
          ("Permit", "permit"), ("Discipline", "discipline"), ("Sign-off date", "signoff_date")]


def _font(size: int):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_form(blank: bool = False) -> Image.Image:
    """The work order. blank=True leaves the permit line empty. Needs Pillow."""
    from PIL import Image, ImageDraw
    W, H = 840, 560
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    big, mid, small = _font(26), _font(19), _font(16)

    d.text((40, 28), "MAINTENANCE WORK ORDER", fill="black", font=big)
    d.line((40, 66, W - 40, 66), fill="black", width=3)

    y = 96
    for label, key in FIELDS:
        value = "" if (blank and key == BLANK_FIELD) else TRUTH[key]
        d.text((44, y), f"{label}", fill="#333333", font=mid)
        d.line((250, y + 26, 560, y + 26), fill="#999999", width=1)   # the writing line
        d.text((256, y), value, fill="black", font=mid)
        y += 46

    d.text((44, y + 16), "READINGS", fill="#333333", font=mid)
    y += 48
    cols = ["Point", "Before", "After", "Unit"]
    xs = [44, 240, 420, 600]
    for x, c in zip(xs, cols):
        d.text((x, y), c, fill="#333333", font=small)
    y += 24
    for point, before, after in [("TP-1", "4.6", "2.1"), ("TP-2", "5.2", "2.4")]:
        d.line((40, y - 4, W - 40, y - 4), fill="#cccccc", width=1)
        for x, v in zip(xs, [point, before, after, "mm/s"]):
            d.text((x, y), v, fill="black", font=small)
        y += 28
    d.line((40, y - 4, W - 40, y - 4), fill="#cccccc", width=1)
    d.text((44, y + 18), "Supervisor: ____________________", fill="#333333", font=small)
    return im


def render_png(blank: bool = False) -> bytes:
    buf = io.BytesIO()
    render_form(blank).save(buf, format="PNG")
    return buf.getvalue()


def truth_for(blank: bool) -> dict:
    """What a truthful reading of the form would say."""
    t = dict(TRUTH)
    if blank:
        t[BLANK_FIELD] = None
    return t





# --- build-time image generation -------------------------------------------
# The app itself does not import Pillow: the three photographs are rendered once,
# here, and committed as JPEGs. That keeps requirements.txt frozen and makes the
# demo byte-identical every time it is shown.

LEVELS = [
    {"id": 0, "label": "Clean scan",   "blur": 0.0, "scale": 1.00, "quality": 92,
     "note": "flatbed scanner, straight on"},
    {"id": 1, "label": "Decent photo", "blur": 1.0, "scale": 0.60, "quality": 60,
     "note": "phone photo in good light"},
    {"id": 2, "label": "Poor photo",   "blur": 1.6, "scale": 0.45, "quality": 40,
     "note": "phone photo, dim, held too far back"},
]


def photograph(level: dict) -> bytes:
    """Make the clean form look like a photograph of a printout."""
    from PIL import ImageFilter
    im = render_form(False).convert("L")
    if level["scale"] != 1.0:
        im = im.resize((int(im.width * level["scale"]), int(im.height * level["scale"])))
    if level["blur"]:
        im = im.filter(ImageFilter.GaussianBlur(level["blur"]))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=level["quality"])
    return buf.getvalue()


def build_static(out_dir: Path | None = None) -> None:
    out = Path(out_dir or (Path(__file__).parent / "static"))
    out.mkdir(parents=True, exist_ok=True)
    for level in LEVELS:
        data = photograph(level)
        (out / f"level_{level['id']}.jpg").write_bytes(data)
        print(f"  level_{level['id']}.jpg  {level['label']:14s} {len(data)/1024:6.1f} KB")


if __name__ == "__main__":
    build_static()
