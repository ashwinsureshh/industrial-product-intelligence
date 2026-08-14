"""Generate the narration and report how long each segment actually takes.

Uses edge-tts — Microsoft's neural voices, free and without an account
(pip install edge-tts). A human read of the same script will still be better,
but the sync is exact either way, because every segment's real duration is
measured here and fed back into record.py's marks rather than estimated from a
word count.

    python docs/video/voiceover.py

Writes footage/vo_<n>.wav and footage/timing.json.

The text below is the script's narration respelled for a speech engine. Do not
"tidy" the spellings back: 6205 is a bearing designation an engineer reads as
"sixty-two oh five", and every normaliser tested renders it "six thousand two
hundred five", which is the wrong number said confidently — the exact failure
this project is about.
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

OUT = Path(__file__).parent / "footage"
VOICE = "en-US-AndrewNeural"   # "warm, confident, authentic" — fits the pitch
RATE = "+6%"                   # measured pace; the content is what sets the length
GAP = 0.16        # breath between segments, seconds

SEGMENTS: list[tuple[str, str]] = [
    ("architecture",
     "Here is the problem. A distributor gets a part number, a brand, and if they "
     "are lucky, four words. Someone has to turn that into a page a buyer can "
     "trust. Get it wrong, and a plumber fits a valve that melts. However it "
     "arrives, it takes the same ten steps."),
    ("bearing",
     "Using it is three steps. Pick how your data comes in, paste what you have, "
     "press enrich. A part number, a brand, a name. Watch. It read "
     "that part number as a standard bearing code, the way a parts specialist "
     "would, and filled in the dimensions it fixes. And the colours matter. Purple "
     "means a published standard says so. Grey means we are guessing, and we say "
     "so rather than quietly pretending."),
    ("gate",
     "We do use A.I., but on a short leash. It suggested a load rating of "
     "fourteen point eight, and a speed of fourteen thousand. The standard says "
     "fourteen, and sixteen thousand. Both refused, in writing. It can fill an "
     "empty box. It does not get to argue with a published standard. That is why "
     "the accuracy holds. Across a hundred and two test products, evidence-backed "
     "values were right every single time."),
    ("catalog",
     "Now a whole spreadsheet. Ten in, and they come back "
     "sorted. Eight ready to publish, one to check, one stopped."),
    ("document",
     "Only have the P.D.F.? Drop it in. No borders on that table, just columns held "
     "apart by spaces, the layout that usually defeats this. Read straight off it."),
    ("discover",
     "Brand and part number only? It goes to the manufacturer's own site. And here "
     "is the good bit. It fetched S.K.F.'s page, found nothing usable, and refused "
     "it, without guessing why. We checked with a real browser afterwards. The "
     "address is wrong, not the page. It still scores ninety four, from the part "
     "number."),
    ("learning",
     "And when something fits no category at all, it works one out and queues it "
     "for a human. It does not invent a shelf and start stacking things on it."),
    ("valve",
     "Some mistakes only show up when you compare fields. Plastic valve, rated to a "
     "hundred and eighty degrees. Each number is fine on its own. Together, that is "
     "not a valve, it is a candle. Sixteen checks catch it."),
    ("content",
     "Shops need the same product written several ways. Here is the forty character "
     "one. It dropped whole facts to fit and told you which, because half a part "
     "number is no use to anybody."),
    ("outputs",
     "Out the other end, whatever the customer's system expects. Their own two "
     "hundred and fifty two column sheet, a format search engines read, or a sheet "
     "where every value carries its source."),
    # "There is no database" invites the obvious objection. The answer is that the
    # customer already has one, so say that instead. The old line also claimed
    # "nothing is sent anywhere else", which is untrue on the live path — the
    # product goes to the model — and the frame carries the rule-book detail this
    # drops. 34 words against a 12.86s shot; the budget is 35.
    ("storage",
     "There is no product database: the customer already has one, and theirs stays "
     "the system of record. This takes a row and hands back an enriched row. The "
     "public copy holds no A.I. key."),
    ("scale",
     "A person takes ten minutes a product. This does two hundred and eighty "
     "seven a second, for less than a penny each."),
    ("close",
     "Last thing, and it is the honest one. Against the customer's own finished "
     "rows, given the facts, fourteen out of fourteen. From a bare catalogue row, "
     "two. We publish both, because knowing what you cannot answer is what makes "
     "a catalogue worth trusting."),
    ("thanks",
     "The prototype is live at that link, no login needed, and the code is public, "
     "so every number you have seen can be checked. Thanks for watching."),
]

def _ffmpeg() -> str:
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found
    packages = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for candidate in packages.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
        return str(candidate)
    raise SystemExit("no ffmpeg — winget install Gyan.FFmpeg")


def synth(text: str, path: Path) -> None:
    """Speak one segment, and land it as PCM the assembler can splice."""
    mp3 = path.with_suffix(".mp3")
    subprocess.run([sys.executable, "-m", "edge_tts", "--voice", VOICE,
                    # One argument, not two: a bare "-4%" is read as an option.
                    f"--rate={RATE}", "--text", text, "--write-media", str(mp3)],
                   check=True, capture_output=True)
    subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(mp3), "-ar", "24000", "-ac", "1", str(path)],
                   check=True, capture_output=True)
    mp3.unlink(missing_ok=True)


def duration(path: Path) -> float:
    """Read it out of the header.

    Deliberately not ffmpeg: the only ffmpeg here is the one Playwright ships
    for webm recording, and it is video-only — no WAV demuxer, no audio
    encoders. The standard library reads a RIFF header perfectly well.
    """
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def assemble(paths: list[Path], starts: list[float], target: Path,
             total: float) -> None:
    """Lay every clip onto one silent track at its own offset.

    This is what makes the sync exact and editor-agnostic: the result is a
    single full-length track that starts at zero, so it lines up with the video
    by being dropped next to it, with nothing to nudge.
    """
    with wave.open(str(paths[0]), "rb") as first:
        params = first.getparams()
    frame_rate, width, channels = params.framerate, params.sampwidth, params.nchannels

    canvas = bytearray(int(total * frame_rate) * width * channels)
    for path, start in zip(paths, starts):
        with wave.open(str(path), "rb") as clip:
            pcm = clip.readframes(clip.getnframes())
        at = int(start * frame_rate) * width * channels
        if at + len(pcm) > len(canvas):
            canvas.extend(b"\x00" * (at + len(pcm) - len(canvas)))
        canvas[at:at + len(pcm)] = pcm

    with wave.open(str(target), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(frame_rate)
        out.writeframes(bytes(canvas))


def mark(seconds: float) -> str:
    return f"{int(seconds) // 60}:{seconds - 60 * (int(seconds) // 60):04.1f}"


def main() -> int:
    OUT.mkdir(exist_ok=True)

    timeline, paths, starts, cursor = [], [], [], 0.0
    for index, (name, text) in enumerate(SEGMENTS, start=1):
        path = OUT / f"vo_{index}_{name}.wav"
        synth(text, path)
        spoken = duration(path)
        timeline.append({"index": index, "name": name, "file": path.name,
                         "start": round(cursor, 2), "duration": round(spoken, 2),
                         "start_mark": mark(cursor), "words": len(text.split())})
        paths.append(path)
        starts.append(cursor)
        print(f"  {index}. {name:<9} {spoken:6.2f}s  starts {mark(cursor)}  "
              f"ends {mark(cursor + spoken)}")
        cursor += spoken + GAP

    total = cursor - GAP
    print(f"\n  narration runs {mark(total)} ({total:.1f}s)")
    if total > 180:
        print(f"  !! over three minutes by {total - 180:.1f}s — cut the script, "
              f"not the pauses")

    track = OUT / "narration.wav"
    assemble(paths, starts, track, max(total + 2.0, 182.0))
    print(f"  wrote {track.name} ({track.stat().st_size/1_000_000:.1f} MB)")

    (OUT / "timing.json").write_text(json.dumps(
        {"gap": GAP, "total": round(total, 2), "segments": timeline}, indent=1))
    print(f"  wrote timing.json — feed start_mark into record.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
