"""Title, description (chapters + credits) and tags for the YouTube upload.

  python meta.py <doc_dir>     (after `doc_render.py --info`, which writes out/chapters.txt)
Writes out/baslik.txt, out/aciklama.txt, out/tags.json. The description stays under YouTube's 5000-byte limit.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from doc_render import ASSETS, OCEAN  # noqa: E402

LIMIT = 4900   # bytes; YouTube rejects > 5000
PD_RE = re.compile(r"public domain|^pd|kamu malı|no restrictions", re.I)


def clean_author(a, source):
    a = html.unescape(re.sub(r"<[^>]+>", "", a or ""))
    a = re.sub(r"\(talk[^)]*\)|\bcontribs\b|No machine-readable author provided\.?.*|\bnull\b|https?://\S+", "", a, flags=re.I)
    a = re.sub(r"\s+", " ", a).strip(" ,;·-/")
    if not a or a.lower().startswith(("unknown", "bilinmeyen", "anonymous")):
        return source
    if len(a) > 60:   # cut at a word boundary, never mid-word
        a = a[:60].rsplit(" ", 1)[0].rstrip(" ,;(")
    return a


def license_name(lic):
    return "Kamu malı" if PD_RE.search(lic or "") else (lic or "").strip()


def music_credit(tracks):
    lic = {}
    for line in (ASSETS / "music" / "CREDITS.txt").read_text(encoding="utf-8").splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] in tracks:
            lic[p[0]] = " ".join(p[1:4])        # e.g. "CC BY 3.0"
    names = ", ".join(f'"{Path(t).stem.replace("_", " ")}"' for t in tracks)
    lics = sorted(set(lic.values())) or ["CC BY"]
    return f"🎵 {names} – Kevin MacLeod (incompetech.com), {' / '.join(lics)}"


def credits(spec, photos, compact=False):
    rows = []
    for key in sorted(photos, key=int):
        seg = spec["segments"][int(key)]
        if "name" not in seg:
            continue
        seen, parts = set(), []
        for m in photos[key]:
            who = clean_author(m.get("author"), m.get("source", "Wikimedia Commons"))
            item = f"{who} ({license_name(m.get('license'))})"
            if item not in seen:
                seen.add(item)
                parts.append(item)
        if compact:
            parts = parts[:1]
        rows.append(f"• {seg['name']}: {'; '.join(parts)}")
    return rows


def main(doc):
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    meta = json.loads((doc / "meta.json").read_text(encoding="utf-8"))
    photos = json.loads((doc / "photos.json").read_text(encoding="utf-8"))
    j = {**OCEAN, **spec.get("journey", {})}
    chapters = (doc / "out" / "chapters.txt").read_text(encoding="utf-8").strip()
    title = meta["title"].replace("<", "").replace(">", "")[:100]
    sources = {m.get("source", "Wikimedia Commons") for ms in photos.values() for m in ms}

    def build(compact):
        parts = [meta["description"].strip(), "", "⏱️ BÖLÜMLER", chapters, ""]
        if meta.get("sources"):
            parts += [f"📚 Bilgiler: {meta['sources']}", ""]
        parts += [f"📷 GÖRSELLER (kamu malı veya Creative Commons; {' ve '.join(sorted(sources))})"]
        parts += credits(spec, photos, compact) + [""]
        parts += [music_credit(j["music"]), "", "🤖 Seslendirme ve kurgu yapay zekâ desteğiyle hazırlanmıştır.", ""]
        parts += [" ".join(meta.get("hashtags", ["#belgesel", "#hayvanlar", "#terrawildnature"]))]
        return "\n".join(parts).replace("<", "").replace(">", "")

    desc = build(False)
    if len(desc.encode()) > LIMIT:
        desc = build(True)
    if len(desc.encode()) > LIMIT:
        raise SystemExit(f"description too long: {len(desc.encode())} bytes")
    tags, total = [], 0
    for t in meta.get("tags", []):   # YouTube: 500 characters for all tags
        if total + len(t) + 2 > 480:
            break
        tags.append(t)
        total += len(t) + 2
    out = doc / "out"
    (out / "baslik.txt").write_text(title, encoding="utf-8")
    (out / "aciklama.txt").write_text(desc, encoding="utf-8")
    (out / "tags.json").write_text(json.dumps(tags, ensure_ascii=False), encoding="utf-8")
    print(f"title {len(title)} chars, description {len(desc.encode())} bytes, {len(tags)} tags")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
