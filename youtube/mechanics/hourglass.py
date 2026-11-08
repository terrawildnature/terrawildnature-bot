"""Hourglass: a lifespan documentary told with time itself. On the right a large hourglass slowly empties as the ranking
climbs from a one-day life to five centuries (log scale), with a big "ÖMÜR" readout and a calendar line that answers
"if it were born today, when would it die?" (8 KASIM 2026 -> 9 KASIM 2026 ... 2026 -> 2533). Along the bottom a
"YAŞAM ÇİZGİSİ" ruler (1 gün, 1 hafta, 1 ay, 1 yıl, 10 yıl, 100 yıl) collects a coloured dot for every animal met so far,
the dots stacking up where lifespans crowd together; the human lifespan is a fixed reference mark. The background
moves from warm sepia (days) to deep indigo (centuries) and carries faint growth rings, the way the age of a clam
or a tree is read.

script.json:
  "mechanic": "hourglass",
  "journey": {"meter": false, "scale": "log", "min": 0.002, "max": 600, "unit": "yıl",
              "units": [[0, "saat", 8766], [0.00272, "gün", 365.25], [0.0833, "ay", 12], [1, "yıl", 1]],
              "card": [40, 96, 1120, 630], "sub_cx": 960, "range_label": "ÖMÜR", "today": "2026-11-08",
              "human": 73, ...}
  creature / landmark segments: "depth" = lifespan in years (ascending), "range" = label shown on the card.
"""
import datetime as dt
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

HX, HY, HW, HH = 1545, 70, 280, 380          # hourglass: centre x, top y, width, height
RX0, RX1, RY = 70, 1850, 806                  # life-line ruler: x range and axis y
ZCOL = [(244, 196, 98), (236, 150, 80), (214, 98, 92), (168, 96, 170), (104, 120, 214), (80, 170, 210)]
SAND = (236, 190, 110)
GLASS = (210, 225, 240)
BG_A = np.array([46, 30, 18], np.float32)     # days: warm sepia
BG_B = np.array([40, 24, 40], np.float32)     # years: plum
BG_C = np.array([14, 18, 46], np.float32)     # centuries: deep indigo
MONTHS = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
TICKS = [(1 / 365.25, "1 GÜN"), (7 / 365.25, "1 HAFTA"), (1 / 12, "1 AY"), (1, "1 YIL"), (10, "10 YIL"), (100, "100 YIL"),
         (500, "500 YIL")]


class Mechanic:
    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.zones = self.j["zones"]
        self.today = dt.date.fromisoformat(self.j.get("today", "2026-11-08"))
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        self.lm = [b for b in scene.blocks if b["kind"] == "landmark"]
        self.thumbs = {}
        # beeswarm: dots that sit close together on the ruler stack upwards
        placed = []
        self.level = {}
        for b in self.cr:
            x = self.rx(b["seg"]["depth"])
            lv = 0
            while any(abs(x - px) < 15 and pl == lv for px, pl in placed):
                lv += 1
            placed.append((x, lv))
            self.level[b["i"]] = lv
        # faint growth rings centred behind the hourglass + drifting sand grains
        yy, xx = np.mgrid[0:R.H, 0:R.W].astype(np.float32)
        r = np.sqrt((xx - HX) ** 2 + (yy - (HY + HH / 2)) ** 2)
        self.r = r
        rng = np.random.default_rng(7)
        self.grains = rng.uniform(0, 1, (120, 4))

    # ------------------------------------------------------------------ helpers
    def u(self, d):
        return R.to_unit(max(d, self.j["min"]), self.j)

    def rx(self, d):
        return RX0 + (RX1 - RX0) * self.u(d)

    def zone_index(self, d):
        for k, (a, b, _) in enumerate(self.zones):
            if d < b:
                return k
        return len(self.zones) - 1

    def born_today(self, d):
        if d < 1:
            end = self.today + dt.timedelta(days=max(1, round(d * 365.25)))
            f = lambda x: f"{x.day} {MONTHS[x.month - 1]} {x.year}"
            return f(self.today), f(end)
        return str(self.today.year), str(self.today.year + int(round(d)))

    # ------------------------------------------------------------------ background
    def rings(self, n):
        return self.s.text_img(("rings", n), lambda: self._rings(n))

    def _rings(self, n):
        """n concentric growth rings (more rings = older), as a float mask."""
        if n <= 0:
            return None
        gap = 46.0
        x = self.r / gap
        m = np.clip(1 - np.abs(x - np.round(x)) * 9, 0, 1) * (x < n + 0.5) * (x > 0.5)
        fade = np.clip(1 - self.r / 1500, 0, 1)
        return (m * fade).astype(np.float32)[..., None]

    def background(self, d, t, b):
        u = 0.0 if b["kind"] == "cold" else self.u(d)
        c = BG_A + (BG_B - BG_A) * min(u * 2, 1) if u < 0.5 else BG_B + (BG_C - BG_B) * (u * 2 - 1)
        top, bot = c * 1.45, c * 0.6
        v = self.s.vert[..., None]
        frame = top[None, None, :] * (1 - v) + bot[None, None, :] * v
        frame = np.broadcast_to(frame, (R.H, R.W, 3)).copy()
        rg = self.rings(int(round(u * 24)))
        if rg is not None:
            frame += rg * np.array([26, 20, 14], np.float32)
        frame *= self.s.vign
        for x, y, sz, sp in self.grains:   # slow golden motes drifting down like sand
            px = (x * R.W + 9 * math.sin(t * 0.3 + sp * 20)) % R.W
            py = (y * R.H + t * 12 * (0.4 + sp)) % R.H
            self.s.add(frame, px, py, 1 if sz < 0.7 else 2, 60 + 90 * sp, (1.0, 0.82, 0.5))
        return frame

    # ------------------------------------------------------------------ hourglass
    def glass(self):
        return self.s.text_img("hg_glass", self._glass)

    def _outline(self, S=1):
        """Glass profile: list of (x, y) on the right half, from the top rim to the bottom rim."""
        pts = []
        for k in range(61):
            f = k / 60                       # 0 top .. 1 bottom
            y = HY + 34 + (HH - 68) * f
            w = 10 + (HW / 2 - 30) * abs(math.sin(math.pi * (f - 0.5))) ** 0.75
            pts.append((w * S, y * S))
        return pts

    def _glass(self):
        S = 2
        im = Image.new("RGBA", (R.W * S, (HY + HH + 40) * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        cx = HX * S
        prof = self._outline(S)
        right = [(cx + w, y) for w, y in prof]
        left = [(cx - w, y) for w, y in reversed(prof)]
        dr.polygon(right + left, fill=GLASS + (26,))
        dr.line(right, fill=GLASS + (170,), width=3 * S)
        dr.line(left, fill=GLASS + (170,), width=3 * S)
        wood = (120, 78, 44)
        for y in (HY, HY + HH - 30):   # wooden caps
            dr.rounded_rectangle((cx - HW / 2 * S, y * S, cx + HW / 2 * S, (y + 30) * S), 10 * S, fill=wood + (255,),
                                 outline=(180, 128, 74, 255), width=2 * S)
        for sx in (-1, 1):             # posts
            x = cx + sx * (HW / 2 - 16) * S
            dr.rounded_rectangle((x - 7 * S, (HY + 26) * S, x + 7 * S, (HY + HH - 26) * S), 6 * S, fill=wood + (255,))
        # highlight on the glass
        hl = [(cx - w * 0.62, y) for w, y in prof[4:26]]
        dr.line(hl, fill=(255, 255, 255, 70), width=4 * S)
        return im.resize((R.W, HY + HH + 40), Image.LANCZOS)

    def sand(self, q):
        return self.s.text_img(("hg_sand", q), lambda: self._sand(q / 400))

    def _sand(self, u):
        """Sand image for fraction u that has run through (0 = all on top, 1 = all at the bottom)."""
        S = 2
        im = Image.new("RGBA", (R.W * S, (HY + HH + 40) * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        cx = HX * S
        prof = self._outline(S)
        half = len(prof) // 2
        top, bot = prof[:half + 1], prof[half:]
        # areas per row (proportional to width) to fill by volume
        def fill_rows(rows, frac, from_bottom):
            ws = [w for w, _ in rows]
            tot = sum(ws)
            need, acc = tot * frac, 0.0
            seq = list(reversed(rows)) if from_bottom else rows
            out = []
            for w, y in seq:
                if acc >= need:
                    break
                out.append((w, y))
                acc += w
            return out
        tsand = fill_rows(top, 1 - u, True)       # top sand sits at the neck, its surface sinks
        bsand = fill_rows(bot, u, True)           # bottom pile grows upward
        for rows, mound in ((tsand, False), (bsand, True)):
            if len(rows) < 2:
                continue
            ys = [y for _, y in rows]
            y0, y1 = min(ys), max(ys)
            poly_r = [(cx + w - 6 * S, y) for w, y in sorted(rows, key=lambda p: p[1])]
            poly_l = [(cx - w + 6 * S, y) for w, y in sorted(rows, key=lambda p: -p[1])]
            dr.polygon(poly_r + poly_l, fill=SAND + (255,))
            if mound:   # little cone on the pile
                w0 = rows[-1][0] - 6 * S
                dr.polygon([(cx - w0, y0 + 2 * S), (cx, y0 - min(26 * S, (y1 - y0) * 0.6 + 4 * S)), (cx + w0, y0 + 2 * S)],
                           fill=SAND + (255,))
            dr.line([(cx - (rows[-1][0] - 8 * S), y0 + 3 * S), (cx + rows[-1][0] - 8 * S, y0 + 3 * S)], fill=(255, 225, 160, 200),
                    width=2 * S)
        return im.resize((R.W, HY + HH + 40), Image.LANCZOS)

    def stream(self, img, u, t, moving):
        if u >= 0.999 or u <= 0.0005:
            return
        dr = ImageDraw.Draw(img)
        ny = HY + HH / 2
        prof = self._outline()
        half = len(prof) // 2
        # bottom of the falling stream = top of the pile
        bottom = HY + HH - 40 - (HH / 2 - 60) * (u ** 0.8)
        w = 3 if moving else 2
        dr.line((HX, ny, HX, bottom), fill=SAND, width=w)
        for k in range(6):   # grains sliding down the stream
            y = ny + ((t * (260 if moving else 90) + k * 37) % max(bottom - ny, 1))
            dr.ellipse((HX - 2, y - 2, HX + 2, y + 2), fill=(255, 225, 160))

    # ------------------------------------------------------------------ readout
    def readout(self, d, zk):
        txt = self.s.fmt_pos(d)
        a, b = self.born_today(d)
        return self.s.text_img(("ro", txt, a, b, zk), lambda: self._readout(txt, a, b, zk))

    def _readout(self, txt, a, b, zk):
        im = Image.new("RGBA", (640, 250), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((320, 20), "ÖMÜR", font=R.font(R.F_UI, 28), fill=(240, 200, 120), anchor="mm")
        f = R.font(R.F_ANTON, 84)
        dr.text((323, 88), R.tr_upper(txt), font=f, fill=(0, 0, 0, 140), anchor="mm")
        dr.text((320, 85), R.tr_upper(txt), font=f, fill="white", anchor="mm")
        dr.rounded_rectangle((20, 140, 620, 236), 18, fill=(10, 8, 16, 170), outline=(240, 200, 120, 90), width=2)
        dr.text((320, 162), "BUGÜN DOĞSAYDI", font=R.font(R.F_UI, 22), fill=(200, 190, 175), anchor="mm")
        f2 = R.font(R.F_UI, 34)
        line = f"{a}  →  {b}"
        while dr.textlength(line, font=f2) > 570:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((320, 206), line, font=f2, fill=(255, 220, 150), anchor="mm")
        return im

    # ------------------------------------------------------------------ life-line ruler
    def ruler(self):
        return self.s.text_img("ruler", self._ruler)

    def _ruler(self):
        im = Image.new("RGBA", (R.W, 140), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        y = 70
        dr.text((RX0, y - 58), "YAŞAM ÇİZGİSİ", font=R.font(R.F_UI, 22), fill=(240, 200, 120, 230), anchor="lm")
        for k, (a, b, _) in enumerate(self.zones):
            dr.line((self.rx(a), y, self.rx(b), y), fill=ZCOL[k % len(ZCOL)] + (200,), width=6)
        for v, lab in TICKS:
            if v < self.j["min"] or v > self.j["max"]:
                continue
            x = self.rx(v)
            dr.line((x, y - 9, x, y + 9), fill=(255, 255, 255, 200), width=2)
            dr.text((x, y + 24), lab, font=R.font(R.F_UI, 19), fill=(225, 215, 200, 220), anchor="mm")
        hu = self.j.get("human")
        if hu:
            x = self.rx(hu)
            for yy in range(y - 54, y + 4, 8):
                dr.line((x, yy, x, yy + 4), fill=(140, 220, 255, 220), width=2)
            dr.text((x, y - 62), "İNSAN", font=R.font(R.F_UI, 18), fill=(140, 220, 255, 240), anchor="mm")
        return im

    def dots(self, now, show_now):
        return self.s.text_img(("dots", now, show_now), lambda: self._dots(now, show_now))

    def _dots(self, now, show_now):
        im = Image.new("RGBA", (R.W, 140), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        y = 70
        for b in self.lm:
            if b["i"] <= now:
                x = self.rx(b["seg"]["depth"])
                dr.polygon([(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)], fill=(255, 255, 255, 230))
        for b in self.cr:
            if b["i"] < now or (b["i"] == now and show_now):
                x = self.rx(b["seg"]["depth"])
                yy = y - 14 - self.level[b["i"]] * 13
                zk = self.zone_index(b["seg"]["depth"])
                cur = b["i"] == now
                r = 7 if cur else 5
                dr.ellipse((x - r, yy - r, x + r, yy + r), fill=ZCOL[zk % len(ZCOL)] + (255,),
                           outline=(255, 255, 255, 255) if cur else (20, 14, 10, 200), width=2)
        return im

    def thumb(self, i):
        if i not in self.thumbs:
            key = self.s.photos[f"{i:02d}"][0]["file"][:-4]
            im = Image.open(self.s.doc / "photos" / f"{key}.jpg").convert("RGB")
            c = min(im.size)
            im = im.crop(((im.width - c) // 2, (im.height - c) // 2, (im.width + c) // 2, (im.height + c) // 2))
            sz = 64
            im = im.resize((sz * 2, sz * 2), Image.LANCZOS)
            m = Image.new("L", (sz * 2, sz * 2), 0)
            ImageDraw.Draw(m).ellipse((0, 0, sz * 2 - 1, sz * 2 - 1), fill=255)
            im.putalpha(m)
            ring = Image.new("RGBA", (sz * 2 + 8, sz * 2 + 8), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((0, 0, sz * 2 + 7, sz * 2 + 7), fill=(255, 220, 150, 255))
            ring.alpha_composite(im, (4, 4))
            self.thumbs[i] = ring.resize((sz + 4, sz + 4), Image.LANCZOS)
        return self.thumbs[i]

    # ------------------------------------------------------------------ card-area panels
    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zk = self.zone_index(seg["depth"] + 1e-9)
        col = ZCOL[zk % len(ZCOL)]
        dr.text((cw / 2, ch * 0.24), f"ZAMAN DİLİMİ {zk + 1} / {len(self.zones)}", font=R.font(R.F_UI, 36), fill=col, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 80:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 4, ch * 0.48 + 5), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, ch * 0.48), seg["name"], font=f, fill="white", anchor="mm")
        # small row of hourglasses: how many decades of time this zone spans
        for k in range(len(self.zones)):
            x = cw / 2 + (k - (len(self.zones) - 1) / 2) * 56
            c = ZCOL[k % len(ZCOL)] + ((255,) if k == zk else (80,))
            dr.polygon([(x - 14, ch * 0.68), (x + 14, ch * 0.68), (x, ch * 0.68 + 20)], fill=c)
            dr.polygon([(x - 14, ch * 0.68 + 40), (x + 14, ch * 0.68 + 40), (x, ch * 0.68 + 20)], fill=c)
        dr.text((cw / 2, ch * 0.86), seg["range"], font=R.font(R.F_UI, 46), fill=(235, 225, 210), anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((40, 50, cw - 40, ch - 50), 30, fill=(12, 8, 16, 170), outline=(240, 200, 120, 150), width=3)
        dr.text((cw / 2, 130), "ZAMAN ÖLÇÜSÜ", font=R.font(R.F_UI, 34), fill=(240, 200, 120), anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["value"], font=f) > cw - 140:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 5), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 44)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 140:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 130), name, font=f2, fill=(235, 225, 210), anchor="mm")
        return im

    # ------------------------------------------------------------------ frame
    def draw(self, img, t, b, lt, default):
        k = b["kind"]
        if k == "end":
            default()
            return
        d = R.depth_at(b, t, self.j)
        alpha = R.ease(lt / 0.6) * R.ease((b["dur"] - lt) / 0.6)
        if k in ("creature", "intro", "outro"):
            default()
        elif k == "landmark":
            if self.s.photos.get(f"{b['i']:02d}"):
                default()
            else:
                self.s.paste(img, self.landmark_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        elif k == "zone":
            self.s.paste(img, self.zone_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        # hourglass
        u = self.u(d)
        g = self.glass()
        sd = self.sand(int(round(u * 400)))
        img.paste(sd, (0, 0), sd)
        self.stream(img, u, t, k == "travel")
        img.paste(g, (0, 0), g)
        zk = self.zone_index(d)
        ro = self.readout(d, zk)
        img.paste(ro, (HX - 320, HY + HH + 14), ro)
        # life-line ruler with dots
        rl = self.ruler()
        img.paste(rl, (0, RY - 70), rl)
        now = b.get("i", -1)
        show = k == "creature"
        dt_ = self.dots(now if show or k == "landmark" else now - 0.5, show)
        img.paste(dt_, (0, RY - 70), dt_)
        # moving cursor on the ruler
        x = self.rx(d)
        dr = ImageDraw.Draw(img)
        dr.polygon([(x, RY + 12), (x - 9, RY + 26), (x + 9, RY + 26)], fill=(255, 220, 150))
        if show:   # the current animal's portrait pops up above its dot
            a = R.ease((lt - 0.3) / 0.6) * R.ease((b["dur"] - lt) / 0.6)
            th = self.thumb(b["i"])
            yy = RY - 14 - self.level[b["i"]] * 13 - th.height - 14
            xx = int(min(max(x - th.width / 2, 8), R.W - th.width - 8))
            self.s.paste(img, th, (xx, int(yy)), a)
