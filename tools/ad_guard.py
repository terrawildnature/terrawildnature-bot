"""Daily guard for the paid follower campaign (Meta Marketing API, token in META_ADS_TOKEN).

Writes data/ad_stats.json (spend, reach, frequency, followers gained above the organic trend) and acts on the
owner's rules: pause the ad set when a follower costs more than MAX_COST_PER_FOLLOWER TL after the learning
spend, warn when the audience is tired (frequency) or the token is about to expire. Every action or warning
opens a GitHub issue so the owner gets an e-mail. The token is never printed.
"""
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://graph.facebook.com/v26.0/"
ACCOUNT = "act_1960605268679679"
ADSET = "120252142480490010"            # campaign "Terra Takipçi Profil (Afiş)": since 23 Nov only Hayvanseverler + Aileler sets, 165 TL/day each
START = dt.date(2026, 11, 19)
MAX_COST_PER_FOLLOWER = 10.0            # TL, owner's limit
LEARNING_SPEND = 1000.0                 # TL spent before the cost rule may pause anything
WINDOW_DAYS = 3                         # cost rule judges the latest days, not the whole run (owner, 23 Nov)
WINDOW_SPEND = 500.0                    # TL the window must hold before it may pause
RESTART = dt.date(2026, 11, 29)         # new poster "Keşfet E" went live 28 Nov night; older days are not judged
MAX_FREQUENCY = 4.0                     # average views per person; above this the video is worn out
TOKEN = os.environ.get("META_ADS_TOKEN", "")


def call(path, method="GET", **params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params)
    url = API + path + ("?" + data if method == "GET" else "")
    req = urllib.request.Request(url, data=None if method == "GET" else data.encode(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def followers():
    rows = {dt.date.fromisoformat(d): int(n) for d, n in csv.reader(open(ROOT / "data" / "followers.csv"))
            if d[:1].isdigit()}
    before = [rows[d] for d in sorted(rows) if START - dt.timedelta(days=14) <= d <= START]
    organic = (before[-1] - before[0]) / max(len(before) - 1, 1)     # followers/day before the ad
    last = max(rows)
    days = (last - START).days
    gained = rows[last] - rows[START]
    return {"start": rows[START], "now": rows[last], "date": last.isoformat(), "organic_per_day": round(organic, 1),
            "gained": gained, "extra_from_ad": round(gained - organic * days),
            "window": {"since": (last - dt.timedelta(days=WINDOW_DAYS)).isoformat(),
                       "gained": rows[last] - rows.get(last - dt.timedelta(days=WINDOW_DAYS), rows[START])}}


def issue(title, body):
    print("::warning::" + title)
    if os.environ.get("GITHUB_ACTIONS"):
        subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], check=False)


def main():
    if not TOKEN:
        sys.exit("META_ADS_TOKEN missing")
    adset = call(ADSET, fields="name,status,effective_status")
    if "error" in adset:
        issue("Reklam bekçisi Meta'ya bağlanamadı", f"Meta hatası: {adset['error'].get('message')}\n\n"
              "Anahtar geçersiz olmuş olabilir; Claude ile konuşurken yenilenir.")
        sys.exit(1)
    ins = (call(f"{ADSET}/insights", date_preset="maximum",
                fields="spend,impressions,reach,frequency,video_thruplay_watched_actions").get("data") or [{}])[0]
    spend = float(ins.get("spend", 0))
    f = followers()
    w = f["window"]
    if dt.date.fromisoformat(w["since"]) < RESTART:
        rows = {dt.date.fromisoformat(d): int(n) for d, n in csv.reader(open(ROOT / "data" / "followers.csv"))
                if d[:1].isdigit()}
        w["since"] = RESTART.isoformat()
        w["gained"] = rows[dt.date.fromisoformat(f["date"])] - rows.get(RESTART, rows[max(rows)])
    until = (dt.date.fromisoformat(f["date"]) - dt.timedelta(days=1)).isoformat()
    wins = (call(f"{ACCOUNT}/insights", fields="spend",
                 time_range=json.dumps({"since": w["since"], "until": until})).get("data") or [{}])[0]
    w["spend"] = float(wins.get("spend", 0))
    cpf = w["spend"] / w["gained"] if w["gained"] > 0 else None     # TL per new follower in the window
    stats = {"checked": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"), "adset_status": adset.get("effective_status"),
             "spend_try": spend, "reach": int(ins.get("reach", 0)), "impressions": int(ins.get("impressions", 0)),
             "frequency": round(float(ins.get("frequency", 0)), 2),
             "thruplays": sum(int(a["value"]) for a in ins.get("video_thruplay_watched_actions") or []),
             "followers": f, "cost_per_extra_follower": round(cpf, 2) if cpf else None}
    (ROOT / "data" / "ad_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False))

    summary = (f"Harcama: {spend:.0f} TL · erişim {stats['reach']} · sıklık {stats['frequency']}\n"
               f"Takipçi: {f['start']} → {f['now']} (reklamsız beklenen artışın üstünde +{f['extra_from_ad']})\n"
               f"Son {WINDOW_DAYS} gün: {w['spend']:.0f} TL, +{w['gained']} takipçi → takipçi başı {stats['cost_per_extra_follower'] or '—'} TL")
    if adset.get("effective_status") == "ACTIVE":
        if spend >= LEARNING_SPEND and w["spend"] >= WINDOW_SPEND and (cpf is None or cpf > MAX_COST_PER_FOLLOWER):
            r = call(ADSET, method="POST", status="PAUSED")
            issue("Reklam durduruldu: takipçi başı maliyet 10 TL'yi aştı",
                  f"{summary}\n\nSınır {MAX_COST_PER_FOLLOWER:.0f} TL. Meta yanıtı: {r}\n"
                  "Claude ile konuşunca yeni video/ayarla yeniden başlatılabilir.")
        elif stats["frequency"] > MAX_FREQUENCY:
            issue("Reklam videosu yoruldu (aynı kişiler çok tekrar görüyor)",
                  f"{summary}\n\nYeni bir tanıtım videosu gerekiyor; Claude ile konuşunca hazırlanır.")
    token = call("debug_token", input_token=TOKEN).get("data", {})
    left = (token.get("expires_at") or 0) - dt.datetime.now().timestamp()
    if token.get("expires_at") and left < 10 * 86400:
        issue("Reklam anahtarının süresi doluyor", f"{left / 86400:.0f} gün kaldı. Claude ile konuşunca yenilenir.")


if __name__ == "__main__":
    main()
