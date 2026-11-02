"""Narration for a documentary: one mp3 + word timings per segment.

  python tools/voice.py <doc_dir> [--rate +0%]
Writes <doc_dir>/voice/NN.mp3 and NN.json (word boundaries, seconds). Skips segments already done.
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

VOICE = "tr-TR-AhmetNeural"


async def one(text, out, rate, sem):
    async with sem:
        for attempt in range(6):
            try:
                words, audio = [], bytearray()
                com = edge_tts.Communicate(text, VOICE, rate=rate, boundary="WordBoundary")
                async for c in com.stream():
                    if c["type"] == "audio":
                        audio += c["data"]
                    elif c["type"] == "WordBoundary":
                        words.append({"w": c["text"], "t": c["offset"] / 1e7, "d": c["duration"] / 1e7})
                out.with_suffix(".mp3").write_bytes(bytes(audio))
                out.with_suffix(".json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
                return
            except Exception as e:
                print(f"retry {out.name}: {e}", file=sys.stderr)
                await asyncio.sleep(3 * (attempt + 1))
        raise SystemExit(f"TTS failed: {out}")


async def main(doc, rate):
    spec = json.loads((doc / "script.json").read_text(encoding="utf-8"))
    vd = doc / "voice"
    vd.mkdir(exist_ok=True)
    sem = asyncio.Semaphore(4)
    jobs = [one(s["text"], vd / f"{i:02d}", rate, sem) for i, s in enumerate(spec["segments"])
            if not (vd / f"{i:02d}.json").exists()]
    await asyncio.gather(*jobs)


if __name__ == "__main__":
    rate = sys.argv[sys.argv.index("--rate") + 1] if "--rate" in sys.argv else "+0%"
    asyncio.run(main(Path(sys.argv[1]), rate))
