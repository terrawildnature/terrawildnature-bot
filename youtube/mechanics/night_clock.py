"""Night clock: one night from sunset (18:00) to sunrise (06:00); the animals appear as the night goes on.

The whole screen is the sky of a single night. It starts as an orange-pink sunset over a black forest treeline,
sinks through the blue hour into deep indigo where stars and a faint Milky Way come out (fireflies blink above the
trees early in the evening), and at the end a violet-pink dawn glows on the horizon and the stars fade. The clock
runs continuously through the video (interpolated between segments), so the sky slowly changes while we listen.

On the right stands the "GECE SAATİ": a half-circle dial from 18:00 (left) over midnight (top) to 06:00 (right),
coloured by the five parts of the night, along which a glowing full moon travels (a full moon rises at sunset and
sets at sunrise). Under it a big digital clock, the current part of the night and "ŞAFAĞA … KALDI". Below is the
"GECE NÖBETİ": every animal we have met is added as a pair of glowing eyes (eyeshine) with its name; the current one
is highlighted. Zones show a big night-phase panel with the time span; landmarks are "GÖKYÜZÜ / IŞIK" cards.

script.json:
  "mechanic": "night_clock",
  "journey": {"meter": false, "max": 720, "unit": "dk", "card": [48, 96, 1232, 693], "sub_cx": 664, ...}
  segment "depth" = minutes after 18:00 (0 … 720), always ascending. Creatures: "short" (≤16 chars) for the list.
  Landmarks: "tag" (header text), "value".
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

DIAL_C = (1608, 330)
DIAL_R = 222
LIST_Y = 646
EYES = [(255, 196, 60), (120, 255, 140), (255, 120, 60), (110, 220, 255), (255, 235, 140), (200, 255, 90)]
# sky keyframes: minute -> (top colour, horizon colour)
SKY = [(0, (44, 58, 118), (246, 138, 72)), (20, (34, 42, 100), (196, 92, 96)), (50, (18, 24, 66), (82, 56, 102)),
       (80, (8, 12, 36), (24, 28, 66)), (330, (4, 6, 22), (12, 18, 46)), (600, (5, 8, 26), (16, 22, 56)),
       (660, (14, 20, 60), (70, 58, 116)), (700, (36, 52, 112), (206, 124, 128)), (720, (62, 96, 164), (250, 172, 112))]


def lerp3(a, b, f):
    return np.array([a[k] + (b[k] - a[k]) * f for k in range(3)], np.float32)


def sky_at(m):
    if m <= SKY[0][0]:
        return np.array(SKY[0][1], np.float32), np.array(SKY[0][2], np.float32)
    for (a, ta, ha), (b, tb, hb) in zip(SKY, SKY[1:]):
        if m <= b:
            f = (m - a) / (b - a)
            return lerp3(ta, tb, f), lerp3(ha, hb, f)
    return np.array(SKY[-1][1], np.float32), np.array(SKY[-1][2], np.float32)


def clock(m):
    m = int(round(m))
    h, mm = divmod(18 * 60 + m, 60)
    return f"{h % 24:02d}:{mm:02d}"


def star_vis(m):
    return min(max((m - 25) / 50, 0), 1) * min(max((700 - m) / 70, 0), 1)


class Mechanic:
    subtitles = False             # drawn here: wrapped to the card width so they never reach the right-hand panel

    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.zcols = R.zone_colors(self.j)
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        # continuous clock: knots at the start of every narrated block
        kt, kv = [], []
        for b in scene.blocks:
            if "seg" in b:
                kt.append(b["t0"])
                kv.append(b["seg"]["depth"])
        end = scene.blocks[-1]
        kt.append(end["t0"])
        kv.append(self.j["max"])
        self.kt, self.kv = np.array(kt), np.maximum.accumulate(np.array(kv, np.float64))
        rng = np.random.default_rng(23)
        self.yy = np.linspace(0, 1, R.H, dtype=np.float32)[:, None, None] ** 1.35
        self.stars = rng.uniform(0, 1, (240, 4))
        # milky way: a soft diagonal band of blurred noise
        small = Image.fromarray((rng.uniform(0, 255, (R.H // 8, R.W // 8))).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
        noise = np.asarray(small.resize((R.W, R.H), Image.BILINEAR), np.float32) / 255.0
        xx = np.linspace(0, 1, R.W, dtype=np.float32)[None, :]
        y1 = np.linspace(0, 1, R.H, dtype=np.float32)[:, None]
        band = np.exp(-((y1 - (0.95 - 0.75 * xx)) ** 2) / 0.012)
        self.milky = (band * (0.45 + 0.55 * noise))[..., None] * np.array([0.75, 0.8, 1.0], np.float32)
        # forest treeline silhouette
        mask = Image.new("L", (R.W, R.H), 0)
        dr = ImageDraw.Draw(mask)
        base = R.H - 64
        x = -20
        while x < R.W + 40:
            w = rng.uniform(26, 70)
            h = rng.uniform(60, 150) if rng.uniform() < 0.7 else rng.uniform(25, 50)
            if rng.uniform() < 0.55 or h < w * 1.2:     # conifer
                dr.polygon([(x, base), (x + w / 2, base - h), (x + w, base)], fill=255)
            else:                        # round crown
                dr.ellipse((x, base - h, x + w * 1.3, base - h + w * 1.1), fill=255)
                dr.rectangle((x + w * 0.55, base - h + w * 0.6, x + w * 0.75, base), fill=255)
            x += w * rng.uniform(0.45, 0.8)
        dr.rectangle((0, base, R.W, R.H), fill=255)
        self.trees = (np.asarray(mask.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255.0)[..., None]
        self.flies = rng.uniform(0, 1, (40, 4))

    def minute(self, t):
        return float(np.interp(t, self.kt, self.kv))

    # ------------------------------------------------------------------ background: the night sky
    def background(self, d, t, b):
        m = self.minute(t)
        top, hor = sky_at(m)
        frame = top[None, None, :] * (1 - self.yy) + hor[None, None, :] * self.yy
        frame = np.broadcast_to(frame, (R.H, R.W, 3)).copy()
        sv = star_vis(m)
        if sv > 0:
            frame += self.milky * (38 * sv)
            for x, y, sz, ph in self.stars:
                a = sv * (0.55 + 0.45 * math.sin(t * (0.8 + 2.2 * ph) + ph * 50))
                self.s.add(frame, x * R.W, y * R.H * 0.85, 1 if sz < 0.8 else 2, 230 * a * (0.4 + 0.6 * sz), (0.9, 0.93, 1.0))
        frame *= self.s.vign
        # treeline: almost black, a touch of the horizon colour
        frame = frame * (1 - self.trees) + self.trees * (hor * 0.06 + 3)[None, None, :]
        ff = min(max((260 - m) / 120, 0), 1) * min(max(m / 6, 0), 1)   # fireflies over the trees in the evening
        if ff > 0:
            for x, y, ph, sp in self.flies:
                a = max(0.0, math.sin(t * (0.9 + sp) + ph * 30)) ** 8 * ff
                if a < 0.03:
                    continue
                px = (x * R.W + math.sin(t * 0.3 + ph * 9) * 40) % R.W
                py = R.H - 90 - y * 180 + math.sin(t * 0.5 + sp * 7) * 15
                self.s.add(frame, px, py, 6, 160 * a, (0.75, 1.0, 0.3))
                self.s.add(frame, px, py, 2, 255 * a, (0.95, 1.0, 0.7))
        return frame

    # ------------------------------------------------------------------ dial
    def zone_k(self, m):
        zs = self.j["zones"]
        for k, (a, b, _) in enumerate(zs):
            if a <= m < b:
                return k
        return len(zs) - 1

    def dial(self):
        return self.s.text_img("dial", self._dial)

    def _dial(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        cx, cy = DIAL_C
        r = DIAL_R
        dr.rounded_rectangle((1316, 40, 1900, 1050), 34, fill=(4, 6, 20, 150), outline=(170, 180, 255, 60), width=2)
        dr.text((1346, 72), "GECE SAATİ", font=R.font(R.F_ANTON, 34), fill=(255, 214, 110), anchor="lm")
        box = (cx - r, cy - r, cx + r, cy + r)
        for (a, b, _), c in zip(self.j["zones"], self.zcols):   # dim zone track
            dr.arc(box, 180 + a / 720 * 180, 180 + b / 720 * 180, fill=c + (90,), width=14)
        f = R.font(R.F_UI, 22)
        for h in range(13):
            th = math.pi * (1 - h / 12)
            ca, sa = math.cos(th), math.sin(th)
            major = h % 3 == 0
            r0, r1 = r + 12, r + (30 if major else 22)
            dr.line((cx + ca * r0, cy - sa * r0, cx + ca * r1, cy - sa * r1), fill=(220, 225, 255, 230 if major else 120),
                    width=3 if major else 2)
            if major:
                lbl = f"{(18 + h) % 24:02d}"
                dr.text((cx + ca * (r + 52), cy - sa * (r + 52)), lbl, font=f, fill=(220, 225, 255, 230), anchor="mm")
        dr.line((cx - r - 40, cy, cx + r + 40, cy), fill=(220, 225, 255, 120), width=2)   # horizon
        fs = R.font(R.F_UI, 18)
        dr.text((cx - r - 40, cy + 40), "GÜN BATIMI", font=fs, fill=(255, 170, 110, 220), anchor="la")
        dr.text((cx + r + 40, cy + 40), "GÜN DOĞUMU", font=fs, fill=(255, 190, 150, 220), anchor="ra")
        return im

    def moon(self):
        return self.s.text_img("moon", self._moon)

    def _moon(self):
        n = 120
        im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        glow = Image.new("L", (n, n), 0)
        ImageDraw.Draw(glow).ellipse((22, 22, n - 22, n - 22), fill=150)
        glow = glow.filter(ImageFilter.GaussianBlur(12))
        im.paste((230, 236, 255, 255), (0, 0), glow)
        dr = ImageDraw.Draw(im)
        dr.ellipse((38, 38, n - 38, n - 38), fill=(250, 248, 232, 255))
        for x, y, s in ((52, 50, 7), (66, 62, 9), (56, 70, 5)):   # maria
            dr.ellipse((x - s / 2, y - s / 2, x + s / 2, y + s / 2), fill=(214, 212, 196, 255))
        return im

    def readout(self, m):
        key = ("read", int(round(m)))
        return self.s.text_img(key, lambda: self._readout(m))

    def _readout(self, m):
        im = Image.new("RGBA", (584, 220), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        k = self.zone_k(m)
        c = self.zcols[k]
        dr.text((292, 62), clock(m), font=R.font(R.F_ANTON, 112), fill="white", anchor="mm")
        name = self.j["zones"][k][2]
        dr.text((292, 140), name, font=R.font(R.F_UI, 32), fill=c, anchor="mm")
        left = max(0, 720 - int(round(m)))
        h, mm = divmod(left, 60)
        txt = "GÜNEŞ DOĞDU" if left == 0 else ("ŞAFAĞA " + (f"{h} SAAT " if h else "") + (f"{mm} DAKİKA" if mm else "") + " KALDI")
        dr.rounded_rectangle((60, 172, 524, 212), 14, fill=(255, 255, 255, 22))
        dr.text((292, 192), txt.replace("  ", " "), font=R.font(R.F_UI, 24), fill=(215, 222, 245), anchor="mm")
        return im

    # ------------------------------------------------------------------ the night watch list
    def watch(self, now, show_now):
        items = [b for b in self.cr if b["i"] < now or (b["i"] == now and show_now)]
        cur = now if show_now else -1
        key = ("watch", len(items), cur)
        return self.s.text_img(key, lambda: self._watch(items, cur))

    def _watch(self, items, cur):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((1346, LIST_Y), "GECE NÖBETİ", font=R.font(R.F_ANTON, 34), fill=(255, 214, 110), anchor="lm")
        dr.text((1872, LIST_Y), f"{len(items)} / {len(self.cr)}", font=R.font(R.F_UI, 28), fill=(200, 208, 240), anchor="rm")
        dr.line((1346, LIST_Y + 26, 1872, LIST_Y + 26), fill=(200, 208, 255, 70), width=2)
        f = R.font(R.F_UI, 19)
        glow = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        rows = (len(self.cr) + 1) // 2
        rh = min(28, (1036 - LIST_Y - 44) / max(rows, 1))
        for n, b in enumerate(items):
            col, row = divmod(n, rows)
            x, y = 1350 + col * 266, LIST_Y + 50 + row * rh
            ec = EYES[n % len(EYES)]
            on = b["i"] == cur
            if on:
                dr.rounded_rectangle((x - 8, y - rh / 2 + 1, x + 256, y + rh / 2 - 1), 10, fill=ec + (50,), outline=ec + (200,), width=2)
            for dx in (0, 16):
                gd.ellipse((x + 4 + dx - 7, y - 6, x + 4 + dx + 7, y + 6), fill=ec + (200,))
                dr.ellipse((x + 4 + dx - 5, y - 3, x + 4 + dx + 5, y + 3), fill=ec + (255,))
                dr.ellipse((x + 4 + dx - 1, y - 3, x + 4 + dx + 1, y + 3), fill=(20, 12, 4, 255))
            name = R.tr_upper(b["seg"].get("short", b["seg"]["name"]))
            ff = f
            while dr.textlength(name, font=ff) > 214 and ff.size > 13:
                ff = R.font(R.F_UI, ff.size - 1)
            dr.text((x + 36, y), name, font=ff, fill=(255, 255, 255, 255) if on else (220, 226, 245, 215), anchor="lm")
        glow = glow.filter(ImageFilter.GaussianBlur(5))
        glow.alpha_composite(im)
        return glow

    # ------------------------------------------------------------------ card-area panels
    def badge(self, seg):
        return self.s.text_img(("badge", seg["name"]), lambda: self._badge(seg))

    def _badge(self, seg):
        txt = clock(seg["depth"])
        f = R.font(R.F_ANTON, 40)
        w = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(txt, font=f)) + 84
        im = Image.new("RGBA", (w, 64), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 1, 63), 20, fill=(6, 8, 30, 200), outline=(255, 214, 110, 200), width=2)
        dr.ellipse((16, 16, 48, 48), fill=(250, 246, 226))           # little crescent moon
        dr.ellipse((26, 10, 58, 42), fill=(6, 8, 30))
        dr.text((62, 32), txt, font=f, fill="white", anchor="lm")
        return im

    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zones = self.j["zones"]
        k = next((n for n, z in enumerate(zones) if z[2] == seg["name"]), 0)
        c = self.zcols[k]
        # mini arc showing which slice of the night this is
        cx, cy, r = cw / 2, ch * 0.30, 120
        box = (cx - r, cy - r, cx + r, cy + r)
        dr.arc(box, 180, 360, fill=(255, 255, 255, 60), width=10)
        a, b = zones[k][0], zones[k][1]
        dr.arc(box, 180 + a / 720 * 180, 180 + b / 720 * 180, fill=c + (255,), width=16)
        dr.line((cx - r - 30, cy, cx + r + 30, cy), fill=(255, 255, 255, 90), width=2)
        dr.text((cw / 2, ch * 0.40), f"GECENİN {k + 1}. BÖLÜMÜ / {len(zones)}", font=R.font(R.F_UI, 34), fill=c, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 80:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 5, ch * 0.60 + 6), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, ch * 0.60), seg["name"], font=f, fill="white", anchor="mm")
        dr.text((cw / 2, ch * 0.82), f"{clock(a)}  →  {clock(b)}", font=R.font(R.F_ANTON, 64), fill=(255, 214, 110), anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        c = (255, 214, 110)
        dr.rounded_rectangle((40, 50, cw - 40, ch - 50), 30, fill=(6, 8, 30, 190), outline=c + (200,), width=4)
        dr.rounded_rectangle((40, 50, cw - 40, 150), 30, fill=c + (235,))
        dr.rectangle((40, 120, cw - 40, 150), fill=c + (235,))
        dr.text((cw / 2, 100), seg.get("tag", "GÖKYÜZÜ"), font=R.font(R.F_ANTON, 50), fill=(12, 12, 30), anchor="mm")
        f = R.font(R.F_ANTON, 190)
        while dr.textlength(seg["value"], font=f) > cw - 160:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 20), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 50)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 160:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 140), name, font=f2, fill=(230, 232, 248), anchor="mm")
        dr.text((cw / 2, ch - 88), "SAAT " + clock(seg["depth"]), font=R.font(R.F_UI, 32), fill=c, anchor="mm")
        return im

    # ------------------------------------------------------------------ subtitles
    def sub(self, text):
        return self.s.text_img(("nsub", text), lambda: self._sub(text))

    def _sub(self, text):
        maxw = 1200
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
                self.s.paste(img, im, (cx - im.width // 2, 935 - im.height // 2), 1.0)
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
        m = self.minute(t)
        alpha = R.ease(lt / 0.6) * R.ease((b["dur"] - lt) / 0.6)
        if k in ("creature", "intro", "outro"):
            default()
            if k == "creature":
                self.s.paste(img, self.badge(b["seg"]), (R.CARD[0] + 22, R.CARD[1] + 20), alpha)
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
            self._instrument(layer, t, m, b, k)
            self.s.paste(img, layer, (0, 0), pa)
        else:
            self._instrument(img, t, m, b, k)

    def _instrument(self, img, t, m, b, k):
        self.s.paste(img, self.dial(), (0, 0), 1.0)
        cx, cy = DIAL_C
        f = min(max(m / 720, 0), 1)
        dr = ImageDraw.Draw(img)
        box = (cx - DIAL_R, cy - DIAL_R, cx + DIAL_R, cy + DIAL_R)
        if f > 0.002:   # travelled part of the night, in the colours of its zones
            for (a, bb, _), c in zip(self.j["zones"], self.zcols):
                e = min(bb, m)
                if e > a:
                    dr.arc(box, 180 + a / 720 * 180, 180 + e / 720 * 180, fill=c, width=14)
        th = math.pi * (1 - f)
        mo = self.moon()
        self.s.paste(img, mo, (int(cx + math.cos(th) * DIAL_R - mo.width / 2), int(cy - math.sin(th) * DIAL_R - mo.height / 2)), 1.0)
        self.s.paste(img, self.readout(m), (1316, cy + 46), 1.0)
        now = b.get("i", -1)
        show = k == "creature" and t - b["t0"] > 0.3
        if k == "outro":
            now, show = 10 ** 6, False
        self.s.paste(img, self.watch(now, show), (0, 0), 1.0)
