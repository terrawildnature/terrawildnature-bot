"""Speed dial: a car-style speedometer on the right whose needle sweeps from the slowest animals to the fastest. The photo
card sits on the left, a live leaderboard ("HIZ SIRALAMASI") under the dial fills up with every animal (each new one
takes the lead), and speed streaks in the background rush past faster and faster as the needle climbs.

script.json:
  "mechanic": "speed_dial",
  "journey": {"meter": false, "scale": "log", "min": 0.001, "max": 400, "unit": "km/sa",
              "units": [[0, "m/sa", 1000], [1, "km/sa", 1]], "zones": [[0.001, 1, "AĞIR ÇEKİM"], ...],
              "card": [56, 120, 1120, 630], "sub_cx": 960, "range_label": "HIZ", ...}
  creature / landmark segments: "depth" = speed in km/h (ascending), "range" = speed label shown on the card.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import doc_render as R

DCX, DCY, DR = 1545, 300, 212          # dial centre and radius
A0, SWEEP = 225.0, 270.0               # start angle (deg, maths convention) and clockwise sweep
ZCOL = [(60, 200, 175), (120, 215, 90), (240, 215, 60), (250, 160, 45), (245, 95, 45), (225, 35, 70)]
LB_X, LB_Y, LB_W, ROW, ROWS = 1236, 566, 650, 48, 5
GROW = 1.3                             # seconds for a new bar to grow
BG_SLOW, BG_MID, BG_FAST = np.array([10, 30, 42], np.float32), np.array([34, 26, 58], np.float32), np.array([62, 14, 22], np.float32)


def u_of(d, j):
    return R.to_unit(max(d, j.get("min", 0.001)), j)


class Mechanic:
    def __init__(self, scene):
        self.s = scene
        self.j = scene.spec["journey"]
        self.zones = self.j["zones"]
        self.cr = [b for b in scene.blocks if b["kind"] == "creature"]
        self.thumbs = {}
        rng = np.random.default_rng(11)
        # speed streaks: thin horizontal light lines on a 2W-wide strip that scrolls left
        st = Image.new("L", (R.W * 2, R.H), 0)
        dr = ImageDraw.Draw(st)
        for _ in range(170):
            y = rng.uniform(0, R.H)
            x = rng.uniform(0, R.W * 2)
            ln = rng.uniform(80, 520)
            dr.line((x, y, x + ln, y), fill=int(rng.uniform(40, 200)), width=int(rng.choice([1, 1, 2, 3])))
        st = st.filter(ImageFilter.GaussianBlur(1.2))
        a = np.asarray(st, np.float32) / 255.0
        a[:, :R.W] = np.maximum(a[:, :R.W], a[:, R.W:])   # seamless wrap
        a[:, R.W:] = a[:, :R.W]
        self.streak = a
        self.offsets = self._offsets()

    # ------------------------------------------------------------------ helpers
    def _offsets(self):
        """Cumulative scroll of the streaks per frame (deterministic, so parallel shards agree)."""
        blocks = self.s.blocks
        total = blocks[-1]["t0"] + blocks[-1]["dur"]
        n = int(total * R.FPS) + 2
        off = np.zeros(n, np.float32)
        k, acc = 0, 0.0
        for f in range(n):
            t = f / R.FPS
            while k + 1 < len(blocks) and t >= blocks[k]["t0"] + blocks[k]["dur"]:
                k += 1
            b = blocks[k]
            u = 0.0 if b["kind"] == "cold" else u_of(R.depth_at(b, t, self.j), self.j)
            acc += (30 + 2600 * u ** 2.2) / R.FPS
            off[f] = acc
        return off

    def zone_index(self, d):
        for k, (a, b, _) in enumerate(self.zones):
            if d < b:
                return k
        return len(self.zones) - 1

    def ang(self, u):
        return math.radians(A0 - SWEEP * u)

    def pt(self, u, r):
        a = self.ang(u)
        return DCX + r * math.cos(a), DCY - r * math.sin(a)

    # ------------------------------------------------------------------ background
    def background(self, d, t, b):
        u = 0.0 if b["kind"] in ("cold",) else u_of(d, self.j)
        c = BG_SLOW + (BG_MID - BG_SLOW) * min(u * 2, 1) if u < 0.5 else BG_MID + (BG_FAST - BG_MID) * (u * 2 - 1)
        if b["kind"] == "end":
            c = BG_MID * 0.8
        top, bot = c * 1.35, c * 0.55
        v = self.s.vert[..., None]
        frame = top[None, None, :] * (1 - v) + bot[None, None, :] * v
        f = min(int(t * R.FPS), len(self.offsets) - 1)
        off = int(self.offsets[f]) % R.W
        amp = 26 + 120 * u
        tint = np.array([0.75, 0.85, 1.0], np.float32) * (1 - u) + np.array([1.0, 0.72, 0.55], np.float32) * u
        frame = frame + self.streak[:, off:off + R.W, None] * (amp * tint)
        return frame * self.s.vign

    # ------------------------------------------------------------------ dial
    def dial(self, zk):
        return self.s.text_img(("dial", zk), lambda: self._dial(zk))

    def _dial(self, zk):
        S = 2   # supersampled for smooth arcs
        im = Image.new("RGBA", (R.W * S, 720 * S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        cx, cy, r = DCX * S, DCY * S, DR * S
        dr.ellipse((cx - r - 34 * S, cy - r - 34 * S, cx + r + 34 * S, cy + r + 34 * S), fill=(6, 10, 18, 185),
                   outline=(255, 255, 255, 40), width=3 * S)
        box = (cx - r, cy - r, cx + r, cy + r)
        for k, (a, b, _) in enumerate(self.zones):
            ua, ub = u_of(a, self.j), u_of(b, self.j)
            # PIL arcs run clockwise from 3 o'clock in screen degrees
            s0, s1 = -(A0 - SWEEP * ua), -(A0 - SWEEP * ub)
            col = ZCOL[k % len(ZCOL)]
            alpha = 255 if k == zk else 110
            dr.arc(box, s0, s1, fill=col + (alpha,), width=(30 if k == zk else 20) * S)
        # ticks: decades major, 2..9 minor
        lo, hi = self.j.get("min", 0.001), self.j["max"]
        dec = 10 ** math.floor(math.log10(lo))
        while dec <= hi:
            for m in range(1, 10):
                v = dec * m
                if v < lo or v > hi:
                    continue
                u = u_of(v, self.j)
                major = m == 1
                p0, p1 = self.pt(u, DR - 26), self.pt(u, DR - (52 if major else 38))
                dr.line((p0[0] * S, p0[1] * S, p1[0] * S, p1[1] * S), fill=(255, 255, 255, 230 if major else 110), width=(4 if major else 2) * S)
                if major:
                    lx, ly = self.pt(u, DR - 80)
                    dr.text((lx * S, ly * S), R.fmt_num(v, max(0, -int(math.floor(math.log10(v))))), font=R.font(R.F_UI, 24 * S),
                            fill=(220, 230, 240, 230), anchor="mm")
            dec *= 10
        u = u_of(hi, self.j)
        lx, ly = self.pt(u, DR - 80)
        dr.text((lx * S, ly * S), R.fmt_num(hi), font=R.font(R.F_UI, 24 * S), fill=(255, 120, 110, 255), anchor="mm")
        im = im.resize((R.W, 720), Image.LANCZOS)
        return im

    def needle(self, img, u, wob):
        u = min(max(u + wob, 0.0), 1.0)
        a = self.ang(u)
        ca, sa = math.cos(a), -math.sin(a)
        px, py = -sa, ca
        tip = (DCX + (DR - 30) * ca, DCY + (DR - 30) * sa)
        tail = (DCX - 34 * ca, DCY - 34 * sa)
        w = 9
        dr = ImageDraw.Draw(img)
        dr.polygon([(tail[0] + px * w, tail[1] + py * w), tip, (tail[0] - px * w, tail[1] - py * w)], fill=(255, 70, 50))
        dr.ellipse((DCX - 26, DCY - 26, DCX + 26, DCY + 26), fill=(30, 34, 44), outline=(255, 70, 50), width=4)

    def readout(self, d, zk):
        txt = self.s.fmt_pos(d)
        return self.s.text_img(("ro", txt, zk), lambda: self._readout(txt, zk))

    def _readout(self, txt, zk):
        im = Image.new("RGBA", (520, 190), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.text((260, 40), txt, font=R.font(R.F_ANTON, 56), fill="white", anchor="mm")
        name = self.zones[zk][2]
        col = ZCOL[zk % len(ZCOL)]
        f = R.font(R.F_UI, 28)
        tw = dr.textlength(name, font=f)
        dr.rounded_rectangle((260 - tw / 2 - 20, 84, 260 + tw / 2 + 20, 124), 20, fill=col + (235,))
        dr.text((260, 104), name, font=f, fill=(15, 15, 20), anchor="mm")
        return im

    # ------------------------------------------------------------------ leaderboard
    def thumb(self, i):
        if i not in self.thumbs:
            key = self.s.photos[f"{i:02d}"][0]["file"][:-4]
            im = Image.open(self.s.doc / "photos" / f"{key}.jpg").convert("RGB")
            c = min(im.size)
            im = im.crop(((im.width - c) // 2, (im.height - c) // 2, (im.width + c) // 2, (im.height + c) // 2))
            sz = ROW - 8
            im = im.resize((sz * 2, sz * 2), Image.LANCZOS)
            m = Image.new("L", (sz * 2, sz * 2), 0)
            ImageDraw.Draw(m).ellipse((0, 0, sz * 2 - 1, sz * 2 - 1), fill=255)
            im.putalpha(m)
            self.thumbs[i] = im.resize((sz, sz), Image.LANCZOS)
        return self.thumbs[i]

    def board(self, now, p, show_now):
        q = round(p * 20) / 20
        return self.s.text_img(("lb", now, q, show_now), lambda: self._board(now, q, show_now))

    def _board(self, now, p, show_now):
        im = Image.new("RGBA", (LB_W, 46 + ROWS * ROW + 16), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, LB_W - 1, im.height - 1), 18, fill=(6, 10, 18, 175))
        done = [b for b in self.cr if b["i"] < now or (b["i"] == now and show_now)]
        dr.text((18, 24), "HIZ SIRALAMASI", font=R.font(R.F_UI, 26), fill=(255, 210, 80), anchor="lm")
        dr.text((LB_W - 18, 24), f"{len(done)} / {len(self.cr)} CANLI", font=R.font(R.F_UI, 22), fill=(170, 190, 210), anchor="rm")
        rows = sorted(done, key=lambda b: (-b["seg"]["depth"], -b["i"]))[:ROWS]
        lead_before = max([b["seg"]["depth"] for b in self.cr if b["i"] < now] or [0])
        for k, b in enumerate(rows):
            y = 46 + k * ROW
            cur = b["i"] == now
            if cur:
                dr.rounded_rectangle((6, y + 2, LB_W - 7, y + ROW - 2), 12, fill=(255, 255, 255, 34))
            dr.text((30, y + ROW / 2), str(k + 1), font=R.font(R.F_ANTON, 30), fill=(255, 210, 80) if k == 0 else (200, 210, 220), anchor="mm")
            th = self.thumb(b["i"])
            im.alpha_composite(th, (52, y + 4))
            name = R.tr_upper(b["seg"]["name"])
            f = R.font(R.F_UI, 22)
            while dr.textlength(name, font=f) > 222 and f.size > 14:
                f = R.font(R.F_UI, f.size - 1)
            while dr.textlength(name, font=f) > 222:
                name = name[:-2] + "…" if not name.endswith("…") else name[:-2] + "…"
            dr.text((104, y + ROW / 2), name, font=f, fill="white", anchor="lm")
            u = u_of(b["seg"]["depth"], self.j)
            g = R.ease(p) if cur else 1.0
            bx0, bx1 = 336, LB_W - 140
            zk = self.zone_index(b["seg"]["depth"])
            dr.rounded_rectangle((bx0, y + 17, bx1, y + ROW - 17), 8, fill=(255, 255, 255, 30))
            xe = bx0 + max(16, (bx1 - bx0) * u * g)
            dr.rounded_rectangle((bx0, y + 17, xe, y + ROW - 17), 8, fill=ZCOL[zk % len(ZCOL)] + (255,))
            val = self.s.fmt_pos(b["seg"]["depth"] * g if cur else b["seg"]["depth"])
            dr.text((LB_W - 16, y + ROW / 2), val, font=R.font(R.F_UI, 21), fill="white", anchor="rm")
            if cur and k == 0 and b["seg"]["depth"] > lead_before and p >= 1:
                f2 = R.font(R.F_UI, 20)
                tw = dr.textlength("YENİ LİDER", font=f2)
                dr.rounded_rectangle((236, 9, 236 + tw + 24, 39), 10, fill=(255, 70, 50, 255))
                dr.text((248, 24), "YENİ LİDER", font=f2, fill="white", anchor="lm")
        return im

    # ------------------------------------------------------------------ card-area panels
    def zone_panel(self, seg):
        return self.s.text_img(("zp", seg["name"]), lambda: self._zone_panel(seg))

    def _zone_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        zk = self.zone_index(seg["depth"])
        col = ZCOL[zk % len(ZCOL)]
        dr.text((cw / 2, ch * 0.30), f"HIZ BÖLGESİ {zk + 1} / {len(self.zones)}", font=R.font(R.F_UI, 36), fill=col, anchor="mm")
        f = R.font(R.F_ANTON, 150)
        while dr.textlength(seg["name"], font=f) > cw - 80:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2 + 4, ch * 0.52 + 5), seg["name"], font=f, fill=(0, 0, 0, 150), anchor="mm")
        dr.text((cw / 2, ch * 0.52), seg["name"], font=f, fill="white", anchor="mm")
        dr.rounded_rectangle((cw / 2 - 260, ch * 0.72, cw / 2 + 260, ch * 0.72 + 12), 6, fill=col + (255,))
        dr.text((cw / 2, ch * 0.83), seg["range"], font=R.font(R.F_UI, 46), fill=(225, 232, 240), anchor="mm")
        return im

    def landmark_panel(self, seg):
        return self.s.text_img(("lp", seg["name"]), lambda: self._landmark_panel(seg))

    def _landmark_panel(self, seg):
        cw, ch = R.CARD[2], R.CARD[3]
        im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((40, 60, cw - 40, ch - 60), 30, fill=(6, 10, 18, 165), outline=(255, 210, 80, 150), width=3)
        dr.text((cw / 2, 150), "KARŞILAŞTIRMA", font=R.font(R.F_UI, 34), fill=(255, 210, 80), anchor="mm")
        f = R.font(R.F_ANTON, 160)
        while dr.textlength(seg["value"], font=f) > cw - 140:
            f = R.font(R.F_ANTON, f.size - 6)
        dr.text((cw / 2, ch / 2 + 10), seg["value"], font=f, fill="white", anchor="mm")
        f2 = R.font(R.F_UI, 46)
        name = R.tr_upper(seg["name"])
        while dr.textlength(name, font=f2) > cw - 140:
            f2 = R.font(R.F_UI, f2.size - 2)
        dr.text((cw / 2, ch - 150), name, font=f2, fill=(220, 230, 240), anchor="mm")
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
        # dial
        zk = self.zone_index(d)
        dial = self.dial(zk)
        img.paste(dial, (0, 0), dial)
        u = u_of(d, self.j)
        wob = 0.0
        if k == "creature":   # the needle trembles a little at top speed
            wob = 0.004 * math.sin(t * 23.0) + 0.003 * math.sin(t * 37.0)
        self.needle(img, u, wob)
        ro = self.readout(d, zk)
        img.paste(ro, (DCX - 260, DCY + 108), ro)
        # leaderboard
        now = b.get("i", -1)
        show = k == "creature"
        p = min(1.0, max(0.0, (lt - 0.4) / GROW)) if show else 1.0
        lb = self.board(now if show else now + 0.5, p, show)
        img.paste(lb, (LB_X, LB_Y), lb)
