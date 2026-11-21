"""One-off pruning of the poster test (owner's request, 2026-11-21): after midnight keep the KEEP posters that sent
the most people to the Instagram profile and pause the rest. Ties go to the cheaper cost per visit.
Does nothing when KEEP or fewer posters are still running, so a second run is harmless. Opens an issue (e-mail)
with the ranking. The token is never printed.
"""
import json

from ad_guard import ADSET, call, issue, TOKEN
import sys

KEEP = 3
PREFIX = "GPT "            # the ten ChatGPT posters; the old "Afiş ..." ads stay paused


def main():
    if not TOKEN:
        sys.exit("META_ADS_TOKEN missing")
    ads = {a["id"]: a for a in call(f"{ADSET}/ads", fields="name,effective_status", limit=100).get("data", [])
           if a["name"].startswith(PREFIX) and a["effective_status"] == "ACTIVE"}
    if len(ads) <= KEEP:
        print(f"{len(ads)} posters running, nothing to prune")
        return
    rows = []
    for r in call(f"{ADSET}/insights", level="ad", date_preset="maximum", limit=100,
                  fields="ad_id,ad_name,spend,actions").get("data", []):
        if r["ad_id"] not in ads:
            continue
        visits = sum(int(a["value"]) for a in r.get("actions") or [] if a["action_type"] == "link_click")
        spend = float(r.get("spend", 0))
        rows.append({"id": r["ad_id"], "name": r["ad_name"], "visits": visits, "spend": spend,
                     "cpv": spend / visits if visits else float("inf")})
    rows += [{"id": i, "name": a["name"], "visits": 0, "spend": 0.0, "cpv": float("inf")}
             for i, a in ads.items() if i not in {r["id"] for r in rows}]
    rows.sort(key=lambda r: (-r["visits"], r["cpv"]))
    lines = []
    for n, r in enumerate(rows):
        if n >= KEEP:
            res = call(r["id"], method="POST", status="PAUSED")
            r["paused"] = res.get("success", res)
        cpv = f"{r['cpv']:.2f} TL" if r["visits"] else "—"
        lines.append(f"{'✅ devam' if n < KEEP else '⏸ durduruldu'} · {r['name']} · profil ziyareti {r['visits']}"
                     f" · harcama {r['spend']:.0f} TL · ziyaret başı {cpv}")
    print(json.dumps(rows, ensure_ascii=False, default=str))
    issue(f"Reklam: en iyi {KEEP} afiş bırakıldı, diğerleri durduruldu", "\n".join(lines))


if __name__ == "__main__":
    main()
