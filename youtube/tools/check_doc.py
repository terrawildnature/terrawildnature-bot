"""Sanity checks for a documentary before it is committed (run by the weekly routine).

  python check_doc.py <doc_dir>
Prints problems and exits 1 if there are any.
"""
import json
import re
import sys
from pathlib import Path

TYPES = {"intro", "zone", "creature", "landmark", "outro"}


def main(doc):
    errs = []
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    meta = json.loads((doc / "meta.json").read_text(encoding="utf-8"))
    photos = json.loads((doc / "photos.json").read_text(encoding="utf-8"))
    segs = spec["segments"]
    j = spec.get("journey", {})
    mx = j.get("max", 10935)
    if segs[0]["type"] != "intro" or segs[-1]["type"] != "outro":
        errs.append("ilk segment intro, son segment outro olmalı")
    prev = None
    for i, s in enumerate(segs):
        key = f"{i:02d}"
        if s["type"] not in TYPES and not spec.get("mechanic"):
            errs.append(f"{key}: bilinmeyen tür {s['type']}")
        if prev is not None and s["depth"] < prev:
            errs.append(f"{key}: depth geriye gidiyor ({prev} -> {s['depth']})")
        if not 0 <= s["depth"] <= mx:
            errs.append(f"{key}: depth 0..{mx} dışında")
        prev = s["depth"]
        need = {"zone": ["name", "range"], "creature": ["name", "latin", "range"], "landmark": ["name", "value"]}.get(s["type"], [])
        errs += [f"{key}: '{k}' eksik" for k in need if not s.get(k)]
        if s["type"] == "creature" and not photos.get(key):
            errs.append(f"{key} {s['name']}: fotoğraf yok")
        for m in photos.get(key, []):
            if not m["file"].startswith(key + "_"):
                errs.append(f"{key}: dosya adı {m['file']} '{key}_k.jpg' olmalı")
            if not (doc / "photos" / m["file"]).exists():
                errs.append(f"{key}: {m['file']} indirilmemiş (fetch_photos.py çalıştır)")
            for k in ("src", "license", "author", "source"):
                if k not in m:
                    errs.append(f"{key}: {m['file']} '{k}' eksik")
            if any(x in (m.get("license") or "").upper() for x in ("NC", "ND")):
                errs.append(f"{key}: {m['file']} lisansı yasak ({m['license']})")
        if not s.get("text_en"):
            errs.append(f"{key}: 'text_en' (İngilizce altyazı metni) eksik")
        if s.get("name") and not s.get("name_en"):
            errs.append(f"{key}: 'name_en' eksik")
        if any(c in s["text"] for c in "()[]<>/") and s["type"] != "landmark":
            errs.append(f"{key}: metinde parantez/özel işaret var (seslendirme bozulur)")
    chars = sum(len(s["text"]) for s in segs)
    if not 17000 <= chars <= 23000:
        errs.append(f"toplam metin {chars} karakter; 30 dakika için 18.000-21.000 olmalı")
    n_cr = sum(s["type"] == "creature" for s in segs)
    if n_cr < 20:
        errs.append(f"sadece {n_cr} canlı var (en az 20)")
    mech = spec.get("mechanic")   # owner's rule: every documentary has a new mechanic, never reused
    root = Path(__file__).resolve().parents[1]
    used = {m: f for m, f in re.findall(r"^Mekanik:\s*(\S+)\s*\(([^)]*)\)", (root / "published.md").read_text(encoding="utf-8"), re.M)}
    if not mech:
        errs.append("script.json: 'mechanic' eksik (her belgesel yeni bir mekanik kullanmalı, bkz. youtube/mechanics/README.md)")
    elif not (root / "mechanics" / f"{mech}.py").exists():
        errs.append(f"mekanik dosyası yok: youtube/mechanics/{mech}.py")
    elif mech in used and used[mech] != doc.name:
        errs.append(f"'{mech}' mekaniği daha önce kullanıldı ({used[mech]}); yeni bir mekanik seç ya da yaz")
    sys.path.insert(0, str(Path(__file__).parent))   # owner's rule: different music in every video
    from music import check_doc as music_check
    errs += music_check(doc, j.get("music") or [])
    tz = meta.get("teaser") or {}
    if not (isinstance(tz.get("seg"), int) and 0 <= tz["seg"] < len(segs) and segs[tz["seg"]]["type"] == "creature" and tz.get("title")):
        errs.append("meta.json: 'teaser' {seg: <creature segmenti>, title} eksik ya da hatalı (tanıtım Shorts'u)")
    elif len(tz["title"]) > 60:
        errs.append(f"tanıtım başlığı çok uzun ({len(tz['title'])} kr)")
    for k in ("title", "description", "tags", "hashtags", "thumb", "story"):
        if k not in meta:
            errs.append(f"meta.json: '{k}' eksik")
    en = meta.get("en", {})
    if not (en.get("title") and en.get("description")):
        errs.append("meta.json: 'en' {title, description} eksik (İngilizce başlık ve açıklama)")
    elif len(en["title"]) > 70:
        errs.append(f"İngilizce başlık çok uzun ({len(en['title'])} kr)")
    t = meta.get("title", "")
    if len(t) > 70 or "|" in t or "(Belgesel)" in t:
        errs.append(f"başlık kurala uymuyor ({len(t)} kr): kısa, merak uyandıran, '|' ve '(Belgesel)' yok")
    th = meta.get("thumb", {})
    if th and not (doc / "photos" / f"{th.get('photo')}.jpg").exists():
        errs.append(f"kapak fotoğrafı {th.get('photo')}.jpg yok")
    for k in spec.get("intro_photos", []) + spec.get("outro_photos", []):
        if not (doc / "photos" / f"{k}.jpg").exists():
            errs.append(f"intro/outro fotoğrafı {k}.jpg yok")
    print("\n".join(errs) or f"OK: {len(segs)} segment, {n_cr} canlı, {chars} karakter")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
