"""Thermometer: animals ranked from the coldest to the hottest place they live, on a giant laboratory thermometer.

On the right stands a tall glass thermometer (−90 … +100 °C, linear). Its liquid column rises with the story and
changes colour from icy cyan through green and amber to glowing red. A digital readout above it shows the current
temperature and what is measured ("HAVA", "VÜCUT", "SU"…), and a line compares it with the human body (37 °C):
"İNSAN VÜCUDUNDAN 107 °C SOĞUK". Every animal we have met leaves a small coloured tick and its name on the scale, so
the thermometer fills up into a ranking. The background is the climate itself: a frosted, crystal-veined blue with
falling snow at the cold end, a neutral dusk in the middle and a shimmering orange heat haze with rising embers at the
hot end. Zones show a big temperature band with a snowflake or a sun drawn in code; landmarks are "KAYIT" cards.

script.json:
  "mechanic": "thermometer",
  "journey": {"meter": false, "offset": 90, "max": 190, "unit": "°C", "card": [48, 96, 1232, 693], "sub_cx": 740, ...}
  segment "depth" = temperature + offset (so −89 °C -> 1), always ascending. Creatures/landmarks may add
  "measure": "HAVA" | "VÜCUT" | "SU" | "YÜZEY" … (what the temperature is).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

TUBE_X = 1630                 # thermometer centre line
TUBE_TOP, TUBE_BOT = 334, 900  # scale top (+100 °C) and bottom (−90 °C)
TUBE_W = 34
BULB_Y, BULB_R = 952, 50
READ = (1336, 40, 548, 214)   # digital readout x, y, w, h
T_LO, T_HI = -90.0, 100.0

# liquid / accent colour by temperature
LIQ = [(-90, (120, 220, 255)), (-40, (60, 170, 255)), (0, (70, 210, 200)), (25, (150, 220, 80)),
       (40, (255, 190, 40)), (60, (255, 110, 30)), (100, (235, 30, 30))]
# background (top colour) by temperature
SKY = [(-90, (24, 58, 96)), (-40, (30, 82, 124)), (-5, (36, 78, 104)), (15, (40, 54, 66)),
       (35, (88, 52, 30)), (55, (116, 46, 18)), (100, (96, 18, 10))]


def lerp_tab(tab, v):
    if v <= tab[0][0]:
        return np.array(tab[0][1], np.float32)
    for (a, ca), (b, cb) in zip(tab, tab[1:]):
        if v <= b:
            f = (v - a) / (b - a)
            return np.array([ca[k] + (cb[k] - ca[k]) * f for k in range(3)], np.float32)
    return np.array(tab[-1][1], np.float32)


def liq(v):
    return tuple(int(c) for c in lerp_tab(LIQ, v))


def fmt_t(v, dec=None):
    if dec is None:
        dec = 0 if abs(v - round(v)) < 0.05 else 1
    s = R.fmt_num(abs(v), dec)
    return ("−" if v < -0.04 else ("+" if v > 0.04 else "")) + s + " °C"


def ty(v):
    """Temperature -> y on the scale."""
    v = min(max(v, T_LO), T_HI)
    return TUBE_BOT - (v - T_LO) / (T_HI - T_LO) * (TUBE_BOT - TUBE_TOP)


class Mechanic:
    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.off = self.j.get("offset", 90)
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        yy = np.linspace(0, 1, R.H, dtype=np.float32)[:, None, None]
        self.yy = yy
        rng = np.random.default_rng(11)
        # frost veins: a fixed blurred crack texture, faded in at the cold end
        im = Image.new("L", (R.W // 2, R.H // 2), 0)
        dr = ImageDraw.Draw(im)
        for _ in range(60):
            x, y = rng.uniform(0, R.W // 2), rng.uniform(0, R.H // 2)
            a = rng.uniform(0, math.pi * 2)
            for _ in range(int(rng.uniform(4, 10))):
                L = rng.uniform(10, 40)
                nx, ny = x + math.cos(a) * L, y + math.sin(a) * L
                dr.line((x, y, nx, ny), fill=int(rng.uniform(90, 200)), width=1)
                x, y, a = nx, ny, a + rng.uniform(-0.9, 0.9)
        self.frost = (np.asarray(im.filter(ImageFilter.GaussianBlur(0.8)).resize((R.W, R.H), Image.BILINEAR),
                                 np.float32) / 255.0)[..., None]
        edge = np.minimum(np.linspace(0, 1, R.W)[None, :] * 4, 1) * np.minimum(np.linspace(1, 0, R.W)[None, :] * 4, 1)
        edge = edge * np.minimum(np.linspace(0, 1, R.H)[:, None] * 4, 1) * np.minimum(np.linspace(1, 0, R.H)[:, None] * 4, 1)
        self.frost *= (1 - edge[..., None] * 0.75)            # frost gathers at the edges like on a window
        # heat haze: horizontal wavy bands
        self.haze_y = np.arange(R.H, dtype=np.float32)
        self.parts = rng.uniform(0, 1, (260, 4))

    def temp(self, d):
        return d - self.off

    # ------------------------------------------------------------------ background: the climate itself
    def background(self, d, t, b):
        T = self.temp(d)
        top = lerp_tab(SKY, T)
        bot = top * 0.42
        frame = top[None, None, :] * (1 - self.yy) + bot[None, None, :] * self.yy
        frame = np.broadcast_to(frame, (R.H, R.W, 3)).copy()
        cold = min(max((-T - 0) / 50, 0), 1)
        hot = min(max((T - 30) / 40, 0), 1)
        if cold > 0:
            frame += self.frost * (110 * cold) * np.array([0.75, 0.92, 1.0], np.float32)
        if hot > 0:   # shimmering haze bands rising from the bottom
            w = 0.5 + 0.5 * np.sin(self.haze_y / 23.0 - t * 2.2 + np.sin(self.haze_y / 71.0 + t) * 2)
            band = (w ** 6 * (self.haze_y / R.H) ** 1.5)[:, None, None]
            frame += band * (70 * hot) * np.array([1.0, 0.55, 0.2], np.float32)
        frame *= self.s.vign
        self.particles(frame, T, t, cold, hot)
        return frame

    def particles(self, frame, T, t, cold, hot):
        if cold > 0.05:   # snow falling
            n = int(len(self.parts) * min(1, 0.2 + cold))
            for x, y, sz, sp in self.parts[:n]:
                px = (x * R.W + t * 22 * (0.3 + sp) + math.sin(t * 0.7 + y * 20) * 18) % R.W
                py = (y * R.H + t * 55 * (0.4 + sp)) % R.H
                self.s.add(frame, px, py, 1 if sz < 0.6 else (2 if sz < 0.93 else 3), 200 * cold * (0.4 + 0.6 * sp), (1, 1, 1))
        if hot > 0.05:    # embers / dust rising
            n = int(len(self.parts) * 0.45 * hot)
            for x, y, sz, sp in self.parts[:n]:
                px = (x * R.W + math.sin(t * 1.3 + y * 30) * 14) % R.W
                py = (y * R.H - t * 40 * (0.4 + sp)) % R.H
                self.s.add(frame, px, py, 1 if sz < 0.7 else 2, 230 * hot * (0.3 + 0.7 * sp), (1.0, 0.6, 0.2))

    # ------------------------------------------------------------------ thermometer
    def glass(self):
        return self.s.text_img("glass", self._glass)

    def _glass(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        x = TUBE_X
        # back plate
        dr.rounded_rectangle((x - 150, TUBE_TOP - 46, x + 266, BULB_Y + BULB_R + 24), 40, fill=(8, 12, 18, 150),
                             outline=(255, 255, 255, 40), width=2)
        # glass tube + bulb
        dr.rounded_rectangle((x - TUBE_W / 2 - 6, TUBE_TOP - 30, x + TUBE_W / 2 + 6, BULB_Y), 22,
                             fill=(220, 235, 245, 40), outline=(230, 240, 250, 190), width=3)
        dr.ellipse((x - BULB_R - 6, BULB_Y - BULB_R - 6, x + BULB_R + 6, BULB_Y + BULB_R + 6),
                   fill=(220, 235, 245, 40), outline=(230, 240, 250, 190), width=3)
        # scale ticks
        f = R.font(R.F_UI, 22)
        for v in range(-90, 101, 5):
            y = ty(v)
            major = v % 10 == 0
            dr.line((x - TUBE_W / 2 - 14 - (14 if major else 0), y, x - TUBE_W / 2 - 12, y),
                    fill=(230, 240, 250, 220 if major else 120), width=3 if major else 2)
            if major and v % 20 == 0 or v in (-90, 100):
                lbl = ("−" if v < 0 else "") + str(abs(v))
                dr.text((x - TUBE_W / 2 - 46, y), lbl, font=f, fill=(230, 240, 250, 230), anchor="rm")
        dr.text((x - 96, TUBE_TOP - 66), "°C", font=R.font(R.F_ANTON, 30), fill=(230, 240, 250, 230), anchor="mm")
        # reference lines: freezing point and human body
        for v in (0, 37):
            y = ty(v)
            for xx in range(int(x - 140), int(x + 260), 14):
                dr.line((xx, y, xx + 7, y), fill=(255, 255, 255, 80), width=1)
        return im

    def shine(self):
        return self.s.text_img("shine", self._shine)

    def _shine(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        x = TUBE_X
        dr.rounded_rectangle((x - TUBE_W / 2 + 3, TUBE_TOP - 20, x - TUBE_W / 2 + 9, BULB_Y - 60), 3, fill=(255, 255, 255, 120))
        dr.ellipse((x - 30, BULB_Y - 34, x - 12, BULB_Y - 8), fill=(255, 255, 255, 120))
        return im

    def liquid(self, img, T, t):
        dr = ImageDraw.Draw(img)
        x = TUBE_X
        c = liq(T)
        y = ty(T)
        dr.ellipse((x - BULB_R, BULB_Y - BULB_R, x + BULB_R, BULB_Y + BULB_R), fill=c)
        dr.rectangle((x - TUBE_W / 2 + 2, y, x + TUBE_W / 2 - 2, BULB_Y - BULB_R + 10), fill=c)
        dr.ellipse((x - TUBE_W / 2 + 2, y - 8, x + TUBE_W / 2 - 2, y + 8), fill=c)
        dark = tuple(int(v * 0.72) for v in c)
        dr.rectangle((x + 4, y + 6, x + TUBE_W / 2 - 2, BULB_Y - BULB_R + 10), fill=dark)
        # pointer at the meniscus
        dr.polygon([(x + TUBE_W / 2 + 12, y), (x + TUBE_W / 2 + 32, y - 12), (x + TUBE_W / 2 + 32, y + 12)], fill="white")

    def ticks(self, img, now, show_now):
        """Animals already met: a coloured tick and the name on the right of the tube (de-overlapped)."""
        items = [b for b in self.cr if b["i"] < now or (b["i"] == now and show_now)]
        if not items:
            return
        key = ("ticks", tuple(b["i"] for b in items))
        self.s.paste(img, self.s.text_img(key, lambda: self._ticks(items)), (0, 0), 1.0)

    def _ticks(self, items):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        f = R.font(R.F_UI, 17)
        x = TUBE_X + TUBE_W / 2 + 40
        ys = [ty(self.temp(b["seg"]["depth"])) for b in items]
        lab = list(ys)
        order = sorted(range(len(lab)), key=lambda k: -lab[k])          # bottom to top
        last = 10 ** 9
        for k in order:                                                  # push labels up so they don't overlap
            lab[k] = min(lab[k], last - 19)
            last = lab[k]
        shift = max(0, TUBE_TOP - 40 - min(lab))
        if shift:                                                        # too many: pull everything back down
            lab = [min(v + shift, ys[k]) for k, v in enumerate(lab)]
        for k, b in enumerate(items):
            T = self.temp(b["seg"]["depth"])
            c = liq(T)
            dr.line((TUBE_X + TUBE_W / 2 + 4, ys[k], x - 6, ys[k]), fill=c + (230,), width=3)
            dr.line((x - 6, ys[k], x + 4, lab[k]), fill=c + (160,), width=1)
            dr.ellipse((x + 2, lab[k] - 4, x + 10, lab[k] + 4), fill=c + (255,))
            name = R.tr_upper(b["seg"].get("short", b["seg"]["name"]))
            dr.text((x + 16, lab[k]), name[:18], font=f, fill=(240, 244, 248, 225), anchor="lm")
        return im

    # ------------------------------------------------------------------ readout
    def readout(self, T, seg):
        T = round(T, 1) if seg else float(round(T))
        key = ("read", T, seg.get("name") if seg else None)
        return self.s.text_img(key, lambda: self._readout(T, seg))

    def _readout(self, T, seg):
        x0, y0, w, h = READ
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        c = liq(T)
        dr.rounded_rectangle((0, 0, w - 1, h - 1), 22, fill=(6, 10, 16, 200), outline=c + (200,), width=3)
        measure = "SICAKLIK"
        if seg and seg.get("measure"):
            measure = "SICAKLIK · " + seg["measure"]
        dr.text((26, 20), measure, font=R.font(R.F_UI, 26), fill=c)
        dec = 1 if seg and abs(T - round(T)) > 0.05 else 0
        dr.text((22, 46), fmt_t(T, dec), font=R.font(R.F_ANTON, 96), fill="white")
        diff = T - 37
        if abs(diff) < 1:
            txt = "İNSAN VÜCUDUYLA AYNI"
        elif diff < 0:
            txt = f"İNSAN VÜCUDUNDAN {R.fmt_num(-diff, 0)} °C SOĞUK"
        else:
            txt = f"İNSAN VÜCUDUNDAN {R.fmt_num(diff, 0)} °C SICAK"
        f2 = R.font(R.F_UI, 26)
        while dr.textlength(txt, font=f2) > w - 50:
            f2 = R.font(R.F_UI, f2.size - 1)
        dr.rounded_rectangle((18, h - 52, w - 18, h - 14), 12, fill=(255, 255, 255, 24))
        dr.text((w / 2, h - 33), txt, font=f2, fill=(235, 240, 245), anchor="mm")
        return im

    # ------------------------------------------------------------------ card-area panels
    def icon(self, dr, cx, cy, r, T, col):
        if T < 0:   # snowflake
            for k in range(6):
                a = k * math.pi / 3
                ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r
                dr.line((cx, cy, ex, ey), fill=col, width=7)
                for q in (0.45, 0.72):
                    bx, by = cx + math.cos(a) * r * q, cy + math.sin(a) * r * q
                    for s in (-1, 1):
                        aa = a + s * 0.75
                        dr.line((bx, by, bx + math.cos(aa) * r * 0.26, by + math.sin(aa) * r * 0.26), fill=col, width=6)
        else:       # sun
            dr.ellipse((cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45), fill=col)
            for k in range(12):
                a = k * math.pi / 6
                dr.line((cx + math.cos(a) * r * 0.62, cy + math.sin(a) * r * 0.62,
                         cx + math.cos(a) * r, cy + math.sin(a) * r), fill=col, width=8)

    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zones = self.j["zones"]
        k = next((n for n, z in enumerate(zones) if z[2] == seg["name"]), 0)
        a, b = zones[k][0] - self.off, zones[k][1] - self.off
        c = liq((a + b) / 2)
        self.icon(dr, cw / 2, ch * 0.2, 70, (a + b) / 2, c + (255,))
        dr.text((cw / 2, ch * 0.38), f"İKLİM KUŞAĞI {k + 1} / {len(zones)}", font=R.font(R.F_UI, 34), fill=c, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 80:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 5, ch * 0.58 + 6), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, ch * 0.58), seg["name"], font=f, fill="white", anchor="mm")
        # temperature band bar
        y = ch * 0.78
        x0, x1 = cw / 2 - 360, cw / 2 + 360
        for q in range(72):
            v = a + (b - a) * q / 71
            dr.rectangle((x0 + q * 10, y, x0 + q * 10 + 10, y + 26), fill=liq(v) + (255,))
        dr.text((x0, y + 40), fmt_t(a), font=R.font(R.F_UI, 40), fill="white", anchor="la")
        dr.text((x1, y + 40), fmt_t(b), font=R.font(R.F_UI, 40), fill="white", anchor="ra")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        T = self.temp(seg["depth"])
        c = liq(T)
        dr.rounded_rectangle((40, 50, cw - 40, ch - 50), 30, fill=(6, 10, 16, 185), outline=c + (200,), width=4)
        dr.rounded_rectangle((40, 50, cw - 40, 150), 30, fill=c + (230,))
        dr.rectangle((40, 120, cw - 40, 150), fill=c + (230,))
        dr.text((cw / 2, 100), seg.get("tag", "SICAKLIK KAYDI"), font=R.font(R.F_ANTON, 50), fill=(10, 12, 16), anchor="mm")
        f = R.font(R.F_ANTON, 190)
        while dr.textlength(seg["value"], font=f) > cw - 160:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 30), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 50)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 160:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 130), name, font=f2, fill=(230, 236, 242), anchor="mm")
        return im

    # ------------------------------------------------------------------ frame
    def draw(self, img, t, b, lt, default):
        k = b["kind"]
        if k == "end":
            default()
            return
        d = R.depth_at(b, t, self.j)
        T = self.temp(d)
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
        seg = b.get("seg")
        if k == "travel" or (seg and seg["type"] not in ("creature", "landmark")):
            seg = None
        pa = 1.0 if t > R.COLD_OPEN + 1.2 else R.ease((t - R.COLD_OPEN) / 1.2)
        if pa < 0.999:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            self._instrument(layer, t, T, b, k, seg)
            self.s.paste(img, layer, (0, 0), pa)
        else:
            self._instrument(img, t, T, b, k, seg)

    def _instrument(self, img, t, T, b, k, seg):
        self.s.paste(img, self.glass(), (0, 0), 1.0)
        self.liquid(img, T, t)
        self.s.paste(img, self.shine(), (0, 0), 1.0)
        now = b.get("i", -1)
        show = k == "creature" and t - b["t0"] > 0.3
        if k == "outro":
            now, show = 10 ** 6, True
        self.ticks(img, now, show)
        self.s.paste(img, self.readout(T, seg), (READ[0], READ[1]), 1.0)
