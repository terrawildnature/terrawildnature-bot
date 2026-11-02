"""Instagram Reels -> YouTube Shorts. The Reels pipeline deletes its video after posting, so this re-renders the
reel from its recipe (posted_reels/<dir>/reel.json, tools/reel.py) and uploads it to YouTube as a public Short.

  python youtube/tools/shorts.py --pick            prints the reel dirs to upload today (newest + one old backfill)
  python youtube/tools/shorts.py <reel_dir> --dry  prints the title/description only
  python youtube/tools/shorts.py <reel_dir>        renders (reel.py) and uploads, writes <reel_dir>/youtube.json
Needs env YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (GitHub secrets).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(__file__).resolve().parents[2]
POSTED = ROOT / "posted_reels"


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
            "Her Cumartesi 20:00'de yeni belgesel: https://www.youtube.com/@terrawildnature-tr\n"
            "Instagram: https://www.instagram.com/terrawildnature\n\n"
            f"{credits}\n\n"
            "Seslendirme yapay zekâ ile üretilmiştir; bilgiler Wikipedia ve bilimsel kaynaklardan derlenmiştir.\n\n"
            f"#shorts #hayvanlar #terrawildnature {tags}").strip()


def pick():
    """Newest posted reel not on YouTube yet, plus the oldest one left over (backfill, one a day)."""
    todo = sorted(d for d in POSTED.iterdir()
                  if d.is_dir() and (d / "reel.json").exists() and not (d / "youtube.json").exists())
    return list(dict.fromkeys(todo[-1:] + todo[:1]))


def main(reel_dir):
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
    from yt_upload import access_token, upload
    vid = upload(work / "reel.mp4", body, access_token())["id"]
    (reel_dir / "youtube.json").write_text(json.dumps({"video_id": vid, "title": body["snippet"]["title"]},
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"https://youtube.com/shorts/{vid}")


if __name__ == "__main__":
    if sys.argv[1] == "--pick":
        print("\n".join(d.relative_to(ROOT).as_posix() for d in pick()))
    else:
        main(Path(sys.argv[1]).resolve())
