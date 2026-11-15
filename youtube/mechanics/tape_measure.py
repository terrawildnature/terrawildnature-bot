"""Tape measure: a size ranking from millimetres to the blue whale, told with a workshop's tools.

A yellow steel tape measure runs across the screen under the photo card. It is logarithmic and scrolls so the red
hairline in the middle always sits on the current size (mm -> cm -> m labels change by themselves); every animal we
have met stays pinned to the tape as a small round portrait, so the earlier animals slide away to the left as we grow.
On the right a "KIYAS" (comparison) panel draws a person (1,71 m) next to a bar of the current size on a common
baseline, with a live line such as "İNSAN BOYUNA 95 TANESİ SIĞAR" or "17,5 İNSAN BOYU". The background is a green
cutting mat whose grid zooms out continuously (powers of ten) as the sizes grow, its colour sinking from leaf green
to ocean navy for the giants.

script.json:
  "mechanic": "tape_measure",
  "journey": {"meter": false, "scale": "log", "min": 1, "max": 3000, "unit": "cm",
              "units": [[0, "mm", 10], [1, "cm", 1], [100, "m", 0.01]], "human": 171,
              "card": [56, 64, 1120, 630], "sub_cx": 960, "range_label": "BOYUT", ...}
  creature / landmark segments: "depth" = size in cm (ascending); creatures may add "measure" (e.g. "KANAT AÇIKLIĞI").
"""
import math

import numpy as np
from PIL import Image, ImageDraw

import doc_render as R

TAPE_Y, TAPE_H = 716, 78             # tape strip
PX_DEC = 560                         # pixels per decade on the tape
CX = 960                             # hairline
PIN_Y = 800                          # portrait pins under the tape
PANEL = (1206, 64, 674, 630)         # right comparison panel x, y, w, h
YEL, INK, RED = (247, 201, 38), (26, 22, 14), (226, 50, 40)
MAT = [(0.0, (14, 64, 44)), (0.35, (16, 74, 62)), (0.6, (18, 62, 80)), (0.8, (16, 44, 84)), (1.0, (10, 24, 56))]


def lg(v):
    return math.log10(max(v, 1e-3))


def mat_color(u):
    for (u0, c0), (u1, c1) in zip(MAT, MAT[1:]):
        if u <= u1:
            f = (u - u0) / (u1 - u0)
            return np.array([c0[k] + (c1[k] - c0[k]) * f for k in range(3)], np.float32)
    return np.array(MAT[-1][1], np.float32)


def fmt_len(cm):
    """Tape labels: 1 mm, 5 mm, 1 cm, 50 cm, 1 m, 20 m."""
    if cm < 0.1:
        return f"{R.fmt_num(cm * 10, 1)} mm"
    if cm < 1:
        return f"{R.fmt_num(cm * 10, 0)} mm"
    if cm < 100:
        return f"{R.fmt_num(cm, 0)} cm"
    return f"{R.fmt_num(cm / 100, 0)} m"


class Mechanic:
    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.human = self.j.get("human", 171)
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        self.thumbs = {}
        xs = np.arange(R.W, dtype=np.float32) - CX
        ys = np.arange(R.H, dtype=np.float32) - 380
        self.ax, self.ay = np.abs(xs), np.abs(ys)
        yy = np.linspace(0, 1, R.H, dtype=np.float32)[:, None, None]
        self.shade = 1.18 - 0.42 * yy

    # ------------------------------------------------------------------ background: zooming cutting mat
    def grid(self, sp):
        lx = ((self.ax % sp) < 1.6) | ((self.ax % sp) > sp - 0.6)
        ly = ((self.ay % sp) < 1.6) | ((self.ay % sp) > sp - 0.6)
        return lx[None, :] | ly[:, None]

    def background(self, d, t, b):
        u = R.to_unit(max(d, self.j["min"]), self.j)
        base = mat_color(u)
        frame = np.broadcast_to(base[None, None, :] * self.shade, (R.H, R.W, 3)).copy()
        f = lg(max(d, self.j["min"])) % 1.0            # zoom phase inside the current decade
        sp = 150.0 * 10 ** (-f)                         # fine grid shrinks 150 -> 15 px, then hands over
        fine = self.grid(sp)
        coarse = self.grid(sp * 10)
        light = np.array([150, 230, 200], np.float32)
        frame[fine] += light * 0.10 * (1 - f)
        frame[coarse] += light * 0.16
        return frame * self.s.vign

    # ------------------------------------------------------------------ tape measure
    def tape_x(self, v, d):
        return CX + (lg(v) - lg(d)) * PX_DEC

    def tape(self, d):
        key = round(lg(d) * 400)                        # ~1.4 px steps
        return self.s.text_img(("tape", key), lambda: self._tape(10 ** (key / 400)))

    def _tape(self, d):
        im = Image.new("RGBA", (R.W, 150), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        y0 = 10
        dr.rectangle((0, y0 + 6, R.W, y0 + TAPE_H + 6), fill=(0, 0, 0, 90))                   # shadow
        dr.rectangle((0, y0, R.W, y0 + TAPE_H), fill=YEL + (255,))
        dr.line((0, y0 + 3, R.W, y0 + 3), fill=(255, 232, 120, 255), width=2)                 # steel highlight
        dr.line((0, y0 + TAPE_H - 2, R.W, y0 + TAPE_H - 2), fill=(170, 130, 10, 255), width=3)
        lo = math.floor(lg(d) - CX / PX_DEC) - 1
        hi = math.ceil(lg(d) + (R.W - CX) / PX_DEC) + 1
        f_big, f_small = R.font(R.F_ANTON, 30), R.font(R.F_UI, 19)
        for e in range(lo, hi + 1):
            for m in range(1, 10):
                v = m * 10.0 ** e
                x = self.tape_x(v, d)
                if x < -40 or x > R.W + 40:
                    continue
                major = m == 1
                ln = 40 if major else (28 if m == 5 else 18)
                dr.line((x, y0, x, y0 + ln), fill=INK + (255,), width=4 if major else 2)
                if major:
                    dr.text((x + 6, y0 + 38), fmt_len(v), font=f_big, fill=INK + (255,), anchor="lt")
                elif m in (2, 5):
                    dr.text((x + 4, y0 + 30), fmt_len(v), font=f_small, fill=(70, 55, 20, 255), anchor="lt")
                # millimetre-like ticks between 1..2 for texture
                if m == 1:
                    for q in range(1, 10):
                        xx = self.tape_x(v * (1 + q / 10), d)
                        dr.line((xx, y0, xx, y0 + 9), fill=INK + (200,), width=1)
        return im

    def hairline(self, img, d):
        dr = ImageDraw.Draw(img)
        y0 = TAPE_Y + 10
        dr.line((CX, y0 - 22, CX, y0 + TAPE_H + 8), fill=RED, width=4)
        dr.polygon([(CX - 16, y0 - 34), (CX + 16, y0 - 34), (CX, y0 - 14)], fill=RED)

    def thumb(self, i):
        if i not in self.thumbs:
            key = self.s.photos[f"{i:02d}"][0]["file"][:-4]
            im = Image.open(self.s.doc / "photos" / f"{key}.jpg").convert("RGB")
            c = min(im.size)
            im = im.crop(((im.width - c) // 2, (im.height - c) // 2, (im.width + c) // 2, (im.height + c) // 2))
            sz = 52
            im = im.resize((sz * 2, sz * 2), Image.LANCZOS)
            m = Image.new("L", (sz * 2, sz * 2), 0)
            ImageDraw.Draw(m).ellipse((0, 0, sz * 2 - 1, sz * 2 - 1), fill=255)
            ring = Image.new("RGBA", (sz * 2 + 8, sz * 2 + 8), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((0, 0, sz * 2 + 7, sz * 2 + 7), fill=YEL + (255,))
            im.putalpha(m)
            ring.alpha_composite(im, (4, 4))
            self.thumbs[i] = ring.resize((sz + 4, sz + 4), Image.LANCZOS)
        return self.thumbs[i]

    def pins(self, img, d, now, show_now):
        dr = ImageDraw.Draw(img)
        for b in self.cr:
            if b["i"] > now or (b["i"] == now and not show_now):
                continue
            x = self.tape_x(b["seg"]["depth"], d)
            if x < -30 or x > R.W + 30:
                continue
            th = self.thumb(b["i"])
            dr.line((x, TAPE_Y + 10 + TAPE_H - 4, x, PIN_Y + 4), fill=(255, 255, 255), width=2)
            img.paste(th, (int(x - th.width / 2), PIN_Y), th)

    # ------------------------------------------------------------------ comparison panel
    def panel(self, d, seg):
        key = (round(lg(d) * 300), seg.get("name") if seg else None, seg.get("type") if seg else None)
        return self.s.text_img(("panel",) + key, lambda: self._panel(d, seg))

    def _panel(self, d, seg):
        x0, y0, w, h = PANEL
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, w - 1, h - 1), 26, fill=(6, 16, 12, 178), outline=YEL + (120,), width=3)
        measure = "BOYUT"
        if seg and seg.get("type") == "creature":
            measure = seg.get("measure", "BOY")
        elif seg and seg.get("type") == "landmark":
            measure = "KARŞILAŞTIRMA"
        dr.text((34, 30), measure, font=R.font(R.F_UI, 30), fill=YEL)
        dr.text((30, 62), self.s.fmt_pos(d), font=R.font(R.F_ANTON, 104), fill="white")
        # baseline comparison: person vs current size, the larger one is 300 px tall
        base_y, top = h - 92, 300
        hmax = base_y - top
        sc = hmax / max(d, self.human)
        hp, hc = self.human * sc, max(d * sc, 3)
        dr.line((34, base_y, w - 34, base_y), fill=(200, 220, 210, 200), width=3)
        for k in range(0, 11):                       # little ruler on the baseline
            xx = 34 + k * (w - 68) / 10
            dr.line((xx, base_y, xx, base_y + (14 if k % 5 == 0 else 8)), fill=(200, 220, 210, 160), width=2)
        # person silhouette
        px = 180
        self.person(dr, px, base_y, hp)
        dr.text((px, base_y + 22), "İNSAN 1,71 m", font=R.font(R.F_UI, 24), fill=(205, 225, 215), anchor="mt")
        # current size bar
        bx = 470
        bw = 96
        dr.rounded_rectangle((bx - bw / 2, base_y - hc, bx + bw / 2, base_y), min(14, hc / 2), fill=YEL + (255,))
        if hc > 60:
            for k in range(1, int(hc // 30)):
                dr.line((bx - bw / 2, base_y - k * 30, bx - bw / 2 + 18, base_y - k * 30), fill=INK + (200,), width=2)
        if hc < 24:   # too small to see: a pointer and a ring
            dr.ellipse((bx - 16, base_y - 32, bx + 16, base_y), outline=RED + (255,), width=3)
            dr.line((bx + 12, base_y - 30, bx + 46, base_y - 70), fill=RED + (255,), width=3)
        label = R.tr_upper(seg["name"]) if seg and seg.get("type") in ("creature", "landmark") else "ŞU AN"
        f = R.font(R.F_UI, 24)
        while dr.textlength(label, font=f) > 300 and f.size > 15:
            f = R.font(R.F_UI, f.size - 1)
        dr.text((bx, base_y + 22), label, font=f, fill=YEL, anchor="mt")
        # live ratio line
        r = d / self.human
        if r < 1:
            n = self.human / d
            txt = f"İNSAN BOYUNA {R.fmt_num(n, 0)} TANESİ SIĞAR" if n >= 1.5 else "NEREDEYSE İNSAN BOYU"
        else:
            txt = f"{R.fmt_num(r, 1)} İNSAN BOYU" if r < 9.95 else f"{R.fmt_num(r, 0)} İNSAN BOYU"
        f2 = R.font(R.F_ANTON, 40)
        while dr.textlength(txt, font=f2) > w - 60:
            f2 = R.font(R.F_ANTON, f2.size - 2)
        dr.rounded_rectangle((24, 222, w - 24, 278), 14, fill=(255, 255, 255, 22))
        dr.text((w / 2, 250), txt, font=f2, fill="white", anchor="mm")
        return im

    @staticmethod
    def person(dr, x, base, hgt):
        """Simple standing figure, hgt px tall."""
        col = (190, 215, 205, 235)
        u = hgt / 8.0                                 # head = 1/8 of the body
        dr.ellipse((x - u * 0.5, base - hgt, x + u * 0.5, base - hgt + u), fill=col)
        dr.rounded_rectangle((x - u * 0.95, base - hgt + u * 1.1, x + u * 0.95, base - hgt + u * 4.1), max(1, u * 0.4), fill=col)
        dr.rounded_rectangle((x - u * 1.35, base - hgt + u * 1.2, x - u * 1.0, base - hgt + u * 4.2), max(1, u * 0.18), fill=col)
        dr.rounded_rectangle((x + u * 1.0, base - hgt + u * 1.2, x + u * 1.35, base - hgt + u * 4.2), max(1, u * 0.18), fill=col)
        dr.rounded_rectangle((x - u * 0.85, base - hgt + u * 4.0, x - u * 0.1, base), max(1, u * 0.2), fill=col)
        dr.rounded_rectangle((x + u * 0.1, base - hgt + u * 4.0, x + u * 0.85, base), max(1, u * 0.2), fill=col)

    # ------------------------------------------------------------------ card-area panels
    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zones = self.j["zones"]
        k = next((n for n, z in enumerate(zones) if z[2] == seg["name"]), 0)
        dr.text((cw / 2, ch * 0.24), f"BOYUT SINIFI {k + 1} / {len(zones)}", font=R.font(R.F_UI, 36), fill=YEL, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 80:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 5, ch * 0.48 + 6), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, ch * 0.48), seg["name"], font=f, fill="white", anchor="mm")
        # a short piece of tape as the divider
        y = ch * 0.68
        dr.rectangle((cw / 2 - 300, y, cw / 2 + 300, y + 34), fill=YEL + (255,))
        for q in range(0, 61):
            xx = cw / 2 - 300 + q * 10
            dr.line((xx, y, xx, y + (20 if q % 10 == 0 else 10)), fill=INK + (255,), width=2 if q % 10 == 0 else 1)
        dr.text((cw / 2, ch * 0.84), seg["range"], font=R.font(R.F_UI, 48), fill=(225, 235, 230), anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((40, 50, cw - 40, ch - 50), 30, fill=(6, 16, 12, 175), outline=YEL + (170,), width=3)
        dr.text((cw / 2, 130), "ÖLÇEK KIYASI", font=R.font(R.F_UI, 36), fill=YEL, anchor="mm")
        f = R.font(R.F_ANTON, 170)
        while dr.textlength(seg["value"], font=f) > cw - 160:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 6), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 50)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 160:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 140), name, font=f2, fill=(225, 235, 230), anchor="mm")
        return im

    # ------------------------------------------------------------------ frame
    def draw(self, img, t, b, lt, default):
        k = b["kind"]
        if k == "end":
            default()
            return
        d = max(R.depth_at(b, t, self.j), self.j["min"])
        alpha = R.ease(lt / 0.6) * R.ease((b["dur"] - lt) / 0.6)
        if k in ("creature", "intro", "outro"):
            default()
        elif k == "landmark":
            self.s.paste(img, self.landmark_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        elif k == "zone":
            self.s.paste(img, self.zone_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        seg = b.get("seg")
        if k == "travel" or (seg and seg["type"] not in ("creature", "landmark")):
            seg = None
        pa = 1.0 if t > R.COLD_OPEN + 1.2 else R.ease((t - R.COLD_OPEN) / 1.2)
        self.s.paste(img, self.panel(d, seg), (PANEL[0], PANEL[1]), pa)
        tp = self.tape(d)
        self.s.paste(img, tp, (0, TAPE_Y), pa)
        now = b.get("i", -1)
        show = k in ("creature",) and lt > 0.3
        if k in ("outro",):
            now, show = 10 ** 6, True
        self.pins(img, d, now, show)
        self.hairline(img, d)
