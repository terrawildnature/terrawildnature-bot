"""Hourly safety net: compares what went out today (Turkey time) with the schedule and prints the workflows that have
to run again to catch up (a skipped GitHub cron, a failed run, a cancelled one). watchdog.yml dispatches them.

  python tools/watchdog.py          prints one workflow file per line (publish.yml, publish-reel.yml, ...)
  python tools/watchdog.py --show   also explains the counts
"""
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "youtube" / "tools"))
TR = dt.timezone(dt.timedelta(hours=3))
START = dt.date(2026, 11, 5)              # the 5 posts / 3 reels / 3 shorts schedule starts here

# (workflow, slot times in Turkey, minutes after a slot before it counts as missed)
SCHEDULE = {
    "post": ("publish.yml", ["09:00", "12:00", "15:30", "18:00", "22:00"], 75),
    "reel": ("publish-reel.yml", ["10:30", "13:30", "20:00"], 60),
    "short": ("youtube-shorts.yml", ["11:30", "14:30", "21:30"], 75),
}


def stamp(f, key):
    try:
        t = json.loads(f.read_text(encoding="utf-8")).get(key)
        return dt.datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(TR) if t else None
    except (OSError, ValueError):
        return None


def done_today(kind, today):
    files = {"post": (ROOT.glob("posted/*/published.json"), "published_at"),
             "reel": (ROOT.glob("posted_reels/*/published.json"), "published_at"),
             "short": (ROOT.glob("posted_reels/*/youtube.json"), "uploaded_at")}[kind]
    return sum(1 for f in files[0] if (t := stamp(f, files[1])) and t.date() == today)


def has_work(kind):
    if kind == "post":
        return any((d / "post.json").exists() for d in (ROOT / "queue").iterdir())
    if kind == "reel":
        return any((d / "reel.json").exists() for d in (ROOT / "queue_reels").iterdir())
    import shorts
    return bool(shorts.pick(backfill=True))


def main():
    now = dt.datetime.now(TR)
    out = []
    if now.date() >= START:
        for kind, (wf, slots, grace) in SCHEDULE.items():
            due = sum(1 for s in slots
                      if now >= dt.datetime.combine(now.date(), dt.time.fromisoformat(s), TR) + dt.timedelta(minutes=grace))
            done = done_today(kind, now.date())
            work = has_work(kind) if done < due else False
            if "--show" in sys.argv:
                print(f"{kind}: due {due}, done {done}, work {work}", file=sys.stderr)
            if done < due and work:
                out.append(wf)
    print("\n".join(out))


if __name__ == "__main__":
    main()
