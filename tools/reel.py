"""Terra Wild Nature reel builder: narrated photo documentary, 1080x1920.

Usage:
  python tools/reel.py <reel_dir>             video (reel.mp4) + cover (cover.jpg)
  python tools/reel.py --cover <reel_dir>     cover only
  python tools/reel.py --preview <reel_dir>   preview.jpg: first/last frame of every shot (no voice)

reel.json:
{
  "voice": "tr-TR-AhmetNeural", "rate": "+8%",
  "music": {"file": "assets/music/Reawakening.mp3", "loudness": -27},
  "photos": {"p1.jpg": "File:Some photo on Commons.jpg", ...},   # downloaded when missing
  "segments": [
    {"text": "Bir cümle.", "image": "p1.jpg", "cx": 0.5, "cy": 0.5, "motion": "zoom_in"},
    ...
  ],
  "cover": {"image": "p6.jpg", "cx": 0.5, "cy": 0.45, "title": [[["350 KİLO", "R"]], [["AMA İKİ", "W"]]]},
  "caption": "..."
}
motion: zoom_in | zoom_out | pan_right | pan_left  (pan = camera slides across a wide photo)

Each segment's sentence is spoken while its image is on screen. Subtitles come from the
TTS word timings, so they are always in sync with the voice.
"""
import asyncio
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
W, H, FPS = 1080, 1920, 30
GAP = 0.35          # silence after each sentence (s)
FADE = 0.4          # crossfade between photos (s)
TAIL = 0.8          # hold after the last sentence (s)


def ffmpeg_bin(name):
    return shutil.which(name) or name


# ---------------- voice ----------------
async def _tts(text, voice, rate, out):
    import edge_tts
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(out, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append((chunk["offset"] / 1e7, (chunk["offset"] + chunk["duration"]) / 1e7, chunk["text"]))
    return words


def tts(text, voice, rate, out, cache_dir, retries=8):
    """Narrate text into out, returning word timings. Cached per (voice, rate, text) so
    re-renders don't hit the service again; it drops requests now and then, so retry."""
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    cached_mp3, cached_json = cache_dir / f"{key}.mp3", cache_dir / f"{key}.json"
    if cached_mp3.exists() and cached_json.exists():
        shutil.copy(cached_mp3, out)
        return [tuple(w) for w in json.loads(cached_json.read_text(encoding="utf-8"))]
    import edge_tts
    for i in range(retries):
        try:
            words = asyncio.run(_tts(text, voice, rate, out))
            break
        except (edge_tts.exceptions.NoAudioReceived, edge_tts.exceptions.WebSocketError, OSError):
            if i == retries - 1:
                raise
            time.sleep(min(3 + 4 * i, 25))
    cache_dir.mkdir(exist_ok=True)
    shutil.copy(out, cached_mp3)
    cached_json.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def duration(path):
    out = subprocess.run([ffmpeg_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ---------------- subtitles ----------------
def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def ass_time(t):
    t = max(0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


SUB_SIZE = 146
SUB_MAX_W = W - 2 * 130   # px; keeps subtitles clear of the frame edges
_sub_font = None


def sub_width(words):
    """Rendered width of a subtitle line. libass scales the font so ascent+descent = font size."""
    global _sub_font
    if _sub_font is None:
        probe = ImageFont.truetype(str(ASSETS / "fonts" / "Anton-Regular.ttf"), 1000)
        asc, desc = probe.getmetrics()
        _sub_font = ImageFont.truetype(str(ASSETS / "fonts" / "Anton-Regular.ttf"), round(SUB_SIZE * 1000 / (asc + desc)))
    text = " ".join(tr_upper(w[2]) for w in words)
    return _sub_font.getlength(text) + len(text) * 1 + 16   # + letter spacing + outline


def build_ass(timed_words, out):
    """timed_words: list of segments, each a list of (start, end, text) in absolute seconds."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Anton,{SUB_SIZE},&H00FFFFFF,&H00FFFFFF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,8,4,2,70,70,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for seg in timed_words:
        # split by rendered width so every line sits well inside the frame (centered, wide side margins)
        chunks, cur = [], []
        for w in seg:
            if cur and (len(cur) == 3 or sub_width(cur + [w]) > SUB_MAX_W):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
        for ci, ch in enumerate(chunks):
            chunk_end = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else ch[-1][1] + 0.25
            for wi, w in enumerate(ch):
                start = w[0]
                end = ch[wi + 1][0] if wi + 1 < len(ch) else chunk_end
                text = " ".join(
                    ("{\\c&H0000FE&}" + tr_upper(x[2]) + "{\\c&HFFFFFF&}") if xi == wi else tr_upper(x[2])
                    for xi, x in enumerate(ch))
                lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{text}")
    Path(out).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


# ---------------- frames ----------------
def ease(t):
    return t * t * (3 - 2 * t)


def shot_rects(img, cx, cy, motion):
    """Start/end crop rectangles (x, y, w, h) with 9:16 aspect inside img."""
    iw, ih = img.size
    ar = W / H
    h_full = min(ih, iw / ar)
    w_full = h_full * ar

    def rect(scale, fx, fy):
        w, h = w_full / scale, h_full / scale
        x = min(max(0, fx * iw - w / 2), iw - w)
        y = min(max(0, fy * ih - h / 2), ih - h)
        return (x, y, w, h)

    if motion in ("pan_right", "pan_left"):
        span = min(0.18, max(0.0, (iw - w_full) / iw / 2))
        a, b = rect(1.0, cx - span, cy), rect(1.0, cx + span, cy)
        return (a, b) if motion == "pan_right" else (b, a)
    if motion == "zoom_out":
        return rect(1.15, cx, cy), rect(1.0, cx, cy)
    return rect(1.0, cx, cy), rect(1.15, cx, cy)


def render_shot(img, r0, r1, n):
    for i in range(n):
        t = ease(i / max(1, n - 1))
        x, y, w, h = (a + (b - a) * t for a, b in zip(r0, r1))
        yield np.asarray(img.resize((W, H), Image.BICUBIC, box=(x, y, x + w, y + h)))


# ---------------- cover ----------------
COVER_TITLE_SIZE = 182   # px, identical on every cover
COVER_TITLE_TOP = 758    # y of the first title line
COVER_BADGE_Y = 624      # y of the "Terra Wild Nature" badge
COVER_MAX_W = 990        # widest allowed title line
def render_cover(spec, reel_dir):
    """Full-screen photo, dark fade behind a big centred headline (white + red), brand badge and logo.
    The title block sits inside the 3:4 centre area so the profile grid crop keeps it whole."""
    from PIL import ImageDraw
    c = spec["cover"]
    img = Image.open(reel_dir / c["image"]).convert("RGB")
    r0, _ = shot_rects(img, c.get("cx", 0.5), c.get("cy", 0.5), "zoom_in")
    x, y, w, h = r0
    canvas = img.resize((W, H), Image.LANCZOS, box=(x, y, x + w, y + h))

    from PIL import ImageFilter
    lines = c["title"]
    font_path = str(ASSETS / "fonts" / "Anton-Regular.ttf")
    gap = 30

    def widths(size):
        f = ImageFont.truetype(font_path, size)
        return f, [sum(f.getlength(t) for t, _ in parts) + gap * (len(parts) - 1) for parts in lines]

    # Fixed layout on every cover (the takin cover the user approved): same title size, badge and
    # title start position no matter how long the title is. A title that doesn't fit must be shortened.
    size = COVER_TITLE_SIZE
    f, ws = widths(size)
    if not 1 <= len(lines) <= 4:
        raise ValueError(f"cover title needs 1-4 lines, got {len(lines)}")
    for parts, w in zip(lines, ws):
        if w > COVER_MAX_W:
            raise ValueError(f"COVER OVERFLOW: line '{' '.join(t for t, _ in parts)}' is {w:.0f}px wide "
                             f"(max {COVER_MAX_W}); shorten it (about 11 characters per line)")
    line_h = int(size * 1.16)
    block_h = line_h * len(lines)
    top = COVER_TITLE_TOP

    # darken behind the title area (and a little towards the bottom) so it always reads
    arr = np.asarray(canvas).astype(np.float32)
    ys = np.arange(H)[:, None, None]
    full_h = line_h * 4
    centre, half = top + full_h / 2, full_h / 2 + 260
    band = np.clip(1 - np.abs(ys - centre) / half, 0, 1) ** 0.8 * 0.72
    bottom = np.clip((ys - 1300) / 620, 0, 1) * 0.6
    canvas = Image.fromarray((arr * (1 - np.maximum(band, bottom))).astype(np.uint8))

    tmpl = Image.open(ASSETS / "template_a.jpeg").convert("RGB")
    badge = tmpl.crop((390, 835, 731, 902))
    badge = badge.resize((int(badge.width * 1.25), int(badge.height * 1.25)), Image.LANCZOS)
    mask = Image.new("L", badge.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, badge.width - 1, badge.height - 1], radius=35, fill=255)
    canvas.paste(badge, ((W - badge.width) // 2, COVER_BADGE_Y), mask)

    # soft drop shadow, then the text with a heavy black outline
    shadow = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shadow)
    pos = []
    for i, (parts, lw) in enumerate(zip(lines, ws)):
        xx, yy = (W - lw) / 2, top + i * line_h
        for t, col in parts:
            pos.append((xx, yy, t, col))
            sd.text((xx + 8, yy + 12), t, font=f, fill=200, stroke_width=10, stroke_fill=200)
            xx += f.getlength(t) + gap
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    canvas = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), canvas, shadow)
    d = ImageDraw.Draw(canvas)
    for xx, yy, t, col in pos:
        d.text((xx, yy), t, font=f, fill=(255, 255, 255) if col == "W" else (254, 0, 0),
               stroke_width=6, stroke_fill=(0, 0, 0))
    canvas.save(reel_dir / "cover.jpg", quality=93)
    print(f"OK: {reel_dir / 'cover.jpg'} (title size {size})")


def main(reel_dir):
    reel_dir = Path(reel_dir)
    spec = json.loads((reel_dir / "reel.json").read_text(encoding="utf-8"))
    voice, rate = spec.get("voice", "tr-TR-AhmetNeural"), spec.get("rate", "+0%")
    segs = spec["segments"]
    work = reel_dir / "_work"
    work.mkdir(exist_ok=True)

    # 1. narration per sentence -> durations + absolute word timings
    t, timed, starts, durs, parts = 0.0, [], [], [], []
    for i, s in enumerate(segs):
        mp3 = work / f"s{i}.mp3"
        words = tts(s["text"], voice, rate, mp3, reel_dir / "_tts_cache")
        d = duration(mp3) + (GAP if i < len(segs) - 1 else TAIL)
        starts.append(t)
        durs.append(d)
        timed.append([(t + a, t + b, w) for a, b, w in words])
        parts.append(mp3)
        t += d
    total = t

    # voice track: each sentence placed at its start time
    inputs, filt = [], []
    for i, p in enumerate(parts):
        inputs += ["-i", str(p)]
        filt.append(f"[{i}:a]adelay={int(starts[i] * 1000)}:all=1[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(parts))) + f"amix=inputs={len(parts)}:normalize=0,apad,atrim=0:{total:.3f}[out]")
    subprocess.run([ffmpeg_bin("ffmpeg"), "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt),
                    "-map", "[out]", "-c:a", "libmp3lame", "-q:a", "2", str(reel_dir / "voice.mp3")], check=True)

    # optional background music: quiet bed that ducks further while the narrator speaks
    audio = reel_dir / "voice.mp3"
    music = spec.get("music")
    if music:
        audio = work / "mix.m4a"
        lufs = music.get("loudness", -27)   # tracks differ a lot in level; normalise first
        subprocess.run([
            ffmpeg_bin("ffmpeg"), "-y", "-v", "error",
            "-i", str(reel_dir / "voice.mp3"),
            "-ss", str(music.get("start", 0)), "-i", str(ROOT / music["file"]),
            "-filter_complex",
            f"[1:a]atrim=0:{total:.3f},asetpts=PTS-STARTPTS,loudnorm=I={lufs}:TP=-3:LRA=11,"
            f"afade=t=in:d=1.5,afade=t=out:st={max(0, total - 2):.3f}:d=2[m];"
            "[0:a]asplit=2[v][sc];"
            "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=400[duck];"
            "[v][duck]amix=inputs=2:normalize=0:duration=first[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(audio)], check=True)

    build_ass(timed, reel_dir / "subs.ass")

    # 2. frames: each photo with slow camera move, crossfaded into the next
    logo = Image.open(ASSETS / "template_a.jpeg").convert("RGB").crop((55, 32, 169, 130))
    logo = logo.resize((int(logo.width * 1.1), int(logo.height * 1.1)), Image.LANCZOS)
    lx, ly = 48, 150
    logo_arr = np.asarray(logo)

    fade_n = int(FADE * FPS)
    subs = str(reel_dir / "subs.ass").replace("\\", "/").replace(":", "\\:")
    fonts = str(ASSETS / "fonts").replace("\\", "/").replace(":", "\\:")
    enc = subprocess.Popen([
        ffmpeg_bin("ffmpeg"), "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(audio),
        "-vf", f"subtitles='{subs}':fontsdir='{fonts}'",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        str(reel_dir / "reel.mp4")], stdin=subprocess.PIPE)

    prev_tail = None
    for i, s in enumerate(segs):
        img = Image.open(reel_dir / s["image"]).convert("RGB")
        n = round(durs[i] * FPS) + (fade_n if i < len(segs) - 1 else 0)
        r0, r1 = shot_rects(img, s.get("cx", 0.5), s.get("cy", 0.5), s.get("motion", "zoom_in"))
        frames = render_shot(img, r0, r1, n)
        tail = []
        for k, fr in enumerate(frames):
            if prev_tail is not None and k < len(prev_tail):
                a = (k + 1) / (len(prev_tail) + 1)
                fr = (prev_tail[k] * (1 - a) + fr * a).astype(np.uint8)
            if i < len(segs) - 1 and k >= n - fade_n:
                tail.append(fr.astype(np.float32))
                continue
            fr = fr.copy()
            fr[ly:ly + logo_arr.shape[0], lx:lx + logo_arr.shape[1]] = logo_arr
            enc.stdin.write(fr.tobytes())
        prev_tail = tail
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    shutil.rmtree(work)
    print(f"OK: {reel_dir / 'reel.mp4'} ({total:.1f}s)")


def fetch_photos(spec, reel_dir):
    """Download any photo listed in spec["photos"] that isn't in reel_dir yet."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import commons
    for name, title in spec.get("photos", {}).items():
        if not (reel_dir / name).exists():
            commons.download(title, str(reel_dir / name))


def preview(spec, reel_dir):
    """Contact sheet: start and end frame of every shot, so crops can be checked without rendering."""
    th_w, th_h = 270, 480
    segs = spec["segments"]
    sheet = Image.new("RGB", (th_w * 2 * 5 + 40, (th_h + 10) * ((len(segs) + 4) // 5)), (60, 60, 60))
    for i, s in enumerate(segs):
        img = Image.open(reel_dir / s["image"]).convert("RGB")
        r0, r1 = shot_rects(img, s.get("cx", 0.5), s.get("cy", 0.5), s.get("motion", "zoom_in"))
        for k, (x, y, w, h) in enumerate((r0, r1)):
            fr = img.resize((th_w, th_h), Image.BICUBIC, box=(x, y, x + w, y + h))
            sheet.paste(fr, ((i % 5) * (th_w * 2 + 8) + k * th_w, (i // 5) * (th_h + 10)))
    sheet.save(reel_dir / "preview.jpg", quality=85)
    print(f"OK: {reel_dir / 'preview.jpg'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) == 3 and sys.argv[1] == "--voice":
        # pre-record narration into _tts_cache (run hours before publishing; the voice service is flaky)
        d = Path(sys.argv[2])
        spec = json.loads((d / "reel.json").read_text(encoding="utf-8"))
        tmp, missing = d / "_voice_tmp.mp3", 0
        for s in spec["segments"]:
            try:
                tts(s["text"], spec.get("voice", "tr-TR-AhmetNeural"), spec.get("rate", "+0%"), tmp, d / "_tts_cache", retries=4)
            except Exception as e:
                missing += 1
                print(f"not yet: {s['text'][:50]} ({type(e).__name__})")
        tmp.unlink(missing_ok=True)
        print(f"voice: {len(spec['segments']) - missing}/{len(spec['segments'])} sentences ready")
    elif len(sys.argv) == 3 and sys.argv[1] in ("--cover", "--preview"):
        d = Path(sys.argv[2])
        spec = json.loads((d / "reel.json").read_text(encoding="utf-8"))
        fetch_photos(spec, d)
        (render_cover if sys.argv[1] == "--cover" else preview)(spec, d)
    elif len(sys.argv) == 2:
        d = Path(sys.argv[1])
        fetch_photos(json.loads((d / "reel.json").read_text(encoding="utf-8")), d)
        main(d)
        spec = json.loads((d / "reel.json").read_text(encoding="utf-8"))
        if "cover" in spec:
            render_cover(spec, d)
    else:
        sys.exit(__doc__)
