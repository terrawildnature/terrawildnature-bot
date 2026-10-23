"""Publish the oldest post in queue/ to Instagram as a 2-image carousel.

Env: IG_TOKEN (Instagram User access token, Instagram API with Instagram Login)
     RAW_BASE  (e.g. https://raw.githubusercontent.com/terrawildnature/terrawildnature-bot/main)
Moves the published post folder to posted/ and writes published.json into it.
Exit code 2 when the queue is empty (so the workflow run shows as failed and you get an email).

  python tools/publish.py            publish next post
  python tools/publish.py --check    only verify token and show account
  python tools/publish.py --refresh  refresh the long-lived token, print new token to stdout
  python tools/publish.py --list-posts  write every existing post's date + caption to data/instagram_posts.txt
  python tools/publish.py --reel <dir>  publish <dir>/reel.mp4 as a Reel with <dir>/cover.jpg, move <dir> to posted_reels/
"""
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRAPH = "https://graph.instagram.com"


def call(method, path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode())
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Instagram API error on {method} {path}: {e.code} {e.read().decode(errors='replace')}")


def wait_ready(container_id):
    for _ in range(30):
        st = call("GET", container_id, fields="status_code").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            sys.exit(f"container {container_id} status {st}")
        time.sleep(10)
    sys.exit(f"container {container_id} not ready after 5 minutes")


def publish_reel(me, reel_dir):
    """Upload reel.mp4 straight to Instagram (resumable upload, no public video URL needed),
    with cover.jpg (served from the repo) as the custom cover."""
    reel_dir = Path(reel_dir)
    spec = json.loads((reel_dir / "reel.json").read_text(encoding="utf-8"))
    base = os.environ["RAW_BASE"].rstrip("/")
    cover_url = f"{base}/{reel_dir.relative_to(ROOT).as_posix()}/cover.jpg"
    c = call("POST", f"{me['user_id']}/media", media_type="REELS", upload_type="resumable",
             caption=spec["caption"], cover_url=cover_url,
             share_to_feed="true", is_ai_generated="true")
    video = (reel_dir / "reel.mp4").read_bytes()
    req = urllib.request.Request(c["uri"], data=video, method="POST", headers={
        "Authorization": f"OAuth {os.environ['IG_TOKEN']}", "offset": "0", "file_size": str(len(video))})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            print("upload:", r.read().decode()[:200])
    except urllib.error.HTTPError as e:
        sys.exit(f"video upload failed: {e.code} {e.read().decode(errors='replace')}")
    for _ in range(60):   # video processing can take several minutes
        st = call("GET", c["id"], fields="status_code,status").get("status_code")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            sys.exit(f"reel container {c['id']} status {st}: {call('GET', c['id'], fields='status')}")
        time.sleep(15)
    else:
        sys.exit("reel not processed after 15 minutes")
    pub = call("POST", f"{me['user_id']}/media_publish", creation_id=c["id"])
    print(f"published reel media id {pub['id']}")
    dest = ROOT / "posted_reels" / reel_dir.name
    dest.parent.mkdir(exist_ok=True)
    shutil.move(str(reel_dir), str(dest))
    for f in dest.iterdir():   # keep only the recipe; media lives on Instagram now
        if f.name != "reel.json":
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    (dest / "published.json").write_text(json.dumps(
        {"media_id": pub["id"], "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2))


def next_post():
    posts = sorted(p for p in (ROOT / "queue").iterdir() if (p / "post.json").exists()
                   and (p / "a.jpg").exists() and (p / "b.jpg").exists())
    return posts[0] if posts else None


def main():
    if "--refresh" in sys.argv:
        r = urllib.request.urlopen(f"{GRAPH}/refresh_access_token?grant_type=ig_refresh_token&access_token={os.environ['IG_TOKEN']}", timeout=60)
        print(json.load(r)["access_token"])
        return
    me = call("GET", "me", fields="user_id,username")
    if "--check" in sys.argv:
        print(f"token OK for @{me['username']} (id {me['user_id']})")
        return
    if "--reel" in sys.argv:
        publish_reel(me, sys.argv[sys.argv.index("--reel") + 1])
        return
    if "--stats" in sys.argv:
        acct = call("GET", "me", fields="username,followers_count,follows_count,media_count")
        posts, page = [], call("GET", "me/media", limit="100",
                               fields="id,timestamp,media_type,like_count,comments_count,caption,permalink")
        while True:
            posts += page.get("data", [])
            nxt = page.get("paging", {}).get("next")
            if not nxt:
                break
            with urllib.request.urlopen(nxt, timeout=120) as r:
                page = json.load(r)
        for p in posts:  # insights need instagram_business_manage_insights; skip quietly if missing
            p["caption"] = (p.get("caption") or "")[:120]
            try:
                req = urllib.request.Request(f"{GRAPH}/{p['id']}/insights?metric=reach,views,saved,shares,total_interactions&access_token={os.environ['IG_TOKEN']}")
                with urllib.request.urlopen(req, timeout=60) as r:
                    p["insights"] = {m["name"]: m["values"][0]["value"] for m in json.load(r)["data"]}
            except Exception as e:
                p["insights_error"] = str(e)[:80]
        try:
            req = urllib.request.Request(f"{GRAPH}/me/insights?metric=follower_count,reach&period=day&access_token={os.environ['IG_TOKEN']}")
            with urllib.request.urlopen(req, timeout=60) as r:
                acct["daily"] = json.load(r)["data"]
        except Exception as e:
            acct["daily_error"] = str(e)[:80]
        try:  # followers online per hour (account time zone is UTC in the API: PST/UTC offsets vary)
            req = urllib.request.Request(f"{GRAPH}/me/insights?metric=online_followers&period=lifetime&access_token={os.environ['IG_TOKEN']}")
            with urllib.request.urlopen(req, timeout=60) as r:
                acct["online_followers"] = json.load(r)["data"]
        except Exception as e:
            acct["online_followers_error"] = str(e)[:200]
        (ROOT / "data" / "stats.json").write_text(json.dumps({"account": acct, "posts": posts}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"stats for {len(posts)} posts written to data/stats.json")
        return
    if "--list-posts" in sys.argv:
        lines, page = [], call("GET", "me/media", fields="timestamp,caption,permalink", limit="100")
        while True:
            for m in page.get("data", []):
                cap = (m.get("caption") or "").replace("\n", " ")
                lines.append(f"{m['timestamp'][:10]} | {m['permalink']} | {cap}")
            nxt = page.get("paging", {}).get("next")
            if not nxt:
                break
            with urllib.request.urlopen(nxt, timeout=120) as r:
                page = json.load(r)
        (ROOT / "data" / "instagram_posts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{len(lines)} posts written to data/instagram_posts.txt")
        return

    post_dir = next_post()
    if post_dir is None:
        print("queue is empty — nothing to publish")
        sys.exit(2)
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    base = os.environ["RAW_BASE"].rstrip("/") + f"/queue/{urllib.parse.quote(post_dir.name)}"
    print(f"publishing {post_dir.name} as @{me['username']}")

    children = []
    for name in ("a.jpg", "b.jpg"):
        c = call("POST", f"{me['user_id']}/media", image_url=f"{base}/{name}", is_carousel_item="true")
        children.append(c["id"])
    for c in children:
        wait_ready(c)
    carousel = call("POST", f"{me['user_id']}/media", media_type="CAROUSEL",
                    children=",".join(children), caption=post["caption"], is_ai_generated="true")
    wait_ready(carousel["id"])
    pub = call("POST", f"{me['user_id']}/media_publish", creation_id=carousel["id"])
    print(f"published media id {pub['id']}")

    dest = ROOT / "posted" / post_dir.name
    shutil.move(str(post_dir), str(dest))
    for img in dest.glob("*.jpg"):  # images live on Instagram now; keep the repo small
        img.unlink()
    (dest / "published.json").write_text(json.dumps(
        {"media_id": pub["id"], "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=2))


if __name__ == "__main__":
    main()
