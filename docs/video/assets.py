"""Build the sample datasheet the video uploads on camera.

The Document segment claims the engine "reads the table straight off the page".
Showing an empty drop zone while saying that is the sort of small gap that
undoes a demo, so the video uploads a real PDF and the viewer watches the values
arrive.

    python docs/video/assets.py

Deliberately a *ruleless* table — columns held apart by whitespace, no borders —
because that is the layout that defeats naive extraction, and the one whose
reader took three attempts to get right (§7.8).
"""
from __future__ import annotations

import sys
from pathlib import Path

OUT = Path(__file__).parent / "assets"
ROWS = [
    ("Bore Diameter", "25 mm"),
    ("Outer Diameter", "52 mm"),
    ("Width", "15 mm"),
    ("Dynamic Load Rating", "14.0 kN"),
    ("Static Load Rating", "7.8 kN"),
    ("Limiting Speed", "16000 rpm"),
    ("Cage Material", "Steel"),
    ("Seal Type", "2RS"),
]


def main() -> int:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    OUT.mkdir(exist_ok=True)
    path = OUT / "SKF_6205-2RS_datasheet.pdf"
    width, height = A4
    c = canvas.Canvas(str(path), pagesize=A4)

    c.setFont("Helvetica-Bold", 17)
    c.drawString(25 * mm, height - 30 * mm, "SKF Deep Groove Ball Bearing")
    c.setFont("Helvetica", 11)
    c.drawString(25 * mm, height - 38 * mm, "Model No: 6205-2RS   |   Single row, both sides sealed")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(25 * mm, height - 55 * mm, "TECHNICAL DATA")
    c.setFont("Courier", 10)
    y = height - 63 * mm
    c.drawString(25 * mm, y, f"{'CHARACTERISTIC':<30} VALUE")
    for key, value in ROWS:
        y -= 6.5 * mm
        c.drawString(25 * mm, y, f"{key:<30} {value}")

    c.setFont("Helvetica-Oblique", 8.5)
    c.drawString(25 * mm, 25 * mm,
                 "Dimensions conform to ISO 15. Issued for the UniHack demonstration.")
    c.showPage()
    c.save()
    print(f"  wrote {path.name} ({path.stat().st_size/1000:.1f} KB, "
          f"{len(ROWS)} specs, ruleless layout)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
