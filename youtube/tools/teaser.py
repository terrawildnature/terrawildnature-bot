"""Documentary teaser Short: one creature's chapter cut out of the finished documentary, made vertical, with the
documentary's headline on top and "watch the full documentary" below. It goes live together with the documentary
(scheduled to its publish_at) and links to it, to bring Shorts viewers to the long video.

  python youtube/tools/teaser.py --pick       prints the documentary that needs a teaser next (within the API quota)
  python youtube/tools/teaser.py <doc_dir>    downloads the documentary from its release, cuts, uploads,
                                              writes <doc_dir>/teaser.json
  python youtube/tools/teaser.py <doc_dir> --local <belgesel.mp4> <altyazi.srt> <story.jpg> --dry   test, no upload

meta.json "teaser" (optional): {"seg": <segment index>, "title": "<Short title>"}. Default: the creature 40% into the
documentary (the climax at the end is not given away).
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import shorts
from english import parse_srt

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "youtube" / "docs"
ASSETS = ROOT / "assets"
F_ANTON, F_ROBOTO = str(ASSETS / "fonts" / "Anton-Regular.ttf"), str(ASSETS / "fonts" / "Roboto-Bold.ttf")
LOGO = ROOT / "youtube" / "assets" / "logo.png"
W, H = 1080, 1920
VID_Y = 700                     # the 16:9 documentary picture (1080x608) sits here
YELLOW, RED = (255, 204, 64), (230, 33, 23)
MAX_LEN, MIN_LEN = 58, 25
SHORTS_PER_DAY = 3


def pick():
    """Documentaries with a YouTube video but no teaser: upcoming ones first (soonest), then the newest published.
    Only if today's quota still covers this teaser and the Shorts still due today."""
    now = dt.datetime.now(dt.timezone.utc)
    todo = []
    for f in DOCS.glob("*/status.json"):
        s = json.loads(f.read_text(encoding="utf-8"))
        if s.get("video_id") and s.get("publish_at") and not (f.parent / "teaser.json").exists():
            at = dt.datetime.fromisoformat(s["publish_at"].replace("Z", "+00:00"))
            todo.append((at < now, -at.timestamp() if at < now else at.timestamp(), f.parent))
    if not todo:
        return None
    since = shorts.quota_day_start()
    done_today = sum(1 for f in shorts.POSTED.glob("*/youtube.json")
                     if (json.loads(f.read_text(encoding="utf-8")).get("uploaded_at") or "") >= since.isoformat())
    due = max(0, SHORTS_PER_DAY - done_today)
    left = shorts.budget()
    if left < shorts.SHORT_COST * (1 + due):
        print(f"quota: {left} units left, {due} Shorts still due today; teaser waits", file=sys.stderr)
        return None
    return sorted(todo)[0][2]


def chapter_times(doc):
    out = []
    for line in (doc / "chapters.txt").read_text(encoding="utf-8").strip().splitlines():
        t, label = line.split(" ", 1)
        p = [int(x) for x in t.split(":")]
        out.append((sum(v * m for v, m in zip(reversed(p), (1, 60, 3600))), label))
    return out


def clip_range(doc, spec, meta, cues):
    """(start, end, creature name): the chosen creature's chapter, ending on a subtitle boundary."""
    segs = spec["segments"]
    want = (meta.get("teaser") or {}).get("seg")
    creatures = [i for i, s in enumerate(segs) if s["type"] == "creature"]
    i = want if want is not None else creatures[int(len(creatures) * 0.4)]
    name = segs[i]["name"]
    ch = chapter_times(doc)
    k = next(k for k, (_, label) in enumerate(ch) if label == name or label.endswith(" " + name))
    start = ch[k][0]
    nxt = ch[k + 1][0] if k + 1 < len(ch) else start + MAX_LEN
    cap = min(nxt, start + MAX_LEN)
    ends = [z for a, z, _ in cues if start + MIN_LEN <= z <= cap]
    end = (max(ends) + 0.6) if ends else cap
    return start, end, name


def overlay(meta, vid_h):
    """Transparent 1080x1920 layer: logo, red pill, headline above the picture; call to action below it."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def centered(y, text, f, fill, stroke=0):
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))

    logo = Image.open(LOGO).convert("RGBA").resize((96, 96), Image.LANCZOS)
    img.paste(logo, ((W - 96) // 2, 130), logo)
    f = ImageFont.truetype(F_ROBOTO, 36)
    label = "BELGESELDEN BİR BÖLÜM"
    lw = d.textlength(label, font=f)
    d.rounded_rectangle(((W - lw) / 2 - 30, 250, (W + lw) / 2 + 30, 312), 31, fill=RED)
    centered(259, label, f, (255, 255, 255))
    lines = meta["story"]["lines"][:3]
    size = 104 if len(lines) <= 2 else 92
    y = VID_Y - 40 - len(lines) * (size + 14)
    for n, ln in enumerate(lines):
        fh = ImageFont.truetype(F_ANTON, size)
        while d.textlength(ln, font=fh) > W - 80:
            fh = ImageFont.truetype(F_ANTON, fh.size - 4)
        centered(y, ln, fh, YELLOW if n == 0 else (255, 255, 255), stroke=4)
        y += size + 14
    yb = VID_Y + vid_h + 70
    centered(yb, "TAMAMI 30 DAKİKALIK BELGESELDE", ImageFont.truetype(F_ROBOTO, 46), (255, 255, 255))
    f2 = ImageFont.truetype(F_ROBOTO, 40)
    cta = "İZLEMEK İÇİN AŞAĞIDAKİ BAĞLANTIYA DOKUN"
    centered(yb + 78, cta, f2, YELLOW)
    ax = W // 2
    d.polygon([(ax - 30, yb + 150), (ax + 30, yb + 150), (ax, yb + 190)], fill=YELLOW)
    return img


def render(doc, video, srt, story, work):
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    meta = json.loads((doc / "meta.json").read_text(encoding="utf-8"))
    start, end, name = clip_range(doc, spec, meta, parse_srt(Path(srt).read_text(encoding="utf-8")))
    vid_h = 608
    overlay(meta, vid_h).save(work / "overlay.png")
    ff = shutil.which("ffmpeg") or "ffmpeg"
    dur = end - start
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(video),
                    "-i", str(work / "overlay.png"), "-loop", "1", "-t", "0.5", "-i", str(story),
                    "-filter_complex",
                    "[0:v]split=2[a][b];"
                    f"[a]crop=iw:ih*0.72:0:0,scale=-2:{H},crop={W}:{H},gblur=sigma=30,eq=brightness=-0.3:saturation=0.8[bg];"   # top part: no subtitles in the blur
                    f"[b]scale={W}:{vid_h}[fg];"
                    f"[bg][fg]overlay=0:{VID_Y}[v1];[v1][1:v]overlay=0:0,setsar=1,fps=30,format=yuv420p[v];"
                    f"[2:v]scale={W}:{H},setsar=1,fps=30,format=yuv420p[c];[c][v]concat=n=2:v=1:a=0[vo];"
                    f"[0:a]afade=t=out:st={dur - 1.2:.2f}:d=1.2,adelay=500:all=1[ao]",
                    "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(work / "teaser.mp4")], check=True)
    print(f"teaser: {name}, {start:.1f}-{end:.1f} s ({dur:.0f} s)")
    return spec, meta, name


def body(meta, status, name):
    vid = status["video_id"]
    t = (meta.get("teaser") or {}).get("title") or meta["title"]
    t = re.sub(r"\s+", " ", t).strip()[:88] + " #shorts"
    first = re.split(r"(?<=[.!?])\s", meta["description"].strip())[0]
    desc = (f"🎬 Tam belgesel (30 dk): https://youtu.be/{vid}\n\n"
            f"{first}\n\n"
            f"Bu Shorts belgeselimizin \"{name}\" bölümünden. Her Çarşamba ve Cumartesi 20:00'de yeni belgesel: "
            "https://www.youtube.com/@terrawildnature-tr\n\n"
            "Seslendirme ve kurgu yapay zekâ desteğiyle hazırlanmıştır. Görsel ve müzik kaynakları belgeselin açıklamasında.\n\n"
            "#shorts #belgesel #hayvanlar #terrawildnature")
    st = {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}
    at = dt.datetime.fromisoformat(status["publish_at"].replace("Z", "+00:00"))
    if at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30):   # goes live together with the documentary
        st.update(privacyStatus="private", publishAt=status["publish_at"])
    return {"snippet": {"title": t, "description": desc.replace("<", "").replace(">", ""),
                        "tags": ["shorts", "belgesel", "hayvanlar", "vahşi doğa", "terra wild nature"],
                        "categoryId": "15", "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
            "status": st}


def localization(meta, status):
    en = meta.get("en")
    if not en:
        return None
    return {"title": re.sub(r"\s+", " ", en["title"]).strip()[:88] + " #shorts",
            "description": f"🎬 Full documentary (30 min, English subtitles): https://youtu.be/{status['video_id']}\n\n"
                           f"{en['description'].strip()}\n\n#shorts #animals #wildlife #terrawildnature"}


def main(doc):
    status = json.loads((doc / "status.json").read_text(encoding="utf-8"))
    work = ROOT / "_teaser" / doc.name
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    if "--local" in sys.argv:
        k = sys.argv.index("--local")
        video, srt, story = (Path(x) for x in sys.argv[k + 1:k + 4])
    else:
        tag = status["release"].rsplit("/", 1)[1]
        subprocess.run(["gh", "release", "download", tag, "-p", "belgesel.mp4", "-p", "altyazi.srt", "-p", "story.jpg",
                        "-D", str(work), "--clobber"], check=True)
        video, srt, story = work / "belgesel.mp4", work / "altyazi.srt", work / "story.jpg"
    spec, meta, name = render(doc, video, srt, story, work)
    b = body(meta, status, name)
    if "--dry" in sys.argv:
        print(json.dumps(b, ensure_ascii=False, indent=1))
        print(work / "teaser.mp4")
        return
    from yt_upload import access_token, upload
    import urllib.error
    try:
        vid = upload(work / "teaser.mp4", b, access_token())["id"]
    except (SystemExit, urllib.error.HTTPError) as e:
        msg = e.read().decode(errors="replace") if isinstance(e, urllib.error.HTTPError) else str(e)
        if "quotaExceeded" in msg or "uploadLimitExceeded" in msg:
            print(f"YouTube daily limit reached, the {doc.name} teaser waits for a later run")
            return
        raise SystemExit(f"upload failed: {msg[:500]}")
    (doc / "teaser.json").write_text(json.dumps({"video_id": vid, "title": b["snippet"]["title"], "creature": name,
                                                 "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat()},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        shorts.wait_processed(vid)
        shorts.set_cover(vid, story)
    except Exception as e:
        print(f"thumbnail not set for {vid}: {e}")
    try:
        from english import localize
        if loc := localization(meta, status):
            localize(vid, loc)
    except Exception as e:
        print(f"English title not set for {vid}: {e}")
    print(f"https://youtube.com/shorts/{vid} ({b['status'].get('publishAt', 'public now')})")


if __name__ == "__main__":
    if sys.argv[1] == "--pick":
        d = pick()
        print(d.relative_to(ROOT).as_posix() if d else "")
    else:
        main(Path(sys.argv[1]).resolve())
