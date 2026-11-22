"""More YouTube Shorts edits that take turns with quiz_short.py's "Tahmin Et" (owner's request, 2026-11-22:
not the same kind of Short every day; FORMATS is the rotation, seven edits after the owner dropped three). All are built from the same Instagram post
data (name, headline, the three quiz facts with titles, three photos, region, group) and are fully narrated.

  ipucu     3 İPUCU: blurred animal sharpens with each spoken clue, then the answer
  piksel    NETLEŞİYOR: pixelated photo sharpens every second of a 6 s timer, answer, 3 facts
  yakindan  YAKINDAN BAK: extreme close-up in a camera viewfinder zooms out to the whole animal
  top3      3 SÜPER GÜÇ: named up front, facts counted down #3 -> #1
  haber     SON DAKİKA: TV news look with name tag, lower third and scrolling ticker
  dosya     GİZLİ DOSYA: case file with a polaroid, typed evidence, stamps, name redacted until the end
  kart      HAYVAN KARTI: collectible game card whose abilities light up one by one
  sohbet    MESAJLAŞMA: a chat between two friends (two voices) about the animal
  yalan     HANGİSİ YALAN?: three claims, countdown, twist: all three are true

  python youtube/tools/short_formats.py --from-post posted/<post_dir> <work_dir> <format>
  python youtube/tools/short_formats.py <work_dir>          re-render from <work_dir>/format.json
"""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import quiz_short as q  # noqa: E402
from quiz_short import (W, H, FPS, YELLOW, RED, WHITE, BLACK, ANTON, ROBOTO, SAFE_R, font, fit, centred, wrap,  # noqa: E402
                        ease_out, tr_lower, reel)

# rotation order: guessing edits alternate with edits that name the animal up front. haber, dosya and sohbet were
# taken out of the rotation by the owner (2026-11-22); their code stays for a --format run.
FORMATS = ["tahmin", "ipucu", "top3", "piksel", "yakindan", "kart", "yalan"]
GUESS = {"tahmin", "ipucu", "piksel", "yakindan", "dosya"}
GREEN, GOLD, NAVY = (40, 200, 110), (212, 175, 55), (14, 40, 100)
MALE = "tr-TR-AhmetNeural"
NUM = q.NUMBERS
ORD = ["Birinci", "İkinci", "Üçüncü"]
SFX = {"beep": "sine=frequency=880:duration=0.13,volume=0.35,afade=t=out:st=0.08:d=0.05",
       "ding": "sine=frequency=1320:duration=0.16,volume=0.3,afade=t=out:st=0.1:d=0.06",
       "tick": "sine=frequency=1800:duration=0.04,volume=0.25",
       "pop": "sine=frequency=660:duration=0.07,volume=0.3,afade=t=out:st=0.03:d=0.04",
       "thud": "sine=frequency=85:duration=0.28,volume=0.9,afade=t=out:st=0.05:d=0.23",
       "whoosh": "anoisesrc=d=0.6:c=pink:a=0.25,highpass=f=500,afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.3"}


class Seg:
    """One narrated step: its voice line starts `pre` s in and the step lasts at least `dur` s.
    sfx: (name, offset s, or "end" = right after the voice line); says: extra (offset, text) lines."""

    def __init__(self, kind, text=None, voice=None, pre=0.15, pad=0.45, dur=0.0, sfx=(), says=(), **kw):
        self.kind, self.text, self.voice, self.pre, self.pad, self.min = kind, text, voice, pre, pad, dur
        self.sfx, self.says, self.kw = list(sfx), list(says), kw
        self.words, self.start, self.dur, self.speech = [], 0.0, 0.0, 0.0

    def __getattr__(self, k):
        try:
            return self.__dict__["kw"][k]
        except KeyError:
            raise AttributeError(k)


# ---------------- drawing helpers ----------------
def pick(k, options):
    return options[k % len(options)]


def dim(im, k):
    return Image.fromarray((np.asarray(im, dtype=np.float32) * k).astype(np.uint8))


def crop(img, cx, cy, zoom=1.0, size=(W, H)):
    iw, ih = img.size
    ow, oh = size
    h = min(ih, iw * oh / ow) / max(zoom, 1.0)
    w = h * ow / oh
    x = min(max(0, cx * iw - w / 2), iw - w)
    y = min(max(0, cy * ih - h / 2), ih - h)
    return img.resize(size, Image.BICUBIC, box=(x, y, x + w, y + h))


def glass(im, boxes):
    """Translucent rounded panels: boxes = [(xy, rgba, radius), ...]."""
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(layer)
    for xy, fill, r in boxes:
        dr.rounded_rectangle(xy, radius=r, fill=fill)
    return Image.alpha_composite(im.convert("RGBA"), layer).convert("RGB")


def rounded(img, r):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=r, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask)
    return out


def pill(dr, cx, y, text, f, bg, fg, pad=28):
    w = f.getlength(text)
    dr.rounded_rectangle([cx - w / 2 - pad, y, cx + w / 2 + pad, y + f.size * 1.3], radius=int(f.size * 0.65),
                         fill=bg)
    dr.text((cx - w / 2, y + f.size * 0.1), text, font=f, fill=fg)


def check(dr, x, y, r=46):
    dr.ellipse([x - r, y - r, x + r, y + r], fill=GREEN, outline=WHITE, width=5)
    dr.line([(x - r * .45, y), (x - r * .1, y + r * .38), (x + r * .5, y - r * .38)], fill=WHITE, width=11)


def star(dr, cx, cy, r, fill):
    dr.polygon([(cx + (r if i % 2 == 0 else r * .45) * math.sin(i * math.pi / 5),
                 cy - (r if i % 2 == 0 else r * .45) * math.cos(i * math.pi / 5)) for i in range(10)], fill=fill)


def stamp(text, color, size=86, angle=-12):
    f = font(ANTON, size)
    w, h = int(f.getlength(text)) + 64, int(size * 1.45)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([4, 4, w - 4, h - 4], radius=14, outline=color + (255,), width=9)
    dr.text((32, size * 0.12), text, font=f, fill=color + (255,))
    return im.rotate(angle, expand=True, resample=Image.BICUBIC)


def slam(im, st, x, y, lt):
    """A stamp landing at (x, y) centre: big and see-through to normal size in 0.18 s."""
    if lt < 0:
        return
    s = 1 + 0.8 * (1 - ease_out(lt / 0.18))
    sm = st.resize((int(st.width * s), int(st.height * s)), Image.BICUBIC)
    im.paste(sm, (int(x - sm.width / 2), int(y - sm.height / 2)), sm)


def karaoke(dr, now, words, y, size=118, max_w=SAFE_R - 140, base=WHITE, hi=YELLOW, stroke=9, cx=W // 2):
    """quiz_short's 3-word subtitles: the word being spoken in `hi`."""
    chunks, cur = [], []
    for w in words:
        if len(cur) == 3:
            chunks.append(cur)
            cur = []
        cur.append(w)
    chunks += [cur] if cur else []
    for ci, ch in enumerate(chunks):
        end = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else ch[-1][1] + 0.4
        if ch[0][0] <= now < end:
            txt = [reel.tr_upper(w[2]) for w in ch]
            f = fit(" ".join(txt), ANTON, size, max_w)
            x = cx - f.getlength(" ".join(txt)) / 2
            for wi, w in enumerate(ch):
                on = w[0] <= now < (ch[wi + 1][0] if wi + 1 < len(ch) else end)
                dr.text((x, y), txt[wi], font=f, fill=hi if on else base, stroke_width=stroke, stroke_fill=BLACK)
                x += f.getlength(txt[wi] + " ")
            return


def end_card(im, lt, big, lines=("YORUMLARA YAZ",), dark=0.42):
    """Closing card: big question, a line or two, arrow, pulsing ABONE OL."""
    im = dim(im, dark)
    dr = ImageDraw.Draw(im)
    pop = ease_out(lt / 0.35)
    y = 330 - 80 * (1 - pop)
    for b in big:
        f = fit(b, ANTON, 170, SAFE_R - 60)
        centred(dr, y, b, f, YELLOW, 10)
        y += f.size * 1.2
    y += 60
    for line in lines:
        f = fit(line, ANTON, 110, SAFE_R - 60)
        centred(dr, y, line, f, WHITE, 8)
        y += 130
    ay = y + 30 + 18 * math.sin(lt * 6)
    if lines:
        dr.polygon([(W / 2 - 60, ay), (W / 2 + 60, ay), (W / 2, ay + 70)], fill=YELLOW, outline=BLACK)
    s = 1 + 0.06 * math.sin(lt * 7) if lt > 0.6 else ease_out((lt - 0.25) / 0.35)
    bw, bh, by = 560 * s, 150 * s, y + 180
    if s > 0.05:
        dr.rounded_rectangle([(W - bw) / 2, by, (W + bw) / 2, by + bh], radius=int(bh / 2), fill=RED)
        f = font(ANTON, max(10, int(96 * s)))
        dr.text(((W - f.getlength("ABONE OL")) / 2, by + bh * 0.12), "ABONE OL", font=f, fill=WHITE)
    centred(dr, by + 210, "Her gün yeni bir hayvan", font(ROBOTO, 54), WHITE, 4)
    return im


class Pics:
    """The post's three photos (cover, top, inner) with their crop centres and zooms."""

    def __init__(self, d, spec):
        self.d, self.spec, self.raw, self.shots = d, spec, {}, {}

    def img(self, key):
        if key not in self.raw:
            self.raw[key] = Image.open(self.d / self.spec[key]["image"]).convert("RGB")
        return self.raw[key]

    def at(self, key):
        s = self.spec[key]
        return s.get("cx", .5), s.get("cy", .5), s.get("zoom", 1.0)

    def still(self, key, mult=1.0, size=(W, H)):
        cx, cy, z = self.at(key)
        return crop(self.img(key), cx, cy, max(1.0, z * mult), size)

    def move(self, key, s, now, motion="zoom_in", mult=1.0):
        k = (key, id(s), motion)
        if k not in self.shots:
            cx, cy, z = self.at(key)
            self.shots[k] = q.Shot(self.d / self.spec[key]["image"], cx, cy, motion, s.start, s.dur, max(1.0, z * mult))
        return self.shots[k].frame(now)


FACT_SHOTS = [("top", "zoom_in"), ("inner", "zoom_out"), ("cover", "pan_right")]


def reveal_flash(im, lt):
    if lt < 0.25:
        return Image.blend(im, Image.new("RGB", (W, H), WHITE), 1 - lt / 0.25)
    return im


# ---------------- the nine edits: each returns (segments, paint(seg, now) -> image, thumbnail time, logo?) ----------------
def f_ipucu(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    segs = [Seg("hook", pick(k, ["Üç ipucu vereceğim. Bakalım kaçıncısında bileceksin!",
                                 "Sana üç ipucu veriyorum. Bu hayvanı bulabilecek misin?"]), dur=2.2)]
    segs += [Seg("clue", f"{ORD[i]} ipucu: {f['text']}", i=i, sfx=[("ding", 0)]) for i, f in enumerate(facts)]
    segs += [Seg("guess", "Son tahminin ne?", dur=2.4, pad=0.9, sfx=[("beep", 1.3), ("beep", 1.8)]),
             Seg("reveal", f"Cevap: {tr_lower(name)}!", pre=0.3, pad=0.6, sfx=[("whoosh", -0.35), ("ding", 0)]),
             Seg("end", "Kaçıncı ipucunda bildin? Yorumlara yaz ve abone ol!", pad=1.3)]
    base = P.still("cover")
    blurred = {key: dim(base.filter(ImageFilter.GaussianBlur(r)), 0.5)
               for key, r in (("hook", 38), (0, 30), (1, 20), (2, 12), ("guess", 7))}

    def steps(dr, upto):
        for j in range(3):
            x = W / 2 + (j - 1) * 170
            on = j <= upto
            dr.ellipse([x - 55, 180, x + 55, 290], fill=YELLOW if on else (70, 70, 70), outline=BLACK, width=5)
            f = font(ANTON, 76)
            dr.text((x - f.getlength(str(j + 1)) / 2, 188), str(j + 1), font=f, fill=BLACK if on else WHITE)

    def paint(s, now):
        lt = now - s.start
        if s.kind in ("hook", "clue", "guess"):
            im = blurred[s.i if s.kind == "clue" else s.kind].copy()
            dr = ImageDraw.Draw(im)
            if s.kind == "hook":
                pop = ease_out(lt / 0.35)
                pill(dr, W / 2, 300 - 50 * (1 - pop), "3 İPUCU", font(ANTON, 120), YELLOW, BLACK)
                centred(dr, 560, "BU HAYVAN", font(ANTON, 150), WHITE, 9)
                centred(dr, 730, "NE?", font(ANTON, 260), YELLOW, 11)
            elif s.kind == "clue":
                steps(dr, s.i)
                slide = ease_out(lt / 0.3)
                centred(dr, 380 - 40 * (1 - slide), f"İPUCU {s.i + 1}", font(ANTON, 110), WHITE, 8)
                tf = font(ANTON, 96)
                for li, line in enumerate(wrap(facts[s.i]["title"], tf, SAFE_R - 120)[:2]):
                    centred(dr, 560 + li * 115, line, tf, YELLOW, 8)
                karaoke(dr, now, s.words, 1150)
            else:
                steps(dr, 2)
                sc = 1 + 0.08 * math.sin(lt * 8)
                centred(dr, 420, "?", font(ANTON, int(520 * sc)), YELLOW, 14)
                centred(dr, 1150, "SON TAHMİNİN?", font(ANTON, 120), WHITE, 9)
            return im
        if s.kind == "reveal":
            im = reveal_flash(P.move("cover", s, now), lt)
            dr = ImageDraw.Draw(im)
            up = ease_out((lt - 0.1) / 0.35)
            pill(dr, W / 2, 200 - 120 * (1 - up), "CEVAP", font(ANTON, 80), WHITE, BLACK)
            f = fit(name, ANTON, 150, W - 200)
            centred(dr, 340 - 120 * (1 - up), name, f, YELLOW, 10)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["KAÇINCI", "İPUCUNDA BİLDİN?"])
    return segs, paint, 1.2, True


def f_piksel(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    blocks = [110, 80, 56, 38, 26, 16]
    segs = [Seg("hook", pick(k, ["Bu fotoğraf her saniye biraz daha netleşecek. Bildiğin anda yorumlara yaz!",
                                 "Görüntü yavaş yavaş netleşiyor. Kaçıncı saniyede bileceksin?"]), dur=2.2),
            Seg("timer", dur=6.0, sfx=[("tick", i) for i in range(6)]),
            Seg("reveal", f"Cevap: {tr_lower(name)}!", pre=0.3, pad=0.6, sfx=[("whoosh", -0.35), ("ding", 0)])]
    segs += [Seg("fact", f"{NUM[i]}: {f['text']}", i=i) for i, f in enumerate(facts)]
    segs += [Seg("end", "Kaçıncı saniyede bildin? Yorumlara yaz, abone olmayı unutma!", pad=1.3)]
    base = P.still("cover")
    pix = [base.resize((W // b, H // b), Image.BILINEAR).resize((W, H), Image.NEAREST) for b in blocks]

    def paint(s, now):
        lt = now - s.start
        if s.kind in ("hook", "timer"):
            j = 0 if s.kind == "hook" else min(int(lt), 5)
            im = pix[j].copy()
            dr = ImageDraw.Draw(im)
            centred(dr, 200, "NETLEŞİYOR...", font(ANTON, 110), WHITE, 9)
            centred(dr, 340, "BU HAYVAN NE?", font(ANTON, 130), YELLOW, 9)
            n = 6 if s.kind == "hook" else 6 - j
            frac = 0 if s.kind == "hook" else lt - int(lt)
            cx, cy, r = W // 2, 1180, 170
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLACK, outline=WHITE, width=10)
            dr.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - frac), fill=RED, width=20)
            f = font(ANTON, 230)
            dr.text((cx - f.getlength(str(n)) / 2, cy - f.size * 0.62), str(n), font=f, fill=WHITE)
            centred(dr, 1400, "BİLDİĞİN AN YORUMA YAZ!", font(ANTON, 76), WHITE, 7)
            return im
        if s.kind == "reveal":
            im = reveal_flash(P.move("cover", s, now), lt)
            dr = ImageDraw.Draw(im)
            up = ease_out((lt - 0.1) / 0.35)
            f = fit(name, ANTON, 150, W - 200)
            y = 1200 + 200 * (1 - up)
            dr.rectangle([0, y - 20, W, y + f.size * 1.3 + 10], fill=RED)
            centred(dr, y, name, f, WHITE, 0)
            centred(dr, y - 110, "İŞTE CEVAP:", font(ANTON, 84), WHITE, 7)
            return im
        if s.kind == "fact":
            key, mo = FACT_SHOTS[s.i]
            im = P.move(key, s, now, mo)
            slide = ease_out(lt / 0.3)
            y0 = 1150 + 300 * (1 - slide)
            im = glass(im, [([50, y0, SAFE_R + 40, y0 + 420], (255, 255, 255, 235), 36)])
            dr = ImageDraw.Draw(im)
            dr.text((90, y0 + 30), f"BİLGİ {s.i + 1}/3", font=font(ROBOTO, 40), fill=(120, 120, 120))
            dr.text((90, y0 + 80), facts[s.i]["title"], font=fit(facts[s.i]["title"], ANTON, 84, SAFE_R - 80), fill=RED)
            karaoke(dr, now, s.words, y0 + 220, size=88, max_w=SAFE_R - 100, base=BLACK, hi=RED, stroke=0,
                    cx=(50 + SAFE_R + 40) // 2)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["KAÇINCI", "SANİYEDE BİLDİN?"])
    return segs, paint, 1.2, True


def f_yakindan(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    cx, cy, z0 = P.at("cover")
    z0 = max(1.0, z0)
    z_hi = z0 * 4.2
    segs = [Seg("hook", pick(k, ["Bu çok yakın bir çekim. Sence hangi hayvan?",
                                 "Yakından bak! Bu hangi hayvanın parçası?"]), dur=2.4),
            Seg("zoom", "Yavaşça uzaklaşalım...", dur=4.4, sfx=[("tick", 1.5), ("tick", 2.5), ("tick", 3.5),
                                                                ("whoosh", 3.9)]),
            Seg("reveal", f"Bu bir {tr_lower(name)}!", pre=0.2, pad=0.6, sfx=[("ding", 0)])]
    segs += [Seg("fact", f"{NUM[i]}: {f['text']}", i=i) for i, f in enumerate(facts)]
    segs += [Seg("end", "İlk bakışta bildin mi? Yorumlara yaz ve abone ol!", pad=1.3)]
    img = P.img("cover")

    def viewfinder(dr, now, zoom):
        L, T, R, B, n = 60, 170, W - 60, 1760, 90
        for (x, y, dx, dy) in ((L, T, 1, 1), (R, T, -1, 1), (L, B, 1, -1), (R, B, -1, -1)):
            dr.line([(x, y), (x + n * dx, y)], fill=WHITE, width=8)
            dr.line([(x, y), (x, y + n * dy)], fill=WHITE, width=8)
        if int(now * 2) % 2 == 0:
            dr.ellipse([100, 220, 140, 260], fill=RED)
        dr.text((155, 212), "REC", font=font(ROBOTO, 46), fill=WHITE)
        dr.text((100, 1660), f"x{zoom:.1f}", font=font(ROBOTO, 56), fill=WHITE, stroke_width=3, stroke_fill=BLACK)
        dr.line([(W / 2 - 40, H / 2), (W / 2 + 40, H / 2)], fill=WHITE, width=4)
        dr.line([(W / 2, H / 2 - 40), (W / 2, H / 2 + 40)], fill=WHITE, width=4)

    def paint(s, now):
        lt = now - s.start
        if s.kind in ("hook", "zoom"):
            if s.kind == "hook":
                z = z_hi * (1 + 0.03 * lt)
            else:
                e = reel.ease(min(lt / (s.dur - 0.4), 1))
                z = z_hi * (z0 / z_hi) ** e
            im = crop(img, cx, cy, z)
            dr = ImageDraw.Draw(im)
            viewfinder(dr, now, z / z0)
            if s.kind == "hook" or lt < 1.2:
                centred(dr, 330, "YAKINDAN BAK", font(ANTON, 140), YELLOW, 10)
                centred(dr, 1250, "BU HAYVAN NE?", font(ANTON, 120), WHITE, 9)
            return im
        if s.kind == "reveal":
            im = P.move("cover", s, now)
            dr = ImageDraw.Draw(im)
            viewfinder(dr, now, 1.0)
            up = ease_out(lt / 0.3)
            f = fit(name, ANTON, 130, SAFE_R - 140)
            y = 1250 + 150 * (1 - up)
            dr.rectangle([100, y - 70, 100 + max(f.getlength(name), 380) + 60, y + f.size * 1.3], fill=(10, 60, 30))
            dr.text((130, y - 60), "TANIMLANDI", font=font(ROBOTO, 46), fill=GREEN)
            dr.text((130, y), name, font=f, fill=WHITE)
            return im
        if s.kind == "fact":
            key, mo = FACT_SHOTS[s.i]
            im = P.move(key, s, now, mo)
            slide = ease_out(lt / 0.3)
            x0 = -700 * (1 - slide)
            title = facts[s.i]["title"]
            tf = fit(title, ANTON, 80, SAFE_R - 160)
            im = glass(im, [([x0 + 60, 1330, x0 + 60 + tf.getlength(title) + 80, 1330 + 190], (0, 0, 0, 190), 18)])
            dr = ImageDraw.Draw(im)
            viewfinder(dr, now, 1.0)
            dr.text((x0 + 100, 1345), f"GÖZLEM {s.i + 1}", font=font(ROBOTO, 42), fill=GREEN)
            dr.text((x0 + 100, 1400), title, font=tf, fill=WHITE)
            karaoke(dr, now, s.words, 1000)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["İLK BAKIŞTA", "BİLDİN Mİ?"])
    return segs, paint, 1.2, True


def f_top3(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    order = [2, 1, 0]                       # the routine writes the most striking fact first: it is number one
    medal = [(205, 127, 50), (200, 200, 210), (255, 200, 0)]
    label = ["Üç numara", "İki numara", "Ve bir numara"]
    segs = [Seg("hook", f"Bu bir {tr_lower(name)}. Üç süper gücü var ve bir numara inanılmaz!", dur=2.5)]
    segs += [Seg("rank", f"{label[j]}: {facts[i]['text']}", j=j, i=i, sfx=[("whoosh", -0.3), ("ding", 0.05)])
             for j, i in enumerate(order)]
    segs += [Seg("end", "Sence hangisi en iyisi? Yorumlara yaz ve abone ol!", pad=1.3)]

    def paint(s, now):
        lt = now - s.start
        if s.kind == "hook":
            im = P.move("cover", s, now)
            dr = ImageDraw.Draw(im)
            pop = ease_out(lt / 0.35)
            centred(dr, 230 - 60 * (1 - pop), name, fit(name, ANTON, 140, SAFE_R - 80), WHITE, 9)
            pill(dr, W / 2, 420, "3 SÜPER GÜCÜ", font(ANTON, 100), YELLOW, BLACK)
            for j in range(3):
                y = 1080 + j * 150
                dr.rounded_rectangle([160, y, 820, y + 120], radius=24, fill=(0, 0, 0))
                dr.text((190, y + 10), f"#{3 - j}", font=font(ANTON, 90), fill=medal[j])
                dr.text((330, y + 10), "?", font=font(ANTON, 90), fill=WHITE)
            return im
        if s.kind == "rank":
            key, mo = FACT_SHOTS[s.j]
            im = dim(P.move(key, s, now, mo), 0.85)
            dr = ImageDraw.Draw(im)
            slide = ease_out(lt / 0.35)
            num = f"#{3 - s.j}"
            nf = font(ANTON, 360)
            dr.text((60 - 500 * (1 - slide), 140), num, font=nf, fill=medal[s.j], stroke_width=12, stroke_fill=BLACK)
            tf = font(ANTON, 88)
            for li, line in enumerate(wrap(facts[s.i]["title"], tf, SAFE_R - 120)[:2]):
                dr.text((70, 640 + li * 105), line, font=tf, fill=WHITE, stroke_width=8, stroke_fill=BLACK)
            if s.j == 2:
                for a in range(6):
                    ang = now * 2 + a * math.pi / 3
                    star(dr, 300 + 230 * math.cos(ang), 330 + 150 * math.sin(ang), 22, YELLOW)
            karaoke(dr, now, s.words, 1250)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["SENCE HANGİSİ", "EN İYİSİ?"])
    return segs, paint, 1.4, True


def f_haber(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    segs = [Seg("open", f"Son dakika! {sp['headline']}.", dur=2.2, sfx=[("beep", 0), ("ding", 0.15)])]
    segs += [Seg("fact", f["text"], i=i) for i, f in enumerate(facts)]
    segs += [Seg("end", "Doğadan daha fazla haber için abone ol!", pad=1.3)]
    tick = "   •   ".join([reel.tr_upper(sp["headline"])] + [f["title"] for f in facts]) + "   •   "
    tf = font(ROBOTO, 44)
    tick_w = tf.getlength(tick)

    def news(im, now, band):
        im = glass(im, [([0, 1240, W, 1420], NAVY + (235,), 0)])
        dr = ImageDraw.Draw(im)
        dr.rectangle([40, 150, 40 + font(ANTON, 70).getlength("SON DAKİKA") + 50, 255], fill=RED)
        dr.text((65, 158), "SON DAKİKA", font=font(ANTON, 70), fill=WHITE)
        dr.rectangle([40, 265, 250, 325], fill=BLACK)
        if int(now * 2) % 2 == 0:
            dr.ellipse([58, 280, 88, 310], fill=RED)
        dr.text((100, 270), "CANLI", font=font(ROBOTO, 42), fill=WHITE)
        nf = fit(name, ANTON, 62, SAFE_R - 120)
        dr.rectangle([40, 1160, 40 + nf.getlength(name) + 50, 1240], fill=YELLOW)
        dr.text((65, 1163), name, font=nf, fill=BLACK)
        bf = fit(band, ANTON, 84, W - 100)
        dr.text((50, 1270), band, font=bf, fill=WHITE)
        dr.rectangle([0, 1420, W, 1490], fill=RED)
        x = -(now * 220) % tick_w
        for off in (x - tick_w, x, x + tick_w):
            dr.text((off + 200, 1432), tick, font=tf, fill=WHITE)
        dr.rectangle([0, 1420, 185, 1490], fill=WHITE)
        dr.text((22, 1424), "DOĞA", font=font(ANTON, 56), fill=RED)
        return im, dr

    def paint(s, now):
        lt = now - s.start
        if s.kind == "open":
            im = P.move("cover", s, now)
            im, dr = news(im, now, reel.tr_upper(sp["headline"]))
            karaoke(dr, now, s.words, 930, size=96)
            return im
        if s.kind == "fact":
            key, mo = FACT_SHOTS[s.i]
            im, dr = news(P.move(key, s, now, mo), now, facts[s.i]["title"])
            karaoke(dr, now, s.words, 930, size=96)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["DAHA FAZLA", "HABER İÇİN"], [])
    return segs, paint, 1.0, True


def f_dosya(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    say_n = ["bir", "iki", "üç"]
    segs = [Seg("hook", pick(k, ["Gizli dosya açıldı. Bu canlı hakkında üç kanıt var. Kim olduğunu bulabilecek misin?",
                                 "Elimizde gizli bir dosya var. Üç kanıta bakıp bu canlıyı bulabilecek misin?"]),
                dur=2.4, key="cover", sfx=[("thud", 0.3)])]
    segs += [Seg("ev", f"Kanıt {say_n[i]}: {f['text']}", i=i, key=["top", "inner", "cover"][i],
                 sfx=[("thud", "end")]) for i, f in enumerate(facts)]
    segs += [Seg("reveal", f"Dosya çözüldü. Bu bir {tr_lower(name)}!", key="cover", pad=0.8, sfx=[("thud", "end")]),
             Seg("end", "Bildin mi? Yorumlara yaz ve abone ol!", key="cover", pad=1.3)]
    rng = np.random.default_rng(k)
    g = np.linspace(1.0, 0.6, H)[:, None, None] * np.array([70, 46, 28])[None, None, :]
    desk = Image.fromarray(np.clip(g + rng.normal(0, 6, (H, W, 1)), 0, 255).astype(np.uint8))
    case_no = f"DOSYA NO: {k:03d}"
    secret = stamp("GİZLİ", RED, 90, 10)
    ok = stamp("DOĞRULANDI", GREEN, 74)
    solved = stamp("ÇÖZÜLDÜ", RED, 110)
    polas = {}

    def polaroid(key):
        if key not in polas:
            ph = P.still(key, 0.9, (660, 660))
            p = Image.new("RGBA", (720, 820), (250, 250, 245, 255))
            p.paste(ph, (30, 30))
            ImageDraw.Draw(p).text((40, 712), case_no, font=font(ROBOTO, 40), fill=(60, 60, 60))
            polas[key] = p.rotate(-3 + 6 * (len(polas) % 2), expand=True, resample=Image.BICUBIC)
        return polas[key]
    lines_f = font(ROBOTO, 46)

    def paint(s, now):
        lt = now - s.start
        im = desk.copy()
        po = polaroid(s.key)
        dy = 90 * (1 - ease_out(lt / 0.35)) if s.kind in ("hook", "ev") else 0
        im.paste(po, (int(470 - po.width / 2), int(130 + dy)), po)
        im.paste(secret, (60, 120), secret)
        if s.kind == "end":
            return end_card(im, lt, ["BİLDİN Mİ?"])
        dr = ImageDraw.Draw(im)
        dr.rectangle([60, 1080, SAFE_R, 1700], fill=(236, 228, 205), outline=(170, 160, 130), width=4)
        dr.text((95, 1105), "KİMLİK:", font=font(ANTON, 64), fill=(40, 40, 40))
        nf = fit(name, ANTON, 64, SAFE_R - 340)
        if s.kind == "reveal":
            dr.text((330, 1105), name, font=nf, fill=RED)
            cover_x = 330 + (SAFE_R - 360) * ease_out((lt - 0.3) / 0.5)
            if cover_x < SAFE_R - 30:
                dr.rectangle([cover_x, 1110, SAFE_R - 30, 1185], fill=BLACK)
        else:
            dr.rectangle([330, 1110, SAFE_R - 30, 1185], fill=BLACK)
        if s.kind == "hook":
            dr.text((95, 1230), "DURUM: ARAŞTIRILIYOR", font=font(ANTON, 60), fill=RED)
            dr.text((95, 1330), "3 kanıt bulundu.", font=lines_f, fill=(40, 40, 40))
            dr.text((95, 1395), "Bu canlı kim?", font=lines_f, fill=(40, 40, 40))
        elif s.kind == "ev":
            dr.text((95, 1220), f"KANIT {s.i + 1}/3: {facts[s.i]['title']}",
                    font=fit(f"KANIT {s.i + 1}/3: {facts[s.i]['title']}", ANTON, 56, SAFE_R - 140), fill=RED)
            body = facts[s.i]["text"]
            frac = min(max((now - s.start - s.pre) / max(s.speech, 0.1), 0), 1)
            n = int(len(body) * frac)
            shown, blink = 0, int(now * 3) % 2 == 0
            for li, line in enumerate(wrap(body, lines_f, SAFE_R - 150)):
                part = line[:max(0, n - shown)]
                typing = shown <= n < shown + len(line) + 1 and n < len(body)
                shown += len(line) + 1
                dr.text((95, 1320 + li * 64), part + ("|" if typing and blink else ""), font=lines_f, fill=(30, 30, 30))
            slam(im, ok, 640, 1580, now - (s.start + s.pre + s.speech + 0.05))
        else:
            slam(im, solved, 600, 1450, now - (s.start + s.pre + s.speech + 0.05))
        return im
    return segs, paint, 1.2, True


def f_kart(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    loc, group = sp.get("loc") or "", reel.tr_upper(sp.get("group") or "canlı")
    segs = [Seg("hook", f"Yeni hayvan kartı: {tr_lower(name)}! Yaşam alanı: {loc}." if loc
                else f"Yeni hayvan kartı: {tr_lower(name)}!", dur=2.6, sfx=[("whoosh", 0), ("ding", 0.6)])]
    segs += [Seg("ab", f"{ORD[i]} yetenek: {f['text']}", i=i, sfx=[("pop", 0)]) for i, f in enumerate(facts)]
    segs += [Seg("end", "Yeni kartlar için abone ol, koleksiyonu tamamla!", pad=1.3)]
    cw, ch, X, Y = 740, 1240, 140, 130
    bg = dim(P.still("cover").filter(ImageFilter.GaussianBlur(30)), 0.35)
    photo = rounded(P.still("cover", 0.8, (cw - 48, 500)), 24)
    stars = 4 + k % 2

    def card(active):
        c = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        dr = ImageDraw.Draw(c)
        dr.rounded_rectangle([0, 0, cw - 1, ch - 1], radius=40, fill=(22, 24, 32, 255), outline=GOLD + (255,), width=12)
        gf = font(ROBOTO, 34)
        dr.rounded_rectangle([28, 26, 28 + gf.getlength(group) + 40, 76], radius=25, fill=GOLD)
        dr.text((48, 31), group, font=gf, fill=BLACK)
        for i in range(5):
            star(dr, cw - 60 - i * 52, 51, 22, YELLOW if 4 - i < stars else (80, 80, 80))
        c.paste(photo, (24, 96), photo)
        nf = fit(name, ANTON, 92, cw - 60)
        dr.text(((cw - nf.getlength(name)) / 2, 612), name, font=nf, fill=YELLOW)
        lf = font(ROBOTO, 36)
        if loc:
            t = f"YAŞAM ALANI: {reel.tr_upper(loc)}"
            dr.text(((cw - lf.getlength(t)) / 2, 740), t, font=lf, fill=(200, 200, 200))
        for i, f in enumerate(facts):
            y = 810 + i * 135
            on = i == active
            dr.rounded_rectangle([24, y, cw - 24, y + 115], radius=22, fill=YELLOW if on else (42, 46, 60))
            dr.ellipse([42, y + 18, 120, y + 96], fill=BLACK if on else GOLD)
            dr.text((81 - font(ANTON, 54).getlength(str(i + 1)) / 2, y + 22), str(i + 1), font=font(ANTON, 54),
                    fill=YELLOW if on else BLACK)
            tf = fit(f["title"], ANTON, 56, cw - 200)
            dr.text((145, y + 57 - tf.size * 0.62), f["title"], font=tf, fill=BLACK if on else WHITE)
        return c
    cards = {a: card(a) for a in (None, 0, 1, 2)}

    def place(im, c, now, scale=1.0):
        bob = 6 * math.sin(now * 2)
        if scale < 0.999:
            c = c.resize((max(1, int(cw * scale)), max(1, int(ch * scale))), Image.BICUBIC)
        im.paste(c, (int(X + (cw - c.width) / 2), int(Y + bob + (ch - c.height) / 2)), c)

    def paint(s, now):
        lt = now - s.start
        im = bg.copy()
        if s.kind == "hook":
            place(im, cards[None], now, 0.25 + 0.75 * ease_out(lt / 0.6))
            dr = ImageDraw.Draw(im)
            if lt > 0.6:
                centred(dr, 1440, "YENİ KART!", font(ANTON, 110), YELLOW, 9)
            return im
        if s.kind == "ab":
            place(im, cards[s.i], now)
            karaoke(ImageDraw.Draw(im), now, s.words, 1420, size=88)
            return im
        return end_card(im, lt, ["KOLEKSİYONA", "EKLE!"], [], dark=0.8)
    return segs, paint, 1.6, True


def f_sohbet(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    nt = name_title(name)
    script = [("L", "Bunu gördün mü?", None),
              ("L", None, "cover"),
              ("R", pick(k, ["Bu ne böyle? Gerçek mi?", "Yok artık, bu hayvan gerçek mi?"]), None),
              ("L", f"Gerçek! Adı {nt}.", None),
              ("L", facts[0]["text"], None),
              ("R", pick(k // 2, ["Ciddi misin?", "İnanamıyorum!", "Şaka yapıyorsun!"]), None),
              ("L", facts[1]["text"], None),
              ("L", None, "top"),
              ("L", facts[2]["text"], None),
              ("R", "İnanılmaz! Böyle hayvanlar için hemen abone oluyorum.", None)]
    segs = []
    for side, text, photo in script:
        if photo:
            segs.append(Seg("msg", side=side, photo=photo, body=None, dur=1.3, pre=0.1, sfx=[("pop", 0.1)]))
        else:
            pre = 0.75 if side == "L" else 0.3
            segs.append(Seg("msg", text, voice=None if side == "L" else MALE, side=side, photo=None, body=text,
                            pre=pre, pad=0.35, sfx=[("pop", pre - 0.1)]))
    segs.append(Seg("end", dur=2.8))
    msgs = [s for s in segs if s.kind == "msg"]
    bf = font(ROBOTO, 50)

    def bubble(s):
        color = (44, 47, 60) if s.side == "L" else (0, 122, 94)
        if s.photo:
            ph = rounded(P.still(s.photo, 0.85, (600, 600)), 28)
            b = Image.new("RGBA", (616, 616), (0, 0, 0, 0))
            ImageDraw.Draw(b).rounded_rectangle([0, 0, 615, 615], radius=34, fill=color)
            b.paste(ph, (8, 8), ph)
            return b
        lines = wrap(s.body, bf, 620)
        w = int(max(bf.getlength(x) for x in lines)) + 64
        h = len(lines) * 64 + 44
        b = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(b)
        dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=34, fill=color)
        for i, line in enumerate(lines):
            dr.text((32, 18 + i * 64), line, font=bf, fill=WHITE)
        return b
    bubbles = {id(s): bubble(s) for s in msgs}
    bg = dim(P.still("cover").filter(ImageFilter.GaussianBlur(40)), 0.18)
    logo_p = Path(__file__).parent / "assets" / "logo_round.png"
    avatar = Image.open(logo_p).convert("RGBA").resize((104, 104)) if logo_p.exists() else None
    BOTTOM, GAP = 1610, 22

    def paint(s, now):
        im = bg.copy()
        items = []                                    # (image or "typing", side, appear time)
        for m in msgs:
            show = m.start + m.pre - 0.1
            if m.side == "L" and m.pre >= 0.5 and m.start <= now < show:
                items.append(("typing", "L", m.start))
            elif now >= show:
                items.append((bubbles[id(m)], m.side, show))
        y = BOTTOM
        for n, (b, side, t0) in enumerate(reversed(items)):
            h = 110 if b == "typing" else b.height
            e = ease_out((now - t0) / 0.25) if n == 0 else 1
            top = y - h + (h + GAP) * (1 - e)
            if top + h < 190:
                break
            if b == "typing":
                dr = ImageDraw.Draw(im)
                dr.rounded_rectangle([40, top, 230, top + h], radius=34, fill=(44, 47, 60))
                for j in range(3):
                    a = 0.5 + 0.5 * math.sin(now * 9 - j)
                    c = int(120 + 120 * a)
                    dr.ellipse([75 + j * 50, top + 40, 105 + j * 50, top + 70], fill=(c, c, c))
            else:
                x = 40 if side == "L" else 960 - b.width
                im.paste(b, (int(x), int(top)), b)
            y -= (h + GAP) * e
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, W, 190], fill=(24, 26, 34))
        if avatar is not None:
            im.paste(avatar, (40, 60), avatar)
        dr.text((170, 62), "Doğa Meraklıları", font=font(ROBOTO, 50), fill=WHITE)
        dr.text((170, 122), "çevrimiçi", font=font(ROBOTO, 34), fill=GREEN)
        dr.rectangle([0, 1650, W, H], fill=(24, 26, 34))
        dr.rounded_rectangle([40, 1680, 880, 1780], radius=50, fill=(44, 47, 60))
        dr.text((90, 1705), "Mesaj yaz...", font=font(ROBOTO, 44), fill=(150, 150, 150))
        dr.ellipse([910, 1680, 1010, 1780], fill=(0, 122, 94))
        dr.polygon([(945, 1705), (985, 1730), (945, 1755)], fill=WHITE)
        if s.kind == "end":
            return end_card(im, now - s.start, ["SEN DE", "ŞAŞIRDIN MI?"])
        return im
    return segs, paint, None, False


def f_yalan(sp, P):
    name, facts, k = sp["name"], sp["facts"], sp["k"]
    letters = "ABC"

    def sentence(t):
        t = tr_lower(t)
        return t[:1].upper() + t[1:]
    segs = [Seg("hook", f"Bu bir {tr_lower(name)}. Hakkında üç bilgi var ama biri yalan olabilir!", dur=2.4),
            Seg("read", " ".join(f"{letters[i]}: {sentence(f['title'])}." for i, f in enumerate(facts)), pad=0.3),
            Seg("count", "Hangisi yalan?", dur=4.0, says=[(1.5, "Üç!"), (2.3, "İki!"), (3.1, "Bir!")],
                sfx=[("beep", 1.5), ("beep", 2.3), ("beep", 3.1)]),
            Seg("reveal", "Hiçbiri! Üçü de gerçek!", pre=0.2, pad=1.0,
                sfx=[("whoosh", -0.3), ("ding", 0.3), ("ding", 0.6), ("ding", 0.9)])]
    segs += [Seg("fact", f"{letters[i]}: {f['text']}", i=i) for i, f in enumerate(facts)]
    segs += [Seg("end", "Sen hangisini seçtin? Yorumlara yaz ve abone ol!", pad=1.3)]
    hook_t = [0.0]

    def cards(im, now, t0, checks_at=None):
        boxes = []
        for i in range(3):
            y = 880 + i * 175
            a = ease_out((now - t0 - 0.4 - i * 0.3) / 0.3)
            if a > 0:
                boxes.append(([80 - 300 * (1 - a), y, SAFE_R, y + 150], (0, 0, 0, 200), 28))
        im = glass(im, boxes)
        dr = ImageDraw.Draw(im)
        for i in range(3):
            y = 880 + i * 175
            a = ease_out((now - t0 - 0.4 - i * 0.3) / 0.3)
            if a <= 0:
                continue
            x = 80 - 300 * (1 - a)
            dr.ellipse([x + 20, y + 25, x + 120, y + 125], fill=YELLOW)
            lf = font(ANTON, 70)
            dr.text((x + 70 - lf.getlength(letters[i]) / 2, y + 28), letters[i], font=lf, fill=BLACK)
            tf = fit(facts[i]["title"], ANTON, 66, SAFE_R - x - 260)
            dr.text((x + 150, y + 75 - tf.size * 0.62), facts[i]["title"], font=tf, fill=WHITE)
            if checks_at is not None and now >= checks_at + i * 0.3:
                check(dr, SAFE_R - 70, y + 75)
        return im, dr

    def paint(s, now):
        lt = now - s.start
        if s.kind in ("hook", "read", "count", "reveal"):
            if s.kind == "hook":
                hook_t[0] = s.start
            im = dim(P.move("cover", s, now) if s.kind == "hook" else P.still("cover"), 0.6)
            im, dr = cards(im, now, hook_t[0], s.start + 0.3 if s.kind == "reveal" else None)
            if s.kind == "reveal":
                pop = ease_out(lt / 0.3)
                centred(dr, 250 - 60 * (1 - pop), "HİÇBİRİ!", font(ANTON, 170), GREEN, 10)
                centred(dr, 460, "HEPSİ GERÇEK!", font(ANTON, 130), WHITE, 9)
            else:
                centred(dr, 230, "HANGİSİ", font(ANTON, 170), WHITE, 10)
                centred(dr, 430, "YALAN?", font(ANTON, 200), RED, 11)
                pill(dr, W / 2, 700, name, fit(name, ANTON, 64, SAFE_R - 160), YELLOW, BLACK)
            if s.kind == "count" and lt >= 1.5:
                c = lt - 1.5
                n = 3 - min(int(c / 0.8), 2)
                r = 120
                dr.ellipse([W / 2 - r, 1440, W / 2 + r, 1440 + 2 * r], fill=BLACK, outline=WHITE, width=8)
                f = font(ANTON, 170)
                dr.text((W / 2 - f.getlength(str(n)) / 2, 1460), str(n), font=f, fill=YELLOW)
            return im
        if s.kind == "fact":
            key, mo = FACT_SHOTS[s.i]
            im = P.move(key, s, now, mo)
            tf = fit(facts[s.i]["title"], ANTON, 70, SAFE_R - 300)
            im = glass(im, [([60, 200, SAFE_R, 360], (0, 0, 0, 200), 28)])
            dr = ImageDraw.Draw(im)
            dr.ellipse([85, 230, 185, 330], fill=YELLOW)
            dr.text((135 - font(ANTON, 70).getlength(letters[s.i]) / 2, 233), letters[s.i], font=font(ANTON, 70),
                    fill=BLACK)
            dr.text((215, 280 - tf.size * 0.62), facts[s.i]["title"], font=tf, fill=WHITE)
            check(dr, SAFE_R - 70, 280)
            centred(dr, 400, "GERÇEK", font(ANTON, 70), GREEN, 6)
            karaoke(dr, now, s.words, 1150)
            return im
        return end_card(P.move("top", s, now, "zoom_out"), lt, ["SEN HANGİSİNİ", "SEÇTİN?"])
    return segs, paint, 2.0, True


EDITS = {"ipucu": f_ipucu, "piksel": f_piksel, "yakindan": f_yakindan, "top3": f_top3, "haber": f_haber,
         "dosya": f_dosya, "kart": f_kart, "sohbet": f_sohbet, "yalan": f_yalan}


# ---------------- timeline, audio, encode ----------------
def build(d):
    sp = json.loads((d / "format.json").read_text(encoding="utf-8"))
    P = Pics(d, sp["img"])
    segs, paint, cover_at, with_logo = EDITS[sp["format"]](sp, P)
    voice, rate = sp.get("voice", "tr-TR-EmelNeural"), sp.get("rate", "+6%")
    work, cache = d / "_work", d / "_tts_cache"
    work.mkdir(exist_ok=True)
    clips, sfx = [], []

    def say(text, start, v):
        mp3 = work / f"v{len(clips):02d}.mp3"
        words = reel.tts(text, v or voice, rate, mp3, cache)
        clips.append((start, mp3))
        return reel.duration(mp3), [(start + a, start + b, w) for a, b, w in words]
    t = 0.0
    for s in segs:
        s.start = t
        if s.text:
            s.speech, s.words = say(s.text, t + s.pre, s.voice)
        for off, txt in s.says:
            say(txt, t + off, s.voice)
        s.dur = max(s.min, s.pre + s.speech + s.pad if s.text else 0)
        for name, off in s.sfx:
            sfx.append((name, t + (s.pre + s.speech + 0.05 if off == "end" else off)))
        t += s.dur
    total = t
    starts = [s.start for s in segs]
    logo_p = Path(__file__).parent / "assets" / "logo_round.png"
    logo = Image.open(logo_p).convert("RGBA") if with_logo and logo_p.exists() else None

    def frame(now):
        i = max(j for j, st in enumerate(starts) if now >= st)
        im = paint(segs[i], now)
        dr = ImageDraw.Draw(im)
        dr.rectangle([0, 0, W, 14], fill=(60, 60, 60))
        dr.rectangle([0, 0, int(W * now / total), 14], fill=YELLOW)
        if logo is not None:
            im.paste(logo, (W - logo.width - 40, 60), logo)
        return im

    ff = reel.ffmpeg_bin("ffmpeg")
    inputs, filt = [], []
    for i, (st, mp3) in enumerate(clips):
        inputs += ["-i", str(mp3)]
        filt.append(f"[{i}:a]adelay={int(st * 1000)}:all=1[a{i}]")
    for j, (name, st) in enumerate(sfx):
        filt.append(f"{SFX[name]},adelay={int(max(0, st) * 1000)}:all=1[b{j}]")
    labels = "".join(f"[a{i}]" for i in range(len(clips))) + "".join(f"[b{j}]" for j in range(len(sfx)))
    filt.append(labels + f"amix=inputs={len(clips) + len(sfx)}:normalize=0,apad,atrim=0:{total:.3f}[out]")
    subprocess.run([ff, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-c:a", "libmp3lame", "-q:a", "2", str(work / "voice.mp3")], check=True)
    audio = work / "voice.mp3"
    music = sp.get("music")
    if music:
        audio = work / "mix.m4a"
        subprocess.run([
            ff, "-y", "-v", "error", "-i", str(work / "voice.mp3"),
            "-ss", str(music.get("start", 0)), "-i", str(q.ROOT / music["file"]),
            "-filter_complex",
            f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I={music.get('loudness', -26)}:TP=-3:LRA=11,"
            f"afade=t=in:d=0.8,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[m];"
            "[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=350[duck];"
            "[v][duck]amix=inputs=2:normalize=0:duration=first[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)

    if cover_at is None:                      # chat: the moment the photo and the first reply are on screen
        cover_at = segs[3].start + 0.2
    # the thumbnail is written after encoding: cover.jpg is also the name of the source photo the shots read
    thumb = frame(min(cover_at, total - 0.1)).convert("RGB")
    enc = subprocess.Popen([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium",
                            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                            "-movflags", "+faststart", str(d / "short.mp4")], stdin=subprocess.PIPE)
    for f in range(round(total * FPS)):
        enc.stdin.write(np.asarray(frame(f / FPS).convert("RGB")).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    thumb.save(d / "cover.jpg", quality=92)
    print(f"OK: {d / 'short.mp4'} ({sp['format']}, {total:.1f}s)")


# ---------------- recipe, titles ----------------
def name_title(name):
    return " ".join(w[:1] + tr_lower(w[1:]) for w in name.split())


def headline(post):
    h = tr_lower(" ".join(w for line in post["title"] for w, _ in line))
    return h[:1].upper() + h[1:]


def from_post(post_dir, work, fmt, recent_music=()):
    """Write work/format.json for one of the nine edits (photos and music come from quiz_short.from_post)."""
    base = q.from_post(post_dir, work, recent_music)
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    facts = [{"title": f.get("title") or reel.tr_upper(" ".join(f["text"].split()[:3])), "text": f["text"]}
             for f in q.post_facts(post)]

    def at(x):
        return {k: x[k] for k in ("image", "cx", "cy", "zoom")}
    spec = {"format": fmt, "voice": base["voice"], "rate": base["rate"], "music": base["music"],
            "name": post["card_title"], "headline": headline(post), "loc": post.get("loc", ""),
            "group": post.get("group", ""), "facts": facts,
            "img": {"cover": at(base["hook"]), "top": at(base["facts"][0]), "inner": at(base["facts"][1])},
            "k": int(hashlib.sha1(post_dir.name.encode()).hexdigest(), 16) % 1000}
    (work / "format.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return spec


def trim(t, n=60):
    t = " ".join(t.split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",:;—-")


def yt_title(fmt, post):
    """Titles for the edits that name the animal; None = the guessing title (quiz.yt_title)."""
    nm, hl = name_title(post["card_title"]), headline(post)
    t = {"top3": f"{nm}: 3 Süper Gücü Var!",
         "haber": f"Son Dakika: {hl}!",
         "kart": f"Hayvan Kartı: {nm}",
         "sohbet": f"Arkadaşım Bunu Gönderdi: {nm}!",
         "yalan": f"{nm} Hakkında 3 Bilgi: Hangisi Yalan?"}.get(fmt)
    if fmt == "haber" and len(t) > 60:          # a cut headline reads badly
        t = f"Son Dakika: {nm} Hakkında Şaşırtıcı Gerçek!"
    return trim(t) if t else None


EN_TITLES = {"top3": "This Animal Has 3 Real Superpowers!",
             "haber": "Breaking Nature News: This Animal Is Real!",
             "kart": "Animal Card: A Real Creature You Never Knew",
             "sohbet": "My Friend Sent Me This Animal...",
             "yalan": "3 Facts About This Animal: Which One Is a Lie?"}


def en_spec(fmt, post):
    en = dict(post.get("quiz", {}).get("en") or {})
    if en and fmt in EN_TITLES:
        en["title"] = EN_TITLES[fmt]
    return {"en": en or None}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 5 and sys.argv[1] == "--from-post":
        from_post(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4])
        build(Path(sys.argv[3]))
    elif len(sys.argv) == 2:
        build(Path(sys.argv[1]))
    else:
        sys.exit(__doc__)
