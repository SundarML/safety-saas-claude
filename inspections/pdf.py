from io import BytesIO
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

from .models import InspectionFinding


def generate_inspection_pdf(inspection, org):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm,
    )

    styles  = getSampleStyleSheet()
    story   = []

    # ── Colour palette ──
    DARK    = colors.HexColor("#1a2c52")
    GREEN   = colors.HexColor("#16a34a")
    RED     = colors.HexColor("#dc2626")
    ORANGE  = colors.HexColor("#ea580c")
    GREY_BG = colors.HexColor("#f8f9fb")
    BORDER  = colors.HexColor("#e2e8f0")

    h1 = ParagraphStyle("h1", fontSize=16, leading=20, textColor=DARK, spaceAfter=2, fontName="Helvetica-Bold")
    h2 = ParagraphStyle("h2", fontSize=11, leading=14, textColor=DARK, spaceAfter=4, fontName="Helvetica-Bold")
    small_label = ParagraphStyle("lbl", fontSize=7, textColor=colors.HexColor("#6c757d"),
                                 fontName="Helvetica-Bold", spaceAfter=1, leading=9)
    body = ParagraphStyle("body", fontSize=9, leading=13, textColor=colors.HexColor("#212529"))
    small = ParagraphStyle("small", fontSize=8, leading=11, textColor=colors.HexColor("#64748b"))

    # ── Header ──
    header_data = [[
        Paragraph(org.name if org else "Vigilo", h1),
        Paragraph("INSPECTION REPORT", ParagraphStyle(
            "rpt", fontSize=9, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#94a3b8"), alignment=2
        )),
    ]]
    header_tbl = Table(header_data, colWidths=["65%", "35%"])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(header_tbl)
    story.append(HRFlowable(width="100%", thickness=1, color=DARK, spaceAfter=10))

    # ── Title + score ──
    score_text = f"{inspection.score:.0f}%" if inspection.score is not None else "—"
    score_colour = GREEN if (inspection.score or 0) >= 90 else (
        ORANGE if (inspection.score or 0) >= 70 else RED
    )
    title_data = [[
        Paragraph(inspection.title, h1),
        Paragraph(
            f'<font color="#{score_colour.hexval()[1:]}"><b>{score_text}</b></font>',
            ParagraphStyle("sc", fontSize=22, alignment=2, fontName="Helvetica-Bold")
        ),
    ]]
    title_tbl = Table(title_data, colWidths=["75%", "25%"])
    title_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
    story.append(title_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Metadata grid ──
    def meta_cell(label, value):
        return [Paragraph(label, small_label), Paragraph(str(value), body)]

    meta = [
        [meta_cell("TEMPLATE", inspection.template.title),
         meta_cell("INSPECTOR", inspection.inspector.get_full_name() if inspection.inspector else "—"),
         meta_cell("LOCATION", inspection.location_display)],
        [meta_cell("SCHEDULED", inspection.scheduled_date.strftime("%d %b %Y")),
         meta_cell("CONDUCTED", inspection.conducted_date.strftime("%d %b %Y") if inspection.conducted_date else "—"),
         meta_cell("STATUS", inspection.get_status_display())],
    ]
    meta_tbl = Table(meta, colWidths=["33%","33%","34%"])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), GREY_BG),
        ("BOX",        (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",  (0,0), (-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(meta_tbl)

    if inspection.has_critical_failures:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph(
            "⚠ This inspection has one or more CRITICAL item failures.",
            ParagraphStyle("warn", fontSize=9, textColor=ORANGE, fontName="Helvetica-Bold")
        ))

    story.append(Spacer(1, 6*mm))

    # ── Findings grouped by section ──
    findings = inspection.findings.select_related(
        "template_item__section"
    ).order_by("template_item__section__order", "template_item__order")

    sections = {}
    for f in findings:
        sec = f.template_item.section
        sections.setdefault(sec, []).append(f)

    RESP_COLOURS = {
        InspectionFinding.RESP_PASS: colors.HexColor("#dcfce7"),
        InspectionFinding.RESP_FAIL: colors.HexColor("#fee2e2"),
        InspectionFinding.RESP_NA:   colors.HexColor("#f1f5f9"),
    }
    RESP_TEXT_COLOURS = {
        InspectionFinding.RESP_PASS: GREEN,
        InspectionFinding.RESP_FAIL: RED,
        InspectionFinding.RESP_NA:   colors.HexColor("#64748b"),
    }

    for section, sec_findings in sections.items():
        story.append(Paragraph(section.title, h2))
        rows = [["#", "Question", "Response", "Notes"]]
        for i, f in enumerate(sec_findings, 1):
            resp_label = f.get_response_display()
            crit = " ⚠" if f.template_item.is_critical else ""
            rows.append([
                Paragraph(str(i), small),
                Paragraph(f.template_item.question + crit, body),
                Paragraph(f"<b>{resp_label}</b>", ParagraphStyle(
                    "resp", fontSize=8, fontName="Helvetica-Bold",
                    textColor=RESP_TEXT_COLOURS.get(f.response, colors.black)
                )),
                Paragraph(f.notes or "—", small),
            ])

        tbl = Table(rows, colWidths=[8*mm, 90*mm, 22*mm, None], repeatRows=1)
        style = [
            ("BACKGROUND",    (0,0), (-1,0), DARK),
            ("TEXTCOLOR",     (0,0), (-1,0), colors.white),
            ("FONTNAME",      (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",      (0,0), (-1,0), 8),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [colors.white, GREY_BG]),
            ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]
        # Colour the response column per row
        for row_idx, f in enumerate(sec_findings, 1):
            bg = RESP_COLOURS.get(f.response, colors.white)
            style.append(("BACKGROUND", (2, row_idx), (2, row_idx), bg))

        tbl.setStyle(TableStyle(style))
        story.append(tbl)
        story.append(Spacer(1, 5*mm))

    # ── Footer note ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=4))
    story.append(Paragraph(
        f"Generated by Vigilo Safety Management &nbsp;·&nbsp; {org.name if org else ''}",
        ParagraphStyle("footer", fontSize=7, textColor=colors.HexColor("#94a3b8"), alignment=1)
    ))

    doc.build(story)
    buf.seek(0)
    filename = f"inspection_{inspection.pk}.pdf"
    response = HttpResponse(buf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response
