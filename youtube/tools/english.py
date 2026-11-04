"""English for the same video: localized title and description (viewers with English YouTube see them) and an
English caption track. The video and its Turkish audio stay as they are.

Documentaries: meta.json "en": {"title", "description"}; every segment "text_en", zone/creature/landmark "name_en"
(optional "range_en", "value_en"). Shorts: reel.json "en": {"title", "description"}.

  python english.py doc <doc_dir>                  -> out/aciklama_en.txt, out/altyazi_en.srt (needs out/altyazi.srt)
  python english.py doc <doc_dir> --upload <id>    also sets the localization and uploads the English captions
  python english.py short <reel_dir> --upload <id> sets the localization of an uploaded Short
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

LIMIT = 4900


def tr_title(s):
    from doc_render import tr_title as t
    return t(s)


def chapters_en(doc, spec):
    """out/chapters.txt with each label swapped for its English one (same timestamps)."""
    labels = {"Giriş": "Intro"}
    for s in spec["segments"]:
        en = s.get("name_en")
        if not en or not s.get("name"):
            continue
        if s["type"] == "zone":
            labels[f"{tr_title(s['name'])} ({s['range']})"] = f"{en} ({s.get('range_en', s['range'])})"
        elif s["type"] == "landmark":
            labels[f"{s['name']} ({s['value']})"] = f"{en} ({s.get('value_en', s['value'])})"
        else:
            labels[s["name"]] = en
            if s.get("rank") is not None:
                labels[f"#{s['rank']} {s['name']}"] = f"#{s['rank']} {en}"
    src = doc / "out" / "chapters.txt"
    if not src.exists():
        src = doc / "chapters.txt"
    out = []
    for line in src.read_text(encoding="utf-8").strip().splitlines():
        t, label = line.split(" ", 1)
        out.append(f"{t} {labels.get(label, label)}")
    return "\n".join(out)


def doc_description(doc):
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    meta = json.loads((doc / "meta.json").read_text(encoding="utf-8"))
    en = meta["en"]
    tr = (doc / "out" / "aciklama.txt").read_text(encoding="utf-8") if (doc / "out" / "aciklama.txt").exists() \
        else (doc / "aciklama.txt").read_text(encoding="utf-8")
    # photo/music credits are the same in both languages: reuse the Turkish block from the photo header on
    credits = tr[tr.index("📷"):] if "📷" in tr else ""
    credits = re.sub(r"^📷 GÖRSELLER \(kamu malı veya Creative Commons; (.*)\)$",
                     lambda m: f"📷 IMAGES (public domain or Creative Commons; {m.group(1).replace(' ve ', ' and ')})",
                     credits, flags=re.M)
    credits = credits.replace("🤖 Seslendirme ve kurgu yapay zekâ desteğiyle hazırlanmıştır.",
                              "🤖 Narration (Turkish) and editing were made with the help of AI. English subtitles available.")
    for s in spec["segments"]:   # credit lines start with the Turkish creature name
        if s.get("name_en") and s.get("name"):
            credits = credits.replace(f"• {s['name']}:", f"• {s['name_en']}:")
    parts = [en["description"].strip(), "", "⏱️ CHAPTERS", chapters_en(doc, spec), ""]
    if en.get("sources"):
        parts += [f"📚 Sources: {en['sources']}", ""]
    desc = "\n".join(parts) + credits
    if len(desc.encode()) > LIMIT:   # keep the chapters, drop credit lines from the end
        lines = desc.splitlines()
        while len("\n".join(lines).encode()) > LIMIT:
            lines.pop(-3)
        desc = "\n".join(lines)
    return {"title": en["title"][:100], "description": desc.replace("<", "").replace(">", "")}


def parse_srt(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) >= 3 and "-->" in lines[1]:
            a, z = [sum(float(x) * m for x, m in zip(p.replace(",", ".").split(":"), (3600, 60, 1))) for p in lines[1].split(" --> ")]
            cues.append((a, z, " ".join(lines[2:])))
    return cues


def norm(s):
    return re.sub(r"[^\w]", "", s.lower())


def split_en(text, max_len=84):
    """Sentences, long ones cut at commas or spaces so a cue stays readable (two short lines)."""
    out = []
    for sent in re.findall(r"[^.!?]+[.!?]*", text):
        sent = sent.strip()
        while len(sent) > max_len:
            cut = sent.rfind(", ", 0, max_len)
            cut = cut + 1 if cut > max_len // 3 else sent.rfind(" ", 0, max_len)
            out.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if sent:
            out.append(sent)
    return out


def ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def doc_srt(doc):
    """English cues timed by the Turkish ones: each segment's Turkish cues give its time window, and the English
    text is spread over that window by length."""
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    cues = parse_srt((doc / "out" / "altyazi.srt").read_text(encoding="utf-8"))
    k, out = 0, []
    for s in spec["segments"]:
        body = norm(s["text"])
        first = k
        while k < len(cues) and norm(cues[k][2]) and norm(cues[k][2]) in body:
            k += 1
        if k == first:
            continue
        a, z = cues[first][0], cues[k - 1][1]
        pieces = split_en(s.get("text_en", ""))
        total = sum(len(p) for p in pieces) or 1
        t = a
        for p in pieces:
            d = (z - a) * len(p) / total
            out.append((t, t + d - 0.05, p))
            t += d
    if k < len(cues) * 0.9:
        raise SystemExit(f"English captions: matched only {k} of {len(cues)} Turkish cues")
    return "\n".join(f"{i}\n{ts(a)} --> {ts(z)}\n{p}\n" for i, (a, z, p) in enumerate(out, 1))


def localize(video_id, loc):
    """Add the English title/description to an uploaded video (Turkish stays the default)."""
    from yt_upload import access_token, request
    tok = access_token()
    v = json.load(request(f"https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations&id={video_id}", tok,
                          method="GET"))["items"][0]
    sn = {k: v["snippet"][k] for k in ("title", "description", "categoryId", "tags") if k in v["snippet"]}
    sn["defaultLanguage"] = "tr"
    body = {"id": video_id, "snippet": sn, "localizations": {**v.get("localizations", {}), "en": loc}}
    request("https://www.googleapis.com/youtube/v3/videos?part=snippet,localizations", tok, json.dumps(body).encode(),
            method="PUT", headers={"Content-Type": "application/json; charset=UTF-8"})
    print(f"English title/description set for {video_id}")


def short_localization(spec):
    en = spec.get("en")
    if not en:
        return None
    t = re.sub(r"\s+", " ", en["title"]).strip()
    return {"title": t[:88] + " #shorts",
            "description": (f"{en['description'].strip()}\n\n"
                            "New wildlife documentaries every Wednesday and Saturday: https://www.youtube.com/@terrawildnature-tr\n"
                            "Instagram: https://www.instagram.com/terrawildnature\n\n"
                            "Narration (Turkish) made with AI; facts from Wikipedia and scientific sources.\n\n"
                            "#shorts #animals #wildlife #terrawildnature")}


def main():
    kind, d = sys.argv[1], Path(sys.argv[2]).resolve()
    vid = sys.argv[sys.argv.index("--upload") + 1] if "--upload" in sys.argv else None
    if kind == "short":
        loc = short_localization(json.loads((d / "reel.json").read_text(encoding="utf-8")))
        if loc and vid:
            localize(vid, loc)
        return
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    if "en" not in meta:
        print("no English in meta.json, skipped")
        return
    loc = doc_description(d)
    (d / "out").mkdir(exist_ok=True)
    (d / "out" / "aciklama_en.txt").write_text(loc["description"], encoding="utf-8")
    srt = doc_srt(d)
    (d / "out" / "altyazi_en.srt").write_text(srt, encoding="utf-8")
    print(f"English: title {len(loc['title'])} chars, description {len(loc['description'].encode())} bytes, "
          f"{srt.count(' --> ')} cues")
    if vid:
        localize(vid, loc)
        from captions import upload
        print("caption", upload(srt.encode("utf-8"), vid, "en", "English"))


if __name__ == "__main__":
    main()
