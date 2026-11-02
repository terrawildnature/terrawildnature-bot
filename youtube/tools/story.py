"""Instagram story (1080x1920) announcing a new YouTube video, built from the thumbnail.
Usage: python story.py <kapak.jpg> <out.jpg> "SATIR1|SATIR2|SATIR3" "alt bilgi" [sure]
       python story.py <doc_dir>     (lines/info from meta.json "story", length from out/info.json -> out/story.jpg)"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).resolve().parents[2] / "assets"
F_ANTON, F_ROBOTO = str(ASSETS / "fonts" / "Anton-Regular.ttf"), str(ASSETS / "fonts" / "Roboto-Bold.ttf")
LOGO = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
W, H = 1080, 1920
YELLOW, RED = (255, 204, 64), (230, 33, 23)

if Path(sys.argv[1]).is_dir():
    doc = Path(sys.argv[1])
    st = json.loads((doc / "meta.json").read_text(encoding="utf-8"))["story"]
    sec = int(json.loads((doc / "out" / "info.json").read_text(encoding="utf-8"))["duration"])
    kapak, out, lines, info = doc / "out" / "kapak.jpg", doc / "out" / "story.jpg", st["lines"], st["info"]
    dur = f"{sec // 60}:{sec % 60:02d}"
else:
    kapak, out, lines, info = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3].split("|"), sys.argv[4]
    dur = sys.argv[5] if len(sys.argv) > 5 else ""
thumb = Image.open(kapak).convert("RGB")

# background: thumbnail cropped to portrait, blurred and darkened towards the bottom
src = thumb.copy()  # hide the corner logo so it doesn't show up blurred in the background
src.paste(src.crop((src.width - 260, 10, src.width - 140, 130)), (src.width - 130, 10))
s = H / thumb.height
bg = src.resize((int(thumb.width * s), H), Image.LANCZOS)
x0 = bg.width - W
bg = bg.crop((x0, 0, x0 + W, H)).filter(ImageFilter.GaussianBlur(18))
shade = Image.new("L", (1, H))
for y in range(H):
    shade.putpixel((0, y), int(110 + 120 * (y / H)))
bg = Image.composite(Image.new("RGB", (W, H), (2, 8, 22)), bg, shade.resize((W, H)))
d = ImageDraw.Draw(bg)


def font(path, size):
    return ImageFont.truetype(path, size)


def centered(y, text, f, fill, stroke=0):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))


# logo + "YENİ BELGESEL" pill
logo = Image.open(LOGO).convert("RGBA").resize((120, 120), Image.LANCZOS)
bg.paste(logo, ((W - 120) // 2, 200), logo)
f = font(F_ROBOTO, 40)
label = "YENİ BELGESEL YAYINDA"
lw = d.textlength(label, font=f)
d.rounded_rectangle(((W - lw) / 2 - 34, 345, (W + lw) / 2 + 34, 415), 35, fill=RED)
centered(355, label, f, (255, 255, 255))

# headline
y = 450
for i, ln in enumerate(lines):
    fh = font(F_ANTON, 118)
    centered(y, ln, fh, YELLOW if i == 0 else (255, 255, 255), stroke=4)
    y += 135

# thumbnail card with play button
cw = 940
card = thumb.resize((cw, int(thumb.height * cw / thumb.width)), Image.LANCZOS)
ch = card.height
cy = y + 30
mask = Image.new("L", card.size, 0)
ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw, ch), 28, fill=255)
glow = Image.new("RGBA", (W, H), 0)
ImageDraw.Draw(glow).rounded_rectangle(((W - cw) // 2 - 6, cy - 6, (W + cw) // 2 + 6, cy + ch + 6), 32, fill=(255, 255, 255, 230))
bg.paste(glow, (0, 0), glow)
bg.paste(card, ((W - cw) // 2, cy), mask)
px, py = W // 2 + 190, cy + ch // 2
d.rounded_rectangle((px - 75, py - 52, px + 75, py + 52), 26, fill=RED)
d.polygon([(px - 22, py - 28), (px - 22, py + 28), (px + 32, py)], fill=(255, 255, 255))
if dur:
    fd = font(F_ROBOTO, 34)
    tw = d.textlength(dur, font=fd)
    bx, by = (W + cw) // 2 - 24 - tw, cy + ch - 70
    d.rounded_rectangle((bx - 14, by - 6, bx + tw + 14, by + 48), 10, fill=(0, 0, 0))
    d.text((bx, by), dur, font=fd, fill=(255, 255, 255))

# info line + link sticker hint
yi = cy + ch + 40
centered(yi, info, font(F_ROBOTO, 40), (220, 232, 245))
centered(yi + 80, "İZLEMEK İÇİN BAĞLANTIYA DOKUN", font(F_ROBOTO, 44), YELLOW)
ax = W // 2
d.polygon([(ax - 34, yi + 145), (ax + 34, yi + 145), (ax, yi + 190)], fill=YELLOW)

bg.save(out, quality=95)
print(out)
