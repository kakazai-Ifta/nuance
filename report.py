"""
report.py - builds the PDF report of a Nuance analysis (made with reportlab).

make_pdf(runs, meta, decisions, baseline) returns the PDF as bytes.
  runs      : {product name: {"reviews", "results", "priority_table", "briefing"}}
  meta      : settings of the run (brand, brand context, topics, product counts ...)
  decisions : {(product, topic): {"decision": "Accept/Edit/Reject/Waiting", "edit": "text"}}
  baseline  : {product name: {"positive": n, "neutral": n, "negative": n}}
"""

import datetime
import io
from xml.sax.saxutils import escape

from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

PLUM = colors.HexColor("#4A2545")
ROSE = colors.HexColor("#B5476B")
BLUSH = colors.HexColor("#F7EEF1")
GOLD = colors.HexColor("#C9A24B")
INK = colors.HexColor("#2B1B2A")
LINE = colors.HexColor("#E8B4C0")
LILAC = colors.HexColor("#7A4B78")

body = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14, textColor=INK, spaceAfter=5)
small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=12, textColor=LILAC, spaceAfter=3)
cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12, spaceAfter=0)
cellh = ParagraphStyle("cellh", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=PLUM, spaceBefore=10, spaceAfter=6, keepWithNext=1)
h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=ROSE, spaceBefore=8, spaceAfter=4, keepWithNext=1)
title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=colors.white)
subtitle = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=12, leading=16, textColor=LINE)
metric_num = ParagraphStyle("mn", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=PLUM, alignment=TA_CENTER)
metric_lbl = ParagraphStyle("ml", fontName="Helvetica", fontSize=8, leading=10, textColor=LILAC, alignment=TA_CENTER)


def clean(text):
    """Make text safe for the PDF font (no emoji or unusual symbols) and for reportlab's markup."""
    text = str(text).encode("cp1252", "replace").decode("cp1252")
    return escape(text)


def P(text, style=body):
    return Paragraph(clean(text), style)


def band(text_paragraphs, height=None):
    t = Table([[text_paragraphs]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), PLUM), ("LEFTPADDING", (0, 0), (-1, -1), 18),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 18), ("TOPPADDING", (0, 0), (-1, -1), 18),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 18)]))
    return t


def metric_row(items):
    """items: list of (number, label). Draws a row of tiles."""
    cells = [[Paragraph(str(n), metric_num), Paragraph(clean(label), metric_lbl)] for n, label in items]
    t = Table([[c for c in cells]], colWidths=[17 * cm / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUSH), ("LINEBEFORE", (0, 0), (-1, -1), 3, ROSE),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                           ("LINEAFTER", (0, 0), (-2, -1), 0, colors.white)]))
    return t


def bar(value, biggest, width=5.2 * cm, colour=ROSE):
    """A small horizontal bar for a table cell."""
    d = Drawing(width, 12)
    length = 0 if biggest == 0 else max(2, width * value / biggest)
    d.add(Rect(0, 1, length, 10, fillColor=colour, strokeColor=None))
    return d


def grid(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BLUSH])]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), PLUM))
    t.setStyle(TableStyle(style))
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(LILAC)
    canvas.drawString(2 * cm, 1.2 * cm, "Nuance  |  reads between the lines of customer reviews")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1)
    canvas.line(2 * cm, 1.7 * cm, A4[0] - 2 * cm, 1.7 * cm)
    canvas.restoreState()


def decision_text(info):
    if not info or info.get("decision", "Waiting") == "Waiting":
        return "Decision: waiting for a person"
    text = "Decision: " + info["decision"]
    if info["decision"] == "Edit" and info.get("edit"):
        text += "  |  Edited action: " + info["edit"]
    return text


def make_pdf(runs, meta, decisions, baseline):
    meta = meta or {}
    decisions = decisions or {}
    buffer = io.BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                          bottomMargin=2.2 * cm, title="Nuance report", author="Nuance")
    doc.addPageTemplates([PageTemplate(id="main", frames=[Frame(2 * cm, 2.2 * cm, 17 * cm, A4[1] - 4 * cm, id="f")],
                                       onPage=footer)])
    story = []

    # ---------- cover band
    brand = meta.get("brand") or "Customer review analysis"
    lines = [Paragraph("Nuance report", title), Spacer(1, 4), P(brand, ParagraphStyle("b", parent=subtitle, fontSize=15, textColor=colors.white)),
             Spacer(1, 4), P("What customers really mean, and what to fix first", subtitle)]
    story.append(band(lines))
    story.append(Spacer(1, 8))

    facts = [["Date", datetime.date.today().strftime("%d %B %Y")],
             ["AI model", meta.get("model", "Llama 3.1 8B")],
             ["Reviews filtered by", meta.get("filters") or "none"],
             ["Products analysed", str(len(runs))]]
    story.append(grid([[P(a, cell), P(b, cell)] for a, b in facts], [4 * cm, 13 * cm], header=False))

    # ---------- summary
    total_read = sum(len(r["results"]) for r in runs.values())
    total_flagged = sum(1 for r in runs.values() for x in r["results"] if x["needs_human_review"])
    story.append(P("Summary", h1))
    story.append(metric_row([(len(runs), "products analysed"), (total_read, "reviews analysed"),
                             (total_flagged, "reviews flagged for a human")]))
    story.append(Spacer(1, 8))

    summary_rows = [[Paragraph("Product", cellh), Paragraph("Biggest issue", cellh), Paragraph("Priority", cellh),
                     Paragraph("Confidence", cellh)]]
    for name, r in runs.items():
        top = r["briefing"][0] if r["briefing"] else None
        summary_rows.append([P(name, cell), P(top["topic"].capitalize() if top else "none found", cell),
                             P(top["priority"] if top else "-", cell), P(top["confidence"] if top else "-", cell)])
    story.append(grid(summary_rows, [8 * cm, 3.6 * cm, 2.6 * cm, 2.8 * cm]))

    # ---------- how it works
    story.append(P("How the analysis works", h1))
    story.append(P("Nuance reads each review the way a thoughtful person would. Four agents work in sequence and a person "
                   "makes the final decision."))
    method = [[Paragraph("Agent", cellh), Paragraph("What it does", cellh), Paragraph("Uses", cellh)],
              [P("1. Theory-of-Mind", cell), P("Guesses what the customer believes, feels and intends (two different explanations per review).", cell), P("Llama", cell)],
              [P("2. Domain", cell), P("Checks each guess against the customer's own words and the brand context, then keeps or drops it.", cell), P("Llama + Python", cell)],
              [P("3. Prioritiser", cell), P("Counts how many reviews mention each topic and ranks them (25% or more = High, 10% or more = Medium).", cell), P("Python", cell)],
              [P("4. Validation", cell), P("Writes advice for each top topic, checks it, and gives a confidence level.", cell), P("Llama + Python", cell)],
              [P("Human decision", cell), P("A person accepts, edits or rejects each piece of advice.", cell), P("Person", cell)]]
    story.append(grid(method, [3.6 * cm, 10.6 * cm, 2.8 * cm]))

    # ---------- products chosen
    counts = meta.get("product_counts") or {}
    if counts:
        story.append(PageBreak())
        story.append(P("Which products were analysed", h1))
        filt = f" (counting {meta['filters']})" if meta.get("filters") else ""
        story.append(P(f"The {len(counts)} product{'s' if len(counts) > 1 else ''} with the most reviews{filt} "
                       f"{'were' if len(counts) > 1 else 'was'} chosen. Nuance read up to "
                       f"{meta.get('reviews_per_product', 'N')} reviews per product."))
        biggest = max(counts.values())
        rows = [[Paragraph("Product", cellh), Paragraph("Reviews in the file", cellh), Paragraph("", cellh)]]
        for name, n in counts.items():
            rows.append([P(name, cell), P(str(n), cell), bar(n, biggest)])
        story.append(grid(rows, [7.6 * cm, 3.4 * cm, 6 * cm]))

    # ---------- one section per product
    for position, (name, r) in enumerate(runs.items()):
        if not (position == 0 and counts):      # the first product continues on the "products analysed" page
            story.append(PageBreak())
        story.append(P(name, h1))
        results, briefing, table = r["results"], r["briefing"], r["priority_table"]
        flagged = [x for x in results if x["needs_human_review"]]
        low = [b for b in briefing if b["needs_human_review"]]
        story.append(metric_row([(len(results), "reviews analysed"), (len(table), "topics found"),
                                 (len(flagged), "reviews flagged"), (len(low), "low-confidence advice")]))

        # sentiment analysis next to the topics found by Nuance
        story.append(P("Detailed analysis", h2))
        base = baseline.get(name, {}) if baseline else {}
        n_rev = max(len(r["reviews"]), 1)
        pos = round(100 * base.get("positive", 0) / n_rev)
        top = briefing[0] if briefing else None
        left = [P("Normal sentiment analysis", ParagraphStyle("lh", parent=cell, fontName="Helvetica-Bold", textColor=PLUM)),
                P(f"Positive: {base.get('positive', 0)}   Neutral: {base.get('neutral', 0)}   Negative: {base.get('negative', 0)}", cell),
                P(f"{pos}% of the reviews are labelled positive.", cell)]
        if top:
            right_text = (f"The biggest issue is {top['topic']} ({top['reviews']} of {len(results)} reviews, "
                          f"priority {top['priority']}). Recommended action: {top['action']} Confidence: {top['confidence']}.")
        else:
            right_text = "No topic could be confirmed in these reviews."
        right = [P("Nuance analysis", ParagraphStyle("rh", parent=cell, fontName="Helvetica-Bold", textColor=ROSE)), P(right_text, cell)]
        cmp_table = Table([[left, right]], colWidths=[7.6 * cm, 9.4 * cm])
        cmp_table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LINEAFTER", (0, 0), (0, 0), 0.5, LINE),
                                       ("BACKGROUND", (0, 0), (0, 0), BLUSH), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                       ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        story.append(cmp_table)

        # ranked topics
        story.append(P("What to fix first", h2))
        if len(table) > 0:
            rows = [[Paragraph(h, cellh) for h in ["Topic", "Reviews", "Share", "Priority", "Risk of losing customers"]]]
            for _, row in table.iterrows():
                rows.append([P(row["topic"].capitalize(), cell), P(str(row["reviews"]), cell), P(f"{row['share_%']}%", cell),
                             P(row["priority"], cell), P(row["risk_of_losing_customer"], cell)])
            story.append(grid(rows, [4.2 * cm, 2.4 * cm, 2.4 * cm, 3 * cm, 5 * cm]))
        else:
            story.append(P("No topics were found."))

        # advice cards
        if briefing:
            story.append(P("Recommended actions", h2))
            story.append(P("Suggested actions are ideas for a human to review. Any detail in them that the customers did not write is the AI's suggestion, not a finding.", small))
        for item in briefing:
            info = decisions.get((name, item["topic"]))
            head = (f"{item['topic'].capitalize()}   |   Priority: {item['priority']}   |   Risk: {item['risk']}   |   "
                    f"Confidence: {item['confidence']}   |   Reviews: {item['reviews']}")
            card = [[Paragraph(clean(head), ParagraphStyle("ch", parent=cell, fontName="Helvetica-Bold", textColor=colors.white))],
                    [[P("What customers believe: " + item["mindset"], cell), Spacer(1, 3),
                      P("Recommended action: " + item["action"], cell), Spacer(1, 3),
                      P("Customers wrote: " + " | ".join(item.get("quotes") or []), small) if item.get("quotes") else Spacer(1, 0),
                      P("Validation check: " + item.get("comment", ""), small),
                      P(decision_text(info), ParagraphStyle("d", parent=cell, fontName="Helvetica-Bold", textColor=PLUM))]]]
            if item["needs_human_review"]:
                card[1][0].insert(0, P("Low confidence. Please review this advice carefully.",
                                       ParagraphStyle("w", parent=cell, fontName="Helvetica-Bold", textColor=ROSE)))
            t = Table(card, colWidths=[17 * cm])
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), ROSE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                                   ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
            story.append(KeepTogether([t, Spacer(1, 8)]))

        # flagged reviews
        if flagged:
            story.append(P(f"Reviews flagged for a human ({len(flagged)})", h2))
            story.append(P("The agents could not confirm what these customers meant. A person should read them.", small))
            for x in flagged[:5]:
                story.append(P("- " + x["review"][:300].replace("\n", " "), cell))
            if len(flagged) > 5:
                story.append(P(f"... and {len(flagged) - 5} more.", small))

    # ---------- appendix
    story.append(PageBreak())
    story.append(P("Appendix: settings used", h1))
    story.append(P("Brand context", h2))
    for line in (meta.get("brand_context") or "not recorded").splitlines():
        story.append(P(line, cell))
    story.append(P("Topics", h2))
    for line in (meta.get("topics") or "not recorded").splitlines():
        story.append(P(line, cell))
    story.append(P("Limits to keep in mind", h2))
    story.append(P("The analysis comes from a small local AI model (Llama 3.1 8B) and a limited sample of reviews. "
                   "Intentions (buy again or stop buying) are the least reliable guess, so the ranking relies mostly on how often "
                   "a topic appears. Every recommendation needs a person's decision before it is used."))

    doc.build(story)
    return buffer.getvalue()
