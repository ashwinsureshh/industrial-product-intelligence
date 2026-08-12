"""Combine the silent capture and the narration into one MP4.

    python docs/video/mux.py

Needs a full ffmpeg — the one Playwright bundles is video-only and cannot read
a WAV. Install once with:  winget install Gyan.FFmpeg

The audio is loudness-normalised to the -16 LUFS broadcast/streaming target
because the Windows speech engine outputs quiet mono; without it the narration
sits well under what a viewer expects and they reach for the volume.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "footage"
VIDEO = OUT / "demo_walkthrough.webm"
AUDIO = OUT / "narration.wav"
TARGET = OUT / "demo_walkthrough.mp4"


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    # winget installs to a versioned package directory and only edits PATH for
    # new shells, so this session will not see it yet.
    packages = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    for candidate in packages.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
        return str(candidate)
    return None


def duration(ffmpeg: str, path: Path) -> float:
    import re
    out = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", out)
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def main() -> int:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print("No full ffmpeg found. Install it with:  winget install Gyan.FFmpeg")
        return 1
    for path in (VIDEO, AUDIO):
        if not path.exists():
            print(f"missing {path.name} — run record.py and voiceover.py first")
            return 1

    # Playwright starts recording when the context is created, so the file
    # opens with however long the browser took to show the first frame. The
    # narration starts at zero, so that lead-in has to come off the front or
    # every line lands early over a blank screen.
    lead_in, span = 0.0, None
    marker = OUT / "lead_in.json"
    if marker.exists():
        data = json.loads(marker.read_text())
        lead_in = float(data.get("lead_in", 0.0))
        span = data.get("span")

    raw = duration(ffmpeg, VIDEO) - lead_in
    # Playwright labels a variable-rate recording as 25 fps, so the file can
    # claim several percent more than actually elapsed. Rescale onto the real
    # span or the narration drifts steadily later against the picture.
    rate = (span / raw) if span else 1.0
    length = raw * rate
    fade = max(length - 0.8, 0)
    print(f"  video {raw:.2f}s -> {length:.2f}s (x{rate:.4f}), "
          f"lead-in {lead_in:.2f}s, audio {duration(ffmpeg, AUDIO):.2f}s")

    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{lead_in:.3f}", "-i", str(VIDEO), "-i", str(AUDIO),
        "-map", "0:v:0", "-map", "1:a:0",
        # A short fade at each end. Cutting hard from black to a dense UI, and
        # out again mid-frame, is the last thing that reads as unfinished.
        "-vf", f"setpts=PTS*{rate:.6f},fade=t=in:st=0:d=0.5,"
               f"fade=t=out:st={fade:.2f}:d=0.8",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st="
               f"{fade:.2f}:d=0.8",
        "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        # End on the picture. The narration track is padded past its last word
        # so the assembler can splice into it; without this the file runs on for
        # a couple of silent seconds after the final frame.
        "-shortest",
        # Puts the index at the front so it plays before it has fully loaded.
        "-movflags", "+faststart",
        str(TARGET),
    ]
    print("  encoding…")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        print(result.stderr[-1500:])
        return result.returncode

    print(f"  wrote {TARGET.name}  "
          f"({TARGET.stat().st_size/1_000_000:.1f} MB, {duration(ffmpeg, TARGET):.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
