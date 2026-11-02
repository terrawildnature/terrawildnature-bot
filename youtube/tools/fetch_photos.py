"""Download the photos listed in <doc_dir>/photos.json into <doc_dir>/photos/.

  python fetch_photos.py <doc_dir>
Each entry: {"file": "07_0.jpg", "src": "File:..." | "https://...", "source", "license", "author"}.
Files already present are skipped, so a re-run only fetches what failed.
"""
import contextlib
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import commons  # noqa: E402

MAX_W = 2400


def main(doc):
    photos = json.loads((doc / "photos.json").read_text(encoding="utf-8"))
    out = doc / "photos"
    out.mkdir(exist_ok=True)
    failed = []
    for key, metas in sorted(photos.items()):
        for m in metas:
            p = out / m["file"]
            if p.exists():
                continue
            for attempt in range(3):
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        commons.download(m["src"], str(p))
                    im = Image.open(p).convert("RGB")
                    if im.width > MAX_W:
                        im = im.resize((MAX_W, int(im.height * MAX_W / im.width)), Image.LANCZOS)
                    im.save(p, quality=92)
                    break
                except BaseException as e:   # commons.download exits on failure
                    p.unlink(missing_ok=True)
                    print(f"  retry {m['file']}: {e}", file=sys.stderr)
                    time.sleep(20 * (attempt + 1))
            else:
                failed.append(m["file"])
            print(f"{m['file']} {'ok' if p.exists() else 'FAILED'}", flush=True)
    if failed:
        raise SystemExit(f"failed: {failed}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
