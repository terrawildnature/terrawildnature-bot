"""Performance analysis -> data/insights.md (read by the daily content task before choosing).

Only posts made by this system are compared (the user's older posts used other designs).
Each post gets three views of "how good was it":

  trend   reach / median reach of the same format published within ±7 days
          (removes the account's growth trend)
  day     median trend score of everything published that same day
          (a busy or quiet day, an ad, an algorithm swing lifts or sinks all posts of the day)
  content trend / day  ->  how the post did compared with its own day: the content's own pull

The composite "skor" mixes content with the rates people act on (shares, saves, likes, follows per
1000 reached, and average watch time for reels), each normalised to the median of its format.

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
DAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def med(xs, default=0.0):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else default


def load_meta():
    """media_id -> our metadata."""
    meta = {}
    for kind, folder, spec_name in (("gönderi", "posted", "post.json"), ("reels", "posted_reels", "reel.json")):
        for pub_file in (ROOT / folder).glob("*/published.json"):
            spec_file = pub_file.parent / spec_name
            if not spec_file.exists():
                continue
            spec = json.loads(spec_file.read_text(encoding="utf-8"))
            pub = json.loads(pub_file.read_text())
            title = spec.get("title") or spec.get("cover", {}).get("title") or []
            words = sum(len(s["text"].split()) for s in spec.get("segments", [])) or None
            music = Path(spec["music"]["file"]).stem if spec.get("music") else None
            meta[pub["media_id"]] = {
                "kind": kind, "name": spec.get("name") or pub_file.parent.name.split("_", 1)[-1],
                "group": spec.get("group", "?"), "hook_style": spec.get("hook_style", "?"),
                "title": " / ".join(" ".join(p[0] for p in line) for line in title),
                "music": music, "words": words, "duration": pub.get("duration_s")}
    return meta


def to_tr(ts):
    return dt.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S") + dt.timedelta(hours=3)


def bucket_duration(s):
    if not s:
        return None
    return "≤40 sn" if s <= 40 else ("40-50 sn" if s <= 50 else ">50 sn")


def main():
    stats = json.loads((ROOT / "data" / "stats.json").read_text(encoding="utf-8"))
    meta = load_meta()
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)

    rows = []
    for p in stats["posts"]:
        ins, m = p.get("insights"), meta.get(p["id"])
        if not ins or not m:
            continue
        if (now - dt.datetime.strptime(p["timestamp"][:19], "%Y-%m-%dT%H:%M:%S")).total_seconds() < SETTLE_H * 3600:
            continue
        t = to_tr(p["timestamp"])
        reach = ins.get("reach") or 0
        per_k = lambda v: (v or 0) / reach * 1000 if reach else 0
        rows.append({
            **m, "id": p["id"], "t": t, "date": t.strftime("%Y-%m-%d"), "weekday": DAYS_TR[t.weekday()],
            "hour": f"{t.hour:02d}:00", "reach": reach, "views": ins.get("views") or 0,
            "likes": ins.get("likes", p.get("like_count")) or 0, "comments": ins.get("comments", p.get("comments_count")) or 0,
            "saves": ins.get("saved") or 0, "shares": ins.get("shares") or 0,
            "follows": ins.get("follows"), "visits": ins.get("profile_visits"),
            "watch": (ins.get("ig_reels_avg_watch_time") or 0) / 1000 or None,
            "share_k": per_k(ins.get("shares")), "save_k": per_k(ins.get("saved")),
            "like_k": per_k(ins.get("likes", p.get("like_count"))),
            "follow_k": per_k(ins.get("follows")) if ins.get("follows") is not None else None,
            "dur_bucket": bucket_duration(m.get("duration"))})

    # trend: reach vs same-format posts within ±7 days (falls back to all of that format)
    for r in rows:
        near = [x["reach"] for x in rows if x["kind"] == r["kind"] and x is not r and abs((x["t"] - r["t"]).days) <= 7]
        if len(near) < 3:
            near = [x["reach"] for x in rows if x["kind"] == r["kind"] and x is not r]
        r["trend"] = r["reach"] / med(near, r["reach"] or 1) if near else 1.0
    # day effect and content score
    by_day = collections.defaultdict(list)
    for r in rows:
        by_day[r["date"]].append(r)
    for d, rs in by_day.items():
        eff = med([x["trend"] for x in rs], 1.0) if len(rs) >= 2 else 1.0
        for r in rs:
            r["day_eff"] = eff
            r["content"] = r["trend"] / eff if eff else r["trend"]
    # composite score per format
    for kind in ("gönderi", "reels"):
        rs = [r for r in rows if r["kind"] == kind]
        norms = {k: med([r[k] for r in rs]) or 1 for k in ("share_k", "save_k", "like_k", "watch")}
        for r in rs:
            parts = [(0.45, r["content"]), (0.2, r["share_k"] / norms["share_k"]),
                     (0.15, r["save_k"] / norms["save_k"]), (0.1, r["like_k"] / norms["like_k"])]
            if kind == "reels" and r["watch"]:
                parts.append((0.1, r["watch"] / norms["watch"]))
            r["score"] = sum(w * v for w, v in parts) / sum(w for w, _ in parts)

    # daily new followers from the account's follower_count series
    new_fol = {}
    for series in stats.get("account", {}).get("daily", []) or []:
        if series.get("name") == "follower_count":
            for v in series.get("values", []):
                new_fol[(to_tr(v["end_time"]) - dt.timedelta(days=1)).strftime("%Y-%m-%d")] = v.get("value")

    out = [f"# Performans raporu ({now + dt.timedelta(hours=3):%Y-%m-%d})", "",
           f"Sadece sistemin attığı (güncel şablonlu) paylaşımlar; en az {SETTLE_H} saatlik **{len(rows)}** paylaşım "
           f"({sum(r['kind'] == 'gönderi' for r in rows)} gönderi, {sum(r['kind'] == 'reels' for r in rows)} Reels).", "",
           "Nasıl okunur:",
           "- **İçerik** = paylaşımın kendi gününün diğer paylaşımlarına göre başarısı (1,00 = o günün tipik paylaşımı). "
           "Gün etkisini (hareketli/durgun gün, reklam) ayıklar, içeriğin kendi çekiciliğini gösterir.",
           "- **Gün** = o gün atılan her şeyin, yakın tarihteki benzerlerine göre ortalaması. 1,30 = o gün her şey %30 iyi gitti.",
           "- **/1000** = 1000 kişiye ulaşınca gelen paylaşım, kaydetme, beğeni, takip.",
           "- **Skor** = içerik + paylaşım + kaydetme + beğeni (+ Reels'te izlenme süresi) birleşimi, 1,00 = tipik.", ""]

    def verdict(n, score):
        if n < MIN_N:
            return "veri yetersiz — denemeye devam"
        if score >= 1.2:
            return "**güçlü — daha sık kullan**"
        if score <= 0.8:
            return "zayıf — daha seyrek kullan"
        return "ortalama"

    findings = []

    def table(key, title, kinds=("gönderi", "reels")):
        lines = []
        for kind in kinds:
            groups = collections.defaultdict(list)
            for r in rows:
                if r["kind"] == kind and r.get(key) not in ("?", None):
                    groups[r[key]].append(r)
            for val, rs in sorted(groups.items(), key=lambda kv: -med([x["score"] for x in kv[1]])):
                sc = med([x["score"] for x in rs])
                fk = med([x["follow_k"] for x in rs], None)
                wt = med([x["watch"] for x in rs], None) if kind == "reels" else None
                lines.append(f"| {kind} | {val} | {len(rs)} | {sc:.2f} | {med([x['content'] for x in rs]):.2f} | "
                             f"{med([x['share_k'] for x in rs]):.1f} | {med([x['save_k'] for x in rs]):.1f} | "
                             f"{med([x['like_k'] for x in rs]):.1f} | {'-' if fk is None else f'{fk:.1f}'} | "
                             f"{'-' if wt is None else f'{wt:.1f}'} | {verdict(len(rs), sc)} |")
                if len(rs) >= MIN_N and (sc >= 1.2 or sc <= 0.8):
                    findings.append((abs(sc - 1), f"{kind} / {title.lower()}: **{val}** skor {sc:.2f} ({len(rs)} paylaşım) → "
                                     + ("daha sık kullan" if sc >= 1.2 else "daha seyrek kullan")))
        if lines:
            out.extend([f"## {title}", "", "| Tür | Değer | Adet | Skor | İçerik | Paylaşım/1000 | Kaydetme/1000 | "
                        "Beğeni/1000 | Takip/1000 | Ort. izlenme sn | Karar |", "|---|---|---|---|---|---|---|---|---|---|---|",
                        *lines, ""])

    table("group", "Canlı grubu")
    table("hook_style", "Başlık (kanca) tarzı")
    table("weekday", "Haftanın günü")
    table("hour", "Paylaşım saati (Türkiye)")
    table("music", "Reels müziği", kinds=("reels",))
    table("dur_bucket", "Reels süresi", kinds=("reels",))

    # day context: was a strong post strong because of its day?
    day_lines = []
    for d in sorted(by_day, reverse=True)[:14]:
        rs = by_day[d]
        best = max(rs, key=lambda r: r["reach"])
        nf = new_fol.get(d)
        day_lines.append(f"| {d} ({DAYS_TR[rs[0]['t'].weekday()]}) | {len(rs)} | {rs[0]['day_eff']:.2f} | "
                         f"{'-' if nf is None else nf} | {best['name']} ({best['reach']}) |")
        if rs[0]["day_eff"] >= 1.3 and len(rs) >= 2:
            findings.append((0.3, f"{d}: o gün **her şey** yüksek erişim aldı (gün {rs[0]['day_eff']:.2f}). "
                                  f"{best['name']} yüksek erişimini büyük ölçüde günden aldı; içerik dersini bundan çıkarma."))
    if day_lines:
        out.extend(["## Gün etkisi (son 14 gün)", "",
                    "| Gün | Paylaşım | Gün etkisi | Yeni takipçi | En çok erişen |", "|---|---|---|---|---|", *day_lines, ""])

    for kind in ("gönderi", "reels"):
        rs = sorted((r for r in rows if r["kind"] == kind), key=lambda r: -r["score"])
        if not rs:
            continue
        head = ("| Tarih | Gün/saat | Canlı | Başlık | Grup | Kanca | Erişim | İçerik | Gün | Beğeni | Paylaşım | Kaydetme | Takip |"
                + (" İzlenme sn | Süre sn | Müzik |" if kind == "reels" else "") + " Skor |")
        sep = "|" + "---|" * (head.count("|") - 1)
        for label, part in (("En iyi", rs[:5]), ("En zayıf", rs[-5:][::-1])):
            out.extend([f"## {label} 5 {kind}", "", head, sep])
            for r in part:
                watch = f"{r['watch']:.1f}" if r["watch"] else "-"
                extra = f" {watch} | {r['duration'] or '-'} | {r['music'] or '-'} |" if kind == "reels" else ""
                out.append(f"| {r['date']} | {r['weekday']} {r['hour']} | {r['name']} | {r['title'] or '-'} | {r['group']} | "
                           f"{r['hook_style']} | {r['reach']} | {r['content']:.2f} | {r['day_eff']:.2f} | {r['likes']} | "
                           f"{r['shares']} | {r['saves']} | {'-' if r['follows'] is None else r['follows']} |{extra} {r['score']:.2f} |")
            out.append("")
        if len(rs) >= 2:
            top = max(rs, key=lambda r: r["shares"])
            findings.append((0.2, f"En çok paylaşılan {kind}: **{top['name']}** ({top['shares']} paylaşım, "
                                  f"kanca: {top['hook_style']}, başlık: {top['title'] or '-'})"))
            fol_rs = [r for r in rs if r["follows"]]
            if fol_rs:
                topf = max(fol_rs, key=lambda r: r["follows"])
                findings.append((0.2, f"En çok takipçi getiren {kind}: **{topf['name']}** ({topf['follows']} takip)"))

    fol = ROOT / "data" / "followers.csv"
    if fol.exists():
        pts = [(d, int(n)) for d, n in (l.split(",") for l in fol.read_text().split() if "," in l) if n.isdigit()]
        if pts:
            week = [n for d, n in pts if d >= (now - dt.timedelta(days=7)).strftime("%Y-%m-%d")]
            out.extend(["## Takipçi", "", f"Şu an {pts[-1][1]}"
                        + (f"; son 7 günde {week[-1] - week[0]:+d}." if len(week) >= 2 else "."), ""])

    findings.sort(key=lambda f: -f[0])
    head = ["## Öne çıkan bulgular", ""]
    head += [f"- {f}" for _, f in findings[:12]] or ["- Henüz yeterli veri yok; grupları ve kanca tarzlarını dengeli dağıtmaya devam et."]
    head.append("")
    out[10:10] = head   # findings right after the explanation

    (ROOT / "data" / "insights.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"insights for {len(rows)} posts written to data/insights.md")


if __name__ == "__main__":
    main()
