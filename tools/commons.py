"""Wikimedia Commons helper.

  python tools/commons.py search "<query>" [--min-width 1600]
      Lists candidate photos: width x height | license | author | title
  python tools/commons.py download "<File:Title.jpg>" <out.jpg>
      Downloads a 2400px-wide version and prints its license/author as JSON.

Public-domain licenses (no credit required) are marked with [PD].
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "TerraWildNatureBot/1.0 (https://github.com/terrawildnature/terrawildnature-bot; terrawildnature@gmail.com)"
PD_RE = re.compile(r"public domain|^pd|cc0", re.I)
ALLOWED_RE = re.compile(r"public domain|^pd|cc0|^cc by(-sa)? \d", re.I)


def get(params, retries=6):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:  # 429 = slow down; honour Retry-After
            if e.code != 429 or i == retries - 1:
                raise
            time.sleep(min(int(e.headers.get("Retry-After") or 0) or 20 * (i + 1), 90))
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(5 * (i + 1))


def meta(ii):
    em = ii.get("extmetadata", {})
    lic = em.get("LicenseShortName", {}).get("value", "")
    artist = re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", "")).strip()
    return lic, artist


def search(query, min_width=1600):
    data = get({
        "action": "query", "generator": "search", "gsrnamespace": 6, "gsrlimit": 50,
        "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo",
        "iiprop": "url|size|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist",
    })
    rows = []
    for p in data.get("query", {}).get("pages", {}).values():
        ii = p["imageinfo"][0]
        lic, artist = meta(ii)
        if ii["width"] < min_width or not ALLOWED_RE.search(lic):
            continue
        tag = "[PD] " if PD_RE.search(lic) else ""
        rows.append((not PD_RE.search(lic), -ii["width"],
                     f"{tag}{ii['width']}x{ii['height']} | {lic} | {artist[:50]} | {p['title']}"))
    for r in sorted(rows):
        print(r[2])


def fetch(url, out, retries=5):
    """Download with backoff; Wikimedia answers 429 when it wants us to slow down."""
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r, open(out, "wb") as f:
                f.write(r.read())
            return True
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == retries - 1:
                print(f"  {url[:90]}... -> HTTP {e.code}", file=sys.stderr)
                return False
            wait = int(e.headers.get("Retry-After") or 0) or 15 * (i + 1)
            time.sleep(min(wait, 90))
        except Exception as e:
            print(f"  {url[:90]}... -> {e}", file=sys.stderr)
            return False
    return False


def download(title, out):
    if not title.startswith("File:"):
        title = "File:" + title
    # 1920 is one of Wikimedia's standard thumbnail widths; non-standard widths get rate-limited.
    data = get({"action": "query", "titles": title, "prop": "imageinfo",
                "iiprop": "url|size|extmetadata", "iiurlwidth": 1920,
                "iiextmetadatafilter": "LicenseShortName|Artist"})
    page = next(iter(data["query"]["pages"].values()))
    ii = page["imageinfo"][0]
    urls = [u for u in (ii.get("thumburl"), ii["url"]) if u]
    if not any(fetch(u, out) for u in urls):
        sys.exit(f"download failed: {title}")
    lic, artist = meta(ii)
    print(json.dumps({"title": page["title"], "license": lic, "author": artist,
                      "public_domain": bool(PD_RE.search(lic)),
                      "page": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_"))},
                     ensure_ascii=False))
    time.sleep(2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) >= 3 and sys.argv[1] == "search":
        mw = int(sys.argv[sys.argv.index("--min-width") + 1]) if "--min-width" in sys.argv else 1600
        search(sys.argv[2], mw)
    elif len(sys.argv) == 4 and sys.argv[1] == "download":
        download(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
