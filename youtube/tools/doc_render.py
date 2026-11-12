"""Render a long-form "journey" documentary (1920x1080, 30 fps): a depth/altitude counter runs down (or up)
while the narration visits creatures, landmarks and zones along the way.

  python doc_render.py <doc_dir>                    full render -> <doc_dir>/out/belgesel.mp4
  python doc_render.py <doc_dir> --stills 5,80,300  still frames at those seconds -> <doc_dir>/out/still_*.jpg
  python doc_render.py <doc_dir> --shard 3/16       only parts k with k % 16 == 3 (parallel CI jobs)
  python doc_render.py <doc_dir> --assemble         concat existing parts + mix audio -> belgesel.mp4
  python doc_render.py <doc_dir> --info             write out/chapters.txt + out/info.json only
  python doc_render.py <doc_dir> --preview          out/preview.jpg: contact sheet of 12 moments (works without voice/)

script.json "mechanic": "<name>" loads youtube/mechanics/<name>.py, a class Mechanic(scene) that can replace the
background and draw each frame its own way (see youtube/mechanics/README.md).

Inputs in <doc_dir>: script.json (see youtube/ROUTINE.md), voice/NN.mp3+json (voice.py), photos/ + photos.json.
Optional 3D intro frames in THREE_D (local machine only); otherwise the cold open is a photo montage.
"""
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
BIN = Path(r"C:\Users\seyit\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin")
FFMPEG = shutil.which("ffmpeg") or str(BIN / "ffmpeg.exe")
FFPROBE = shutil.which("ffprobe") or str(BIN / "ffprobe.exe")
ROOT = Path(__file__).resolve().parents[2]          # terrawildnature-bot
ASSETS, YT_ASSETS = ROOT / "assets", ROOT / "youtube" / "assets"
F_ANTON, F_ROBOTO = str(ASSETS / "fonts" / "Anton-Regular.ttf"), str(ASSETS / "fonts" / "Roboto-Bold.ttf")


def _first(*cands):
    return next((c for c in cands if os.path.exists(c)), F_ROBOTO)


F_UI = _first("C:/Windows/Fonts/bahnschrift.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
F_IT = _first("C:/Windows/Fonts/georgiai.ttf", "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
THREE_D = Path(os.environ.get("TW3D_FRAMES", "C:/tw3d/frames"))
COLD_OPEN = 12.0
END_SCREEN = 20.0

CARD = (520, 92, 1340, 754)          # x, y, w, h (16:9)
SUB_CX, SUB_Y, SUB_W = 1180, 905, 1380
OFFX = 180                            # big titles sit right of the meter


def set_layout(meter, card=None, sub_cx=None):
    """Without the meter (thematic / countdown documentaries) everything is centred. A mechanic may move the card."""
    global CARD, SUB_CX, OFFX
    CARD, SUB_CX, OFFX = ((520, 92, 1340, 754), 1180, 180) if meter else ((290, 92, 1340, 754), 960, 0)
    if card:
        CARD = tuple(card)
    if sub_cx:
        SUB_CX = sub_cx

# The ocean descent is the reference journey; script.json "journey" overrides any of these keys.
OCEAN = {
    "label": "DERİNLİK", "unit": "m", "max": 10935, "direction": "down",
    "zones": [[0, 200, "GÜNEŞ IŞIĞI"], [200, 1000, "ALACAKARANLIK"], [1000, 4000, "GECE"], [4000, 6000, "ABİSAL"],
              [6000, 10935, "HADAL"]],
    "stats": [
        {"name": "BASINÇ", "x": [0, 10935], "y": [1, 1088], "suffix": " atm"},
        {"name": "SICAKLIK", "x": [0, 100, 200, 500, 1000, 2000, 4000, 6000, 10935], "y": [22, 18, 14, 8, 4.5, 3, 2, 1.6, 2.4],
         "prefix": "~", "suffix": " °C"},
        {"name": "IŞIK", "x": [0, 25, 50, 75, 100, 150, 200, 250, 300], "y": [100, 36.8, 13.5, 4.98, 1.83, 0.25, 0.034, 0.0045, 0.0006],
         "style": "pct", "zero": "YOK"}],
    # background colour by position (interpolated on log10(1 + v))
    "palette": [[0, [30, 136, 196]], [19, [14, 92, 156]], [199, [7, 44, 92]], [999, [3, 15, 40]], [3980, [1, 6, 18]], [11220, [0, 2, 8]]],
    "rays": 260, "particles": "marine", "glow": 280,
    "music": ["Reawakening.mp3", "Investigations.mp3"],
}


def font(path, size):
    return _font(path, size)


@lru_cache(None)
def _font(path, size):
    return ImageFont.truetype(path, size)


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def tr_title(s):
    low = lambda w: w.replace("I", "ı").replace("İ", "i").lower()
    return " ".join(tr_upper(w[0]) + low(w[1:]) for w in s.split())


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def duration(p):
    return float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)


# ---------------------------------------------------------------- timeline
def timeline(doc):
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    spec["journey"] = {**OCEAN, **spec.get("journey", {})}
    meter = spec["journey"].get("meter", True)
    set_layout(meter, spec["journey"].get("card"), spec["journey"].get("sub_cx"))
    blocks, t, prev = [{"kind": "cold", "t0": 0.0, "dur": COLD_OPEN, "d0": 0, "d1": 0}], COLD_OPEN, 0
    for i, s in enumerate(spec["segments"]):
        travel = 0.0 if s["depth"] == prev else (3.2 if big_jump(prev, s["depth"], spec["journey"], 0.0366, 0.15) else 2.4)
        if s["type"] == "zone":
            travel = max(travel, 1.2)
        if travel:
            blocks.append({"kind": "travel", "t0": t, "dur": travel, "d0": prev, "d1": s["depth"], "i": i})
            t += travel
        if s.get("rank") is not None:   # countdown: big "#7" before the creature
            blocks.append({"kind": "rank", "t0": t, "dur": 1.8, "d0": s["depth"], "d1": s["depth"], "i": i, "rank": s["rank"]})
            t += 1.8
        hold = s.get("hold", 3.2 if s["type"] == "zone" else 0.5)   # "hold": silent seconds before the voice
        if (doc / "voice" / f"{i:02d}.mp3").exists():
            vd = duration(doc / "voice" / f"{i:02d}.mp3")
            words = json.loads((doc / "voice" / f"{i:02d}.json").read_text(encoding="utf-8"))
        else:   # no narration yet (preview in the cloud routine): estimate ~0.42 s per word
            toks = s["text"].split()
            words = [{"t": k * 0.42, "d": 0.38} for k in range(len(toks))]
            vd = len(toks) * 0.42
        blocks.append({"kind": s["type"], "t0": t, "dur": hold + vd + 1.0, "d0": s["depth"], "d1": s["depth"], "i": i,
                       "voice": t + hold, "seg": s, "subs": sentences(s["text"], words)})
        t += hold + vd + 1.0
        prev = s["depth"]
    blocks.append({"kind": "end", "t0": t, "dur": END_SCREEN, "d0": prev, "d1": prev})
    return spec, blocks, t + END_SCREEN


def sentences(text, words):
    """[(start, end, sentence)] in voice time; word boundaries map 1:1 to whitespace tokens."""
    out, k = [], 0
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        n = len(sent.split())
        if not n or k >= len(words):
            continue
        a, b = words[k], words[min(k + n, len(words)) - 1]
        out.append((a["t"], b["t"] + b["d"], sent))
        k += n
    return out


def block_at(blocks, t):
    for b in blocks:
        if b["t0"] <= t < b["t0"] + b["dur"]:
            return b
    return blocks[-1]


def to_unit(v, j):
    """Position -> 0..1 along the gauge: sqrt by default (room for the busy start), log for ranges like 1 mm .. 30 m."""
    if j.get("scale") == "log":
        lo, hi = math.log10(j["min"]), math.log10(j["max"])
        return min(max((math.log10(max(v, j["min"])) - lo) / (hi - lo), 0.0), 1.0)
    return math.sqrt(min(max(v, 0) / j["max"], 1.0))


def from_unit(u, j):
    if j.get("scale") == "log":
        lo, hi = math.log10(j["min"]), math.log10(j["max"])
        return 10 ** (lo + (hi - lo) * u)
    return u * u * j["max"]


def big_jump(a, b, j, frac, unit):
    if j.get("scale") == "log":
        return abs(to_unit(b, j) - to_unit(a, j)) >= unit
    return abs(b - a) >= j["max"] * frac


def depth_at(b, t, j):
    if b["kind"] != "travel":
        return b["d0"]
    x = ease((t - b["t0"]) / b["dur"])
    u0, u1 = to_unit(b["d0"], j), to_unit(b["d1"], j)
    return from_unit(u0 + (u1 - u0) * x, j)


# ---------------------------------------------------------------- background
def make_palette(j):
    return [(math.log10(1 + max(v, 0)), c) for v, c in j["palette"]]


def water_color(d, pal):
    x = math.log10(1 + max(d, 0))
    if x <= pal[0][0]:
        return np.array(pal[0][1], np.float32)
    for (x0, c0), (x1, c1) in zip(pal, pal[1:]):
        if x <= x1:
            f = (x - x0) / (x1 - x0)
            return np.array([c0[j] + (c1[j] - c0[j]) * f for j in range(3)], np.float32)
    return np.array(pal[-1][1], np.float32)


def zone_colors(j):
    """Gauge colours: light blue -> violet across the zones unless the journey lists its own."""
    if j.get("zone_colors"):
        return [tuple(c) for c in j["zone_colors"]]
    n, c0, c1 = len(j["zones"]), (70, 180, 230), (90, 40, 120)
    mid = (40, 70, 150)
    out = []
    for k in range(n):
        x = k / max(n - 1, 1)
        a, b, f = (c0, mid, x * 2) if x < 0.5 else (mid, c1, x * 2 - 1)
        out.append(tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3)))
    return out


def fmt_num(v, dec=0):
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_stat(st, d):
    v = float(np.interp(d, st["x"], st["y"]))
    if st.get("style") == "pct":
        if v >= 1:
            return f"%{v:.0f}"
        return f"%{v:.2f}".replace(".", ",") if v >= 0.01 else st.get("zero", "%0")
    return st.get("prefix", "") + fmt_num(v, st.get("dec", 0)) + st.get("suffix", "")


class Scene:
    """Per-worker caches: gradients, rays, particles, sprites, rendered text."""

    def __init__(self, doc, spec, blocks):
        self.doc, self.spec, self.blocks = doc, spec, blocks
        self.j = spec["journey"]
        self.pal = make_palette(self.j)
        self.photos = json.loads((doc / "photos.json").read_text(encoding="utf-8"))
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        self.vert = yy
        xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
        r = np.sqrt(xx ** 2 * 0.8 + ((yy - 0.5) * 2) ** 2)
        self.vign = np.clip(1.15 - 0.45 * r ** 2, 0.45, 1.0)[..., None]
        rng = np.random.default_rng(3)
        rays = np.zeros((H, W * 2), np.float32)
        img = Image.fromarray(np.zeros((H, W * 2), np.uint8))
        dr = ImageDraw.Draw(img)
        for _ in range(26):
            x = rng.uniform(0, W * 2)
            w = rng.uniform(30, 140)
            dr.polygon([(x, 0), (x + w, 0), (x + w * 3 - 420, H), (x - 420, H)], fill=int(rng.uniform(60, 160)))
        img = img.filter(ImageFilter.GaussianBlur(28))
        rays = np.asarray(img, np.float32) / 255.0 * (1 - np.linspace(0, 1, H, dtype=np.float32)[:, None]) ** 1.6
        self.rays = rays
        self.parts = rng.uniform(0, 1, (340, 4))          # x, y, size, speed
        self.biolum = rng.uniform(0, 1, (46, 4))           # x, y, phase, colour
        self.sprites = {}
        for rad in (1, 2, 3, 6, 10):
            s = np.arange(-rad * 2, rad * 2 + 1, dtype=np.float32)
            g = np.exp(-(s[:, None] ** 2 + s[None, :] ** 2) / (2 * (rad * 0.7) ** 2))
            self.sprites[rad] = g[..., None]
        self.img_cache = {}
        self.text_cache = {}
        self.mech = None
        if spec.get("mechanic"):
            path = ROOT / "youtube" / "mechanics" / f"{spec['mechanic']}.py"
            ms = importlib.util.spec_from_file_location(f"mechanic_{spec['mechanic']}", path)
            mod = importlib.util.module_from_spec(ms)
            sys.modules["doc_render"] = sys.modules[__name__]   # mechanics share this module's live layout globals
            ms.loader.exec_module(mod)
            self.mech = mod.Mechanic(self)

    # -- water
    def background(self, d, t):
        c = water_color(d, self.pal)
        rays = self.j["rays"]
        near = max(0.0, 1 - d / 300) if rays else 0.0
        top, bot = c * (1.25 + 0.35 * near), c * (0.55 + 0.1 * near)
        if self.j["direction"] == "up":   # sky: lighter towards the horizon
            top, bot = bot * 1.6, top * 0.9
        frame = top[None, None, :] * (1 - self.vert[..., None]) + bot[None, None, :] * self.vert[..., None]
        frame = np.broadcast_to(frame, (H, W, 3)).copy()
        if rays and d < rays:
            a = (1 - d / rays) ** 1.3 * 0.55
            off = int(t * 18) % W
            frame += (self.rays[:, off:off + W, None] * a * 255 * np.array([0.75, 0.9, 1.0], np.float32))
        frame *= self.vign
        if self.j["particles"]:
            self.snow(frame, d, t)
        glow = self.j["glow"]
        if glow is not None and d > glow:
            self.sparkles(frame, d, t)
        return frame

    def snow(self, frame, d, t):
        """marine: plankton drifting past as we sink; snow: flakes falling across the frame; dust: faint motes."""
        kind = self.j["particles"]
        r = max(d, 0) / self.j["max"]
        if kind == "marine":
            dens, bright = min(1.0, 0.25 + d / 600), 70 + 90 * min(1.0, d / 800)
        elif kind == "snow":
            dens, bright = min(1.0, 0.15 + 1.2 * r), 150 + 80 * r
        else:
            dens, bright = 0.35, 70
        n = int(len(self.parts) * dens)
        sign = -1 if self.j["direction"] == "up" else 1
        for x, y, sz, sp in self.parts[:n]:
            if kind == "snow":
                px = (x * W + t * 25 * (0.3 + sp)) % W
                py = (y * H + t * 60 * (0.4 + sp) + sign * math.sqrt(max(d, 0)) * 4) % H
            else:
                px = x * W
                py = (y * H - sign * (math.sqrt(max(d, 0)) * 22 * (0.5 + sp) + t * 14 * (0.4 + sp))) % H
            self.add(frame, px, py, 1 if sz < 0.6 else (2 if sz < 0.92 else 3), bright * (0.4 + 0.6 * sp), (1, 1, 1))

    def sparkles(self, frame, d, t):
        g = self.j["glow"]
        k = min(1.0, (d - g) / max(900, self.j["max"] * 0.08))
        for x, y, ph, col in self.biolum[:int(len(self.biolum) * k)]:
            a = max(0.0, math.sin(t * (0.6 + ph) + ph * 40)) ** 6
            if a < 0.03:
                continue
            c = (0.3, 0.9, 1.0) if col < 0.7 else (0.5, 1.0, 0.6)
            self.add(frame, x * W, (y * H - t * 6) % H, 6, 210 * a, c)
            self.add(frame, x * W, (y * H - t * 6) % H, 2, 255 * a, (0.8, 1, 1))

    def add(self, frame, cx, cy, rad, amp, col):
        sp = self.sprites[rad]
        r = sp.shape[0] // 2
        x0, y0 = int(cx) - r, int(cy) - r
        x1, y1 = x0 + sp.shape[0], y0 + sp.shape[1]
        if x0 < 0 or y0 < 0 or x1 > W or y1 > H:
            return
        frame[y0:y1, x0:x1] += sp * (amp * np.array(col, np.float32))

    # -- overlays
    def text_img(self, key, fn):
        if key not in self.text_cache:
            if len(self.text_cache) > 400:
                self.text_cache.clear()
            self.text_cache[key] = fn()
        return self.text_cache[key]

    def meter(self, d, seg_stats=None):
        key = ("meter", self.fmt_pos(d), json.dumps(seg_stats, ensure_ascii=False))
        return self.text_img(key, lambda: self._meter(d, seg_stats))

    def _meter(self, d, seg_stats):
        im = Image.new("RGBA", (440, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((28, 40, 410, 360), 22, fill=(0, 10, 25, 120), outline=(140, 210, 255, 70), width=2)
        j = self.j
        dr.text((56, 58), j["label"], font=font(F_UI, 28), fill=(150, 210, 240, 255))
        dr.text((52, 88), self.fmt_pos(d), font=font(F_ANTON, 92), fill=(255, 255, 255, 255))
        # rows: journey-wide stats interpolated by position, or per-segment facts (ranking documentaries)
        rows = seg_stats if seg_stats is not None else [(st["name"], fmt_stat(st, d)) for st in j["stats"][:3]]
        for k, (name, val) in enumerate(rows[:3]):
            y = 222 + k * 42
            dr.text((56, y), name, font=font(F_UI, 28), fill=(150, 210, 240, 255))
            fv = font(F_UI, 30)
            while dr.textlength(val, font=fv) > 390 - 56 - dr.textlength(name, font=font(F_UI, 28)) - 16 and fv.size > 18:
                fv = font(F_UI, fv.size - 2)
            dr.text((390, y), val, font=fv, fill=(255, 255, 255, 255), anchor="ra")
        # gauge: sqrt scale gives the busy first part room; "up" journeys grow from the bottom
        gx, gt, gb = 96, 420, 1010
        up = j["direction"] == "up"
        ys = lambda v: (gb - (gb - gt) * to_unit(v, j)) if up else (gt + (gb - gt) * to_unit(v, j))
        zones = j["zones"]
        for (a, b, name), c in zip(zones, zone_colors(j)):
            on = a <= d < b or (b == zones[-1][1] and d >= a)
            dr.rectangle((gx - 7, min(ys(a), ys(b)), gx + 7, max(ys(a), ys(b))), fill=c + ((255,) if on else (120,)))
            dr.text((gx + 26, (ys(a) + ys(b)) / 2), name, font=font(F_UI, 26 if on else 22),
                    fill=(255, 255, 255, 255) if on else (170, 200, 220, 150), anchor="lm")
        last = None
        for v in sorted([z[1] for z in zones], reverse=True):   # the end value wins over a tick right next to it
            if last is None or abs(ys(v) - last) >= 20:
                dr.text((gx - 18, ys(v)), fmt_num(v, 1 if v < 10 and v != int(v) else 0), font=font(F_UI, 18), fill=(170, 200, 220, 170), anchor="rm")
                last = ys(v)
        y = ys(d)
        dr.polygon([(gx + 10, y), (gx + 26, y - 10), (gx + 26, y + 10)], fill=(255, 210, 60, 255))
        dr.line((gx - 10, y, gx + 10, y), fill=(255, 210, 60, 255), width=4)
        return im

    def fmt_pos(self, d):
        """Counter text; journey "units" switches unit by size, e.g. [[0, "cm", 1], [100, "m", 0.01]]."""
        unit, f = self.j["unit"], 1
        for lim, u, fac in self.j.get("units", []):
            if d >= lim:
                unit, f = u, fac
        v = d * f
        dec = self.j.get("dec")
        if dec is None:   # small values keep a decimal (0,5 cm), large ones are whole numbers
            dec = 1 if abs(v) < 10 and abs(v - round(v)) > 0.05 else 0
        return fmt_num(round(v, dec), dec) + " " + unit

    def photo(self, key):
        if key not in self.img_cache:
            if len(self.img_cache) > 12:
                self.img_cache.clear()
            im = Image.open(self.doc / "photos" / f"{key}.jpg").convert("RGB")
            cw, ch = CARD[2], CARD[3]
            s = max(cw * 1.22 / im.width, ch * 1.22 / im.height)
            if s < 1:
                im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            self.img_cache[key] = im
        return self.img_cache[key]

    def kenburns(self, key, x, n):
        """x in 0..1 through this photo's screen time; alternates zoom-in / zoom-out."""
        im = self.photo(key)
        cw, ch = CARD[2], CARD[3]
        base = min(im.width / cw, im.height / ch)
        z0, z1 = (1.0, 1.12) if n % 2 == 0 else (1.12, 1.0)
        z = z0 + (z1 - z0) * x
        w, h = cw * base / z, ch * base / z
        cy = 0.45 if im.height > im.width else 0.5
        px = 0.5 + (0.04 if n % 2 else -0.04) * (x - 0.5)
        w, h = min(w, im.width), min(h, im.height)   # float rounding can make the box a hair larger than the photo
        x0 = max(min(im.width * px - w / 2, im.width - w), 0)
        y0 = max(min(im.height * cy - h / 2, im.height - h), 0)
        return im.resize((cw, ch), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))

    def card_chrome(self):
        return self.text_img("chrome", self._chrome)

    def _chrome(self):
        cw, ch = CARD[2], CARD[3]
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, ch - 1), 26, fill=255)
        shadow = Image.new("L", (cw + 120, ch + 120), 0)
        ImageDraw.Draw(shadow).rounded_rectangle((60, 70, cw + 60, ch + 70), 30, fill=170)
        shadow = shadow.filter(ImageFilter.GaussianBlur(26))
        border = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        ImageDraw.Draw(border).rounded_rectangle((0, 0, cw - 1, ch - 1), 26, outline=(170, 225, 255, 110), width=3)
        grad = np.zeros((ch, cw, 4), np.uint8)
        g = np.clip((np.linspace(0, 1, ch) - 0.62) / 0.38, 0, 1) ** 1.4 * 215
        grad[..., 3] = g[:, None].astype(np.uint8)
        return mask, shadow, border, Image.fromarray(grad, "RGBA")

    def plate(self, seg):
        return self.text_img(("plate", seg["name"]), lambda: self._plate(seg))

    def _plate(self, seg):
        cw, ch = CARD[2], CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        if seg.get("rank") is not None:
            f = font(F_ANTON, 64)
            txt = f"#{seg['rank']}"
            tw = dr.textlength(txt, font=f)
            dr.rounded_rectangle((28, 24, 28 + tw + 40, 118), 18, fill=(230, 33, 23, 235))
            dr.text((48, 30), txt, font=f, fill="white")
        if seg["type"] == "creature":
            dr.text((44, ch - 150), tr_upper(seg["name"]), font=font(F_ANTON, 70), fill="white")
            dr.text((48, ch - 62), seg["latin"], font=font(F_IT, 32), fill=(205, 225, 235))
            label = f"{self.j.get('range_label', 'YAŞAM ALANI')}  {seg['range']}"
            f = font(F_UI, 28)
            tw = dr.textlength(label, font=f)
            dr.rounded_rectangle((cw - tw - 76, ch - 74, cw - 36, ch - 26), 22, fill=(0, 30, 50, 190), outline=(120, 210, 255, 160), width=2)
            dr.text((cw - tw - 56, ch - 50), label, font=f, fill="white", anchor="lm")
        else:
            dr.text((44, ch - 215), seg["value"], font=font(F_ANTON, 92), fill=(255, 205, 70))
            dr.text((48, ch - 40), tr_upper(seg["name"]), font=font(F_UI, 42), fill="white", anchor="ls")
        return im

    def credit(self, m):
        return self.text_img(("credit", m["file"]), lambda: self._credit(m))

    def _credit(self, m):
        lic = m["license"]
        lic = "Kamu malı" if re.search(r"public domain|^pd", lic, re.I) else lic
        who = re.sub(r"\s+", " ", m["author"] or "").strip()
        if not who or who.lower().startswith("unknown"):
            who = m["source"]
        txt = f"Foto: {who[:48]} · {lic} · {m['source']}"
        f = font(F_ROBOTO, 19)
        im = Image.new("RGBA", (int(ImageDraw.Draw(Image.new('L', (1, 1))).textlength(txt, font=f)) + 24, 34), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, im.width - 1, 33), 10, fill=(0, 0, 0, 120))
        dr.text((12, 17), txt, font=f, fill=(230, 230, 230, 230), anchor="lm")
        return im

    def subtitle(self, text):
        return self.text_img(("sub", text), lambda: self._subtitle(text))

    def _subtitle(self, text):
        f = font(F_ROBOTO, 40)
        tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
        lines, cur = [], ""
        for w in text.split():
            nxt = (cur + " " + w).strip()
            if tmp.textlength(nxt, font=f) > SUB_W and cur:
                lines.append(cur)
                cur = w
            else:
                cur = nxt
        lines.append(cur)
        if len(lines) > 2:   # long sentence: balance into two lines
            words, half = text.split(), len(text) / 2
            acc, cut = 0, 0
            for k, w in enumerate(words):
                acc += len(w) + 1
                if acc >= half:
                    cut = k + 1
                    break
            lines = [" ".join(words[:cut]), " ".join(words[cut:])]
            f = font(F_ROBOTO, 40 if max(tmp.textlength(l, font=f) for l in lines) <= SUB_W + 100 else 34)
        im = Image.new("RGBA", (SUB_W + 260, 130), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for k, l in enumerate(lines):
            dr.text((im.width / 2, 30 + k * 54 + (27 if len(lines) == 1 else 0)), l, font=f, fill="white", anchor="mm",
                    stroke_width=4, stroke_fill=(0, 0, 0, 230))
        return im

    def big_title(self, key, title, sub, size=118):
        return self.text_img(("big", key), lambda: self._big(title, sub, size))

    def _big(self, title, sub, size):
        im = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((W / 2 + 4, 160 + 5), title, font=font(F_ANTON, size), fill=(0, 0, 0, 150), anchor="mm")
        dr.text((W / 2, 160), title, font=font(F_ANTON, size), fill="white", anchor="mm")
        if sub:
            dr.text((W / 2, 280), sub, font=font(F_UI, 52), fill=(150, 220, 255), anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        return im

    def logo(self, h):
        return self.text_img(("logo", h), lambda: self._logo(h))

    def _logo(self, h):
        im = Image.open(YT_ASSETS / "logo.png").convert("RGB")
        im = im.resize((h, h), Image.LANCZOS).convert("RGBA")
        return im

    # -- composition
    def frame(self, t):
        b = block_at(self.blocks, t)
        if b["kind"] == "cold":
            return self.cold(t)
        d = depth_at(b, t, self.j)
        lt = t - b["t0"]
        mech = self.mech
        bg = getattr(mech, "background", None)
        fr = bg(d, t, b) if bg else self.background(d, t)
        img = fr.convert("RGB") if isinstance(fr, Image.Image) else Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8))
        if mech:
            mech.draw(img, t, b, lt, lambda: self.content(img, t, b, lt, d))
        else:
            self.content(img, t, b, lt, d)
        if "subs" in b and getattr(mech, "subtitles", True):
            vt = t - b["voice"]
            for s0, s1, txt in b["subs"]:
                if s0 - 0.05 <= vt <= s1 + 0.25:
                    self.paste(img, self.subtitle(txt), (SUB_CX - (SUB_W + 260) // 2, SUB_Y - 30), 1.0)
                    break
        return img

    def content(self, img, t, b, lt, d):
        """The standard layer: meter, zone/rank titles, photo cards, montages, end screen."""
        meter_a = 1.0 if t > COLD_OPEN + 1.5 else ease((t - COLD_OPEN) / 1.5)
        if b["kind"] != "end" and self.j.get("meter", True):
            seg_stats = b["seg"].get("stats") if "seg" in b else None
            if seg_stats is None and self.j["stats"] == []:
                seg_stats = []
            self.paste(img, self.meter(d, seg_stats), (0, 0), meter_a)
        k = b["kind"]
        if k == "travel" and big_jump(b["d0"], b["d1"], self.j, 0.0046, 0.05):
            big = self.big_title(("travel", self.fmt_pos(d)), self.fmt_pos(d), None, 150)
            a = math.sin(math.pi * min(1, lt / b["dur"])) * 0.28
            self.paste(img, big, (CARD[0] // 2 - 120, 300), a)
        elif k == "zone":
            s = b["seg"]
            a = ease(lt / 0.9) * (1 - 0.65 * ease((lt - 6) / 1.5))
            self.paste(img, self.big_title(("zone", s["name"]), s["name"], s["range"]), (OFFX, 230), a)
        elif k == "rank":
            a = ease(lt / 0.4) * ease((b["dur"] - lt) / 0.4)
            self.paste(img, self.big_title(("rank", b["rank"]), f"#{b['rank']}", None, 260), (OFFX, 200), a)
        elif k in ("creature", "landmark"):
            self.card(img, b, lt)
        elif k in ("intro", "outro"):
            self.montage(img, b, lt, self.montage_keys(k))
        elif k == "end":
            self.end(img, lt)

    def paste(self, img, over, xy, a):
        if a <= 0.01:
            return
        if a < 0.999:
            over = over.copy()
            over.putalpha(over.getchannel("A").point(lambda v: int(v * a)))
        img.alpha_composite(over, xy) if img.mode == "RGBA" else img.paste(over, xy, over)

    def card_photo_frame(self, keys, lt, dur, crossfade=0.8):
        n = len(keys)
        each = dur / n
        k = min(int(lt / each), n - 1)
        x = (lt - k * each) / each
        ph = self.kenburns(keys[k], x, k)
        if k + 1 < n and lt > (k + 1) * each - crossfade:
            nxt = self.kenburns(keys[k + 1], 0.0, k + 1)
            ph = Image.blend(ph, nxt, ease((lt - ((k + 1) * each - crossfade)) / crossfade))
        return ph, k

    def place_card(self, img, ph, alpha, overlays=()):
        mask, shadow, border, grad = self.card_chrome()
        x, y = CARD[0], CARD[1]
        sh = shadow.point(lambda v: int(v * alpha))
        black = Image.new("RGB", shadow.size, (0, 0, 0))
        img.paste(black, (x - 60, y - 60), sh)
        layer = ph.convert("RGBA")
        layer.alpha_composite(grad)
        for o, pos in overlays:
            layer.alpha_composite(o, pos)
        layer.alpha_composite(border)
        m = mask if alpha >= 0.999 else mask.point(lambda v: int(v * alpha))
        img.paste(layer.convert("RGB"), (x, y), m)

    def card(self, img, b, lt):
        s, key = b["seg"], f"{b['i']:02d}"
        alpha = ease(lt / 0.6) * ease((b["dur"] - lt) / 0.6)
        metas = self.photos.get(key)
        if not metas:   # landmark without photo: big centred value
            a = alpha
            self.paste(img, self.big_title(("lm", s["name"]), s["value"], tr_upper(s["name"]), 170), (OFFX, 230), a)
            return
        keys = [m["file"][:-4] for m in metas]
        ph, k = self.card_photo_frame(keys, lt, b["dur"])
        cr = self.credit(metas[k])
        self.place_card(img, ph, alpha, [(self.plate(s), (0, 0)), (cr, (CARD[2] - cr.width - 18, 16))])

    def montage_keys(self, kind):
        keys = self.spec.get(f"{kind}_photos")
        if not keys:   # default: first photo of every creature, spread evenly
            keys = [ms[0]["file"][:-4] for i, ms in sorted(self.photos.items())
                    if ms and self.spec["segments"][int(i)]["type"] == "creature"]
            step = max(1, len(keys) // 9)
            keys = keys[::step][:10] if kind == "intro" else keys[::-step][:10]
        return keys

    def montage(self, img, b, lt, keys):
        keys = [k for k in keys if (self.doc / "photos" / f"{k}.jpg").exists()]
        alpha = ease(lt / 0.8) * ease((b["dur"] - lt) / 0.8)
        ph, k = self.card_photo_frame(keys, lt, b["dur"], 1.0)
        meta = next((m for m in self.photos.get(keys[k][:2], []) if m["file"] == keys[k] + ".jpg"), None)
        ov = [(self.credit(meta), (CARD[2] - self.credit(meta).width - 18, 16))] if meta else []
        self.place_card(img, ph, alpha, ov)

    def end(self, img, lt):
        a = ease(lt / 1.0)
        lg = self.logo(150)
        self.paste(img, lg, ((W - lg.width) // 2, 120), a)
        t = self.text_img("endtxt", lambda: self._end_text())
        self.paste(img, t, (0, 300), a)

    def _end_text(self):
        im = Image.new("RGBA", (W, 760), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((W / 2, 40), "TERRA WILD NATURE", font=font(F_ANTON, 96), fill="white", anchor="mm")
        dr.text((W / 2, 130), "İzlediğiniz için teşekkürler", font=font(F_UI, 46), fill=(150, 220, 255), anchor="mm")
        for k, r in enumerate([(360, 520), (1560, 520)]):   # end-screen slots for YouTube's video elements
            dr.rounded_rectangle((r[0] - 300, r[1] - 170, r[0] + 300, r[1] + 170), 24, outline=(150, 220, 255, 90), width=3)
        dr.text((W / 2, 470), "ABONE OL", font=font(F_ANTON, 64), fill=(255, 205, 70), anchor="mm")
        dr.ellipse((W / 2 - 90, 520, W / 2 + 90, 700), outline=(255, 205, 70, 160), width=4)
        dr.text((W / 2, 745), "Görseller: Wikimedia Commons ve iNaturalist katkıcıları (tam liste açıklamada) · "
                "Müzik: Kevin MacLeod (CC BY) · Seslendirme: yapay zekâ", font=font(F_ROBOTO, 22),
                fill=(190, 210, 225), anchor="mb")
        return im

    def cold(self, t):
        if not self.has_3d():
            return self.cold_photos(t)
        f = t * FPS
        i0 = int(f // 2 * 2)
        a = THREE_D / f"{min(i0, 358):04d}.png"
        b = THREE_D / f"{min(i0 + 2, 358):04d}.png"
        im = Image.open(a).convert("RGB")
        if (f - i0) > 0.01 and b.exists():
            im = Image.blend(im, Image.open(b).convert("RGB"), (f - i0) / 2)
        if im.size != (W, H):
            im = im.resize((W, H), Image.LANCZOS)
        im = im.convert("RGBA")
        a1 = ease((t - 2.0) / 1.2) * (1 - ease((t - 10.6) / 1.0))
        self.paste(im, self.big_title("cold", self.spec["title"], self.spec["subtitle"], 128), (0, 300), a1)
        lg = self.logo(60)
        self.paste(im, lg, (48, 40), ease((t - 1.0) / 1.0))
        im = im.convert("RGB")
        if t < 0.8:
            im = Image.blend(Image.new("RGB", (W, H)), im, t / 0.8)
        if t > COLD_OPEN - 1.0:   # dissolve into the surface water
            bg = Image.fromarray(np.clip(self.background(0, t), 0, 255).astype(np.uint8))
            im = Image.blend(im, bg, ease((t - (COLD_OPEN - 1.0)) / 1.0))
        return im


    def has_3d(self):
        return self.spec.get("cold_3d", False) and (THREE_D / "0000.png").exists()

    def cold_photos(self, t):
        """Full-screen Ken Burns over the intro photos with the title, dissolving into the journey background."""
        keys = self.montage_keys("intro")[:4]
        each = COLD_OPEN / len(keys)
        k = min(int(t / each), len(keys) - 1)
        im = self.fullscreen(keys[k], (t - k * each) / each, k)
        if k + 1 < len(keys) and t > (k + 1) * each - 0.7:
            im = Image.blend(im, self.fullscreen(keys[k + 1], 0.0, k + 1), ease((t - ((k + 1) * each - 0.7)) / 0.7))
        im = Image.blend(im, Image.new("RGB", (W, H)), 0.35).convert("RGBA")
        a1 = ease((t - 1.5) / 1.2) * (1 - ease((t - 10.6) / 1.0))
        self.paste(im, self.big_title("cold", self.spec["title"], self.spec["subtitle"], 128), (0, 300), a1)
        self.paste(im, self.logo(60), (48, 40), ease((t - 1.0) / 1.0))
        im = im.convert("RGB")
        if t < 0.8:
            im = Image.blend(Image.new("RGB", (W, H)), im, t / 0.8)
        if t > COLD_OPEN - 1.0:
            first = self.spec["segments"][0]["depth"]
            bg = Image.fromarray(np.clip(self.background(first, t), 0, 255).astype(np.uint8))
            im = Image.blend(im, bg, ease((t - (COLD_OPEN - 1.0)) / 1.0))
        return im

    def fullscreen(self, key, x, n):
        im = self.photo(key)
        base = min(im.width / W, im.height / H)
        z = (1.0 + 0.1 * x) if n % 2 == 0 else (1.1 - 0.1 * x)
        w, h = W * base / z, H * base / z
        x0 = (im.width - w) / 2 + (0.03 if n % 2 else -0.03) * im.width * (x - 0.5)
        x0 = min(max(x0, 0), im.width - w)
        y0 = min(max(im.height * 0.47 - h / 2, 0), im.height - h)
        return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + w, y0 + h))


# ---------------------------------------------------------------- render
_scene = None


def _init(doc):
    global _scene
    spec, blocks, _ = timeline(doc)
    _scene = Scene(doc, spec, blocks)


def frame_rgb(t):
    im = _scene.frame(t)
    return im.convert("RGB")


def render_part(args):
    doc, k, f0, f1 = args
    out = doc / "out" / f"part_{k:03d}.mp4"
    if out.exists():
        return str(out)
    tmp = out.with_suffix(".tmp.mp4")
    p = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-threads", "2",
                          "-pix_fmt", "yuv420p", str(tmp)], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        p.stdin.write(frame_rgb(f / FPS).tobytes())
    p.stdin.close()
    p.wait()
    tmp.rename(out)
    return str(out)


def audio(doc, blocks, total):
    out = doc / "out" / "audio.m4a"
    music = ASSETS / "music"
    voices = [b for b in blocks if "voice" in b]
    t_deep = music_switch(blocks, total)
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for b in voices:
        cmd += ["-i", str(doc / "voice" / f"{b['i']:02d}.mp3")]
    m1, m2 = MUSIC
    cmd += ["-stream_loop", "-1", "-i", str(music / m1), "-stream_loop", "-1", "-i", str(music / m2)]
    n = len(voices)
    fl = []
    for k, b in enumerate(voices):
        ms = int(b["voice"] * 1000)
        fl.append(f"[{k}:a]aresample=48000,adelay={ms}|{ms}[v{k}]")
    fl.append("".join(f"[v{k}]" for k in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,apad=whole_dur={total:.2f},"
              f"atrim=0:{total:.2f},volume=1.6[vo]")
    fl.append(f"[{n}:a]aresample=48000,loudnorm=I=-20:TP=-2,atrim=0:{t_deep + 3:.2f},afade=t=in:d=1,afade=t=out:st={t_deep - 3:.2f}:d=6[ma]")
    dl = int((t_deep - 3) * 1000)
    fl.append(f"[{n + 1}:a]aresample=48000,loudnorm=I=-20:TP=-2,atrim=0:{total - t_deep + 3:.2f},afade=t=in:d=6,"
              f"afade=t=out:st={total - t_deep + 3 - 6:.2f}:d=6,adelay={dl}|{dl}[mb]")
    fl.append(f"[ma][mb]amix=inputs=2:normalize=0:duration=longest,atrim=0:{total:.2f},volume='if(lt(t,{COLD_OPEN}),1.0,0.30)':eval=frame[mus]")
    fl.append("[vo]asplit=2[vo1][vsc]")
    fl.append("[mus][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=80:release=900[mduck]")
    fl.append("[vo1][mduck]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]")
    cmd += ["-filter_complex", ";".join(fl), "-map", "[out]", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", str(out)]
    subprocess.run(cmd, check=True)
    return out


MUSIC = OCEAN["music"]


def music_switch(blocks, total):
    """Second track starts at the zone marked "music_switch" (default: the zone closest to the middle)."""
    zones = [b for b in blocks if b["kind"] == "zone"]
    marked = [b for b in zones if b["seg"].get("music_switch")]
    if marked:
        return marked[0]["t0"]
    return min(zones, key=lambda b: abs(b["t0"] - total / 2))["t0"] if zones else total / 2


def chapters(doc, blocks):
    lines = ["00:00 Giriş"]
    for b in blocks:
        s = b.get("seg")
        if not s:
            continue
        t = int(b["t0"])
        if b["kind"] == "zone":
            lines.append(f"{t // 60:02d}:{t % 60:02d} {tr_title(s['name'])} ({s['range']})")
        elif b["kind"] == "creature" or (b["kind"] == "landmark" and s.get("chapter")):
            name = s["name"] + (f" ({s['value']})" if b["kind"] == "landmark" else "")
            if s.get("rank") is not None:
                name = f"#{s['rank']} {name}"
            lines.append(f"{t // 60:02d}:{t % 60:02d} {name}")
    out, last = [], -99
    for l in lines:   # YouTube needs >= 10 s between chapters
        m, sec = l.split(" ", 1)[0].split(":")
        tt = int(m) * 60 + int(sec)
        if tt - last >= 10:
            out.append(l)
            last = tt
    return out


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def main():
    global MUSIC
    doc = Path(sys.argv[1]).resolve()
    (doc / "out").mkdir(exist_ok=True)
    spec, blocks, total = timeline(doc)
    MUSIC = spec["journey"]["music"]
    print(f"total {total / 60:.1f} min, {len(blocks)} blocks")
    if "--preview" in sys.argv:   # 12 moments: cold open, intro, zones, creatures, landmarks, outro, end
        _init(doc)
        pick = [b for b in blocks if b["kind"] not in ("travel",)]
        step = max(1, len(pick) // 11)
        times = [b["t0"] + min(b["dur"] * 0.55, b["dur"] - 0.1) for b in pick[::step]][:12]
        sheet = Image.new("RGB", (4 * 480, 3 * 270 + 3 * 30), (20, 20, 20))
        dr = ImageDraw.Draw(sheet)
        for k, tt in enumerate(times):
            b = block_at(blocks, tt)
            x, y = k % 4 * 480, k // 4 * 300
            sheet.paste(frame_rgb(tt).resize((480, 270), Image.LANCZOS), (x, y + 30))
            dr.text((x + 6, y + 6), f"{tt:.0f}s {b['kind']} {b.get('seg', {}).get('name', '')}"[:60], font=font(F_UI, 20), fill="white")
        sheet.save(doc / "out" / "preview.jpg", quality=85)
        print(f"OK {doc / 'out' / 'preview.jpg'}  (times: {', '.join(f'{x:.0f}' for x in times)})")
        return
    if "--stills" in sys.argv:
        _init(doc)
        for s in arg("--stills").split(","):
            frame_rgb(float(s)).save(doc / "out" / f"still_{float(s):07.1f}.jpg", quality=88)
        return
    (doc / "out" / "chapters.txt").write_text("\n".join(chapters(doc, blocks)), encoding="utf-8")
    (doc / "out" / "info.json").write_text(json.dumps({"duration": total}), encoding="utf-8")
    if "--info" in sys.argv:
        return
    nf = int(total * FPS)
    step = 900
    jobs = [(doc, k, f0, min(f0 + step, nf)) for k, f0 in enumerate(range(0, nf, step))]
    if "--assemble" not in sys.argv:
        jobs_now = jobs
        if arg("--shard"):
            k, n = map(int, arg("--shard").split("/"))
            jobs_now = [j for j in jobs if j[1] % n == k]
        with Pool(int(arg("--workers", 7)), initializer=_init, initargs=(doc,)) as pool:
            for k, p in enumerate(pool.imap_unordered(render_part, jobs_now)):
                print(f"part {k + 1}/{len(jobs_now)}", flush=True)
        if arg("--shard"):
            return
    missing = [j[1] for j in jobs if not (doc / "out" / f"part_{j[1]:03d}.mp4").exists()]
    if missing:
        raise SystemExit(f"missing parts: {missing}")
    lst = doc / "out" / "parts.txt"
    lst.write_text("".join(f"file '{j[0] / 'out' / f'part_{j[1]:03d}.mp4'}'\n".replace("\\", "/") for j in jobs), encoding="utf-8")
    a = audio(doc, blocks, total)
    final = doc / "out" / "belgesel.mp4"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(a),
                    "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    print(f"OK {final}")


if __name__ == "__main__":
    main()
