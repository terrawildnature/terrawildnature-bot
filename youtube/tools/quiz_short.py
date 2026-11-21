"""YouTube-only "Tahmin Et" Short, a different format from the Instagram Reels (owner's request, 2026-11-22):
blurred mystery animal + spoken 3-2-1 countdown -> reveal with name banner -> "3 şaşırtıcı gerçek" with numbered
badges and word-by-word karaoke subtitles -> "Bildin mi? Yorumlara yaz / Abone ol" end card. Every step is
narrated (female voice, unlike the Reels), with countdown beeps, a reveal whoosh and a ducked music bed.
1080x1920, about 25-30 s.

  python youtube/tools/quiz_short.py <dir>      reads <dir>/quiz.json, writes <dir>/short.mp4 and cover.jpg
  python youtube/tools/quiz_short.py --from-post posted/<post_dir> <work_dir>
                                                builds quiz.json from an Instagram post, then renders it

quiz.json:
{
  "voice": "tr-TR-EmelNeural", "rate": "+6%",
  "music": {"file": "assets/music/Investigations.mp3", "loudness": -26},
  "photos": {"p1.jpg": "File:...", ...},                       # downloaded when missing (tools/commons.py)
  "hook":   {"image": "p5.jpg", "cx": 0.5, "cy": 0.4, "text": "Bu hayvanı tanıyor musun? Üç saniyen var!"},
  "reveal": {"image": "p5.jpg", "cx": 0.5, "cy": 0.4, "name": "GÖZLÜKLÜ AYI", "text": "Bu bir gözlüklü ayı!"},
  "facts": [{"title": "GÜNEY AMERİKA'NIN TEK AYISI", "text": "Bir: ...", "image": "p2.jpg",
             "cx": 0.5, "cy": 0.5, "motion": "zoom_in"}, ... three of them],
  "end":    {"image": "p7.jpg", "cx": 0.5, "cy": 0.5, "text": "Bildin mi? Cevabını yorumlara yaz ve abone ol!"}
}
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import reel  # noqa: E402  (tts, duration, shot_rects, ease, tr_upper, fetch_photos)

W, H, FPS = reel.W, reel.H, reel.FPS
YELLOW, RED, WHITE, BLACK = (255, 210, 31), (255, 0, 51), (255, 255, 255), (0, 0, 0)
ANTON = str(reel.ASSETS / "fonts" / "Anton-Regular.ttf")
ROBOTO = str(reel.ASSETS / "fonts" / "Roboto-Bold.ttf")
COUNT = 3              # seconds of countdown
SAFE_R = 900           # YouTube's like/comment buttons sit right of this; keep text left of it
_fonts = {}


def font(path, size):
    if (path, size) not in _fonts:
        _fonts[(path, size)] = ImageFont.truetype(path, size)
    return _fonts[(path, size)]


def fit(text, path, size, max_w):
    while size > 30 and font(path, size).getlength(text) > max_w:
        size -= 4
    return font(path, size)


def centred(d, y, text, f, fill, stroke=8, cx=W // 2):
    w = f.getlength(text)
    d.text((cx - w / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=BLACK)


def wrap(text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        if cur and f.getlength(cur + " " + word) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    return lines + [cur]


def ease_out(t):
    t = min(max(t, 0), 1)
    return 1 - (1 - t) ** 3


def shot_rects(img, cx, cy, motion, zoom=1.0):
    """reel.shot_rects with a base zoom, for photos where the animal fills only part of the frame."""
    if zoom <= 1.0:
        return reel.shot_rects(img, cx, cy, motion)
    iw, ih = img.size
    h_full = min(ih, iw * W / H)
    w_full = h_full * W / H

    def rect(scale, fx, fy):
        w, h = w_full / scale, h_full / scale
        return (min(max(0, fx * iw - w / 2), iw - w), min(max(0, fy * ih - h / 2), ih - h), w, h)
    if motion in ("pan_right", "pan_left"):
        span = 0.06 / zoom
        a, b = rect(zoom, cx - span, cy), rect(zoom, cx + span, cy)
        return (a, b) if motion == "pan_right" else (b, a)
    near, far = rect(zoom * 1.15, cx, cy), rect(zoom, cx, cy)
    return (far, near) if motion == "zoom_in" else (near, far)


class Shot:
    """A photo with a slow camera move over [start, start+dur)."""

    def __init__(self, path, cx, cy, motion, start, dur, zoom=1.0):
        self.img = Image.open(path).convert("RGB")
        self.r0, self.r1 = shot_rects(self.img, cx, cy, motion, zoom)
        self.start, self.dur = start, dur

    def frame(self, t):
        k = reel.ease(min(max((t - self.start) / self.dur, 0), 1))
        x, y, w, h = (a + (b - a) * k for a, b in zip(self.r0, self.r1))
        return self.img.resize((W, H), Image.BICUBIC, box=(x, y, x + w, y + h))


def build(d):
    spec = json.loads((d / "quiz.json").read_text(encoding="utf-8"))
    reel.fetch_photos(spec, d)
    voice, rate = spec.get("voice", "tr-TR-EmelNeural"), spec.get("rate", "+6%")
    work, cache = d / "_work", d / "_tts_cache"
    work.mkdir(exist_ok=True)

    clips = []                                  # (start, mp3) for the voice track
    def say(text, start, name):
        mp3 = work / f"{name}.mp3"
        words = reel.tts(text, voice, rate, mp3, cache)
        clips.append((start, mp3))
        return reel.duration(mp3), [(start + a, start + b, w) for a, b, w in words]

    # ---- timeline ----
    t = 0.0
    hook_dur, _ = say(spec["hook"]["text"], t, "hook")
    hook_dur += 0.15
    t += hook_dur
    count_start = t
    for i, n in enumerate(("Üç", "İki", "Bir")):
        say(n + "!", count_start + i + 0.05, f"count{i}")
    t += COUNT
    reveal_start = t
    rd, _ = say(spec["reveal"]["text"], t + 0.25, "reveal")
    reveal_dur = rd + 0.55
    t += reveal_dur
    facts = []
    for i, f in enumerate(spec["facts"]):
        fd, words = say(f["text"], t + 0.15, f"fact{i}")
        facts.append((t, fd + 0.45, words))
        t += fd + 0.45
    end_start = t
    ed, _ = say(spec["end"]["text"], t + 0.1, "end")
    end_dur = ed + 1.3
    total = t + end_dur

    # ---- shots ----
    hk, rv, en = spec["hook"], spec["reveal"], spec["end"]
    hook_img = Shot(d / hk["image"], hk.get("cx", .5), hk.get("cy", .5), "zoom_in", 0, hook_dur + COUNT,
                    hk.get("zoom", 1)).frame(0)
    blurs = [Image.fromarray((np.asarray(hook_img.filter(ImageFilter.GaussianBlur(r))).astype(np.float32) * 0.5)
                             .astype(np.uint8)) for r in (26, 19, 13, 8)]
    reveal = Shot(d / rv["image"], rv.get("cx", .5), rv.get("cy", .5), "zoom_in", reveal_start, reveal_dur,
                  rv.get("zoom", 1))
    fact_shots = [Shot(d / f["image"], f.get("cx", .5), f.get("cy", .5), f.get("motion", "zoom_in"), s, du,
                       f.get("zoom", 1))
                  for f, (s, du, _) in zip(spec["facts"], facts)]
    end_shot = Shot(d / en["image"], en.get("cx", .5), en.get("cy", .5), "zoom_out", end_start, end_dur,
                    en.get("zoom", 1))

    logo = Image.open(Path(__file__).parent / "assets" / "logo_round.png").convert("RGBA") \
        if (Path(__file__).parent / "assets" / "logo_round.png").exists() else None

    def karaoke(dr, now, words, y=1240):
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
                f = fit(" ".join(txt), ANTON, 122, SAFE_R - 140)
                x = (W - f.getlength(" ".join(txt))) / 2
                for wi, w in enumerate(ch):
                    on = w[0] <= now < (ch[wi + 1][0] if wi + 1 < len(ch) else end)
                    dr.text((x, y), txt[wi], font=f, fill=YELLOW if on else WHITE, stroke_width=9, stroke_fill=BLACK)
                    x += f.getlength(txt[wi] + " ")
                return

    def frame(now):
        if now < count_start + COUNT:                               # mystery + countdown
            k = 0 if now < count_start else min(int(now - count_start) + 1, 3)
            im = blurs[k].copy()
        elif now < reveal_start + reveal_dur:
            im = reveal.frame(now)
        elif now < end_start:
            i = max(j for j, (s, _, _) in enumerate(facts) if now >= s)
            im = fact_shots[i].frame(now)
        else:
            im = Image.fromarray((np.asarray(end_shot.frame(now)).astype(np.float32) * 0.42).astype(np.uint8))
        dr = ImageDraw.Draw(im)

        if now < count_start + COUNT:
            pop = ease_out(now / 0.35)
            centred(dr, 250 - 60 * (1 - pop), "BU HAYVAN", font(ANTON, 150), WHITE, 9)
            centred(dr, 420 - 60 * (1 - pop), "NE?", font(ANTON, 260), YELLOW, 11)
            if now < count_start:
                centred(dr, 1180, "3 SANİYEN VAR!", font(ANTON, 96), WHITE, 7)
            else:
                c = now - count_start
                n, frac = 3 - int(c), c - int(c)
                s = 1 + 0.25 * (1 - ease_out(frac / 0.25))
                r = 175 * s
                cx, cy = W // 2, 1060
                dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0), outline=WHITE, width=10)
                dr.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - frac), fill=YELLOW, width=18)
                f = font(ANTON, int(250 * s))
                tw = f.getlength(str(n))
                dr.text((cx - tw / 2, cy - f.size * 0.62), str(n), font=f, fill=WHITE)
        elif now < reveal_start + reveal_dur:
            lt = now - reveal_start
            if lt < 0.25:                                          # flash
                im = Image.blend(im, Image.new("RGB", (W, H), WHITE), 1 - lt / 0.25)
                dr = ImageDraw.Draw(im)
            up = ease_out((lt - 0.1) / 0.35)
            y = 1150 + 260 * (1 - up)
            name = rv["name"]
            f = fit(name, ANTON, 150, W - 220)
            bw = f.getlength(name) + 90
            centred(dr, y - 105, "CEVAP:", font(ANTON, 84), WHITE, 7)
            dr.rounded_rectangle([(W - bw) / 2, y, (W + bw) / 2, y + f.size * 1.28], radius=26, fill=YELLOW)
            dr.text(((W - f.getlength(name)) / 2, y + f.size * 0.04), name, font=f, fill=BLACK)
        elif now < end_start:
            i = max(j for j, (s, _, _) in enumerate(facts) if now >= s)
            s, _, words = facts[i]
            slide = ease_out((now - s) / 0.3)
            x0 = -400 * (1 - slide)
            dr.ellipse([x0 + 50, 200, x0 + 230, 380], fill=YELLOW, outline=BLACK, width=6)
            nf = font(ANTON, 130)
            num = str(i + 1)
            dr.text((x0 + 140 - nf.getlength(num) / 2, 205), num, font=nf, fill=BLACK)
            tf = font(ANTON, 76)
            lines = wrap(spec["facts"][i].get("title", ""), tf, SAFE_R - 270)
            for li, line in enumerate(lines[:2]):
                dr.text((x0 + 260, 220 + li * 92 - (46 if len(lines) == 1 else 0) + 46), line, font=tf, fill=WHITE,
                        stroke_width=7, stroke_fill=BLACK)
            dr.text((x0 + 262, 160), f"ŞAŞIRTICI GERÇEK {i + 1}/{len(facts)}", font=font(ROBOTO, 40), fill=YELLOW,
                    stroke_width=4, stroke_fill=BLACK)
            karaoke(dr, now, words)
        else:
            lt = now - end_start
            pop = ease_out(lt / 0.35)
            centred(dr, 420 - 80 * (1 - pop), "BİLDİN Mİ?", font(ANTON, 200), YELLOW, 10)
            centred(dr, 700, "CEVABINI", font(ANTON, 110), WHITE, 8)
            centred(dr, 830, "YORUMLARA YAZ", font(ANTON, 110), WHITE, 8)
            ay = 990 + 18 * np.sin(lt * 6)
            dr.polygon([(W / 2 - 60, ay), (W / 2 + 60, ay), (W / 2, ay + 70)], fill=YELLOW, outline=BLACK)
            s = 1 + 0.06 * np.sin(lt * 7) if lt > 0.6 else ease_out((lt - 0.25) / 0.35)
            bw, bh = 560 * s, 150 * s
            by = 1190
            if s > 0.05:
                dr.rounded_rectangle([(W - bw) / 2, by, (W + bw) / 2, by + bh], radius=int(bh / 2), fill=RED)
                f = font(ANTON, max(10, int(96 * s)))
                dr.text(((W - f.getlength("ABONE OL")) / 2, by + bh * 0.12), "ABONE OL", font=f, fill=WHITE)
            centred(dr, 1400, "Her gün yeni bir hayvan", font(ROBOTO, 54), WHITE, 4)

        # progress bar + logo on every frame
        dr.rectangle([0, 0, W, 14], fill=(60, 60, 60))
        dr.rectangle([0, 0, int(W * now / total), 14], fill=YELLOW)
        if logo is not None:
            im.paste(logo, (W - logo.width - 40, 60), logo)
        return im

    # ---- audio: voice + sound effects, then ducked music ----
    ff = reel.ffmpeg_bin("ffmpeg")
    inputs, filt = [], []
    for i, (st, mp3) in enumerate(clips):
        inputs += ["-i", str(mp3)]
        filt.append(f"[{i}:a]adelay={int(st * 1000)}:all=1[a{i}]")
    n = len(clips)
    sfx = [f"sine=frequency={f}:duration=0.13,volume=0.35,afade=t=out:st=0.08:d=0.05,adelay={int(st * 1000)}:all=1[b{k}]"
           for k, (f, st) in enumerate([(880, count_start), (880, count_start + 1), (880, count_start + 2),
                                        (1320, reveal_start)])]
    sfx.append(f"anoisesrc=d=0.6:c=pink:a=0.25,highpass=f=500,afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.3,"
               f"adelay={int(max(0, reveal_start - 0.35) * 1000)}:all=1[wh]")
    labels = "".join(f"[a{i}]" for i in range(n)) + "".join(f"[b{k}]" for k in range(4)) + "[wh]"
    filt += sfx + [labels + f"amix=inputs={n + 5}:normalize=0,apad,atrim=0:{total:.3f}[out]"]
    subprocess.run([ff, "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-c:a", "libmp3lame", "-q:a", "2", str(work / "voice.mp3")], check=True)
    audio = work / "voice.mp3"
    music = spec.get("music")
    if music:
        audio = work / "mix.m4a"
        subprocess.run([
            ff, "-y", "-v", "error", "-i", str(work / "voice.mp3"),
            "-ss", str(music.get("start", 0)), "-i", str(ROOT / music["file"]),
            "-filter_complex",
            f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I={music.get('loudness', -26)}:TP=-3:LRA=11,"
            f"afade=t=in:d=0.8,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[m];"
            "[0:a]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=5:attack=30:release=350[duck];"
            "[v][duck]amix=inputs=2:normalize=0:duration=first[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)

    enc = subprocess.Popen([ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "medium",
                            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                            "-movflags", "+faststart", str(d / "short.mp4")], stdin=subprocess.PIPE)
    frame(hook_dur * 0.6).convert("RGB").save(d / "cover.jpg", quality=92)   # thumbnail: the "BU HAYVAN NE?" card
    for k in range(round(total * FPS)):
        enc.stdin.write(np.asarray(frame(k / FPS).convert("RGB")).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"OK: {d / 'short.mp4'} ({total:.1f}s)")


# ---------------- recipe from an Instagram post (posted/<dir>/post.json) ----------------
HOOKS = ["Bu hayvanı tanıyor musun? Sadece üç saniyen var!",
         "Sence bu hangi hayvan? Üç saniyen var!",
         "Bu canlının adını biliyor musun? Üç saniyen var!"]
ENDS = ["Bildin mi? Cevabını yorumlara yaz, daha fazlası için abone ol!",
        "Kaç saniyede bildin? Yorumlara yaz ve abone olmayı unutma!",
        "Bildiysen yorumlara yaz, her gün yeni bir hayvan için abone ol!"]
NUMBERS = ["Bir", "İki", "Üç"]


def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def sentences(lines):
    text = " ".join(lines).strip()
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]


def post_facts(post):
    """The three spoken facts: post.json "quiz" (written by the daily routine) or, for older posts, the card texts."""
    if post.get("quiz", {}).get("facts"):
        return post["quiz"]["facts"][:3]
    right = sentences(post["right"])
    return [{"text": " ".join(sentences(post["card_top"]))},
            {"text": " ".join(sentences(post["card_bottom"])[:2])},
            {"text": " ".join(right[:2])}]


def pick_music(recent):
    """A track not used by the recent Shorts (owner's rule: different music per video), stable per call order."""
    tracks = sorted(p.name for p in (reel.ASSETS / "music").glob("*.mp3"))
    fresh = [t for t in tracks if t not in recent] or tracks
    return "assets/music/" + fresh[0]


def from_post(post_dir, work, recent_music=()):
    """Write work/quiz.json for an Instagram post and download its photos (cover, top, inner) into work/."""
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    work.mkdir(parents=True, exist_ok=True)
    titles = {}
    for c in post.get("credits", []):
        for use in c.get("use", "").replace(" ", "").split(","):
            titles.setdefault(use, c.get("title") or c.get("url"))
    sys.path.insert(0, str(ROOT / "tools"))
    import commons

    def fetch(src, out):
        """Commons "File:..." title, a direct URL, or "iNaturalist <photo id>" (how most posts credit iNat)."""
        if src and (m := re.fullmatch(r"iNaturalist (\d+)", src.strip())):
            base = f"https://inaturalist-open-data.s3.amazonaws.com/photos/{m[1]}/original."
            return any(commons.fetch(base + ext, out) for ext in ("jpg", "jpeg", "png", "JPG"))
        if src and (src.startswith("http") or src.startswith("File:")):
            try:
                commons.download(src, out)
                return True
            except (SystemExit, Exception) as e:
                print(f"photo failed: {src}: {e}")
        return False
    got = {}
    for use in ("cover", "top", "inner"):
        src = titles.get(use)
        if src in got:
            shutil.copy(got[src], work / f"{use}.jpg")
        elif fetch(src, str(work / f"{use}.jpg")):
            got[src] = work / f"{use}.jpg"
    if not got:
        raise SystemExit(f"no photo could be downloaded for {post_dir.name}")
    first = next(iter(got.values()))
    for use in ("cover", "top", "inner"):      # a missing photo falls back to one that did download
        if not (work / f"{use}.jpg").exists():
            shutil.copy(first, work / f"{use}.jpg")
    ph = post["photos"]

    def at(use, motion="zoom_in", extra=1.0):
        p = ph.get(use, ph["cover"])
        return {"image": f"{use}.jpg", "cx": p.get("cx", .5), "cy": p.get("cy", .5), "motion": motion,
                "zoom": max(1.0, min(p.get("zoom", 1.0), 2.4) * 0.8 * extra)}
    name = post["card_title"]
    k = int(hashlib.sha1(post_dir.name.encode()).hexdigest(), 16)
    facts = post_facts(post)
    shots = [at("top", "zoom_in"), at("inner", "zoom_out"), at("cover", "pan_right", 1.3)]
    spec = {"voice": "tr-TR-EmelNeural", "rate": "+6%",
            "music": {"file": pick_music(recent_music), "loudness": -26},
            "hook": {**at("cover"), "text": HOOKS[k % len(HOOKS)]},
            "reveal": {**at("cover"), "name": name, "text": f"Cevap: {tr_lower(name)}!"},
            "facts": [{**shot, "title": f.get("title", ""), "text": f"{NUMBERS[i]}: {f['text']}"}
                      for i, (f, shot) in enumerate(zip(facts, shots))],
            "end": {**at("top", "zoom_out"), "text": ENDS[k % len(ENDS)]}}
    (work / "quiz.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    return spec


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 4 and sys.argv[1] == "--from-post":
        from_post(Path(sys.argv[2]), Path(sys.argv[3]))
        build(Path(sys.argv[3]))
    elif len(sys.argv) == 2:
        build(Path(sys.argv[1]))
    else:
        sys.exit(__doc__)
