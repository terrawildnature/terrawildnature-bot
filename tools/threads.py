"""Cross-post to Threads (Threads API). Never fatal: Instagram publishing must not depend on it.

Env: THREADS_TOKEN
  python tools/threads.py --check      verify token
  python tools/threads.py --refresh    print a refreshed long-lived token
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"
AI_LINE = "🤖 Yapay zekâ desteğiyle hazırlanmıştır"


def _call(method, path, **params):
    params["access_token"] = os.environ["THREADS_TOKEN"]
    data = urllib.parse.urlencode(params)
    if method == "GET":
        req = urllib.request.Request(f"{API}/{path}?{data}")
    else:
        req = urllib.request.Request(f"{API}/{path}", data=data.encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Threads API {method} {path}: {e.code} {e.read().decode(errors='replace')[:300]}")


def _wait(cid, minutes=10):
    for _ in range(minutes * 4):
        st = _call("GET", cid, fields="status,error_message")
        if st.get("status") == "FINISHED":
            return
        if st.get("status") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Threads container {cid}: {st}")
        time.sleep(15)
    raise RuntimeError(f"Threads container {cid} not ready")


def adapt_caption(caption):
    """Threads links only one tag per post and caps text at 500 chars: keep #terrawildnature,
    drop the other hashtags, add the AI disclosure line."""
    text = re.sub(r"[ \t]*#(?!terrawildnature\b)\S+", "", caption)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n" + AI_LINE
    return text if len(text) <= 500 else text[:497] + "..."


def post_images(image_urls, caption):
    me = _call("GET", "me", fields="id")["id"]
    kids = [_call("POST", f"{me}/threads", media_type="IMAGE", image_url=u, is_carousel_item="true")["id"]
            for u in image_urls]
    for k in kids:
        _wait(k)
    c = _call("POST", f"{me}/threads", media_type="CAROUSEL", children=",".join(kids), text=adapt_caption(caption))
    _wait(c["id"])
    return _call("POST", f"{me}/threads_publish", creation_id=c["id"])["id"]


def post_video(video_url, caption):
    me = _call("GET", "me", fields="id")["id"]
    c = _call("POST", f"{me}/threads", media_type="VIDEO", video_url=video_url, text=adapt_caption(caption))
    _wait(c["id"], minutes=15)
    return _call("POST", f"{me}/threads_publish", creation_id=c["id"])["id"]


def safe(fn, *args):
    """Run a cross-post; report problems as a workflow warning instead of failing the job."""
    if not os.environ.get("THREADS_TOKEN"):
        print("::warning::THREADS_TOKEN yok, Threads paylaşımı atlandı")
        return None
    try:
        tid = fn(*args)
        print(f"published on Threads: {tid}")
        return tid
    except Exception as e:
        print(f"::warning::Threads paylaşımı başarısız: {e}")
        return None


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        r = urllib.request.urlopen(f"https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token"
                                   f"&access_token={os.environ['THREADS_TOKEN']}", timeout=60)
        print(json.load(r)["access_token"])
    elif "--check" in sys.argv:
        me = _call("GET", "me", fields="id,username")
        print(f"Threads token OK for @{me['username']}")
    else:
        sys.exit(__doc__)
