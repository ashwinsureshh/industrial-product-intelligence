"""Generates the plain-English project understanding document.

Written for a reader with no technical background: every term is explained the
first time it appears, and each concept is grounded in a concrete example
before any abstraction is introduced.
"""

from __future__ import annotations

import pathlib

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, ListFlowable, ListItem, NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

OUT = pathlib.Path(__file__).parent / "Project_Understanding.pdf"

INK = colors.HexColor("#16202C")
MUTED = colors.HexColor("#5B6775")
ACCENT = colors.HexColor("#2563EB")
GOOD = colors.HexColor("#059669")
WARN = colors.HexColor("#D97706")
BAD = colors.HexColor("#DC2626")
RULE = colors.HexColor("#E3E7EC")
SOFT = colors.HexColor("#F6F7F9")
BLUE_SOFT = colors.HexColor("#EFF4FF")

styles = getSampleStyleSheet()


def style(name, parent="BodyText", **kw):
    return ParagraphStyle(name, parent=styles[parent], **kw)


S = {
    "title": style("t", "Title", fontSize=30, leading=35, textColor=INK,
                   spaceAfter=6, fontName="Helvetica-Bold"),
    "subtitle": style("st", fontSize=13.5, leading=19, textColor=MUTED,
                      alignment=TA_CENTER, spaceAfter=4),
    "h1": style("h1", "Heading1", fontSize=19, leading=24, textColor=INK,
                spaceBefore=20, spaceAfter=9, fontName="Helvetica-Bold",
                keepWithNext=1),
    "h2": style("h2", "Heading2", fontSize=13.5, leading=18, textColor=ACCENT,
                spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold",
                keepWithNext=1),
    "body": style("b", fontSize=10.4, leading=16, textColor=INK,
                  alignment=TA_JUSTIFY, spaceAfter=8),
    "lead": style("l", fontSize=12, leading=18, textColor=INK, spaceAfter=10),
    "small": style("sm", fontSize=9, leading=13, textColor=MUTED, spaceAfter=6),
    "quote": style("q", fontSize=10.6, leading=16, textColor=INK,
                   leftIndent=12, rightIndent=12, spaceBefore=4, spaceAfter=4),
    "cell": style("c", fontSize=9.3, leading=13, textColor=INK, spaceAfter=0),
    "cellb": style("cb", fontSize=9.3, leading=13, textColor=INK, spaceAfter=0,
                   fontName="Helvetica-Bold"),
    "cellh": style("ch", fontSize=8.6, leading=12, textColor=MUTED, spaceAfter=0,
                   fontName="Helvetica-Bold"),
}


def P(text, s="body"):
    return Paragraph(text, S[s])


def bullets(items, s="body"):
    return ListFlowable(
        [ListItem(Paragraph(i, S[s]), leftIndent=14) for i in items],
        # ZapfDingbats 'l' is a filled round bullet. The obvious choice,
        # U+2022 in Helvetica, is not in the font's encoding and renders as a
        # missing-glyph box.
        bulletType="bullet", start="l",
        bulletFontName="ZapfDingbats", bulletFontSize=6,
        leftIndent=14, bulletOffsetY=-2, spaceAfter=8,
    )


def callout(title, text, tint=BLUE_SOFT, bar=ACCENT):
    inner = [Paragraph(f"<b>{title}</b>", S["quote"]), Paragraph(text, S["quote"])]
    t = Table([[inner]], colWidths=[165 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), tint),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return KeepTogether([Spacer(1, 4), t, Spacer(1, 10)])


def table(rows, widths, header=True, aligns=None):
    data = []
    for r_i, row in enumerate(rows):
        line = []
        for c_i, cell in enumerate(row):
            if isinstance(cell, Paragraph):
                line.append(cell)
            else:
                s = "cellh" if (header and r_i == 0) else "cell"
                line.append(Paragraph(str(cell), S[s]))
        data.append(line)

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), SOFT),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#CDD4DD"))]
    for col, al in (aligns or {}).items():
        cmds.append(("ALIGN", (col, 0), (col, -1), al))
    t.setStyle(TableStyle(cmds))
    return KeepTogether([t, Spacer(1, 10)])


# ------------------------------------------------------------------ document

def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(22 * mm, h - 13 * mm,
                          "Industrial Product Intelligence  ·  Project Understanding")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(22 * mm, h - 15 * mm, w - 22 * mm, h - 15 * mm)
        canvas.drawRightString(w - 22 * mm, 13 * mm, str(doc.page))
    canvas.restoreState()


def build():
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm,
        title="Industrial Product Intelligence — Project Understanding",
        author="Ashwin Suresh",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                       onPage=header_footer)])

    st = []
    a = st.append

    # ----------------------------------------------------------- cover
    a(Spacer(1, 42 * mm))
    a(Paragraph("Industrial Product<br/>Intelligence", S["title"]))
    a(Spacer(1, 6))
    a(Paragraph("Turning scraps of supplier data into product information "
                "a business can actually sell from", S["subtitle"]))
    a(Spacer(1, 16 * mm))
    a(table([
        ["What this document is",
         "A plain-English explanation of the project: the problem, what was "
         "built, how it works, what has been proven, and what remains."],
        ["Who it is for",
         "Anyone. No technical background is assumed. Every specialist term is "
         "explained where it first appears."],
        ["Status",
         "A working prototype, live on the internet and continuously monitored."],
        ["Live link", "industrial-product-intelligence.onrender.com"],
        ["Submission deadline", "23 August 2026"],
    ], [42 * mm, 123 * mm], header=False))
    a(PageBreak())

    # ------------------------------------------------------- 1. problem
    a(P("1. The problem, in everyday terms", "h1"))

    a(P("Imagine a shop that sells 200,000 industrial parts — bearings, valves, "
        "motors, sensors. Nobody buys these on impulse. An engineer needs to "
        "know that a part is <i>exactly</i> the right size, rated for the right "
        "pressure, made of the right metal. If the listing is wrong, they order "
        "the wrong part, and a machine somewhere stops working."))

    a(P("Now look at where that shop's information actually comes from. One "
        "supplier sends a neat spreadsheet. Another sends a PDF catalogue. A "
        "third has a website and nothing else. A fourth sends an email that "
        "says, in full:"))

    a(callout("A real example of what arrives",
              "&ldquo;6205-2RS, SKF, deep groove ball bearing&rdquo;",
              tint=SOFT, bar=MUTED))

    a(P("That is three pieces of information. A usable product listing needs "
        "around twenty: the internal diameter, the external diameter, the "
        "width, the load it can carry, the top speed it can spin at, the "
        "material, the seal type, and so on. Somebody has to find all of that "
        "and type it in."))

    a(P("Today that somebody is a person. They open the manufacturer's "
        "catalogue, look up the part, and copy the numbers across. It takes "
        "roughly ten minutes per product. For 200,000 products that is about "
        "sixteen years of one person's working life.", "lead"))

    a(P("And people make mistakes. They read a figure from the wrong row. They "
        "type millimetres where the catalogue meant inches. They swap two "
        "numbers around. Most of those mistakes are invisible — the listing "
        "looks perfectly normal, and the error is only discovered when the "
        "wrong part arrives on a factory floor."))

    a(P("What this project does", "h2"))
    a(P("It takes whatever scraps of information a supplier provides and turns "
        "them into a complete, checked product listing — automatically. Just as "
        "importantly, it <b>checks its own work</b>, and it <b>shows where every "
        "single number came from</b>."))

    a(PageBreak())

    # -------------------------------------------------- 2. core idea
    a(P("2. The idea at the heart of it", "h1"))

    a(P("Most systems that fill in missing information are built to always "
        "produce an answer. Ask them anything and they will confidently tell "
        "you something. That is fine when the stakes are low — a wrong film "
        "recommendation costs nothing."))

    a(P("Here the stakes are not low. So this system is built on the opposite "
        "instinct:"))

    a(callout("The rule everything else follows from",
              "A wrong specification on an industrial part stops a machine. So "
              "the system would rather leave a box empty, raise a warning, or "
              "refuse to publish a product altogether than state something it "
              "cannot back up."))

    a(P("In practice that means three habits, which run through everything:"))

    a(bullets([
        "<b>Every number carries a receipt.</b> Nothing appears without a note "
        "saying where it came from — which supplier field, which page of which "
        "PDF, or which published engineering standard.",
        "<b>Confidence is stated, not implied.</b> A figure taken straight from "
        "an international standard is marked as near-certain. An educated guess "
        "is labelled a guess, and is visibly flagged for someone to confirm.",
        "<b>Bad data is stopped, not smoothed over.</b> When the numbers "
        "contradict each other, the product is blocked from publication and the "
        "contradiction is explained in plain language.",
    ]))

    a(P("Why that matters commercially", "h2"))
    a(P("A system that is right 95% of the time but does not tell you which 5% "
        "is wrong is close to useless, because a human still has to re-check "
        "everything. A system that is right 61% of the time and is <i>honest "
        "about the other 39%</i> is genuinely useful: staff can trust the "
        "confident parts and spend their time only where they are needed."))

    a(Spacer(1, 6))

    # ------------------------------------------- 3. what it looks like
    a(P("3. What it actually looks like", "h1"))

    a(P("The prototype is a website. It has four sections, each answering a "
        "different real-world situation."))

    a(P("Section 1 &mdash; A single product", "h2"))
    a(P("You type in whatever you have and press a button. Using the three-word "
        "example from earlier, the system returns:"))

    a(table([
        ["What it worked out", "Value", "Where it came from"],
        ["Internal diameter", "25 mm", "International standard ISO 15"],
        ["External diameter", "52 mm", "International standard ISO 15"],
        ["Width", "15 mm", "International standard ISO 15"],
        ["Load rating", "14 kN", "International standard ISO 15"],
        ["Maximum speed", "16,000 rpm", "International standard ISO 15"],
        ["Seal type", "Rubber sealed", "Decoded from the part number"],
        ["Ring material", "Chrome steel", "Typical value &mdash; flagged to confirm"],
    ], [46 * mm, 32 * mm, 87 * mm], aligns={1: "LEFT"}))

    a(P("Eleven pieces of information from three. And critically, the last row "
        "is <i>marked differently</i> from the others, because it is an "
        "assumption rather than a fact."))

    a(callout("The trick behind those first five rows",
              "The code &ldquo;6205&rdquo; is not a random part number. It is a "
              "designation defined by an international standard, a bit like a "
              "postcode. Any bearing labelled 6205, from any manufacturer in "
              "the world, has a 25 mm bore and a 52 mm outer diameter. The "
              "system knows how to read that code &mdash; so those numbers are "
              "not guesses at all, they are lookups.",
              tint=SOFT, bar=GOOD))

    a(P("Section 2 &mdash; A technical document", "h2"))
    a(P("Suppliers often provide a datasheet: a PDF with a table of "
        "specifications. You drop the file in and the system reads it."))
    a(P("This is harder than it sounds, because datasheets are laid out in "
        "wildly different ways. Some have proper tables with lines and borders. "
        "Some just line the numbers up with spaces. Some are written as "
        "&ldquo;Bore diameter ......... 25 mm&rdquo; running down the page. The "
        "system handles all three, and every value it reads stays linked back "
        "to the document it came from, so it can be checked later."))

    a(P("Section 3 &mdash; A whole catalogue", "h2"))
    a(P("Upload a spreadsheet of hundreds of products and every row is "
        "processed at once. You get a summary: how many are ready to publish, "
        "how many need a human to look at them, how many are blocked, and why. "
        "This is the realistic way the tool would actually be used."))

    a(P("Section 4 &mdash; Learning", "h2"))
    a(P("This is the most unusual part, and it gets its own section later."))

    a(Spacer(1, 6))

    # ------------------------------------------------- 4. how it works
    a(P("4. How it works, step by step", "h1"))

    a(P("When a product goes in, it passes through eight stages. Think of it as "
        "a production line where each station does one job and hands the work "
        "to the next."))

    a(table([
        ["Stage", "What happens, in plain terms"],
        ["1. Tidy up",
         "Clean up the messy input. Recognise that &ldquo;skf&rdquo;, "
         "&ldquo;SKF Group&rdquo; and &ldquo;S.K.F.&rdquo; are the same "
         "manufacturer. Find the part number even if it is buried in a sentence."],
        ["2. Identify",
         "Work out what kind of product this is &mdash; a bearing? a valve? a "
         "motor? This matters because it decides which questions are worth "
         "asking. You do not ask a bearing about its voltage."],
        ["3. Read",
         "Pull out every fact already present in the input, converting units as "
         "it goes. If the supplier wrote &ldquo;5 HP&rdquo; and the catalogue "
         "standard is kilowatts, it converts &mdash; and records that it did."],
        ["4. Fill gaps",
         "Work out what is still missing. Some gaps are filled from engineering "
         "standards; some require judgement, which is where the AI comes in."],
        ["5. Resolve conflicts",
         "When two sources disagree, prefer the better-evidenced one, record "
         "that there was a disagreement, and <i>lower</i> the confidence &mdash; "
         "because a disagreement is itself a reason to be less sure."],
        ["6. Write the listing",
         "Produce the customer-facing title, description and bullet points, "
         "using only facts that survived the earlier stages."],
        ["7. Check",
         "Run the checks. Is anything impossible? Anything contradictory? "
         "Anything unsafe?"],
        ["8. Score",
         "Give the record a mark out of 100 and a verdict: publish, review, or "
         "blocked."],
    ], [30 * mm, 135 * mm]))

    a(P("The checking stage deserves a closer look", "h2"))

    a(P("Most quality checks look at one field at a time: is this number in a "
        "sensible range? Those catch typos, and little else. The interesting "
        "errors are the ones where every individual number looks completely "
        "reasonable, and only the <i>combination</i> is impossible."))

    a(P("Three real examples the system catches:"))

    a(table([
        ["What arrived", "Why it is impossible"],
        ["A valve made of PVC plastic, rated to operate at 180°C",
         "PVC softens at about 60°C. Both figures look normal on their own; "
         "together they describe a product that would melt."],
        ["A bearing with a 90 mm hole and a 40 mm outside diameter",
         "The hole is bigger than the object. Two numbers were swapped during "
         "data entry &mdash; a completely ordinary mistake that no single-field "
         "check would ever notice."],
        ["A hydraulic hose rated to burst at only twice its working pressure",
         "The international safety standard requires a four-times margin. This "
         "is not untidy data; it is a hose that should not be sold for that job."],
    ], [62 * mm, 103 * mm]))

    a(P("There are sixteen such checks, each written from real engineering "
        "rules. They are the difference between a system that tidies data and "
        "one that actually protects the buyer."))

    a(Spacer(1, 6))

    # ------------------------------------------------- 5. learning
    a(P("5. The system teaches itself new categories", "h1"))

    a(P("Here is the obvious objection to everything above. The system knows "
        "about ten kinds of product. A real catalogue has hundreds. So what "
        "happens when something arrives that nobody prepared it for?"))

    a(P("The wrong answer is to hire people to write out hundreds more "
        "categories by hand. The answer built here is different: <b>the system "
        "works out the new category by itself, and asks a human to approve "
        "it.</b>", "lead"))

    a(P("A worked example", "h2"))

    a(P("Five pneumatic cylinders were fed in — a type of product the system "
        "had never encountered. It had no idea what a pneumatic cylinder is. "
        "Left alone, it produced this description of the category, entirely "
        "from the five examples:"))

    a(table([
        ["Property it discovered", "What it concluded"],
        ["Bore size", "A measurement in millimetres, normally 0&ndash;101"],
        ["Stroke length", "A measurement in millimetres, normally 0&ndash;320"],
        ["Operating pressure", "A measurement in bar, normally 4&ndash;15"],
        ["Cushioning", "One of three options: adjustable, air, or rubber"],
        ["Mounting", "One of two options: basic or flange"],
        ["Rod thread", "One of two thread sizes"],
    ], [50 * mm, 115 * mm]))

    a(P("It also named the category &ldquo;Pneumatic Cylinder&rdquo;, and "
        "worked out which properties are essential rather than optional. It did "
        "this without being told anything, and without using AI &mdash; purely "
        "by noticing patterns across the five products."))

    a(P("Then it was tested properly:"))

    a(bullets([
        "<b>Before learning</b>, a pneumatic cylinder was blocked from "
        "publication — the system correctly said it did not understand it.",
        "<b>After a human approved the new category</b>, the same product "
        "scored 99.7 out of 100.",
        "<b>A sixth cylinder</b>, never shown to it during learning, was "
        "classified correctly too. It had learned the <i>kind</i> of thing, not "
        "just those five items.",
        "<b>A deliberately absurd product</b> — a cylinder with a 50-metre bore "
        "— was rejected, caught by a rule the system had invented itself.",
    ]))

    a(callout("Why a human still has to press approve",
              "The system had seen four products whose material was &ldquo;bearing "
              "steel&rdquo;, and proposed a rule that this was the <i>only</i> "
              "permitted material. Left unchecked, the first stainless steel rail "
              "would have been rejected for no good reason. A reviewer looking at "
              "the proposed rule spots that instantly. This is exactly why "
              "proposals are shown to a person in readable form rather than "
              "applied automatically.",
              tint=colors.HexColor("#FFFBEB"), bar=WARN))

    a(Spacer(1, 6))

    # ------------------------------------------------- 6. AI
    a(P("6. Where artificial intelligence fits in", "h1"))

    a(P("The system has two engines, and it chooses between them deliberately."))

    a(table([
        ["", "The rules engine", "The AI engine"],
        ["Used for",
         "Anything with a provable answer &mdash; standards lookups, unit "
         "conversion, arithmetic, contradiction checks",
         "Anything requiring judgement &mdash; unfamiliar products, messy "
         "written descriptions, writing sales copy"],
        ["Cost", "Free", "Costs money per product"],
        ["Consistency", "Identical answer every time", "Can vary slightly"],
        ["Can it be wrong?",
         "Only if the underlying standard is wrong",
         "Yes &mdash; so its answers are capped at a lower confidence"],
    ], [30 * mm, 67 * mm, 68 * mm]))

    a(P("This split is a deliberate engineering choice, not a compromise. If an "
        "international standard fixes a bearing's bore at 25 mm, it would be "
        "worse to ask an AI to estimate it — the standard is simply correct, "
        "and it costs nothing to look up."))

    a(P("But the rules engine has a hard limit, and the project measured "
        "exactly where it is:"))

    a(table([
        ["Situation", "How much the rules engine recovers on its own"],
        ["Product types backed by published standards", "83%"],
        ["Product types with no such standard", "33%"],
    ], [95 * mm, 70 * mm], aligns={1: "CENTER"}))

    a(P("That gap looks like the AI's job. So rather than assume it, the "
        "project measured it — and the obvious approach failed.", "lead"))

    a(P("What happened when the AI was given a free hand", "h2"))

    a(P("Every one of the 102 test products was run through the AI engine and "
        "scored the same way as the rules engine. The result was not the one "
        "the project expected:"))

    a(table([
        ["", "Rules engine", "AI, unrestricted"],
        ["Found, where a standard exists", "83%",
         "<font color='#059669'>98%</font>"],
        ["Found, where no standard exists", "33%",
         "<font color='#DC2626'>27%</font>"],
        ["Wrong, where a standard exists", "5%",
         "<font color='#DC2626'>19%</font>"],
        ["False alarms on clean products", "0%",
         "<font color='#DC2626'>2%</font>"],
    ], [58 * mm, 40 * mm, 67 * mm], aligns={1: "CENTER", 2: "CENTER"}))

    a(P("The AI found considerably more, and got considerably more wrong. On "
        "the product types with no published standard — the very gap it was "
        "meant to close — it did <i>worse</i> than the rules engine."))

    a(callout("The cause was not a weak AI",
              "The AI was allowed to overwrite values the rules engine had "
              "already established from a published standard. A confident "
              "guess was being treated as equal to a measured fact, so it won "
              "arguments it should never have been allowed to enter.",
              tint=colors.HexColor("#FEF2F2"), bar=BAD))

    a(P("The fix: let the AI add, never overrule", "h2"))

    a(P("The system already ranks information by where it came from: a supplier's "
        "own figure outranks a standards lookup, which outranks a calculation, "
        "which outranks a guess. The fix was to hold the AI to that ranking "
        "rather than to write a better instruction for it. The AI is now "
        "permitted exactly two moves:"))

    a(bullets([
        "<b>Fill a blank</b> &mdash; suggest a value where the rules engine "
        "found nothing at all.",
        "<b>Replace a placeholder</b> &mdash; a value marked &ldquo;typical, "
        "please confirm&rdquo; is not evidence, so an informed judgement "
        "genuinely beats it.",
    ]))

    a(P("It may never overwrite a value that came from a supplier, a part "
        "number, a published standard or a calculation. Anything it does "
        "contribute is relabelled as judgement, so the receipt attached to the "
        "value stays honest."))

    a(table([
        ["", "Rules engine", "AI, unrestricted", "<b>Both, AI restricted</b>"],
        ["Found, where a standard exists", "83%", "98%", "<b>99%</b>"],
        ["Found, where no standard exists", "33%", "27%", "<b>42%</b>"],
        ["False alarms on clean products", "0%", "2%", "<b>0%</b>"],
        ["Planted errors caught", "100%", "100%", "<b>100%</b>"],
    ], [50 * mm, 33 * mm, 38 * mm, 44 * mm],
        aligns={1: "CENTER", 2: "CENTER", 3: "CENTER"}))

    a(callout("The restricted version beats the unrestricted one at its own job",
              "Not only are there fewer wrong answers &mdash; there are "
              "<b>more right ones</b>, on both kinds of product. And the "
              "guarantee that matters held completely: of every value backed "
              "by a supplier, a part number, a standard or a calculation, the "
              "number that contradicted the truth stayed at <b>zero</b>. The "
              "AI raised the total found without touching a single established "
              "fact.",
              tint=colors.HexColor("#ECFDF5"), bar=GOOD))

    a(P("Across the 102 products the restriction stepped in <b>28 times</b> to "
        "block the AI from overwriting an established value. Those 28 "
        "interventions are the difference between the two AI columns above.",
        "lead"))

    a(P("Seeing the AI without needing an account", "h2"))
    a(P("There is a practical problem with demonstrating this. Using the AI "
        "engine normally requires the visitor to have their own paid account, "
        "which no reviewer will have."))

    a(P("So the AI was run once, in advance, over every demo product, and the "
        "results were saved into the application itself. Anyone visiting the "
        "live site can switch to the AI engine and see genuine AI-produced "
        "output — including its reasoning — without an account and at no cost "
        "to them. For example, on the bearing it explains:"))

    a(callout("The AI's own explanation of one value",
              "&ldquo;Part number 6205-2RS &mdash; under the ISO 15 bearing "
              "numbering standard, the last two digits &lsquo;05&rsquo; "
              "multiplied by 5 give a 25 mm bore.&rdquo;",
              tint=SOFT, bar=ACCENT))

    a(P("That is the system showing its working, in a form a buyer could check "
        "for themselves."))

    a(Spacer(1, 6))

    # ------------------------------------------------- 7. proof
    a(P("7. Proof that it works", "h1"))

    a(P("Claims are easy. This project was tested against 102 products where "
        "the correct answers were known in advance, so every claim below is "
        "measured rather than asserted."))

    a(P("How the test was built &mdash; and why it is fair", "h2"))

    a(bullets([
        "For bearings and fasteners, the correct answers come from published "
        "international standards. Nobody involved in this project chose those "
        "numbers, so the system cannot have been quietly tuned to match them.",
        "Each product was tested twice: once with most of its information "
        "removed, to see how much the system could recover; and once with a "
        "deliberate error planted in it, to see whether the error was caught.",
        "Only the information that was <i>hidden</i> counts towards the score. "
        "Credit is not taken for repeating back what it was already told.",
    ]))

    a(table([
        ["What was measured", "Result", "What it means"],
        ["Information recovered", "2.75×", "Nearly three times as much usable "
         "information came out as went in"],
        ["Hidden details found", "61%", "Of the details deliberately removed, "
         "it worked out six in ten"],
        ["<b>Wrong answers stated confidently</b>", "<b>0%</b>",
         "<b>Of every value it asserted with evidence, not one contradicted "
         "the truth</b>"],
        ["Planted errors caught", "100%", "All 51 deliberate mistakes were "
         "detected"],
        ["False alarms", "0%", "It never cried wolf on a clean product"],
        ["Speed", "305 per second", "A 200,000-product catalogue in about "
         "eleven minutes"],
    ], [55 * mm, 25 * mm, 85 * mm], aligns={1: "CENTER"}))

    a(callout("Which number actually matters",
              "Not the 2.75×. Any system can fill every box by inventing "
              "content &mdash; that scores brilliantly on &ldquo;how much did "
              "you produce&rdquo; and is worthless. The number that matters is "
              "the <b>0%</b>: of everything the system stated as fact, none of "
              "it was wrong. The gaps it left were honest gaps.",
              tint=colors.HexColor("#ECFDF5"), bar=GOOD))

    a(P("Being honest about the weaker points", "h2"))
    a(bullets([
        "The 0% applies to values backed by evidence. Values the system marks "
        "as &ldquo;typical, please confirm&rdquo; are right about three times "
        "in four &mdash; which is why they are visibly marked rather than "
        "presented as fact.",
        "For product types with no published standard, the test data was "
        "written by hand rather than taken from an external source. Those "
        "results are reported separately and not blended into the headline.",
        "Scanned documents &mdash; photographs of paper — cannot be read. The "
        "system detects this and says so rather than returning nothing.",
        "For product types with no published standard, even the best "
        "configuration finds only about four details in ten. That is a real "
        "improvement on three in ten, but it is not a solved problem, and the "
        "project does not claim otherwise.",
    ]))

    a(callout("Anyone can check these numbers",
              "The AI comparison cost real money to run, so its results were "
              "saved into the code repository. A reviewer can re-run the "
              "entire measurement on their own machine, with no account and "
              "at no cost, and get the same figures. A measurement nobody else "
              "can repeat is an assertion; this one is checkable.",
              tint=BLUE_SOFT, bar=ACCENT))

    a(Spacer(1, 6))

    # ------------------------------------------------- 8. status
    a(P("8. What exists right now", "h1"))

    a(table([
        ["Item", "Status"],
        ["Working prototype",
         "<font color='#059669'><b>Live on the internet</b></font>, monitored "
         "every five minutes, 100% uptime"],
        ["Source code",
         "Complete and version-controlled, with the reasoning behind each "
         "decision recorded"],
        ["Automated tests",
         "Five test suites, all passing, none of which cost anything to run"],
        ["Measured results",
         "Published, with the method open to inspection and the AI comparison "
         "reproducible by anyone"],
        ["AI comparison",
         "<font color='#059669'><b>Complete</b></font> &mdash; all 102 "
         "products, including the restricted version that performed best"],
        ["Presentation deck",
         "<font color='#D97706'>Not started</font> &mdash; awaiting the "
         "required template"],
        ["Demo video", "<font color='#D97706'>Not started</font>"],
    ], [42 * mm, 123 * mm]))

    a(P("What was built, and when", "h2"))
    a(P("All of the following was built in a single working day, roughly four "
        "days ahead of the original plan.", "small"))

    a(table([
        ["Stage", "What it delivered"],
        ["Foundation",
         "The eight-stage production line, ten product categories, sixteen "
         "engineering checks, and the website"],
        ["Measurement",
         "The 102-product test. Building it exposed three genuine faults in the "
         "system, all fixed."],
        ["Documents",
         "Reading datasheets and supplier web pages, handling three different "
         "PDF layouts"],
        ["Learning",
         "Working out new product categories automatically, with human approval"],
        ["Deployment",
         "Packaged as a single unit, published to the internet, monitored"],
        ["AI comparison",
         "All 102 products measured against the AI engine, the result "
         "understood, and the restriction that fixes it built and tested"],
    ], [30 * mm, 135 * mm]))

    a(P("A note on cost control", "h2"))
    a(P("Using AI costs real money per product, and early in the project a "
        "mistake caused about $2.60 to be spent with nothing to show for it: "
        "two identical jobs were accidentally started at once and both were "
        "lost before finishing."))
    a(P("The response was to make that failure impossible rather than to be "
        "more careful. Three safeguards were built and tested:"))
    a(bullets([
        "A second job now <b>refuses to start</b> while one is already running.",
        "Spending is checked <b>after every single product</b>, and the job "
        "stops the instant it crosses a limit you set.",
        "Completed work is saved, so a stopped job <b>resumes for free</b> "
        "rather than starting again.",
    ]))
    a(P("Total spent on the project: <b>about $2.20</b>, of which $1.62 bought "
        "the AI comparison in section 6. Because those results were saved into "
        "the repository, testing further variations of the restriction costs "
        "nothing at all. The published website is deliberately incapable of "
        "spending anything, no matter how many people use it.", "lead"))

    a(Spacer(1, 6))

    # ------------------------------------------------- 9. remaining
    a(P("9. What is left", "h1"))

    a(P("The building is finished. Nothing on this list is engineering.",
        "small"))

    a(table([
        ["Task", "Notes"],
        ["Presentation deck", "Blocked until the required template is "
         "downloaded from the submission portal"],
        ["Demo video", "A short walkthrough of the live site"],
        ["Make the code repository public", "Required at submission; it is "
         "private while under development"],
        ["Replace the access key",
         "Routine housekeeping &mdash; the key used during development is "
         "retired and a fresh one issued"],
    ], [45 * mm, 120 * mm]))

    a(P("One thing deliberately not built", "h2"))
    a(P("The restricted AI configuration described in section 6 &mdash; the "
        "best-performing one &mdash; exists as a measured result, but is not "
        "offered as a choice on the live website. A visitor sees two options: "
        "the rules engine and the unrestricted AI, the latter being the weaker "
        "of the two. Adding the third option is genuine work rather than a "
        "quick change, and with the deck and video still outstanding it was "
        "judged the wrong place to spend the remaining time. It is called out "
        "here so it reads as a decision rather than an oversight."))

    a(P("Honest assessment", "h2"))
    a(P("The engineering is complete and comfortably ahead of schedule. The "
        "remaining risk is not technical — it is that the work is currently "
        "better than the explanation of it. A reviewer will spend a few minutes "
        "forming a judgement, and right now there is no deck or video to shape "
        "that judgement.", "lead"))
    a(P("The sensible course from here is to stop adding capability and spend "
        "the remaining time making what exists easy to understand quickly. "
        "That is particularly true of section 6: the most interesting thing "
        "this project found is that the obvious use of AI made the results "
        "worse, and that restraining it made them better than either engine "
        "managed alone. That finding is invisible to anyone who only clicks "
        "around the website."))

    a(PageBreak())

    # ------------------------------------------------- glossary
    a(P("Glossary", "h1"))
    a(P("Terms used in this document, in plain English.", "small"))

    a(table([
        ["Term", "Meaning"],
        ["Attribute", "One fact about a product — its width, its material, its "
         "voltage."],
        ["Bore", "The diameter of the hole through the middle of a part such as "
         "a bearing."],
        ["Category / taxonomy",
         "The filing system that decides what kind of thing a product is. It "
         "determines which facts are worth collecting."],
        ["Confidence",
         "How sure the system is about a value, shown as a percentage. Low "
         "confidence is a request for a human to check."],
        ["Enrichment", "Filling in missing product information."],
        ["ISO 15 / ISO 898-1 / SAE J517",
         "Published international engineering standards. They define, for "
         "example, the exact dimensions a bearing labelled 6205 must have."],
        ["Provenance",
         "The record of where a piece of information came from — the receipt "
         "attached to every value. It also sets the pecking order when two "
         "sources disagree."],
        ["Ablation",
         "A test that removes or swaps one part of a system to measure what "
         "that part was actually contributing. Here: replacing the rules "
         "engine with the AI to see what the AI adds."],
        ["Readiness score",
         "A mark out of 100 combining how complete a record is, how confident, "
         "and how many problems were found."],
        ["Validation", "Checking data for errors, contradictions and "
         "impossibilities."],
        ["Verdict",
         "The final decision on a product: publish (ready to sell), review "
         "(needs a human), or blocked (must not be published)."],
    ], [42 * mm, 123 * mm]))

    a(Spacer(1, 10))
    a(Paragraph("Live prototype: industrial-product-intelligence.onrender.com",
                S["small"]))
    a(Paragraph("Document generated from the project's own records.", S["small"]))

    doc.build(st)
    print(f"Written: {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
