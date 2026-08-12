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
GAP = 0.40        # breath between segments, seconds

SEGMENTS: list[tuple[str, str]] = [
    ("architecture",
     "This is Product Intelligence. It turns a supplier record, often just a part "
     "number and a brand, into a complete, validated, commerce ready product where "
     "every value carries its evidence. Six input paths all become one shape, and "
     "run the same ten stages. Nothing gets a shortcut."),
    ("bearing",
     "Three fields in. Out comes a full record, and the trace shows all ten stages "
     "with their timings. Bore twenty five millimetres, outer diameter fifty two, "
     "width fifteen. None of that was supplied. I.S.O. fifteen fixes those "
     "dimensions for the designation sixty two oh five. Purple is a published "
     "standard. Grey is an unconfirmed default, flagged, not presented as fact."),
    ("gate",
     "The A.I. is a contributor, never the source of record. Here it proposed a load "
     "rating of fourteen point eight kilonewtons, and a speed of fourteen thousand. "
     "I.S.O. fifteen says fourteen, and sixteen thousand. Both refused, with the "
     "reason printed. It may fill a blank or replace an unbacked default, never "
     "overrule evidence. Bounded this way it beats both the raw model and the "
     "rules engine, and precision on evidence backed values stays at one hundred "
     "percent."),
    ("valve",
     "Sixteen cross field rules catch what no single field check can. A P.V.C. body "
     "rated to one hundred and eighty degrees Celsius. Every number plausible alone, "
     "impossible together. Blocked, in plain English."),
    ("content",
     "The same product is then written five times, to five character limits. This is "
     "the forty character invoice line. It hit the limit by dropping whole facts and "
     "naming which ones, because truncating would have cut the part number in half."),
    ("outputs",
     "That record renders into three target schemas. The customer's own delivery "
     "format, two hundred and fifty two columns in their order. Schema dot org, for "
     "search. And a catalogue sheet where every attribute ships its provenance, "
     "confidence and source, so a downstream system inherits the whole audit "
     "trail, not a summary of it."),
    ("storage",
     "There is no database. The taxonomy, the I.S.O. knowledge base, the unit "
     "tables and the export profiles are versioned JSON in the repository, so "
     "adding a category is a reviewed diff. At runtime it writes a content "
     "addressed cache and any categories it has learned. It runs in one container, "
     "stores no A.P.I. key, and cannot spend money."),
    ("scale",
     "On their own thousand row sample, six hundred and eleven rows a second "
     "ingested, and two hundred and eighty seven products a second enriched on one "
     "core. Under a cent per S.K.U. batched, against the ten minutes a person takes "
     "today."),
    ("close",
     "Measured against their own labelled rows. Fourteen of fourteen fields exact "
     "when the engine has the attribute values. Two of fourteen from a bare "
     "catalogue row. We publish both, because the gap is sourcing, not formatting, "
     "and saying which one you are quoting is the point."),
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
