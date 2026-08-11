"""Their expected delivery row, next to ours, in both honest states. $0.

Thin CLI over `app.unilog.ground_truth`, which is the same code the running app
serves at `/api/ground-truth` — so the deck, the endpoint and this script can
never quote different numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.unilog import ground_truth as gt

OUT = Path(__file__).resolve().parent.parent / "docs" / "deck" / "expected_vs_ours.json"


def main() -> int:
    if not gt.available():
        print("No labelled delivery rows found at", gt.EXPECTED_CSV)
        return 2

    result = gt.compare()
    summary, cases = result["summary"], result["cases"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    print("=" * 70)
    print("  EXPECTED vs OURS - Unilog's labelled delivery rows, $0.00")
    print("=" * 70)
    print()
    print(f"  A. formatter given the attribute values : "
          f"{summary['exact_given_attributes']}/{summary['fields_scored']} exact "
          f"({summary['pct_given_attributes']}%)")
    print(f"  B. pipeline from the 6-column input row : "
          f"{summary['exact_from_input_row']}/{summary['fields_scored']} exact "
          f"({summary['pct_from_input_row']}%)")
    print()
    print("  The gap between A and B is not a formatting failure. It is the")
    print("  attribute values themselves, which are not in the input row.")
    print()

    for case in cases[:1]:
        print(f"  {case['mpn']}")
        for field in case["fields"][:4]:
            given = "IDENTICAL" if field["match_given"] else field["given_attributes"][:86]
            frm = ("IDENTICAL" if field["match_from_input"]
                   else (field["from_input_row"][:86] or "(empty)"))
            print()
            print(f"    {field['column']}  ({field['rule']})")
            print(f"      expected  {field['expected'][:86]}")
            print(f"      A (given) {given}")
            print(f"      B (input) {frm}")

    print()
    print(f"  Written to {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
