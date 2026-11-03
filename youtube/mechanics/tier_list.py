"""Tier list: every creature gets a grade (S, A, B, C, D) and its portrait flies into a board on the right that fills up
through the video. Inspired by the tier-list videos popular on YouTube, with a documentary card on the left.

script.json:
  "mechanic": "tier_list",
  "journey": {"meter": false, "card": [60, 92, 1180, 664], "sub_cx": 960, ...},
  creature segments: "tier": "S" | "A" | "B" | "C" | "D", "verdict": "short reason, <= 34 chars"
  "tier_title": "TEHLİKE" (optional board header)
"""
import math

import numpy as np
from PIL import Image, ImageDraw

import doc_render as R

TIERS = [("S", (255, 92, 92)), ("A", (255, 170, 80)), ("B", (255, 222, 100)), ("C", (140, 220, 120)), ("D", (110, 170, 255))]
BX, BY, BW, BH = 1270, 92, 600, 664      # board
LABEL = 92
ROW = BH // len(TIERS)
TH = ROW - 22                            # thumbnail size
FLY = 1.6                                # seconds of the fly-in at the end of each creature


class Mechanic:
    def __init__(self, scene):
        self.s = scene
        self.order = [b for b in scene.blocks if b["kind"] == "creature" and b["seg"].get("tier")]
        self.slot = {}
        count = {t: 0 for t, _ in TIERS}
        for b in self.order:
            t = b["seg"]["tier"]
            self.slot[b["i"]] = (t, count[t])
            count[t] += 1
        self.per_row = max(max(count.values()), 1)
        self.thumbs = {}

    # -- board
    def thumb(self, i, size):
        k = (i, size)
        if k not in self.thumbs:
            key = self.s.photos[f"{i:02d}"][0]["file"][:-4]
            im = Image.open(self.s.doc / "photos" / f"{key}.jpg").convert("RGB")
            c = min(im.size)
            im = im.crop(((im.width - c) // 2, (im.height - c) // 2, (im.width + c) // 2, (im.height + c) // 2))
            im = im.resize((size, size), Image.LANCZOS).convert("RGBA")
            m = Image.new("L", (size, size), 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), 14, fill=255)
            im.putalpha(m)
            self.thumbs[k] = im
        return self.thumbs[k]

    def cell(self, tier, n):
        r = [t for t, _ in TIERS].index(tier)
        avail = BW - LABEL - 20
        step = min(TH + 8, (avail - TH) / max(self.per_row - 1, 1))   # overlap when a row gets crowded
        return int(BX + LABEL + 12 + n * step), int(BY + r * ROW + 11)

    def board(self):
        return self.s.text_img(("tier_board", self.s.spec.get("tier_title", "")), self._board)

    def _board(self):
        im = Image.new("RGBA", (R.W, R.H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((BX - 8, BY - 8, BX + BW + 8, BY + BH + 8), 22, fill=(0, 0, 0, 120))
        for r, (t, col) in enumerate(TIERS):
            y = BY + r * ROW
            dr.rounded_rectangle((BX, y + 4, BX + LABEL, y + ROW - 4), 14, fill=col + (255,))
            dr.text((BX + LABEL / 2, y + ROW / 2), t, font=R.font(R.F_ANTON, 64), fill=(25, 25, 25), anchor="mm")
            dr.rounded_rectangle((BX + LABEL + 6, y + 4, BX + BW, y + ROW - 4), 14, fill=(255, 255, 255, 28))
        title = self.s.spec.get("tier_title")
        if title:
            dr.text((BX + BW / 2, BY + BH + 50), R.tr_upper(title), font=R.font(R.F_UI, 34), fill=(230, 230, 230), anchor="mm")
        return im

    def verdict(self, seg):
        return self.s.text_img(("verdict", seg["name"]), lambda: self._verdict(seg))

    def _verdict(self, seg):
        col = dict(TIERS)[seg["tier"]]
        im = Image.new("RGBA", (760, 150), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((0, 0, 150, 150), 26, fill=col + (255,))
        dr.text((75, 75), seg["tier"], font=R.font(R.F_ANTON, 110), fill=(25, 25, 25), anchor="mm")
        if seg.get("verdict"):
            dr.rounded_rectangle((165, 40, 760, 110), 20, fill=(0, 0, 0, 190))
            dr.text((185, 75), seg["verdict"], font=R.font(R.F_UI, 38), fill="white", anchor="lm")
        return im

    # -- frame
    def draw(self, img, t, b, lt, default):
        default()
        if b["kind"] in ("cold", "end", "intro"):
            return
        img.paste(self.board(), (0, 0), self.board())
        now = b.get("i", -1)
        for c in self.order:
            if c["i"] > now or (c["i"] == now and b["kind"] != "outro" and lt < b["dur"] - FLY):
                continue
            tier, n = self.slot[c["i"]]
            x, y = self.cell(tier, n)
            th = self.thumb(c["i"], TH)
            if c["i"] == now:   # flying in from the card
                p = R.ease((lt - (b["dur"] - FLY)) / (FLY * 0.8))
                sx, sy = R.CARD[0] + R.CARD[2] // 2 - TH, R.CARD[1] + R.CARD[3] // 2 - TH
                x, y = int(sx + (x - sx) * p), int(sy + (y - sy) * p - math.sin(math.pi * p) * 120)
                big = int(TH * (2 - p))
                th = self.thumb(c["i"], big)
            img.paste(th, (x, y), th)
        if b["kind"] == "creature" and b["seg"].get("tier"):
            v0 = b["dur"] - FLY - 2.6    # the grade stamps onto the card just before it flies to the board
            if lt > v0:
                p = min(1.0, (lt - v0) / 0.35)
                v = self.verdict(b["seg"])
                if p < 1:
                    z = 1.6 - 0.6 * p
                    v = v.resize((int(v.width * z), int(v.height * z)), Image.BILINEAR)
                a = min(1.0, p * 1.5) * (1 - R.ease((lt - (b["dur"] - FLY)) / 0.5))
                self.s.paste(img, v, (R.CARD[0] + 40, R.CARD[1] + 40), a)
