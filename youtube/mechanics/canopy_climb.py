"""Canopy climb: a rope climb up a giant rainforest tree, from the dark forest floor to the top of the emergent layer.

On the right stands a cross-section of the rainforest drawn in code: a giant emergent tree with buttress roots, a
straight trunk and a crown that breaks through the canopy into open sky, surrounded by the layers of the forest
(forest floor, understory, canopy, emergent layer), each a coloured band with its name and its height range. A
climber in an orange helmet hangs on a rope from the crown and climbs with the story; a tag beside the climber shows
the current height in metres. Every animal we meet is pinned to the cross-section at the height where it lives as a
round portrait, so the tree slowly fills with its inhabitants from the roots to the crown.
The background is the forest itself: almost black-green, misty and dim at the floor, layered foliage with slanting
sun shafts in the middle and bright open sky above the canopy, with leaves drifting down the whole time.
Zones show a "KATMAN n / 4" panel with the share of sunlight that reaches them; landmarks are "BOY KIYASI" cards.

script.json:
  "mechanic": "canopy_climb",
  "journey": {"meter": false, "max": 101, "unit": "m", "card": [40, 96, 1232, 693], "sub_cx": 656, ...}
  segment "depth" = height above the forest floor in metres (always ascending).
  zone segments may add "light": "%2" (share of sunlight); creatures/landmarks may add "short" (name on the tree).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

PX0, PX1 = 1296, 1904          # cross-section panel
TRUNK_X = 1600
HB = [0, 2, 30, 45, 101]       # height breakpoints (zone limits)
YB = [1030, 872, 600, 400, 128]  # screen y of those heights
ZCOL = [(150, 105, 60), (70, 150, 80), (60, 200, 90), (120, 200, 255)]   # band colours per zone

# background colour (top, bottom) by height
BG = [(0, (22, 34, 20), (8, 12, 8)), (2, (26, 48, 28), (10, 18, 10)), (30, (34, 82, 44), (14, 34, 18)),
      (45, (70, 130, 120), (26, 70, 40)), (101, (120, 185, 230), (60, 120, 90))]


def hy(h):
    """Height (m) -> screen y on the cross-section."""
    return float(np.interp(h, HB, YB))


def bg_cols(h):
    hs = [b[0] for b in BG]
    top = np.array([np.interp(h, hs, [b[1][k] for b in BG]) for k in range(3)], np.float32)
    bot = np.array([np.interp(h, hs, [b[2][k] for b in BG]) for k in range(3)], np.float32)
    return top, bot


def fmt_h(h):
    if (h < 10 or h > 99) and abs(h - round(h)) > 0.05:
        return R.fmt_num(h, 1) + " m"
    return R.fmt_num(round(h), 0) + " m"


class Mechanic:
    subtitles = False             # own subtitles: narrower, centred under the photo card

    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        self.yy = np.linspace(0, 1, R.H, dtype=np.float32)[:, None, None]
        rng = np.random.default_rng(23)
        # foliage texture: dark leaf clusters, blurred; fades in with the canopy
        im = Image.new("L", (R.W // 2, R.H // 2), 0)
        dr = ImageDraw.Draw(im)
        for _ in range(420):
            x, y = rng.uniform(0, R.W // 2), rng.uniform(0, R.H // 2)
            a = rng.uniform(0, math.pi)
            L, w = rng.uniform(10, 34), rng.uniform(4, 11)
            pts = [(x + math.cos(a + q) * L * (1 if q == 0 or q == math.pi else 0.0) + math.cos(a + math.pi / 2) * w * s,
                    y + math.sin(a + q) * L * (1 if q == 0 or q == math.pi else 0.0) + math.sin(a + math.pi / 2) * w * s)
                   for q, s in ((0, 0), (math.pi / 2, 1), (math.pi, 0), (math.pi / 2, -1))]
            dr.polygon(pts, fill=int(rng.uniform(80, 220)))
        self.leaves = (np.asarray(im.filter(ImageFilter.GaussianBlur(2.2)).resize((R.W, R.H), Image.BILINEAR),
                                  np.float32) / 255.0)[..., None]
        # mist bands near the floor
        xx = np.linspace(0, 1, R.W, dtype=np.float32)[None, :]
        self.mist = ((0.5 + 0.5 * np.sin(xx * 9.0)) * np.clip((self.yy[..., 0] - 0.45) / 0.55, 0, 1))[..., None]
        self.fall = rng.uniform(0, 1, (70, 5))      # falling leaves: x, y, size, speed, colour
        self.ports = {}

    # ------------------------------------------------------------------ background: the forest itself
    def background(self, d, t, b):
        top, bot = bg_cols(d)
        frame = top[None, None, :] * (1 - self.yy) + bot[None, None, :] * self.yy
        frame = np.broadcast_to(frame, (R.H, R.W, 3)).copy()
        dense = float(np.interp(d, [0, 2, 20, 40, 60, 101], [0.55, 0.7, 0.85, 0.75, 0.35, 0.12]))
        frame *= (1 - self.leaves * dense * 0.55)                       # layered foliage
        sun = float(np.interp(d, [0, 2, 30, 45, 101], [0.10, 0.18, 0.45, 0.8, 0.6]))
        off = int(t * 14) % R.W
        frame += self.s.rays[:, off:off + R.W, None] * sun * 150 * np.array([1.0, 0.95, 0.7], np.float32)
        mist = float(np.interp(d, [0, 2, 10, 101], [0.55, 0.45, 0.1, 0.0]))
        if mist > 0.01:
            m = np.roll(self.mist, int(t * 9) % R.W, axis=1)
            frame += m * mist * 60 * np.array([0.8, 0.95, 0.85], np.float32)
        frame *= self.s.vign
        for x, y, sz, sp, c in self.fall:
            px = (x * R.W + math.sin(t * (0.6 + sp) + y * 17) * 40) % R.W
            py = (y * R.H + t * 30 * (0.4 + sp)) % R.H
            col = (0.5, 0.9, 0.35) if c < 0.6 else (1.0, 0.8, 0.3)
            self.s.add(frame, px, py, 2 if sz < 0.7 else 3, 120 * (0.4 + 0.6 * sz), col)
        return frame

    # ------------------------------------------------------------------ the cross-section
    def section(self):
        return self.s.text_img("section", self._section)

    def _section(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((PX0, 40, PX1, 1060), 34, fill=(4, 10, 6, 150), outline=(190, 240, 200, 60), width=2)
        zones = self.j["zones"]
        # layer bands
        for k, (a, b, name) in enumerate(zones):
            y0, y1 = hy(b), hy(a)
            c = ZCOL[k % len(ZCOL)]
            dr.rectangle((PX0 + 2, y0, PX1 - 2, y1), fill=c + (26,))
            dr.line((PX0 + 14, y0, PX1 - 14, y0), fill=c + (120,), width=2)
            dr.rectangle((PX1 - 26, y0 + 3, PX1 - 16, y1 - 3), fill=c + (220,))
        # ground and soil
        gy = hy(0)
        dr.rectangle((PX0 + 2, gy, PX1 - 2, 1058), fill=(52, 34, 20, 235))
        for k in range(26):
            x = PX0 + 20 + k * 23
            dr.line((x, gy + 6, x + 9, gy + 6), fill=(120, 80, 40, 200), width=3)
        # understory shrubs and small trees
        rng = np.random.default_rng(7)
        for x in (1352, 1450, 1730, 1830):
            h = rng.uniform(8, 24)
            ty = hy(h)
            dr.line((x, gy, x, ty), fill=(70, 50, 32, 230), width=6)
            for q in range(5):
                rx, ry = rng.uniform(-38, 38), rng.uniform(-22, 18)
                r = rng.uniform(18, 30)
                dr.ellipse((x + rx - r, ty + ry - r * 0.7, x + rx + r, ty + ry + r * 0.7), fill=(40, 110, 50, 200))
        # canopy trees on both sides
        for x, h in ((1390, 38), (1790, 41), (1470, 33)):
            ty = hy(h)
            dr.line((x, gy, x, ty + 20), fill=(78, 56, 36, 235), width=11)
            for q in range(9):
                rx, ry = rng.uniform(-55, 55), rng.uniform(-30, 30)
                r = rng.uniform(30, 48)
                dr.ellipse((x + rx - r, ty + ry - r * 0.6, x + rx + r, ty + ry + r * 0.6),
                           fill=(30 + int(rng.uniform(0, 30)), 120 + int(rng.uniform(0, 50)), 55, 225))
        # the giant emergent tree: buttress roots, trunk, branches, crown
        top = hy(97)
        dr.polygon([(TRUNK_X - 70, gy), (TRUNK_X - 14, gy - 70), (TRUNK_X + 14, gy - 70), (TRUNK_X + 70, gy)],
                   fill=(96, 70, 44, 255))
        dr.polygon([(TRUNK_X - 16, gy - 60), (TRUNK_X - 7, top + 40), (TRUNK_X + 7, top + 40), (TRUNK_X + 16, gy - 60)],
                   fill=(110, 82, 52, 255))
        dr.line((TRUNK_X - 4, gy - 60, TRUNK_X - 2, top + 50), fill=(150, 118, 80, 255), width=3)
        for (h, s, L) in ((60, -1, 110), (70, 1, 120), (80, -1, 90), (86, 1, 80)):
            y = hy(h)
            dr.line((TRUNK_X, y, TRUNK_X + s * L, y - 40), fill=(110, 82, 52, 255), width=7)
        for q in range(16):
            rx, ry = rng.uniform(-150, 150), rng.uniform(-22, 40)
            r = rng.uniform(36, 56)
            dr.ellipse((TRUNK_X + rx - r, top + ry - r * 0.55, TRUNK_X + rx + r, top + ry + r * 0.55),
                       fill=(40 + int(rng.uniform(0, 40)), 140 + int(rng.uniform(0, 50)), 60, 235))
        # layer names on top of the trees, on dark pills
        for k, (a, b, name) in enumerate(zones):
            y0 = hy(b)
            c = ZCOL[k % len(ZCOL)]
            f = R.font(R.F_UI, 22)
            rng_txt = f"{R.fmt_num(a, 0)}–{R.fmt_num(min(b, 100), 0)} m"
            w = max(dr.textlength(name, font=f), dr.textlength(rng_txt, font=R.font(R.F_UI, 18))) + 24
            dr.rounded_rectangle((PX1 - 36 - w, y0 + 6, PX1 - 30, y0 + 62), 12, fill=(4, 12, 6, 200))
            dr.text((PX1 - 42, y0 + 12), name, font=f, fill=(235, 245, 235, 245), anchor="ra")
            dr.text((PX1 - 42, y0 + 40), rng_txt, font=R.font(R.F_UI, 18), fill=c + (240,), anchor="ra")
        # height scale on the left edge
        f = R.font(R.F_UI, 18)
        for v in (0, 2, 10, 20, 30, 40, 45, 60, 80, 100):
            y = hy(v)
            dr.line((PX0 + 10, y, PX0 + 26, y), fill=(235, 245, 235, 200), width=2)
            dr.text((PX0 + 32, y), f"{v} m", font=f, fill=(235, 245, 235, 200), anchor="lm")
        dr.text(((PX0 + PX1) / 2, 62), "YAĞMUR ORMANI KESİTİ", font=R.font(R.F_ANTON, 30), fill=(235, 245, 235, 235),
                anchor="mm")
        return im

    def portrait(self, i, size):
        k = (i, size)
        if k not in self.ports:
            metas = self.s.photos.get(f"{i:02d}")
            m = metas[0]
            seg = self.s.spec["segments"][i]
            im = Image.open(self.s.doc / "photos" / m["file"]).convert("RGB")
            cx, cy = seg.get("pcx", 0.5), seg.get("pcy", 0.5)
            c = min(im.size) * seg.get("pz", 0.8)
            x0 = min(max(im.width * cx - c / 2, 0), im.width - c)
            y0 = min(max(im.height * cy - c / 2, 0), im.height - c)
            im = im.resize((size, size), Image.LANCZOS, box=(x0, y0, x0 + c, y0 + c)).convert("RGBA")
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
            im.putalpha(mask)
            self.ports[k] = im
        return self.ports[k]

    def slot(self, b):
        """Where an animal is pinned: x cycles across the panel so neighbours do not overlap."""
        n = self.cr.index(b)
        xs = [1350, 1650, 1420, 1680, 1500, 1380, 1630, 1460]
        return xs[n % len(xs)], hy(b["seg"]["depth"])

    def pins(self, img, now, show_now, cur):
        items = [b for b in self.cr if b["i"] < now or (b["i"] == now and show_now)]
        if not items:
            return
        key = ("pins", tuple(b["i"] for b in items), cur)
        self.s.paste(img, self.s.text_img(key, lambda: self._pins(items, cur)), (0, 0), 1.0)

    def _pins(self, items, cur):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for b in items:
            x, y = self.slot(b)
            on = b["i"] == cur
            r = 34 if on else 23
            dr.line((x, y, TRUNK_X + (-8 if x < TRUNK_X else 8), y), fill=(255, 255, 255, 70), width=1)
            dr.ellipse((x - r - 4, y - r - 4, x + r + 4, y + r + 4), fill=(255, 200, 60, 255) if on else (240, 245, 240, 220))
            im.alpha_composite(self.portrait(b["i"], 2 * r), (int(x - r), int(y - r)))
            if on:
                name = R.tr_upper(b["seg"].get("short", b["seg"]["name"]))
                f = R.font(R.F_UI, 22)
                tw = dr.textlength(name, font=f)
                lx = min(max(x - tw / 2 - 12, PX0 + 6), PX1 - tw - 30)
                dr.rounded_rectangle((lx, y + r + 8, lx + tw + 24, y + r + 40), 12, fill=(255, 200, 60, 240))
                dr.text((lx + 12, y + r + 24), name, font=f, fill=(20, 24, 16), anchor="lm")
        return im

    def climber(self, img, d, t):
        dr = ImageDraw.Draw(img)
        y = hy(d)
        x = TRUNK_X - 26
        dr.line((x, hy(97) + 30, x, y - 16), fill=(250, 240, 210), width=2)       # rope from the crown
        sway = math.sin(t * 1.7) * 2
        dr.ellipse((x - 9 + sway, y - 24, x + 9 + sway, y - 8), fill=(255, 140, 30))     # helmet
        dr.rectangle((x - 7 + sway, y - 8, x + 7 + sway, y + 12), fill=(40, 120, 200))  # body
        dr.line((x - 7 + sway, y + 12, x - 11 + sway, y + 24), fill=(40, 60, 90), width=4)
        dr.line((x + 7 + sway, y + 12, x + 11 + sway, y + 24), fill=(40, 60, 90), width=4)
        tag = self.s.text_img(("htag", fmt_h(d)), lambda: self._tag(fmt_h(d)))
        self.s.paste(img, tag, (int(x - tag.width - 18), int(y - tag.height / 2)), 1.0)

    def _tag(self, txt):
        f = R.font(R.F_ANTON, 40)
        w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(txt, font=f)) + 44
        im = Image.new("RGBA", (w, 58), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 14, 57), 14, fill=(255, 140, 30, 245))
        dr.polygon([(w - 15, 18), (w - 1, 29), (w - 15, 40)], fill=(255, 140, 30, 245))
        dr.text((16, 29), txt, font=f, fill="white", anchor="lm")
        return im

    # ------------------------------------------------------------------ card-area panels
    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zones = self.j["zones"]
        k = next((n for n, z in enumerate(zones) if z[2] == seg["name"]), 0)
        c = ZCOL[k % len(ZCOL)]
        dr.rounded_rectangle((30, 40, cw - 30, ch - 40), 34, fill=(4, 12, 6, 170), outline=c + (180,), width=3)
        dr.text((cw / 2, 120), f"KATMAN {k + 1} / {len(zones)}", font=R.font(R.F_UI, 38), fill=c, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 120:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 5, 270 + 6), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, 270), seg["name"], font=f, fill="white", anchor="mm")
        dr.text((cw / 2, 400), seg["range"], font=R.font(R.F_ANTON, 64), fill=c, anchor="mm")
        # four-layer strip with this layer lit
        x0, y0, w = cw / 2 - 360, 470, 720
        for n in range(len(zones)):
            cc = ZCOL[n % len(ZCOL)]
            a = 255 if n == k else 70
            dr.rounded_rectangle((x0 + n * w / len(zones) + 4, y0, x0 + (n + 1) * w / len(zones) - 4, y0 + 22), 8,
                                 fill=cc + (a,))
        if seg.get("light"):
            txt = f"GÜNEŞ IŞIĞININ {seg['light']}'Sİ ULAŞIYOR"
            ff = R.font(R.F_UI, 40)
            dr.text((cw / 2, 560), txt, font=ff, fill=(255, 220, 120), anchor="mm")
        elif seg.get("note"):
            dr.text((cw / 2, 560), seg["note"], font=R.font(R.F_UI, 40), fill=(255, 220, 120), anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        c = (255, 170, 60)
        dr.rounded_rectangle((60, 60, cw - 60, ch - 60), 30, fill=(10, 16, 8, 195), outline=c + (210,), width=4)
        dr.rounded_rectangle((60, 60, cw - 60, 160), 30, fill=c + (235,))
        dr.rectangle((60, 130, cw - 60, 160), fill=c + (235,))
        dr.text((cw / 2, 110), seg.get("tag", "BOY KIYASI"), font=R.font(R.F_ANTON, 50), fill=(20, 16, 8), anchor="mm")
        f = R.font(R.F_ANTON, 200)
        while dr.textlength(seg["value"], font=f) > cw - 200:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 20), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 52)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 200:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 140), name, font=f2, fill=(235, 240, 230), anchor="mm")
        return im

    # ------------------------------------------------------------------ subtitles
    def sub(self, text):
        return self.s.text_img(("csub", text), lambda: self._sub(text))

    def _sub(self, text):
        maxw = 1180
        tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
        for size in (40, 37, 34, 31):
            f = R.font(R.F_ROBOTO, size)
            lines, cur = [], ""
            for w in text.split():
                nxt = (cur + " " + w).strip()
                if tmp.textlength(nxt, font=f) > maxw and cur:
                    lines.append(cur)
                    cur = w
                else:
                    cur = nxt
            lines.append(cur)
            if len(lines) <= 2 or size == 31:
                break
        step = int(size * 1.3)
        im = Image.new("RGBA", (maxw + 40, step * len(lines) + 20), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for k, l in enumerate(lines):
            dr.text((im.width / 2, 10 + step * k + step / 2), l, font=f, fill="white", anchor="mm",
                    stroke_width=4, stroke_fill=(0, 0, 0, 230))
        return im

    def subtitle(self, img, t, b):
        if "subs" not in b:
            return
        vt = t - b["voice"]
        for s0, s1, txt in b["subs"]:
            if s0 - 0.05 <= vt <= s1 + 0.25:
                im = self.sub(txt)
                cx = R.CARD[0] + R.CARD[2] // 2
                self.s.paste(img, im, (cx - im.width // 2, 905 - im.height // 2), 1.0)
                break

    # ------------------------------------------------------------------ frame
    def draw(self, img, t, b, lt, default):
        k = b["kind"]
        if k == "end":
            default()
            return
        self._draw(img, t, b, lt, default)
        self.subtitle(img, t, b)

    def _draw(self, img, t, b, lt, default):
        k = b["kind"]
        d = R.depth_at(b, t, self.j)
        alpha = R.ease(lt / 0.6) * R.ease((b["dur"] - lt) / 0.6)
        if k in ("creature", "intro", "outro"):
            default()
        elif k == "landmark":
            if self.s.photos.get(f"{b['i']:02d}") and lt > 4.0:
                default()
            else:
                self.s.paste(img, self.landmark_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        elif k == "zone":
            self.s.paste(img, self.zone_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        pa = 1.0 if t > R.COLD_OPEN + 1.2 else R.ease((t - R.COLD_OPEN) / 1.2)
        if pa < 0.999:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            self._instrument(layer, t, d, b, k)
            self.s.paste(img, layer, (0, 0), pa)
        else:
            self._instrument(img, t, d, b, k)

    def _instrument(self, img, t, d, b, k):
        self.s.paste(img, self.section(), (0, 0), 1.0)
        now = b.get("i", -1)
        show = k == "creature" and t - b["t0"] > 0.3
        cur = now if k == "creature" else None
        if k == "outro":
            now, show = 10 ** 6, True
        self.pins(img, now, show, cur)
        self.climber(img, d, t)
