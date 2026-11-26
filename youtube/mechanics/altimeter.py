"""Altimeter: a cockpit climb through the sky, from the ground to 11,300 metres, the highest a bird has ever flown.

The whole screen is the sky seen from a climbing aircraft. Near the ground there are green and blue hills at the
bottom of the frame; as we climb they sink away, three cloud decks (low cumulus, mid-level altocumulus and high
cirrus) slide down through the picture as we pass through them, a snowy mountain range rises in front of us and then
drops below, the blue turns to deep navy and faint stars appear above the death zone. Wind streaks rush past.

On the right is a cockpit instrument panel drawn in code:
  * a round three-pointer aviation ALTIMETER (0-9 dial, hundreds / thousands / ten-thousands hands) whose hands spin
    with the climb, with a rolling digital drum "06.540 M" in its face;
  * three gauges under it, read from the international standard atmosphere: OUTSIDE AIR (°C), AIR PRESSURE (hPa) and
    OXYGEN (share of the sea-level amount), each with a bar that empties as we climb;
  * a paper "UÇUŞ DEFTERİ" (flight log) where every animal we meet is written in with the altitude where it flew,
    newest line on top.
Travel blocks show a big translucent climb readout ("▲ 6.540 m") in the card area; zones are "HAVA KATMANI" panels
with that layer's air values; landmarks are "İRTİFA KIYASI" cards with a code-drawn tower or mountain icon.

script.json:
  "mechanic": "altimeter",
  "journey": {"meter": false, "max": 11300, "unit": "m", "card": [40, 96, 1232, 693], "sub_cx": 656,
              "air": {"x": [...], "p": [...], "t": [...], "o2": [...]}, "clouds": [1800, 4200, 8800], ...}
  segment "depth" = altitude in metres (always ascending).
  landmarks may add "icon": "tower" | "mountain" and "tag"; creatures may add "short" (name in the flight log).
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

PX0, PX1 = 1300, 1900          # instrument panel
DCX, DCY, DR = 1600, 290, 220  # altimeter dial centre and radius

SKY_H = [0, 1000, 3000, 6000, 9000, 11300]
SKY_TOP = [(70, 140, 215), (60, 125, 205), (45, 100, 185), (30, 70, 150), (14, 36, 98), (6, 16, 58)]
SKY_BOT = [(178, 212, 236), (166, 205, 235), (140, 190, 230), (108, 162, 214), (78, 130, 196), (56, 104, 176)]
AMBER = (255, 176, 46)


def fmt_m(v):
    return R.fmt_num(round(v), 0) + " m"


def interp_col(d, hs, cols):
    return np.array([np.interp(d, hs, [c[k] for c in cols]) for k in range(3)], np.float32)


class Mechanic:
    subtitles = False             # own subtitles under the photo card (the instrument panel takes the right side)

    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.air = self.j["air"]
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        self.yy = np.linspace(0, 1, R.H, dtype=np.float32)[:, None, None]
        rng = np.random.default_rng(41)
        self.clouds = [self._cloud_band(rng, kind) for kind in ("cumulus", "alto", "cirrus")]
        self.hills = self._hills(rng)
        self.peaks = self._peaks(rng)
        self.stars = rng.uniform(0, 1, (140, 3))
        self.streaks = rng.uniform(0, 1, (26, 4))

    # ------------------------------------------------------------------ background layers (built once)
    def _cloud_band(self, rng, kind):
        """A 2W x 420 RGBA float layer of soft clouds; tiles horizontally."""
        w, h = R.W * 2, 420
        im = Image.new("L", (w // 2, h // 2), 0)
        dr = ImageDraw.Draw(im)
        n = {"cumulus": 70, "alto": 130, "cirrus": 60}[kind]
        for _ in range(n):
            x, y = rng.uniform(0, w // 2), rng.uniform(40, h // 2 - 40)
            if kind == "cumulus":
                r = rng.uniform(18, 46)
                for q in range(5):
                    ox, oy = rng.uniform(-1.6, 1.6) * r, rng.uniform(-0.5, 0.2) * r
                    rr = r * rng.uniform(0.6, 1.0)
                    dr.ellipse((x + ox - rr, y + oy - rr, x + ox + rr, y + oy + rr * 0.7), fill=int(rng.uniform(170, 255)))
            elif kind == "alto":
                r = rng.uniform(6, 14)
                dr.ellipse((x - r * 1.6, y - r, x + r * 1.6, y + r), fill=int(rng.uniform(120, 220)))
            else:
                L = rng.uniform(80, 220)
                for q in range(4):
                    dr.line((x, y + q * 3, x + L, y - L * 0.12 + q * 3), fill=int(rng.uniform(90, 180)), width=2)
        # wrap the edge so the band tiles
        arr = np.asarray(im, np.float32)
        blur = {"cumulus": 7, "alto": 3, "cirrus": 4}[kind]
        im = Image.fromarray(arr.astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)).resize((w, h), Image.BILINEAR)
        a = np.asarray(im, np.float32) / 255.0
        fade = np.clip(np.minimum(np.arange(h), h - 1 - np.arange(h)) / 90.0, 0, 1)[:, None]
        a = a * fade
        shade = 1.0 - 0.25 * np.linspace(0, 1, h, dtype=np.float32)[:, None]      # darker cloud bases
        return a[..., None], shade[..., None]

    def _hills(self, rng):
        im = Image.new("RGBA", (R.W, 520), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for layer, (base, amp, col) in enumerate(((150, 70, (110, 150, 190, 255)), (300, 60, (70, 120, 80, 255)),
                                                  (400, 40, (50, 95, 55, 255)))):
            pts = [(0, 520)]
            ph = rng.uniform(0, 6)
            for x in range(0, R.W + 40, 40):
                y = base - amp * (0.5 + 0.5 * math.sin(x / (260 - layer * 50) + ph)) - rng.uniform(0, 12)
                pts.append((x, y))
            pts.append((R.W, 520))
            dr.polygon(pts, fill=col)
        return im

    def _peaks(self, rng):
        im = Image.new("RGBA", (R.W, 700), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        x = -80
        while x < R.W + 80:
            w = rng.uniform(220, 420)
            h = rng.uniform(260, 520)
            top = (x + w / 2 + rng.uniform(-40, 40), 700 - h)
            dr.polygon([(x, 700), top, (x + w, 700)], fill=(88, 104, 130, 255))
            dr.polygon([(top[0], top[1]), (top[0] - w * 0.16, top[1] + h * 0.26), (top[0] - w * 0.05, top[1] + h * 0.2),
                        (top[0] + w * 0.04, top[1] + h * 0.29), (top[0] + w * 0.17, top[1] + h * 0.25)],
                       fill=(236, 242, 250, 255))
            dr.line((top, (top[0] + w * 0.25, 700)), fill=(70, 84, 108, 255), width=3)
            x += w * 0.62
        return im

    # ------------------------------------------------------------------ the sky
    def u(self, d):
        return R.to_unit(d, self.j)

    def background(self, d, t, b):
        top, bot = interp_col(d, SKY_H, SKY_TOP), interp_col(d, SKY_H, SKY_BOT)
        frame = top[None, None, :] * (1 - self.yy) + bot[None, None, :] * self.yy
        frame = np.broadcast_to(frame, (R.H, R.W, 3)).copy()
        u = self.u(d)
        # stars above the death zone
        sa = float(np.clip((d - 7500) / 3800, 0, 1))
        if sa > 0.02:
            for x, y, ph in self.stars:
                self.s.add(frame, x * R.W, y * R.H * 0.55, 1, 160 * sa * (0.6 + 0.4 * math.sin(t * 2 + ph * 9)),
                           (0.9, 0.95, 1.0))
        # snowy range: towers above us at 2.5 km, sinks below the frame near 10 km
        if 1500 < d < 10500:
            py = int(560 + (u - self.u(5200)) * 1700)
            if py < R.H:
                frame = self._layer(frame, self.peaks, py, 0.9 * float(np.clip((d - 1500) / 1200, 0, 1)), haze=bot)
        # hills at the bottom, gone by 2 km
        hy = int(560 + u * 2100)
        if hy < R.H:
            frame = self._layer(frame, self.hills, hy, 1.0, haze=bot, haze_a=0.25)
        # cloud decks slide down through the frame as we pass them
        for (a, shade), h, col, amp in zip(self.clouds, self.j.get("clouds", [1800, 4200, 8800]),
                                           ((255, 255, 255), (240, 244, 250), (250, 252, 255)), (0.95, 0.8, 0.65)):
            cy = int(540 + (u - self.u(h)) * 2600)
            if -220 < cy < R.H + 220:
                off = int(t * (22 + 8 * amp)) % R.W
                y0 = cy - 210
                ys0, ys1 = max(0, -y0), min(420, R.H - y0)
                if ys1 > ys0:
                    al = a[ys0:ys1, off:off + R.W] * amp
                    c = np.array(col, np.float32) * shade[ys0:ys1]
                    sl = frame[y0 + ys0:y0 + ys1]
                    frame[y0 + ys0:y0 + ys1] = sl * (1 - al) + c * al
        frame *= self.s.vign
        # wind streaks
        for x, y, ln, sp in self.streaks:
            px = (x * R.W - t * (500 + 500 * sp)) % (R.W + 300) - 150
            py = y * R.H
            L = int(60 + ln * 120)
            x0, x1 = int(max(px, 0)), int(min(px + L, R.W))
            if x1 > x0:
                frame[int(py):int(py) + 2, x0:x1] += 38 * (0.4 + 0.6 * sp)
        return frame

    def _layer(self, frame, im, y, alpha, haze, haze_a=0.35):
        """Composite an RGBA silhouette with its top edge at screen row y (clipped at the bottom)."""
        h = min(im.height, R.H - y)
        if h <= 0 or alpha <= 0.01:
            return frame
        arr = np.asarray(im, np.float32)[:h]
        a = arr[..., 3:4] / 255.0 * alpha
        rgb = arr[..., :3] * (1 - haze_a) + haze[None, None, :] * haze_a
        y0 = max(y, 0)
        cut = y0 - y
        frame[y0:y + h] = frame[y0:y + h] * (1 - a[cut:]) + rgb[cut:] * a[cut:]
        return frame

    # ------------------------------------------------------------------ instrument panel
    def panel(self):
        return self.s.text_img("panel", self._panel)

    def _panel(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((PX0, 28, PX1, 1062), 30, fill=(18, 20, 24, 236), outline=(90, 96, 104, 255), width=3)
        for x, y in ((PX0 + 22, 50), (PX1 - 22, 50), (PX0 + 22, 1040), (PX1 - 22, 1040)):      # panel screws
            dr.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(70, 74, 80))
            dr.line((x - 5, y, x + 5, y), fill=(30, 32, 36), width=2)
        # dial bezel and face
        dr.ellipse((DCX - DR - 18, DCY - DR - 18, DCX + DR + 18, DCY + DR + 18), fill=(52, 56, 62))
        dr.ellipse((DCX - DR - 6, DCY - DR - 6, DCX + DR + 6, DCY + DR + 6), fill=(8, 9, 11))
        for k in range(50):
            a = math.radians(k * 7.2 - 90)
            r0 = DR - (30 if k % 5 == 0 else 16)
            dr.line((DCX + math.cos(a) * r0, DCY + math.sin(a) * r0, DCX + math.cos(a) * (DR - 4), DCY + math.sin(a) * (DR - 4)),
                    fill=(240, 240, 240), width=5 if k % 5 == 0 else 2)
        f = R.font(R.F_ANTON, 52)
        for n in range(10):
            a = math.radians(n * 36 - 90)
            dr.text((DCX + math.cos(a) * (DR - 66), DCY + math.sin(a) * (DR - 66)), str(n), font=f, fill="white", anchor="mm")
        dr.text((DCX, DCY - 92), "ALTİMETRE", font=R.font(R.F_UI, 24), fill=(200, 200, 200), anchor="mm")
        dr.text((DCX, DCY - 64), "× 100 METRE", font=R.font(R.F_UI, 18), fill=(150, 150, 150), anchor="mm")
        # gauge labels
        for k, name in enumerate(("DIŞ HAVA", "HAVA BASINCI", "OKSİJEN")):
            x0 = PX0 + 24 + k * 188
            dr.rounded_rectangle((x0, 560, x0 + 176, 720), 16, fill=(8, 9, 11), outline=(70, 74, 80), width=2)
            dr.text((x0 + 88, 584), name, font=R.font(R.F_UI, 20), fill=(190, 190, 190), anchor="mm")
            dr.rounded_rectangle((x0 + 16, 690, x0 + 160, 704), 7, fill=(40, 42, 46))
        # flight log paper
        dr.rounded_rectangle((PX0 + 24, 744, PX1 - 24, 1038), 12, fill=(238, 230, 205, 255))
        dr.rectangle((PX0 + 24, 744, PX1 - 24, 794), fill=(200, 60, 40, 255))
        dr.text(((PX0 + PX1) / 2, 769), "UÇUŞ DEFTERİ", font=R.font(R.F_ANTON, 32), fill=(255, 245, 230), anchor="mm")
        for k in range(6):
            y = 836 + k * 40
            dr.line((PX0 + 40, y, PX1 - 40, y), fill=(160, 180, 200, 255), width=1)
        dr.line((PX0 + 168, 800, PX0 + 168, 1030), fill=(220, 120, 110, 255), width=2)
        return im

    def hands(self, img, d):
        dr = ImageDraw.Draw(img)

        def hand(frac, length, width, col, tri=False):
            a = math.radians(frac * 360 - 90)
            ca, sa = math.cos(a), math.sin(a)
            px, py = -sa, ca
            tip = (DCX + ca * length, DCY + sa * length)
            tail = (DCX - ca * 30, DCY - sa * 30)
            if tri:
                dr.line((tail, tip), fill=col, width=3)
                b = (DCX + ca * (length - 34), DCY + sa * (length - 34))
                dr.polygon([tip, (b[0] + px * 14, b[1] + py * 14), (b[0] - px * 14, b[1] - py * 14)], fill=col)
            else:
                dr.polygon([(tail[0] + px * width, tail[1] + py * width), (tip[0] + px * width * 0.35, tip[1] + py * width * 0.35),
                            tip, (tip[0] - px * width * 0.35, tip[1] - py * width * 0.35),
                            (tail[0] - px * width, tail[1] - py * width)], fill=col)

        hand(d / 100000.0, DR - 12, 2, AMBER, tri=True)          # ten-thousands: thin pointer with triangle
        hand((d % 10000) / 10000.0, DR * 0.52, 12, (235, 235, 235))   # thousands: short wide
        hand((d % 1000) / 1000.0, DR - 26, 7, (255, 255, 255))   # hundreds: long
        dr.ellipse((DCX - 14, DCY - 14, DCX + 14, DCY + 14), fill=(60, 62, 66), outline=(200, 200, 200), width=2)

    def drum(self, d):
        v = int(round(d))
        return self.s.text_img(("drum", v), lambda: self._drum(v))

    def _drum(self, v):
        txt = f"{v // 1000:02d}.{v % 1000:03d}"
        im = Image.new("RGBA", (230, 66), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, 229, 65), 8, fill=(30, 32, 36), outline=(120, 120, 120), width=2)
        f = R.font(R.F_ANTON, 46)
        for k, ch in enumerate(txt):
            x = 18 + k * 30
            if ch != ".":
                dr.rectangle((x - 2, 8, x + 26, 57), fill=(6, 6, 8))
            dr.text((x + 12, 33), ch, font=f, fill=AMBER if k < 2 else "white", anchor="mm")
        dr.text((206, 40), "M", font=R.font(R.F_UI, 22), fill=(200, 200, 200), anchor="mm")
        return im

    def gauges(self, d):
        key = int(round(d / 25.0))
        return self.s.text_img(("gauges", key), lambda: self._gauges(key * 25.0))

    def _gauges(self, d):
        im = Image.new("RGBA", (PX1 - PX0, 180), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        x = self.air["x"]
        temp = float(np.interp(d, x, self.air["t"]))
        pres = float(np.interp(d, x, self.air["p"]))
        o2 = float(np.interp(d, x, self.air["o2"]))
        vals = [(("−" if temp < -0.5 else "") + R.fmt_num(abs(temp), 0) + " °C", (temp + 60) / 75, (120, 200, 255)),
                (R.fmt_num(pres, 0) + " hPa", pres / 1013.25, (255, 255, 255)),
                ("%" + R.fmt_num(o2, 0), o2 / 100, (120, 240, 140) if o2 > 50 else (255, 190, 60) if o2 > 35 else (255, 90, 70))]
        for k, (txt, frac, col) in enumerate(vals):
            x0 = 24 + k * 188
            f = R.font(R.F_ANTON, 46)
            while dr.textlength(txt, font=f) > 160:
                f = R.font(R.F_ANTON, f.size - 2)
            dr.text((x0 + 88, 82), txt, font=f, fill=col, anchor="mm")
            w = max(4, 144 * float(np.clip(frac, 0, 1)))
            dr.rounded_rectangle((x0 + 16, 130, x0 + 16 + w, 144), 7, fill=col)
            if k == 2:
                dr.text((x0 + 88, 116), "DENİZ SEVİYESİNE GÖRE", font=R.font(R.F_UI, 13), fill=(160, 160, 160), anchor="mm")
        return im

    def log(self, img, now, show_now, cur):
        items = [b for b in self.cr if b["i"] < now or (b["i"] == now and show_now)]
        key = ("log", tuple(b["i"] for b in items), cur)
        self.s.paste(img, self.s.text_img(key, lambda: self._log(items, cur)), (0, 0), 1.0)

    def _log(self, items, cur):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        f1, f2 = R.font(R.F_ANTON, 26), R.font(R.F_UI, 23)
        rows = list(reversed(items))[:6]
        for k, b in enumerate(rows):
            y = 816 + k * 40
            on = b["i"] == cur
            if on:
                dr.rectangle((PX0 + 34, y - 18, PX1 - 34, y + 18), fill=(255, 214, 120, 255))
            ink = (30, 40, 90) if k == 0 else (70, 80, 110)
            dr.text((PX0 + 156, y), fmt_m(b["seg"]["depth"]), font=f1, fill=ink, anchor="rm")
            name = R.tr_upper(b["seg"].get("short", b["seg"]["name"]))
            while dr.textlength(name, font=f2) > PX1 - PX0 - 230 and len(name) > 4:
                name = name[:-2]
            dr.text((PX0 + 184, y), name, font=f2, fill=ink, anchor="lm")
        n = len(items)
        dr.text((PX1 - 40, 1022), f"{n} / {len(self.cr)} CANLI", font=R.font(R.F_UI, 18), fill=(120, 110, 90), anchor="rm")
        return im

    def instrument(self, img, d, b, k):
        self.s.paste(img, self.panel(), (0, 0), 1.0)
        self.hands(img, d)
        dm = self.drum(d)
        self.s.paste(img, dm, (DCX - dm.width // 2, DCY + 70), 1.0)
        self.s.paste(img, self.gauges(d), (PX0, 560), 1.0)
        now = b.get("i", -1)
        show = k == "creature"
        cur = now if k == "creature" else None
        if k in ("outro", "end"):
            now, show = 10 ** 6, True
        self.log(img, now, show, cur)

    # ------------------------------------------------------------------ card-area panels
    def climb_readout(self, d):
        key = int(round(d / 10.0)) * 10
        return self.s.text_img(("climb", key), lambda: self._climb(key))

    def _climb(self, v):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        txt = fmt_m(v)
        f = R.font(R.F_ANTON, 190)
        dr.text((cw / 2 + 6, ch / 2 + 8), txt, font=f, fill=(0, 20, 50, 110), anchor="mm")
        dr.text((cw / 2, ch / 2), txt, font=f, fill=(255, 255, 255, 235), anchor="mm")
        dr.text((cw / 2, ch / 2 - 150), "▲ TIRMANIYORUZ", font=R.font(R.F_UI, 40), fill=AMBER + (240,), anchor="mm")
        return im

    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zones = self.j["zones"]
        k = next((n for n, z in enumerate(zones) if z[2] == seg["name"]), 0)
        dr.rounded_rectangle((40, 40, cw - 40, ch - 40), 30, fill=(6, 18, 40, 175), outline=(170, 210, 255, 170), width=3)
        dr.text((cw / 2, 115), f"HAVA KATMANI {k + 1} / {len(zones)}", font=R.font(R.F_UI, 36), fill=(150, 205, 255), anchor="mm")
        f = R.font(R.F_ANTON, 140)
        while dr.textlength(seg["name"], font=f) > cw - 140:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 5, 250 + 6), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, 250), seg["name"], font=f, fill="white", anchor="mm")
        dr.text((cw / 2, 375), seg["range"], font=R.font(R.F_ANTON, 60), fill=AMBER, anchor="mm")
        # air at the top of this layer
        a, b = zones[k][0], zones[k][1]
        x = self.air["x"]
        cells = [("SICAKLIK", lambda h: ("−" if np.interp(h, x, self.air["t"]) < -0.5 else "")
                  + R.fmt_num(abs(float(np.interp(h, x, self.air["t"]))), 0) + " °C"),
                 ("BASINÇ", lambda h: R.fmt_num(float(np.interp(h, x, self.air["p"])), 0) + " hPa"),
                 ("OKSİJEN", lambda h: "%" + R.fmt_num(float(np.interp(h, x, self.air["o2"])), 0))]
        for n, (name, fn) in enumerate(cells):
            cx = cw / 2 + (n - 1) * 330
            dr.rounded_rectangle((cx - 150, 440, cx + 150, 600), 18, fill=(0, 0, 0, 120))
            dr.text((cx, 470), name, font=R.font(R.F_UI, 26), fill=(170, 200, 230), anchor="mm")
            dr.text((cx, 520), f"{fn(a)}", font=R.font(R.F_ANTON, 40), fill="white", anchor="mm")
            dr.text((cx, 568), f"→ {fn(b)}", font=R.font(R.F_ANTON, 34), fill=AMBER, anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((60, 60, cw - 60, ch - 60), 30, fill=(8, 14, 26, 200), outline=AMBER + (220,), width=4)
        dr.rounded_rectangle((60, 60, cw - 60, 150), 30, fill=AMBER + (240,))
        dr.rectangle((60, 120, cw - 60, 150), fill=AMBER + (240,))
        dr.text((cw / 2, 105), seg.get("tag", "İRTİFA KIYASI"), font=R.font(R.F_ANTON, 46), fill=(20, 16, 8), anchor="mm")
        # icon on the left
        ix, base = 250, ch - 110
        if seg.get("icon") == "tower":
            dr.polygon([(ix - 26, base), (ix - 9, base - 330), (ix + 9, base - 330), (ix + 26, base)], fill=(200, 210, 225))
            dr.line((ix, base - 330, ix, base - 390), fill=(200, 210, 225), width=4)
            for q in range(1, 6):
                y = base - q * 55
                dr.line((ix - 26 + q * 3, y, ix + 26 - q * 3, y), fill=(120, 130, 150), width=2)
        else:
            dr.polygon([(ix - 170, base), (ix, base - 330), (ix + 170, base)], fill=(120, 135, 160))
            dr.polygon([(ix, base - 330), (ix - 58, base - 218), (ix - 18, base - 240), (ix + 16, base - 212),
                        (ix + 58, base - 222)], fill=(245, 248, 252))
        dr.line((90, base, 420, base), fill=(200, 200, 200), width=3)
        f = R.font(R.F_ANTON, 170)
        while dr.textlength(seg["value"], font=f) > cw - 560:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 160, ch / 2 + 10), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 50)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 560:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2 + 160, ch - 150), name, font=f2, fill=(235, 240, 230), anchor="mm")
        return im

    # ------------------------------------------------------------------ subtitles
    def sub(self, text):
        return self.s.text_img(("asub", text), lambda: self._sub(text))

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
        d = R.depth_at(b, t, self.j)
        alpha = R.ease(lt / 0.6) * R.ease((b["dur"] - lt) / 0.6)
        if k in ("creature", "intro", "outro"):
            default()
        elif k == "landmark":
            self.s.paste(img, self.landmark_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        elif k == "zone":
            self.s.paste(img, self.zone_panel(b["seg"]), (R.CARD[0], R.CARD[1]), alpha)
        elif k == "travel":
            a = math.sin(math.pi * min(1.0, lt / b["dur"])) * 0.85
            self.s.paste(img, self.climb_readout(d), (R.CARD[0], R.CARD[1]), a)
        pa = 1.0 if t > R.COLD_OPEN + 1.2 else R.ease((t - R.COLD_OPEN) / 1.2)
        if pa < 0.999:
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            self.instrument(layer, d, b, k)
            self.s.paste(img, layer, (0, 0), pa)
        else:
            self.instrument(img, d, b, k)
        self.subtitle(img, t, b)
