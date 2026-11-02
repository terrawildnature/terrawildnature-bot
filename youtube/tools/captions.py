"""Turkish caption track (SRT) from the narration's word timings, so YouTube can index and translate the speech.

  python captions.py <doc_dir>                 -> <doc_dir>/out/altyazi.srt
  python captions.py <doc_dir> --upload <id>   also uploads it to that video (env YT_* like yt_upload.py)
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from doc_render import timeline  # noqa: E402


def ts(x):
    ms = int(round(x * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(doc):
    _, blocks, _ = timeline(doc)
    cues = []
    for b in blocks:
        for s0, s1, txt in b.get("subs", []):   # same window the burned-in subtitle uses
            cues.append((b["voice"] + s0 - 0.05, b["voice"] + s1 + 0.25, txt))
    return "\n".join(f"{k}\n{ts(a)} --> {ts(min(z, cues[k][0] if k < len(cues) else z))}\n{t}\n"
                     for k, (a, z, t) in enumerate(cues, 1))


def upload(srt_bytes, video_id):
    from yt_upload import access_token, request
    boundary = uuid.uuid4().hex
    meta = {"snippet": {"videoId": video_id, "language": "tr", "name": "Türkçe", "isDraft": False}}
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
            f"--{boundary}\r\nContent-Type: application/x-subrip\r\n\r\n").encode() + srt_bytes + f"\r\n--{boundary}--".encode()
    r = request("https://www.googleapis.com/upload/youtube/v3/captions?part=snippet&uploadType=multipart", access_token(),
                body, headers={"Content-Type": f"multipart/related; boundary={boundary}"})
    return json.load(r)["id"]


def main(doc):
    out = doc / "out"
    out.mkdir(exist_ok=True)
    text = srt(doc)
    (out / "altyazi.srt").write_text(text, encoding="utf-8")
    print(f"{text.count(' --> ')} cues -> {out / 'altyazi.srt'}")
    if "--upload" in sys.argv:
        print("caption", upload(text.encode("utf-8"), sys.argv[sys.argv.index("--upload") + 1]))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
