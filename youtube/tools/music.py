"""Music library (assets/music/library.json) and the owner's rule: every video gets different music.

Documentaries: the two tracks in script.json journey.music must not have been used by an earlier documentary while
unused tracks of the library remain (after that: not in the last 10). Reels/Shorts: not the track of the last 6 reels.

  python music.py            list documentary tracks, never-used first, with mood and length
  python music.py --reels    list tracks for Reels, least recently used first
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = json.loads((ROOT / "assets" / "music" / "library.json").read_text(encoding="utf-8"))
DOC_MIN_LEN = 120   # shorter tracks loop too often under 15 minutes of narration
RECENT_DOCS, RECENT_REELS = 10, 6


def doc_history(exclude=None):
    """Tracks of earlier documentaries, oldest first: [(doc name, [tracks])]."""
    out = []
    for f in sorted((ROOT / "youtube" / "docs").glob("*/script.json")):
        if exclude and f.parent.resolve() == Path(exclude).resolve():
            continue
        m = json.loads(f.read_text(encoding="utf-8")).get("journey", {}).get("music") or ["Reawakening.mp3", "Investigations.mp3"]
        out.append((f.parent.name, m))
    return out


def reel_history():
    """Track files of reels, most recent first (posted ones, then the queue)."""
    out = []
    for d in ("posted_reels", "queue_reels"):
        for f in sorted((ROOT / d).glob("*/reel.json")):
            m = json.loads(f.read_text(encoding="utf-8")).get("music")
            if m:
                out.append(Path(m["file"]).name)
    return out[::-1]


def check_doc(doc, tracks):
    errs = []
    if len(tracks) != 2 or tracks[0] == tracks[1]:
        errs.append("journey.music iki farklı parça olmalı")
    hist = doc_history(exclude=doc)
    used = {t for _, m in hist for t in m}
    recent = {t for _, m in hist[-RECENT_DOCS:] for t in m}
    fresh = [k for k, v in LIB.items() if v["len"] >= DOC_MIN_LEN and k not in used]
    for t in tracks:
        if t not in LIB:
            errs.append(f"müzik {t} kütüphanede yok (assets/music/library.json)")
            continue
        if LIB[t]["len"] < DOC_MIN_LEN:
            errs.append(f"müzik {t} belgesel için çok kısa ({LIB[t]['len']} sn)")
        if t in used and (len(fresh) >= 2 or t in recent):
            errs.append(f"müzik {t} daha önceki bir belgeselde kullanıldı; `python youtube/tools/music.py` ile yeni parça seç")
    return errs


def main():
    if "--reels" in sys.argv:
        hist = reel_history()
        rank = {t: hist.index(t) if t in hist else 999 for t in LIB}
        for t in sorted(LIB, key=lambda t: -rank[t]):
            print(f"{'son ' + str(rank[t] + 1) + '.' if rank[t] < 999 else 'hiç':>8}  {LIB[t]['mood']:8s} {LIB[t]['len']:4d} sn  {t}  — {LIB[t]['desc']}")
        return
    used = {}
    for name, m in doc_history():
        for t in m:
            used[t] = name
    for t in sorted(LIB, key=lambda t: (t in used, used.get(t, ""), LIB[t]["mood"])):
        if LIB[t]["len"] < DOC_MIN_LEN:
            continue
        print(f"{used.get(t, 'KULLANILMADI'):32s} {LIB[t]['mood']:8s} {LIB[t]['len']:4d} sn  {t}  — {LIB[t]['desc']}")


if __name__ == "__main__":
    main()
