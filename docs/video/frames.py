"""Build the explainer frames the product itself cannot show.

A screen recording proves the thing works. It does not say what was built,
where the data lives, or what comes out — and those are what a judge is scoring.
These frames fill exactly that gap and nothing else; every claim on them is a
number measured elsewhere in the repo, and the output preview is fetched live
from the deployed service so the bytes on screen are real.

    python docs/video/frames.py

Writes footage/frames/*.html, which record.py navigates to between product shots.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "footage" / "frames"
BASE = "https://industrial-product-intelligence.onrender.com"

SHELL = """<!doctype html><html><head><meta charset="utf-8"><style>
:root {{
  --bg:#f6f8fb; --surface:#fff; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
  --navy:#1e3a8a; --blue:#2563eb; --ok:#059669; --amber:#b45309; --violet:#6d28d9;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; width:1280px; height:720px; background:var(--bg); color:var(--ink);
  font:15px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif;
  padding:40px 56px; overflow:hidden;
  display:flex; flex-direction:column; justify-content:center; }}
h1 {{ font-size:31px; margin:0 0 6px; color:var(--navy); letter-spacing:-.4px; }}
.sub {{ color:var(--muted); font-size:15.5px; margin:0 0 26px; }}
.row {{ display:flex; gap:14px; align-items:stretch; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:15px 17px; box-shadow:0 1px 3px rgba(15,23,42,.05);
  /* A flex item defaults to min-width:auto, so a white-space:pre block inside
     one pushes the whole row wider than the frame. Same trap as the nav tabs. */
  min-width:0; }}
.k {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); font-weight:700; margin-bottom:9px; }}
.big {{ font-size:26px; font-weight:700; color:var(--navy); line-height:1.15; }}
.lab {{ font-size:12.5px; color:var(--muted); margin-top:3px; }}
.chip {{ display:inline-block; padding:5px 11px; border-radius:999px; font-size:12.5px;
  background:#eef2ff; color:var(--navy); border:1px solid #dbe2f8; margin:0 5px 6px 0; }}
.chip.out {{ background:#ecfdf5; color:#065f46; border-color:#c7ecdc; }}
.chip.gate {{ background:#fef3c7; color:var(--amber); border-color:#f5e0a3; }}
li {{ margin-bottom:7px; }} ul {{ margin:0; padding-left:19px; }}
code {{ font:12.5px ui-monospace,Consolas,monospace; background:#f1f5f9;
  padding:1px 5px; border-radius:4px; color:#334155; }}
.mono {{ font:11px/1.5 ui-monospace,Consolas,monospace; color:#334155;
  white-space:pre; overflow:hidden; }}
.arrow {{ align-self:center; color:var(--muted); font-size:21px; }}
</style></head><body>{body}</body></html>"""


def write(name: str, body: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.html").write_text(SHELL.format(body=body), encoding="utf-8")
    print(f"  {name}.html")


def architecture() -> None:
    stages = ["normalise", "classify", "extract", "infer + AI gate", "reconcile",
              "vocabulary", "content", "compliance", "validate", "score"]
    write("1_architecture", f"""
<h1>However it arrives, one process</h1>
<p class="sub">A fact read off page 2 of a datasheet is checked exactly as hard
as one typed in by hand. Nothing takes a shortcut.</p>
<div class="row">
  <div class="card" style="width:250px">
    <div class="k">Inputs</div>
    {''.join(f'<span class="chip">{i}</span>' for i in
             ["form entry", "catalogue row", "CSV batch", "datasheet PDF",
              "product page", "brand + part number"])}
  </div>
  <div class="arrow">&rarr;</div>
  <div class="card" style="width:150px;display:flex;flex-direction:column;justify-content:center;text-align:center;background:var(--navy);color:#fff;border-color:var(--navy)">
    <div style="font-size:16px;font-weight:700">One common<br>record</div>
  </div>
  <div class="arrow">&rarr;</div>
  <div class="card" style="flex:1">
    <div class="k">The same ten checks, every time</div>
    {''.join(f'<span class="chip{" gate" if "gate" in s else ""}">{s}</span>'
             for s in stages)}
  </div>
</div>
<div class="row" style="margin-top:16px">
  <div class="card" style="flex:1">
    <div class="k">Out</div>
    {''.join(f'<span class="chip out">{o}</span>' for o in
             ["Unilog 252-column delivery", "schema.org JSON-LD",
              "catalogue CSV with provenance", "refusal ledger"])}
  </div>
  <div class="card" style="width:430px">
    <div class="k">The rule everything turns on</div>
    <div style="font-size:14.5px;line-height:1.55">A wrong specification ships a
    broken machine. So a value is published only with evidence behind it —
    otherwise the field stays empty and the record says why.</div>
  </div>
</div>""")


def outputs(sample: str, jsonld: str, columns: int) -> None:
    write("2_outputs", f"""
<h1>What comes out</h1>
<p class="sub">Three target schemas from the same record. The output schema is
data, not code — a new customer format is a JSON profile, not a release.</p>
<div class="row">
  <div class="card" style="flex:1.35">
    <div class="k">Unilog delivery format &middot; {columns} columns, their order</div>
    <div class="mono">{sample}</div>
  </div>
  <div class="card" style="flex:1">
    <div class="k">schema.org Product (JSON-LD)</div>
    <div class="mono">{jsonld}</div>
  </div>
</div>
<div class="row" style="margin-top:16px">
  <div class="card" style="flex:1">
    <div class="k">Catalogue CSV &mdash; every attribute ships its audit trail</div>
    <div class="mono">bore_diameter, bore_diameter.provenance, bore_diameter.confidence, bore_diameter.source
25 mm,          knowledge_base,             0.93,                      ISO 15:2017</div>
    <div class="lab" style="margin-top:9px">A downstream PIM inherits the whole
    audit trail, not a summary of it.</div>
  </div>
</div>""")


def storage() -> None:
    write("3_storage", """
<h1>Where the data lives</h1>
<p class="sub">No product database by design &mdash; their PIM stays the system
of record. The engine takes a row and returns an enriched row.</p>
<div class="row">
  <div class="card" style="flex:1">
    <div class="k">Versioned in the repository</div>
    <ul>
      <li><code>taxonomy.json</code> — categories, attribute schemas, 16 cross-field rules</li>
      <li>ISO 15 / ISO 898-1 knowledge base — dimensions per designation</li>
      <li>unit tables, house style, list of values, export profiles</li>
      <li><code>discovery/sources.json</code> — the manufacturer-only policy</li>
    </ul>
    <div class="lab" style="margin-top:8px">Adding a category or a customer
    schema means editing data and reviewing a diff — not shipping code.</div>
  </div>
  <div class="card" style="flex:1">
    <div class="k">Written at runtime</div>
    <ul>
      <li>content-addressed result cache — keyed by input, mode, model and taxonomy</li>
      <li>learned categories and their pending proposals</li>
      <li>20 pre-computed AI results, so a reviewer with no key sees real model output</li>
    </ul>
    <div class="lab" style="margin-top:8px">Results are content-addressed, so the
    same input reproduces exactly and nothing has to be kept to be trusted. A
    free-tier container does not hold these across a restart.</div>
    <div class="k" style="margin-top:15px">Deployment</div>
    <ul>
      <li>one container on Render, public link, monitored every 5 minutes</li>
      <li><b>no API key is stored</b> — the deployment cannot spend</li>
      <li>a key a visitor supplies is used for that request and never written</li>
    </ul>
  </div>
</div>""")


def scale() -> None:
    write("4_scale", """
<h1>Scale, and what it costs</h1>
<p class="sub">Measured on their own 1,000-row sample and a 102-case benchmark.
The projections are labelled as projections.</p>
<div class="row">
  <div class="card" style="flex:1"><div class="k">Ingest</div>
    <div class="big">611 rows/s</div>
    <div class="lab">their 1,000 rows in 1.6 s</div></div>
  <div class="card" style="flex:1"><div class="k">Enrich</div>
    <div class="big">287 /s</div>
    <div class="lab">one core, measured locally</div></div>
  <div class="card" style="flex:1"><div class="k">Cost per SKU</div>
    <div class="big" style="color:var(--ok)">$0.0084</div>
    <div class="lab">batched, at standard rates</div></div>
  <div class="card" style="flex:1"><div class="k">Their manual baseline</div>
    <div class="big" style="color:var(--amber)">$5.83</div>
    <div class="lab">10 min/SKU at $35/hr</div></div>
</div>
<div class="row" style="margin-top:16px">
  <div class="card" style="flex:1.3">
    <div class="k">What a merchandiser actually gets</div>
    <div style="font-size:14.5px;line-height:1.6">Every record arrives sorted into
    <b style="color:var(--ok)">ready to publish</b>,
    <b style="color:var(--amber)">needs review</b> or
    <b style="color:#b91c1c">blocked</b>, with the reason attached — so a person
    opens only what needs a person. On a 10-product run: 7 publishable, 1 review,
    2 blocked.</div>
  </div>
  <div class="card" style="flex:1">
    <div class="k">Categories it has never seen</div>
    <div style="font-size:14.5px;line-height:1.6">Learned from the data and held
    for approval: coverage on their 1,000 rows goes <b>8.9% &rarr; 81.7%</b>.
    Nothing publishes under a learned category until a human confirms it.</div>
  </div>
</div>""")


def accuracy() -> None:
    write("5_accuracy", """
<h1>Measured against their own labelled rows</h1>
<p class="sub">Unilog supplied two fully worked delivery rows. Both numbers are
published, because only one of them is flattering.</p>
<div class="row">
  <div class="card" style="flex:1;text-align:center">
    <div class="big" style="font-size:44px;color:var(--ok)">14 / 14</div>
    <div class="lab" style="font-size:14px">prose fields exact — given the attribute values</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="big" style="font-size:44px;color:var(--amber)">2 / 14</div>
    <div class="lab" style="font-size:14px">from a bare six-column catalogue row</div>
  </div>
</div>
<div class="row" style="margin-top:16px">
  <div class="card" style="flex:1">
    <div style="font-size:15px;line-height:1.6">The gap is <b>sourcing, not
    formatting</b>. Series, mounting, wash cycles and voltage are not in a
    catalogue row — they are on the manufacturer's site, which their own
    delivery row cites. The copy engine is exact once it has the values; saying
    which of the two numbers you are quoting is the point.</div>
  </div>
  <div class="card" style="width:360px">
    <div class="k">Also measured</div>
    <div style="font-size:14px;line-height:1.7">
    <b>100%</b> of 51 seeded defects caught<br>
    <b>0.0%</b> false alarms on clean records<br>
    <b>0.0%</b> contradictions on evidence-backed values</div>
  </div>
</div>""")


def closing() -> None:
    write("6_close", """
<div style="text-align:center">
  <h1 style="font-size:38px;margin-bottom:14px">Thank you</h1>
  <p class="sub" style="font-size:17px;margin-bottom:30px">
    Product Intelligence for Industrial Commerce &middot; Team Codes</p>
</div>
<div class="row" style="justify-content:center">
  <div class="card" style="width:430px;text-align:center">
    <div class="k">Try the prototype</div>
    <div style="font-size:15px;color:var(--blue);word-break:break-all">
      industrial-product-intelligence.onrender.com</div>
    <div class="lab" style="margin-top:7px">Live, no login, no API key needed</div>
  </div>
  <div class="card" style="width:430px;text-align:center">
    <div class="k">Source and evidence</div>
    <div style="font-size:15px;color:var(--blue);word-break:break-all">
      github.com/ashwinsureshh/industrial-product-intelligence</div>
    <div class="lab" style="margin-top:7px">Public &middot; every figure here is reproducible</div>
  </div>
</div>
<div class="row" style="justify-content:center;margin-top:18px">
  <div style="font-size:13.5px;color:var(--muted);text-align:center;max-width:760px">
    Ten test suites, a 102-case benchmark and the customer's own labelled rows
    all run from the repository with one command each.</div>
</div>""")


def main() -> int:
    print("fetching a real export from the deployed service…")
    record = urllib.request.urlopen(urllib.request.Request(
        f"{BASE}/api/enrich", data=json.dumps({
            "product": {"sku": "BRG-6205-2RS", "mpn": "6205-2RS", "brand": "SKF",
                        "name": "Deep groove ball bearing"}, "mode": "demo"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=90).read()
    record = json.loads(record)

    def export(profile: str) -> str:
        req = urllib.request.Request(
            f"{BASE}/api/export?profile={profile}", data=json.dumps([record]).encode(),
            headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")

    # csv.reader, not split(","): the descriptions contain commas inside quoted
    # fields, and a naive split shifts every column after the first one — which
    # put `"SKF` under MOBILE_DESC on the first render of this frame.
    import csv as _csv
    import io as _io
    rows = list(_csv.reader(_io.StringIO(export("unilog_delivery"))))
    header, row = rows[0], rows[1]
    columns = len(header)
    shown = [(h, v) for h, v in zip(header, row) if v.strip()][:8]
    width = max(len(h) for h, _ in shown)
    sample = "\n".join(f"{h:<{width}}  {v[:44]}" for h, v in shown)

    jsonld = "\n".join(export("schema_org").splitlines()[:14])

    architecture()
    outputs(sample, jsonld, columns)
    storage()
    scale()
    accuracy()
    closing()
    print(f"  (delivery row read live: {columns} columns, "
          f"{len([v for v in row if v.strip()])} populated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
