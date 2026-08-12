"""Generate the narration and report how long each segment actually takes.

Uses the Windows speech engine, which is free and local. It is plainly
synthetic, and a human read of the same script will be better — but it makes
the sync exact, because every segment's real duration is measured here and fed
back into record.py's marks rather than estimated from a word count.

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
VOICE = "Microsoft David Desktop"
RATE = 0          # SAPI scale, -10..10. 0 is roughly 160 wpm.
GAP = 0.45        # breath between segments, seconds

SEGMENTS: list[tuple[str, str]] = [
    ("open", "In industrial commerce, a wrong specification ships a broken machine. "
             "So this engine is built to do something unusual. It would rather leave "
             "a field empty than state something it cannot defend."),
    ("bearing", "Three fields in. A part number, a brand, a name. Out comes a full "
                "record. Bore twenty five millimetres, outer diameter fifty two, "
                "width fifteen. None of that was supplied. I.S.O. fifteen fixes those "
                "dimensions for the designation sixty two oh five. The purple badge "
                "means a published standard. The grey ones "
                "are category defaults, flagged as unconfirmed, not presented as fact."),
    ("gate", "Now the A.I. engine. It proposed a load rating of fourteen point eight "
             "kilonewtons, and a speed of fourteen thousand r.p.m. I.S.O. fifteen says "
             "fourteen, and sixteen thousand. Both refused, and the reason is printed. "
             "The model may fill a blank, or replace an unbacked default. It may never "
             "overrule evidence. Bounded this way it beats both the raw model and the "
             "rules engine, and precision on evidence backed values stays at exactly "
             "one hundred percent."),
    ("valve", "Sixteen cross field rules catch what no single field check can. A "
              "P.V.C. body rated to one hundred and eighty degrees Celsius. Every "
              "number plausible alone, impossible together. Blocked, in plain English, "
              "with the reason a buyer can act on."),
    ("content", "The customer needs the same product written five times, to five "
                "character limits. This is the forty character invoice line. It hit "
                "the limit by dropping whole facts, and naming which ones. Cutting at "
                "forty characters would truncate the part number, and an unsearchable "
                "part number is worse than a shorter line."),
    ("discover", "Discovery, from a brand and a part number. It found S.K.F.'s own "
                 "page, fetched it, and refused it. The page renders client side and "
                 "yielded nothing. That refusal is the honest answer. The record below "
                 "still scores ninety four, because the part number itself decodes "
                 "against I.S.O. fifteen. Nothing was invented to fill the gap."),
    ("catalog", "At volume. Ten products, triaged into publish, review, and blocked. "
                "Exports render into the customer's own two hundred and fifty two "
                "column delivery format, or schema dot org. The target schema is "
                "data, so a new one needs no code."),
    ("close", "Against their own labelled rows. Fourteen of fourteen fields exact when "
              "the engine has the attribute values. Two of fourteen from a bare "
              "catalogue row. Both numbers, because the gap is sourcing, and saying so "
              "is the point."),
]

PS_TEMPLATE = """
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice("{voice}")
$s.Rate = {rate}
$s.SetOutputToWaveFile("{path}")
$s.Speak(@'
{text}
'@)
$s.Dispose()
"""


def synth(text: str, path: Path) -> None:
    script = PS_TEMPLATE.format(voice=VOICE, rate=RATE, path=str(path).replace("\\", "\\\\"),
                                text=text)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   check=True, capture_output=True)


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
