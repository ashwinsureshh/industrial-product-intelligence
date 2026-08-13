"""Find the segment boundaries in the recording, and lay the narration on them.

    python docs/video/align.py

Why this exists. The recording's own clock cannot be trusted: Playwright writes
the webm at a variable rate but labels it 25 fps, so wall-clock time and the
file's timeline disagree — and the disagreement is *not* uniform. It accumulates
at page navigations, so rescaling by a single factor lines the two ends up and
lets the middle drift, which is exactly what "the voiceover isn't quite synced"
sounds like.

So the picture is asked instead of assumed. record.py flashes a magenta square
in the top-left corner at the start of every segment; this reads those flashes
back out of the finished file and gets the player's own timestamp for each one.
The narration clips are then placed at those timestamps, and sync stops being a
calculation that can be wrong.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "footage"
VIDEO = OUT / "demo_walkthrough.webm"
TRACK = OUT / "narration.wav"
FPS = 25
BEACON_RGB = (255, 0, 255)
TOLERANCE = 60
# The picture should arrive a beat before the line that describes it. Landing a
# sentence on the exact frame the screen changes feels like a jump cut; a short
# lead reads as someone looking at the screen and then speaking.
LEAD = 0.45


def ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in (Path.home() / "AppData/Local/Microsoft/WinGet/Packages").glob(
            "Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
        return str(candidate)
    raise SystemExit("no ffmpeg — winget install Gyan.FFmpeg")


def beacon_times() -> list[float]:
    """Timestamps, in the file's own timeline, where a beacon starts."""
    # One pixel per frame: crop the corner the beacon lives in, average it, and
    # read the raw stream. 25 fps for three minutes is 4,500 pixels — trivial.
    result = subprocess.run(
        [ffmpeg(), "-hide_banner", "-loglevel", "error", "-i", str(VIDEO),
         # the beacon strip: bottom-left, below the delivered frame
         "-vf", "crop=28:12:6:724,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    pixels = result.stdout
    hits: list[int] = []
    for index in range(len(pixels) // 3):
        r, g, b = pixels[index * 3], pixels[index * 3 + 1], pixels[index * 3 + 2]
        if (abs(r - BEACON_RGB[0]) < TOLERANCE and abs(g - BEACON_RGB[1]) < TOLERANCE
                and abs(b - BEACON_RGB[2]) < TOLERANCE):
            hits.append(index)

    starts: list[float] = []
    for frame in hits:
        # Only the leading edge of a flash is a boundary. The window has to be
        # comfortably longer than the flash itself (1 s) and comfortably shorter
        # than the closest two segments (13 s) — at exactly one second it split
        # a single beacon into two.
        if not starts or frame - (starts[-1] * FPS) > FPS * 3:
            starts.append(frame / FPS)
    return starts


def lay(clips: list[Path], starts: list[float], total: float) -> None:
    with wave.open(str(clips[0]), "rb") as first:
        rate, width, channels = (first.getframerate(), first.getsampwidth(),
                                 first.getnchannels())
    canvas = bytearray(int(total * rate) * width * channels)
    for clip, start in zip(clips, starts):
        with wave.open(str(clip), "rb") as handle:
            pcm = handle.readframes(handle.getnframes())
        at = int(start * rate) * width * channels
        if at + len(pcm) > len(canvas):
            canvas.extend(b"\x00" * (at + len(pcm) - len(canvas)))
        canvas[at:at + len(pcm)] = pcm
    with wave.open(str(TRACK), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.setframerate(rate)
        out.writeframes(bytes(canvas))


def main() -> int:
    clips = sorted(OUT.glob("vo_*.wav"), key=lambda p: int(p.name.split("_")[1]))
    if not clips or not VIDEO.exists():
        print("run voiceover.py and record.py first")
        return 1

    found = beacon_times()
    print(f"  {len(found)} beacons found, {len(clips)} narration clips")
    if len(found) != len(clips):
        print("  !! count mismatch — every segment must flash exactly once")
        print(f"     beacons at: {[round(f, 2) for f in found]}")
        return 1

    # A beacon says when the *picture* changed. If the previous line is still
    # being spoken then, the two talk over each other — which is what "it jumps
    # straight to the AI" sounded like at 0:38. The picture is allowed to move
    # early; the voice is not allowed to collide.
    lengths = []
    for clip in clips:
        with wave.open(str(clip), "rb") as handle:
            lengths.append(handle.getnframes() / handle.getframerate())

    placed: list[float] = []
    tight: list[str] = []
    for index, (start, length) in enumerate(zip(found, lengths)):
        wanted = start + (LEAD if index else 0.0)
        earliest = 0.0 if not placed else placed[-1] + lengths[index - 1] + 0.12
        if wanted < earliest - 0.01:
            tight.append(f"{clips[index].stem.split('_', 2)[2]} "
                         f"+{earliest - wanted:.2f}s")
        placed.append(max(wanted, earliest))
    if tight:
        print(f"  shots tighter than their line: {', '.join(tight)}")
    leads = [p - f for p, f in zip(placed, found)]
    print(f"  picture leads the voice by {min(leads):.2f}–{max(leads):.2f}s")
    found = placed

    tail = lengths[-1]
    total = found[-1] + tail + 1.0

    print("  segment  narration starts at (player time)")
    for clip, start in zip(clips, found):
        print(f"    {clip.stem.split('_', 2)[2]:<13} {int(start)//60}:{start % 60:04.1f}")

    lay(clips, found, total)
    (OUT / "aligned.json").write_text(json.dumps(
        {"starts": [round(f, 3) for f in found], "total": round(total, 3)}, indent=1))
    print(f"\n  wrote narration.wav laid on the picture ({total:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
