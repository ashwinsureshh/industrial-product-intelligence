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
RATE = "-4%"                   # a touch under default; this is dense material
GAP = 0.28        # breath between segments, seconds

SEGMENTS: list[tuple[str, str]] = [
    ("architecture",
     "A distributor's catalogue arrives looking like this. A part number, a brand, "
     "and a few words. Somebody then has to turn each one into a product page a "
     "buyer can search and trust. Get it wrong and a plumber fits a valve that "
     "fails. This system does that job automatically. Whatever comes in, a "
     "spreadsheet row, a datasheet, or just a part number, goes through the same "
     "ten steps."),
    ("bearing",
     "Here it is on a real part. We give it three things. A part number, a brand, "
     "a name. It recognises that part number as a standard bearing code, the way an "
     "experienced parts person would, and fills in the dimensions it fixes. Every "
     "value is colour coded by where it came from. Purple is a "
     "published standard. Grey is a sensible guess we have not confirmed, and it "
     "says so rather than pretending."),
    ("gate",
     "We do use A.I., but on a leash. Here it suggested a load rating of fourteen "
     "point eight, and a speed of fourteen thousand. The standard says fourteen, "
     "and sixteen thousand, so both were refused, and the refusal is written down. "
     "It may fill an empty box. It may never overrule a source. That one rule is "
     "why the accuracy holds. Across a hundred and two test products, values backed "
     "by evidence were right every time."),
    ("valve",
     "Some mistakes only appear when you compare fields. A plastic valve rated to "
     "a hundred and eighty degrees. Each number looks fine alone. Together they "
     "describe a product that would melt. Sixteen checks catch it, and it is "
     "stopped with a reason in plain English."),
    ("content",
     "Shops need the same product written several ways. A till receipt line, a "
     "phone listing, a full page. This is the forty character version. It dropped "
     "whole facts to fit and listed which ones, because half a part number is "
     "impossible to search for."),
    ("outputs",
     "What comes out is whatever the customer's system expects. Their own two "
     "hundred and fifty two column sheet, a format search engines understand, or a "
     "spreadsheet where every value carries its source and how sure we are. A new "
     "customer's format is a settings file, not a rewrite."),
    ("storage",
     "There is no database to run or back up. The rule book, categories, standards "
     "and units, is plain text kept with the code, so changing a rule gets "
     "reviewed. Nothing is sent anywhere else, and the public version holds no "
     "A.I. key, so it cannot spend money."),
    ("scale",
     "A person takes ten minutes a product. This handles two hundred and "
     "eighty seven a second on one machine, for under a penny each. And it does not "
     "hand you a pile of work. Every record comes out marked ready to publish, "
     "needs review, or blocked, so a merchandiser only opens what needs a person."),
    ("close",
     "Measured against the customer's own completed rows. Given the facts, fourteen "
     "of fourteen fields exactly right. From a bare catalogue row, two of fourteen, "
     "because the rest are not in that row. We publish both. Knowing what you "
     "cannot answer is what makes a catalogue trustworthy."),
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
