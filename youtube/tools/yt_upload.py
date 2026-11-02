"""Upload a finished documentary to YouTube as a scheduled private video, then set its thumbnail.

  python yt_upload.py <doc_dir> --publish-at 2026-11-07T17:00:00Z
Needs env YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (GitHub secrets). Prints the video id.
Until Google's API audit is approved YouTube locks API uploads to private, so publish-at has no effect yet.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHUNK = 32 * 1024 * 1024


def access_token():
    body = urllib.parse.urlencode({"client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
                                   "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", body, timeout=60))["access_token"]


def request(url, tok, data=None, method="POST", headers=None):
    h = {"Authorization": f"Bearer {tok}", **(headers or {})}
    return urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=h), timeout=600)


def upload(video, body, tok):
    size = video.stat().st_size
    r = request("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                tok, json.dumps(body).encode(), headers={"Content-Type": "application/json; charset=UTF-8",
                                                         "X-Upload-Content-Type": "video/mp4",
                                                         "X-Upload-Content-Length": str(size)})
    session, pos = r.headers["Location"], 0
    with open(video, "rb") as f:
        while True:
            f.seek(pos)
            chunk = f.read(CHUNK)
            end = pos + len(chunk) - 1
            for attempt in range(5):
                try:
                    r = request(session, tok, chunk, "PUT", {"Content-Range": f"bytes {pos}-{end}/{size}"})
                    return json.load(r)          # 200/201: upload complete
                except urllib.error.HTTPError as e:
                    if e.code == 308:            # chunk accepted, continue from the server's offset
                        rng = e.headers.get("Range")
                        pos = int(rng.split("-")[1]) + 1 if rng else 0
                        print(f"  {pos / size:.0%}", flush=True)
                        break
                    if e.code < 500 or attempt == 4:
                        raise SystemExit(f"upload failed: {e.code} {e.read()[:500]}")
                except (urllib.error.URLError, TimeoutError) as e:
                    if attempt == 4:
                        raise
                    print(f"  retry: {e}", flush=True)
                time.sleep(10 * (attempt + 1))


def main(doc):
    out = doc / "out"
    publish_at = sys.argv[sys.argv.index("--publish-at") + 1] if "--publish-at" in sys.argv else None
    tok = access_token()
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}
    if publish_at:
        status["publishAt"] = publish_at
    body = {"snippet": {"title": (out / "baslik.txt").read_text(encoding="utf-8").strip(),
                        "description": (out / "aciklama.txt").read_text(encoding="utf-8"),
                        "tags": json.loads((out / "tags.json").read_text(encoding="utf-8")),
                        "categoryId": "27", "defaultLanguage": "tr", "defaultAudioLanguage": "tr"},
            "status": status}
    vid = upload(out / "belgesel.mp4", body, tok)["id"]
    print(f"video {vid}", flush=True)
    request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}", access_token(),
            (out / "kapak.jpg").read_bytes(), headers={"Content-Type": "image/jpeg"})
    (out / "video_id.txt").write_text(vid, encoding="utf-8")
    print(f"https://youtu.be/{vid}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
