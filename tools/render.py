"""Terra Wild Nature poster renderer.

Usage: python tools/render.py <post_dir>
Reads <post_dir>/post.json, writes <post_dir>/a.jpg (cover) and <post_dir>/b.jpg (info page).
Fails with a clear message if any text overflows its box.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ANTON = str(ASSETS / "fonts" / "Anton-Regular.ttf")
ROBOTO = str(ASSETS / "fonts" / "Roboto-Bold.ttf")

WHITE = (255, 255, 255)
RED = (254, 0, 0)
CARD = (150, 0, 1)
BLACK = (0, 0, 0)

# Layout limits (right edge of ink) — beyond these, text collides with frames/borders.
MAX_TITLE_HALF = 520      # title lines are centered on x=560
MAX_CARD_RIGHT = 528
MAX_RIGHT_COL = 1004
MAX_LOC_RIGHT = 900

_font_cache = {}


def font(path, em):
    key = (path, em)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, em)
    return _font_cache[key]


def ink(f, s):
    """Ink box of s relative to (pen origin, baseline): (x0, y0, x1, y1)."""
    mask, (ox, oy) = f.getmask2(s, anchor="ls")
    bb = mask.getbbox()
    if bb is None:
        return (0, 0, 0, 0)
    return (ox + bb[0], oy + bb[1], ox + bb[2], oy + bb[3])


def draw_at(img, s, f, color, ox, baseline):
    ImageDraw.Draw(img).text((ox, baseline), s, font=f, fill=color, anchor="ls")
    x0, y0, x1, y1 = ink(f, s)
    return (ox + x0, baseline + y0, ox + x1, baseline + y1)


def origin_from_left(ref, f, ink_left):
    return ink_left - ink(f, ref)[0]


def base_from_top(ref, f, ink_top):
    return ink_top - ink(f, ref)[1]


# ---------------- photo helpers ----------------
def cover_box(src, dw, dh, cx, cy, zoom):
    ar = dw / dh
    w = src.width
    h = w / ar
    if h > src.height:
        h = src.height
        w = h * ar
    w /= zoom
    h /= zoom
    x = min(max(0, cx * src.width - w / 2), src.width - w)
    y = min(max(0, cy * src.height - h / 2), src.height - h)
    return (x, y, x + w, y + h)


def place_photo(canvas, spec, dest):
    """dest = (x, y, w, h). spec = {file, cx, cy, zoom}."""
    src = Image.open(spec["file"]).convert("RGB")
    x, y, w, h = dest
    box = cover_box(src, w, h, spec.get("cx", 0.5), spec.get("cy", 0.5), spec.get("zoom", 1.0))
    canvas.paste(src.resize((w, h), Image.BICUBIC, box=box), (x, y))


def grade(arr, y1, bright, contrast, sat):
    reg = arr[:y1].astype(np.float32)
    lum = (0.299 * reg[..., 0] + 0.587 * reg[..., 1] + 0.114 * reg[..., 2])[..., None]
    reg = lum + (reg - lum) * sat
    reg = (reg - 128) * contrast + 128 + bright
    arr[:y1] = np.clip(np.round(reg), 0, 255)


def fade(arr, y0, y1, gamma):
    ys = np.arange(y0, y1)
    m = ((y1 - ys) / (y1 - y0)) ** gamma
    m[ys >= y1 - 1] = 0
    arr[y0:y1] = np.clip(np.round(arr[y0:y1].astype(np.float32) * m[:, None, None]), 0, 255)


def round_rect_mask(size, rect, radius, ss=4):
    x, y, w, h = rect
    big = Image.new("L", (size[0] * ss, size[1] * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle(
        [x * ss, y * ss, (x + w) * ss, (y + h) * ss], radius=radius * ss, fill=255)
    return big.resize(size, Image.BOX)


def fill(img, color, x, y, w, h):
    ImageDraw.Draw(img).rectangle([x, y, x + w - 1, y + h - 1], fill=color)


# ---------------- validation ----------------
class Overflow(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise Overflow(msg)


# ---------------- cover (a) ----------------
def render_cover(post, out):
    orig = Image.open(ASSETS / "template_a.jpeg").convert("RGB")
    img = orig.copy()
    place_photo(img, post["photos"]["cover"], (0, 0, 1122, 890))
    arr = np.array(img).astype(np.float32)
    grade(arr, 890, -14, 1.08, 0.92)
    fade(arr, 520, 891, 1.7)
    img = Image.fromarray(arr.astype(np.uint8))
    # logo + badge from template, pixel-exact
    img.paste(orig.crop((55, 32, 169, 130)), (55, 32))
    badge = round_rect_mask(img.size, (390.5, 835.5, 340, 66), 28)
    img = Image.composite(orig, img, badge)

    fill(img, BLACK, 0, 903, 1122, 499)
    f = font(ANTON, 109.6)
    cap = ink(f, "H")
    lines = post["title"]
    check(len(lines) == 3, "title must have exactly 3 lines")
    for parts, cap_top in zip(lines, (948, 1102, 1255)):
        widths = [ink(f, t)[2] - ink(f, t)[0] for t, _ in parts]
        total = sum(widths) + 33 * (len(parts) - 1)
        check(total / 2 <= MAX_TITLE_HALF,
              f"title line too wide ({total:.0f}px > {2 * MAX_TITLE_HALF}px): {' '.join(t for t, _ in parts)}")
        x = 560 - total / 2
        base = cap_top - cap[1]
        for (t, c), w in zip(parts, widths):
            ox = x - ink(f, t)[0]
            draw_at(img, t, f, WHITE if c == "W" else RED, ox, base)
            x += w + 33
    img.save(out, quality=95)


# ---------------- info (b) ----------------
def render_info(post, out):
    orig = Image.open(ASSETS / "template_b.jpeg").convert("RGB")
    img = orig.copy()
    place_photo(img, post["photos"]["top"], (0, 0, 1122, 848))
    arr = np.array(img).astype(np.float32)
    grade(arr, 848, -10, 1.06, 0.95)
    fade(arr, 560, 849, 1.5)
    img = Image.fromarray(arr.astype(np.uint8))
    card = round_rect_mask(img.size, (41, 836, 501.5, 543), 20.5)
    img = Image.composite(orig, img, card)
    place_photo(img, post["photos"]["inner"], (65, 1028, 454, 234))

    fill(img, CARD, 136, 862, 396, 40)
    fill(img, CARD, 50, 936, 482, 84)
    fill(img, CARD, 50, 1263, 482, 111)
    fill(img, BLACK, 566, 878, 440, 196)
    fill(img, CARD, 634, 1316, 272, 38)

    check(len(post["card_top"]) == 2, "card_top must have exactly 2 lines")
    check(len(post["card_bottom"]) == 3, "card_bottom must have exactly 3 lines")
    check(len(post["right"]) == 5, "right must have exactly 5 lines")

    ft = font(ROBOTO, 29.25)
    bb = draw_at(img, post["card_title"], ft, WHITE,
                 origin_from_left("D", ft, 140), base_from_top("D", ft, 874))
    check(bb[2] <= MAX_CARD_RIGHT, f"card_title too wide: {post['card_title']}")

    fb = font(ROBOTO, 28)
    ox = origin_from_left("Z", fb, 66)
    bl2 = base_from_top("l", fb, 984)
    for i, s in enumerate(post["card_top"]):
        bb = draw_at(img, s, fb, WHITE, ox, bl2 - 39 + 39 * i)
        check(bb[2] <= MAX_CARD_RIGHT, f"card_top line too wide ({bb[2]:.0f}px): {s}")
    ox = origin_from_left("V", fb, 69)
    bl = base_from_top("l", fb, 1269)
    for i, s in enumerate(post["card_bottom"]):
        bb = draw_at(img, s, fb, WHITE, ox, bl + 39 * i)
        check(bb[2] <= MAX_CARD_RIGHT, f"card_bottom line too wide ({bb[2]:.0f}px): {s}")
    ox = origin_from_left("d", fb, 575)
    bl5 = base_from_top("b", fb, 1046)
    for i, s in enumerate(post["right"]):
        bb = draw_at(img, s, fb, WHITE, ox, bl5 - 39 * (4 - i))
        check(bb[2] <= MAX_RIGHT_COL, f"right line too wide ({bb[2]:.0f}px): {s}")

    fl = font(ROBOTO, 23.9)
    bb = draw_at(img, post["loc"], fl, WHITE,
                 origin_from_left("H", fl, 640), base_from_top("k", fl, 1324))
    check(bb[2] <= MAX_LOC_RIGHT, f"loc too wide: {post['loc']}")
    img.save(out, quality=95)


def render(post_dir):
    post_dir = Path(post_dir)
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    for k in ("cover", "top", "inner"):
        p = Path(post["photos"][k]["file"])
        if not p.is_absolute():
            post["photos"][k]["file"] = str(post_dir / p)
    render_cover(post, post_dir / "a.jpg")
    render_info(post, post_dir / "b.jpg")
    print(f"OK: {post_dir / 'a.jpg'}, {post_dir / 'b.jpg'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        render(sys.argv[1])
    except Overflow as e:
        sys.exit(f"OVERFLOW: {e}")
