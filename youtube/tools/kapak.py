"""YouTube thumbnail (1280x720): photo on the right, 2-4 big lines on the left, journey bar, logo.

  python kapak.py <doc_dir>        -> <doc_dir>/out/kapak.jpg
meta.json "thumb": {"lines": ["10.935 METRE", "AŞAĞIDA", "NE YAŞIYOR?"], "photo": "16_0",
                    "cx": 0.6, "cy": 0.5, "zoom": 1.0, "bar": ["YÜZEY", "DİP"]}
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from doc_render import F_ANTON, F_UI, OCEAN, YT_ASSETS, make_palette, water_color, zone_colors  # noqa: E402

W, H = 1280, 720
YELLOW = (255, 204, 64)


def main(doc):
    meta = json.loads((doc / "meta.json").read_text(encoding="utf-8"))
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    j = {**OCEAN, **spec.get("journey", {})}
    th = meta["thumb"]
    pal = make_palette(j)

    # background: darkest journey colour with faint particles
    c = water_color(j["max"] * 0.6, pal) * 1.6 + 6
    yy = np.linspace(0, 1, H)[:, None, None]
    bg = (c * (1.25 - 0.6 * yy)).clip(0, 255) * np.ones((1, W, 1))
    img = Image.fromarray(bg.astype(np.uint8))
    rng = np.random.default_rng(5)
    d = ImageDraw.Draw(img)
    for x, y, r in zip(rng.uniform(0, W, 160), rng.uniform(0, H, 160), rng.uniform(0.6, 2.2, 160)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=(200, 220, 240))

    # photo: right 62%, faded into the background on its left edge
    ph = Image.open(doc / "photos" / f"{th['photo']}.jpg").convert("RGB")
    pw, phh = int(W * 0.62), H
    z = th.get("zoom", 1.0)
    base = min(ph.width / pw, ph.height / phh) / z
    w, h = pw * base, phh * base
    x0 = min(max(ph.width * th.get("cx", 0.5) - w / 2, 0), ph.width - w)
    y0 = min(max(ph.height * th.get("cy", 0.5) - h / 2, 0), ph.height - h)
    crop = ph.resize((pw, phh), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h))
    mask = Image.fromarray((np.clip(np.linspace(-0.15, 1.6, pw), 0, 1) ** 1.3 * 255).astype(np.uint8)[None, :].repeat(phh, 0))
    img.paste(crop, (W - pw, 0), mask)

    # headline
    d = ImageDraw.Draw(img)
    lines = th["lines"]
    size = 132 if len(lines) <= 3 else 108
    while max(d.textlength(l, font=ImageFont.truetype(F_ANTON, size)) for l in lines) > 640 and size > 60:
        size -= 4
    f = ImageFont.truetype(F_ANTON, size)
    step = int(size * 1.08)
    y = (H - step * len(lines)) // 2 - (40 if th.get("bar", True) else 0)
    shadow = Image.new("RGBA", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    for k, l in enumerate(lines):
        sd.text((52 + 6, y + k * step + 8), l, font=f, fill=(0, 0, 0, 200))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(6)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(6)))
    for k, l in enumerate(lines):
        d.text((52, y + k * step), l, font=f, fill=YELLOW if k == 0 else (255, 255, 255), stroke_width=5, stroke_fill=(0, 0, 0))

    # journey bar: one block per zone, marker at the end of the journey
    if th.get("bar", True):
        labels = th.get("bar_labels") or (["YÜZEY", "DİP"] if j["direction"] == "down" else ["ALT", "ZİRVE"])
        zones = j["zones"]
        bx, by, bw = 52, y + len(lines) * step + 46, 475
        seg = bw / len(zones)
        for k, col in enumerate(zone_colors(j)):
            d.rectangle((bx + k * seg + 2, by, bx + (k + 1) * seg - 2, by + 20), fill=col)
        d.polygon([(bx + bw - 14, by - 16), (bx + bw + 4, by - 16), (bx + bw - 5, by - 3)], fill=YELLOW)
        fl = ImageFont.truetype(F_UI, 24)
        d.text((bx, by + 30), labels[0], font=fl, fill=(200, 225, 245))
        d.text((bx + bw, by + 30), labels[1], font=fl, fill=(200, 225, 245), anchor="ra")

    logo = Image.open(YT_ASSETS / "logo.png").convert("RGB").resize((90, 90), Image.LANCZOS)
    img.paste(logo, (W - 90 - 28, 24))
    (doc / "out").mkdir(exist_ok=True)
    img.save(doc / "out" / "kapak.jpg", quality=92)
    print(doc / "out" / "kapak.jpg")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
