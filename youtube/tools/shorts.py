"""Instagram posts -> YouTube "Tahmin Et" Shorts (since 2026-11-22, owner's request: YouTube gets its own format, not
a copy of the Reels). Each Instagram post published since QUIZ_SINCE becomes a quiz Short (youtube/tools/quiz_short.py:
mystery animal, countdown, reveal, 3 facts, comment/subscribe card) uploaded as a public Short, so the channel gets
as many Shorts as Instagram gets posts (5 a day) about animals that differ from the Reels.
Older Reels recipes (posted_reels/<dir>/reel.json) can still be uploaded in the old format by passing their dir.

  python youtube/tools/shorts.py --pick            prints the newest Instagram post not on YouTube yet
  python youtube/tools/shorts.py --pick --backfill also the oldest one left over (evening run)
                                                   (--pick keeps within the daily API quota, see budget())
  python youtube/tools/shorts.py <reel_dir> --dry  prints the title/description only
  python youtube/tools/shorts.py <post_dir>        renders (quiz_short.py), uploads, writes <post_dir>/youtube.json
  python youtube/tools/shorts.py <reel_dir>        old format: renders reel.py with the Reels cover
Needs env YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (GitHub secrets).
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[2]
POSTED = ROOT / "posted_reels"
POSTS = ROOT / "posted"
QUIZ_SINCE = dt.datetime(2026, 11, 22, tzinfo=dt.timezone.utc)   # posts published from here on become quiz Shorts
DOCS = ROOT / "youtube" / "docs"
QUOTA = 10000            # YouTube Data API units per day, reset at midnight Pacific time
MARGIN = 600
SHORT_COST = 1750        # videos.insert 1600 + thumbnails.set 50 + English localization 50 + processing polls
DOC_COST = 2600          # videos.insert 1600 + 2 captions.insert 800 + thumbnails.set 50 + localization 50 + polls


def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def title(spec):
    """yt_title from the recipe, else the cover text as a sentence: 'Dünyanın en büyük maymunu mandril'."""
    t = spec.get("yt_title")
    if not t:
        words = " ".join(w for line in spec["cover"]["title"] for w, _ in line)
        t = tr_lower(words)
        t = t[0].upper() + t[1:]
    t = re.sub(r"\s+", " ", t).strip()
    return (t[:88] + " #shorts") if "#shorts" not in t.lower() else t[:100]


def description(spec):
    cap = spec["caption"]
    body = cap.split("\n\n")[0].strip()
    tags = " ".join(h for h in re.findall(r"#\w+", cap) if h != "#terrawildnature")
    credits = "\n".join(l for l in cap.splitlines() if l.startswith(("📷", "🎵")))
    credits = credits.replace("🎵 Kevin MacLeod (CC BY)", "🎵 Müzik: Kevin MacLeod (incompetech.com), CC BY 3.0")
    return (f"{body}\n\n"
            "Her Çarşamba ve Cumartesi 20:00'de yeni belgesel: https://www.youtube.com/@terrawildnature-tr\n"
            "Instagram: https://www.instagram.com/terrawildnature\n\n"
            f"{credits}\n\n"
            "Seslendirme yapay zekâ ile üretilmiştir; bilgiler Wikipedia ve bilimsel kaynaklardan derlenmiştir.\n\n"
            f"#shorts #hayvanlar #terrawildnature {tags}").strip()


def quota_day_start():
    """Last midnight in Pacific time, as UTC (approximated as UTC-8 when tzdata is missing)."""
    now = dt.datetime.now(dt.timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        pt = now.astimezone(ZoneInfo("America/Los_Angeles"))
    except Exception:
        pt = now.astimezone(dt.timezone(dt.timedelta(hours=-8)))
    return pt.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)


def budget():
    """Units left today: Shorts and documentaries uploaded since the quota reset are spent, and a documentary that is
    committed but not built yet gets its share reserved, so Shorts never starve a documentary upload."""
    since = quota_day_start()

    def today(f):
        try:
            t = json.loads(f.read_text(encoding="utf-8")).get("uploaded_at")
            return bool(t) and dt.datetime.fromisoformat(t.replace("Z", "+00:00")) >= since
        except (OSError, ValueError):
            return False
    used = SHORT_COST * sum(today(f) for f in POSTED.glob("*/youtube.json"))
    used += SHORT_COST * sum(today(f) for f in POSTS.glob("*/youtube.json"))
    used += DOC_COST * sum(today(f) for f in DOCS.glob("*/status.json"))
    used += SHORT_COST * sum(today(f) for f in DOCS.glob("*/teaser.json"))   # documentary teaser Shorts
    pending = sum(1 for d in DOCS.glob("*/meta.json") if not (d.parent / "status.json").exists())
    return QUOTA - MARGIN - used - DOC_COST * pending


def published_at(d):
    try:
        t = json.loads((d / "published.json").read_text(encoding="utf-8"))["published_at"]
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError):
        return None


def pick(backfill=False):
    """Newest Instagram post not on YouTube yet, plus (backfill) the oldest one left over, as many as the quota allows."""
    todo = sorted((published_at(d), d) for d in POSTS.iterdir()
                  if d.is_dir() and (d / "post.json").exists() and not (d / "youtube.json").exists()
                  and (published_at(d) or QUIZ_SINCE - dt.timedelta(1)) >= QUIZ_SINCE)
    todo = [d for _, d in todo]
    want = list(dict.fromkeys(todo[-1:] + (todo[:1] if backfill else [])))
    n = max(0, budget() // SHORT_COST)
    if len(want) > n:
        print(f"quota: {budget()} units left today, uploading {n} of {len(want)}", file=sys.stderr)
    return want[:n]


def with_cover(work, sec=0.5):
    """short.mp4 = the cover for half a second, then the reel. The API thumbnail does not reach the Shorts feed and
    shelf, which show a frame of the video, so the cover has to be in the video itself."""
    ff = shutil.which("ffmpeg") or "ffmpeg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(work / "reel.mp4"), "-loop", "1", "-t", str(sec), "-i", str(work / "cover.jpg"),
                    "-filter_complex",
                    f"[1:v]scale=1080:1920,setsar=1,fps=30,format=yuv420p[c];[0:v]setsar=1,format=yuv420p[v];[c][v]concat=n=2:v=1:a=0[vo];"
                    f"[0:a]adelay={int(sec * 1000)}:all=1[ao]",
                    "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "160k",
                    "-movflags", "+faststart", str(work / "short.mp4")], check=True)


def wait_processed(vid, minutes=15):
    import time
    from yt_upload import access_token, request
    for _ in range(minutes * 2):
        r = json.load(request(f"https://www.googleapis.com/youtube/v3/videos?part=processingDetails&id={vid}", access_token(),
                              method="GET"))
        if r["items"] and r["items"][0].get("processingDetails", {}).get("processingStatus") == "succeeded":
            time.sleep(60)
            return
        time.sleep(30)


def set_cover(vid, cover):
    """The Reels cover (1080x1920) as the Short's thumbnail; YouTube wants a JPEG under 2 MB."""
    import io
    from PIL import Image
    from yt_upload import access_token, request
    buf = io.BytesIO()
    Image.open(cover).convert("RGB").save(buf, "JPEG", quality=90)
    request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", access_token(),
            buf.getvalue(), headers={"Content-Type": "image/jpeg"})
    print(f"thumbnail set for {vid}")


def quiz_title(post):
    """quiz.yt_title from the routine, else the post headline as a question that does not give the answer away."""
    t = post.get("quiz", {}).get("yt_title")
    if not t:
        head = tr_lower(" ".join(w for line in post["title"] for w, _ in line))
        head = head[0].upper() + head[1:]
        t = (head if len(head) <= 42 else head[:42].rsplit(" ", 1)[0]) + " — Tanıyor musun?"
    return re.sub(r"\s+", " ", t).strip()[:60] + " #shorts"


def publish(work, body, record_dir, en_spec, extra=None):
    """Upload work/short.mp4, write record_dir/youtube.json at once, then thumbnail and English localization."""
    from yt_upload import access_token, upload
    import urllib.error
    try:
        vid = upload(work / "short.mp4", body, access_token())["id"]
    except (SystemExit, urllib.error.HTTPError) as e:
        msg = e.read().decode(errors="replace") if isinstance(e, urllib.error.HTTPError) else str(e)
        if "quotaExceeded" in msg or "uploadLimitExceeded" in msg:   # not an error: it goes up in a later run
            print(f"YouTube daily limit reached, {record_dir.name} waits for a later run")
            return
        raise SystemExit(f"upload failed: {msg[:500]}")
    # written right away: if a later step fails, the Short is not uploaded a second time
    (record_dir / "youtube.json").write_text(json.dumps({"video_id": vid, "title": body["snippet"]["title"],
                                                         "uploaded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                                                         **(extra or {})}, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    try:
        wait_processed(vid)   # a thumbnail set while YouTube is still processing did not show up on the Short
        set_cover(vid, work / "cover.jpg")
    except Exception as e:   # the video is up; its first frames still show in the feed
        print(f"thumbnail not set for {vid}: {e}")
    try:
        from english import localize, short_localization
        if loc := short_localization(en_spec):
            localize(vid, loc)
        else:
            print(f"no English title for {record_dir.name}")
    except Exception as e:
        print(f"English title not set for {vid}: {e}")
    print(f"https://youtube.com/shorts/{vid}")


def next_format():
    """The ten edits take turns (owner's request, 2026-11-22): the one after the last uploaded Short's."""
    import short_formats
    done = [json.loads(f.read_text(encoding="utf-8")) for f in POSTS.glob("*/youtube.json")]
    if not done:
        return short_formats.FORMATS[0]
    last = max(done, key=lambda r: r.get("uploaded_at", "")).get("format", "tahmin")
    i = short_formats.FORMATS.index(last) if last in short_formats.FORMATS else 0
    return short_formats.FORMATS[(i + 1) % len(short_formats.FORMATS)]


def main_quiz(post_dir):
    import quiz_short
    import short_formats
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    fmt = sys.argv[sys.argv.index("--format") + 1] if "--format" in sys.argv else next_format()
    title = short_formats.yt_title(fmt, post)
    title = title + " #shorts" if title else quiz_title(post)
    spec = {"caption": post["caption"] + "\n\n🎵 Kevin MacLeod (CC BY)"}
    body = {"snippet": {"title": title, "description": description(spec),
                        "tags": ["shorts", "hayvanlar", "bu hayvan ne", "tahmin et", "ilginç bilgiler", "terra wild nature"],
                        "categoryId": "15", "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}}
    if "--dry" in sys.argv:
        print(json.dumps(body, ensure_ascii=False, indent=1))
        return
    recent = [json.loads(f.read_text(encoding="utf-8")).get("music") for f in
              sorted(POSTS.glob("*/youtube.json"), key=lambda f: f.name)[-20:]]
    work = ROOT / "_shorts" / post_dir.name   # render outside posted/ so nothing but youtube.json gets committed
    shutil.rmtree(work, ignore_errors=True)
    recent = [m.rsplit("/", 1)[-1] for m in recent if m]
    if fmt == "tahmin":
        q = quiz_short.from_post(post_dir, work, recent)
        quiz_short.build(work)
    else:
        q = short_formats.from_post(post_dir, work, fmt, recent)
        short_formats.build(work)
    print(f"format: {fmt}")
    publish(work, body, post_dir, short_formats.en_spec(fmt, post), {"music": q["music"]["file"], "format": fmt})


def main(reel_dir):
    if (reel_dir / "post.json").exists():
        return main_quiz(reel_dir)
    spec = json.loads((reel_dir / "reel.json").read_text(encoding="utf-8"))
    body = {"snippet": {"title": title(spec), "description": description(spec),
                        "tags": ["shorts", "hayvanlar", "vahşi doğa", "belgesel", "ilginç bilgiler", "terra wild nature"],
                        "categoryId": "15", "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}}
    if "--dry" in sys.argv:
        print(json.dumps(body, ensure_ascii=False, indent=1))
        return
    work = ROOT / "_shorts" / reel_dir.name   # render outside posted_reels so nothing but youtube.json gets committed
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    shutil.copy(reel_dir / "reel.json", work / "reel.json")
    subprocess.run([sys.executable, str(ROOT / "tools" / "reel.py"), str(work)], check=True)
    with_cover(work)
    publish(work, body, reel_dir, spec)


if __name__ == "__main__":
    if sys.argv[1] == "--pick":
        print("\n".join(d.relative_to(ROOT).as_posix() for d in pick("--backfill" in sys.argv)))
    else:
        main(Path(sys.argv[1]).resolve())
