"""Performance analysis -> data/insights.md (read by the daily content task before choosing).

Joins Instagram stats (data/stats.json) with our own post metadata (posted/*/post.json,
posted_reels/*/reel.json via published.json media ids) and compares each post with others
of the same format, so carousels are judged against carousels and reels against reels.

  python tools/analyze.py
"""
import collections
import datetime as dt
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_N = 4          # fewer samples than this -> "veri yetersiz"
SETTLE_H = 72      # insights keep growing for ~3 days; younger posts are ignored


def load_meta():
    """media_id -> our metadata (creature, group, hook style, title, format)."""
    meta = {}
    for kind, folder, spec_name in (("gönderi", "posted", "post.json"), ("reels", "posted_reels", "reel.json")):
        for pub in (ROOT / folder).glob("*/published.json"):
            spec_file = pub.parent / spec_name
            if not spec_file.exists():
                continue
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
            title = spec.get("title") or spec.get("cover", {}).get("title") or []
            meta[json.loads(pub.read_text())["media_id"]] = {
                "kind": kind, "name": spec.get("name") or pub.parent.name.split("_", 1)[-1],
                "group": spec.get("group", "?"), "hook_style": spec.get("hook_style", "?"),
                "title": " / ".join(" ".join(p[0] for p in line) for line in title)}
    return meta


def tr_hour(ts):
    t = dt.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S") + dt.timedelta(hours=3)
    return t.hour, t.strftime("%a")


def main():
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    meta = load_meta()
    now = dt.datetime.utcnow()
    rows = []
    for p in stats["posts"]:
        ins = p.get("insights")
        if not ins:
            continue
        age_h = (now - dt.datetime.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() / 3600
        if age_h < SETTLE_H:
            continue
        m = meta.get(p["id"], {})
        kind = m.get("kind") or ("reels" if p.get("media_product_type") == "REELS" else "gönderi")
        hour, _ = tr_hour(p["timestamp"])
        reach = ins.get("reach", 0) or 0
        rows.append({
            "id": p["id"], "date": p["timestamp"][:10], "kind": kind, "auto": bool(m),
            "name": m.get("name") or p["caption"][:40].replace("\n", " "),
            "group": m.get("group", "?"), "hook_style": m.get("hook_style", "?"), "title": m.get("title", ""),
            "hour": hour, "reach": reach, "views": ins.get("views", 0), "saves": ins.get("saved", 0),
            "shares": ins.get("shares", 0), "watch": ins.get("ig_reels_avg_watch_time"),
            "eng": ((ins.get("saved", 0) or 0) + 2 * (ins.get("shares", 0) or 0)) / reach * 100 if reach else 0})

    # relative reach: reach / median reach of the same format (1.0 = typical)
    for kind in ("gönderi", "reels"):
        same = [r["reach"] for r in rows if r["kind"] == kind]
        med = st.median(same) if same else 1
        for r in rows:
            if r["kind"] == kind:
                r["rel"] = r["reach"] / med if med else 0

    out = [f"# Performans raporu ({now:%Y-%m-%d})", "",
           f"Son 45 gün, en az {SETTLE_H} saatlik {len(rows)} paylaşım. **Göreli erişim** = erişim / aynı türdeki "
           "paylaşımların medyan erişimi (1,00 = tipik; 1,30 = %30 daha iyi). **Etkileşim** = (kaydetme + 2×paylaşım) / erişim, %.", ""]

    def table(key, title, kinds=("gönderi", "reels")):
        out.append(f"## {title}")
        out.append("")
        out.append("| Tür | Değer | Adet | Göreli erişim | Etkileşim % | Karar |")
        out.append("|---|---|---|---|---|---|")
        for kind in kinds:
            groups = collections.defaultdict(list)
            for r in rows:
                if r["kind"] == kind and r[key] not in ("?", None):
                    groups[r[key]].append(r)
            for val, rs in sorted(groups.items(), key=lambda kv: -st.median(x["rel"] for x in kv[1])):
                rel = st.median(x["rel"] for x in rs)
                eng = st.median(x["eng"] for x in rs)
                if len(rs) < MIN_N:
                    verdict = "veri yetersiz — denemeye devam"
                elif rel >= 1.2:
                    verdict = "**güçlü — daha sık kullan**"
                elif rel <= 0.8:
                    verdict = "zayıf — daha seyrek kullan"
                else:
                    verdict = "ortalama"
                out.append(f"| {kind} | {val} | {len(rs)} | {rel:.2f} | {eng:.2f} | {verdict} |")
        out.append("")

    table("group", "Canlı grubuna göre")
    table("hook_style", "Başlık (kanca) tarzına göre")
    table("hour", "Paylaşım saatine göre (Türkiye)")

    for kind in ("gönderi", "reels"):
        rs = sorted((r for r in rows if r["kind"] == kind), key=lambda r: -r["rel"])
        if not rs:
            continue
        for label, part in (("En iyi", rs[:5]), ("En zayıf", rs[-5:][::-1])):
            out.append(f"## {label} 5 {kind}")
            out.append("")
            out.append("| Tarih | Canlı | Başlık | Grup | Kanca | Erişim | Göreli | Kaydet | Paylaş |"
                       + (" Ort. izlenme sn |" if kind == "reels" else ""))
            out.append("|---|---|---|---|---|---|---|---|---|" + ("---|" if kind == "reels" else ""))
            for r in part:
                w = f" {r['watch'] / 1000:.1f} |" if kind == "reels" and r["watch"] else (" - |" if kind == "reels" else "")
                out.append(f"| {r['date']} | {r['name']} | {r['title'] or '-'} | {r['group']} | {r['hook_style']} | "
                           f"{r['reach']} | {r['rel']:.2f} | {r['saves']} | {r['shares']} |{w}")
            out.append("")

    fol = (ROOT / "data" / "followers.csv")
    if fol.exists():
        pts = [l.split(",") for l in fol.read_text().split() if "," in l]
        pts = [(d, int(n)) for d, n in pts if n.isdigit()]
        if len(pts) >= 2:
            week = [n for d, n in pts if d >= (now - dt.timedelta(days=7)).strftime("%Y-%m-%d")]
            out.append(f"## Takipçi")
            out.append("")
            out.append(f"Şu an {pts[-1][1]}; son 7 günde {week[-1] - week[0]:+d}." if len(week) >= 2 else f"Şu an {pts[-1][1]}.")
            out.append("")

    (ROOT / "data" / "insights.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"insights for {len(rows)} posts written to data/insights.md")


if __name__ == "__main__":
    main()
