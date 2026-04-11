# hira/pdf_report.py
"""
Generate a formal HIRA PDF report using ReportLab.
Layout: branded header, assessment metadata, full hazard table with
initial/residual risk scores, controls, and actions.
"""
from __future__ import annotations

from io import BytesIO

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.logo_utils import get_logo_for_pdf
from .models import RISK_LEVEL_COLORS, RISK_LEVEL_LABELS

# ── Palette ───────────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a2c52")
BRAND_ORANGE = colors.HexColor("#f97316")
LIGHT_GREY   = colors.HexColor("#f8f9fb")
MID_GREY     = colors.HexColor("#dee2e6")
LABEL_GREY   = colors.HexColor("#6c757d")

RISK_RL = {
    "low":      colors.HexColor("#198754"),
    "medium":   colors.HexColor("#ca8a04"),
    "high":     colors.HexColor("#ea580c"),
    "critical": colors.HexColor("#dc2626"),
}
RISK_BG = {
    "low":      colors.HexColor("#d1fae5"),
    "medium":   colors.HexColor("#fef9c3"),
    "high":     colors.HexColor("#ffedd5"),
    "critical": colors.HexColor("#fee2e2"),
}

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 1.6 * cm


def _s(name, **kw):
    defaults = dict(fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#212529"))
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


STYLES = {
    "header_org":    _s("ho",  fontSize=13, fontName="Helvetica-Bold", textColor=colors.white, leading=16),
    "header_sub":    _s("hs",  fontSize=8,  textColor=colors.HexColor("#adb5bd"), leading=11),
    "section":       _s("sec", fontSize=9,  fontName="Helvetica-Bold", textColor=BRAND_DARK, leading=12, spaceBefore=4),
    "meta_label":    _s("ml",  fontSize=7,  fontName="Helvetica-Bold", textColor=LABEL_GREY, leading=10),
    "meta_value":    _s("mv",  fontSize=8,  leading=11),
    "col_header":    _s("ch",  fontSize=7.5,fontName="Helvetica-Bold", textColor=colors.white, alignment=TA_CENTER, leading=10),
    "cell":          _s("ce",  fontSize=7.5,leading=11),
    "cell_center":   _s("cc",  fontSize=7.5,leading=11, alignment=TA_CENTER),
    "risk_badge":    _s("rb",  fontSize=7,  fontName="Helvetica-Bold", alignment=TA_CENTER, leading=10),
    "footer":        _s("ft",  fontSize=6.5,textColor=LABEL_GREY, leading=9),
    "control_type":  _s("ct",  fontSize=6.5,fontName="Helvetica-Bold", textColor=BRAND_DARK, leading=9),
}

CONTROL_ABBR = {
    "elimination":    "ELIM",
    "substitution":   "SUBS",
    "engineering":    "ENG",
    "administrative": "ADM",
    "ppe":            "PPE",
}


def _risk_cell(level, score):
    """Coloured risk cell."""
    if level is None:
        return Paragraph("—", STYLES["cell_center"])
    label = RISK_LEVEL_LABELS.get(level, level.title())
    text  = f'<b>{score}</b><br/><font size="6">{label}</font>'
    p = Paragraph(text, STYLES["risk_badge"])
    t = Table([[p]], colWidths=[1.8 * cm], rowHeights=[0.9 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), RISK_BG.get(level, colors.white)),
        ("TEXTCOLOR",    (0, 0), (-1, -1), RISK_RL.get(level, LABEL_GREY)),
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [3]),
        ("LEFTPADDING",  (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


def generate_hira_pdf(register) -> bytes:
    buf = BytesIO()
    org = register.organization
    generated_at = timezone.localtime(timezone.now()).strftime("%d %b %Y  %H:%M")

    # ── Page template ─────────────────────────────────────────────────────────
    def _draw(canvas, doc):
        canvas.saveState()

        # Header bar
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, PAGE_H - 2.2 * cm, PAGE_W, 2.2 * cm, fill=1, stroke=0)

        # Logo
        logo_img = get_logo_for_pdf(org, 3 * cm, 1.4 * cm)
        lx = MARGIN
        if logo_img:
            logo_img.drawOn(canvas, lx, PAGE_H - 1.9 * cm)
            tx = lx + logo_img.drawWidth + 0.4 * cm
        else:
            canvas.setFillColor(BRAND_ORANGE)
            canvas.roundRect(lx, PAGE_H - 1.85 * cm, 1.2 * cm, 1.2 * cm, 3, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 16)
            canvas.drawCentredString(lx + 0.6 * cm, PAGE_H - 1.4 * cm, "V")
            tx = lx + 1.6 * cm

        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(tx, PAGE_H - 1.1 * cm, org.name if org else "Organisation")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#adb5bd"))
        canvas.drawString(tx, PAGE_H - 1.65 * cm, "Hazard Identification & Risk Assessment (HIRA)")

        # Doc ref right
        canvas.setFillColor(BRAND_ORANGE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.0 * cm,
                               f"HIRA-{register.pk:04d}  Rev {register.revision_no}")
        canvas.setFillColor(colors.HexColor("#adb5bd"))
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.6 * cm,
                               register.get_status_display().upper())

        # Footer
        canvas.setFillColor(MID_GREY)
        canvas.rect(0, 0, PAGE_W, 1.0 * cm, fill=1, stroke=0)
        canvas.setFillColor(LABEL_GREY)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(MARGIN, 0.38 * cm,
                          "Generated by Vigilo Safety Platform · safety-desk.com  |  ISO 45001 Aligned")
        canvas.drawRightString(PAGE_W - MARGIN, 0.38 * cm,
                               f"Generated: {generated_at}  ·  Page {doc.page}")

        canvas.restoreState()

    frame = Frame(
        MARGIN, 1.2 * cm,
        PAGE_W - 2 * MARGIN, PAGE_H - 2.2 * cm - 1.2 * cm,
        leftPadding=0, rightPadding=0, topPadding=0.25 * cm, bottomPadding=0,
    )
    doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=2.2 * cm, bottomMargin=1.2 * cm)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw)])

    story = []
    usable_w = PAGE_W - 2 * MARGIN

    # ── Assessment metadata ───────────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))

    meta_rows = [
        [
            Paragraph("ASSESSMENT TITLE", STYLES["meta_label"]),
            Paragraph(register.title, ParagraphStyle("t", fontSize=11, fontName="Helvetica-Bold",
                                                      textColor=BRAND_DARK, leading=14)),
            Paragraph("STATUS", STYLES["meta_label"]),
            Paragraph(register.get_status_display(), ParagraphStyle("s", fontSize=9,
                      fontName="Helvetica-Bold", textColor=BRAND_ORANGE, leading=12)),
        ],
        [
            Paragraph("ACTIVITY / WORK AREA", STYLES["meta_label"]),
            Paragraph(register.activity, STYLES["meta_value"]),
            Paragraph("LOCATION", STYLES["meta_label"]),
            Paragraph(register.location_text or "—", STYLES["meta_value"]),
        ],
        [
            Paragraph("ASSESSED BY", STYLES["meta_label"]),
            Paragraph(register.assessed_by.get_full_name() if register.assessed_by else "—", STYLES["meta_value"]),
            Paragraph("ASSESSMENT DATE", STYLES["meta_label"]),
            Paragraph(str(register.assessment_date), STYLES["meta_value"]),
        ],
        [
            Paragraph("APPROVED BY", STYLES["meta_label"]),
            Paragraph(register.approved_by.get_full_name() if register.approved_by else "Pending", STYLES["meta_value"]),
            Paragraph("NEXT REVIEW DATE", STYLES["meta_label"]),
            Paragraph(str(register.next_review_date) if register.next_review_date else "—", STYLES["meta_value"]),
        ],
    ]

    cw = usable_w / 4
    meta_table = Table(meta_rows, colWidths=[cw * 0.45, cw * 1.05, cw * 0.45, cw * 1.05],
                       rowHeights=[0.75 * cm] * len(meta_rows))
    meta_table.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GREY, colors.white]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.5, MID_GREY),
        ("LINEAFTER",    (1, 0), (1, -1), 0.5, MID_GREY),
        ("BOX",          (0, 0), (-1, -1), 0.5, MID_GREY),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_DARK))
    story.append(Spacer(1, 0.3 * cm))

    # ── Hazard table ──────────────────────────────────────────────────────────
    story.append(Paragraph("HAZARD REGISTER", STYLES["section"]))
    story.append(Spacer(1, 0.2 * cm))

    hazards = list(register.hazards.all())

    if not hazards:
        story.append(Paragraph("No hazards recorded in this register.", STYLES["cell"]))
    else:
        # Column widths (total = usable_w)
        col_w = {
            "#":        0.5 * cm,
            "cat":      2.0 * cm,
            "hazard":   4.5 * cm,
            "harm":     3.5 * cm,
            "who":      2.0 * cm,
            "init_r":   1.9 * cm,
            "ctrl_type":1.6 * cm,
            "controls": 4.5 * cm,
            "res_r":    1.9 * cm,
            "action":   3.5 * cm,
        }
        cws = list(col_w.values())

        def _ch(text):
            return Paragraph(text, STYLES["col_header"])

        header = [
            _ch("#"), _ch("Category"), _ch("Hazard Description"), _ch("Potential Harm"),
            _ch("Who at Risk"), _ch("Initial\nRisk"), _ch("Control\nType"),
            _ch("Controls in Place / Planned"), _ch("Residual\nRisk"), _ch("Action / Owner / Due"),
        ]

        rows = [header]

        for i, h in enumerate(hazards, 1):
            # Action cell
            if h.action_required:
                owner_name = h.action_owner.get_full_name() if h.action_owner else "Unassigned"
                due        = str(h.action_due_date) if h.action_due_date else "No date"
                action_txt = f"<b>Required</b><br/>{owner_name}<br/>{due}"
            else:
                action_txt = "None required"

            ctrl_abbr = CONTROL_ABBR.get(h.primary_control_type, h.primary_control_type.upper()[:4])
            ctrl_full = h.get_primary_control_type_display()

            row = [
                Paragraph(str(i), STYLES["cell_center"]),
                Paragraph(h.get_category_display(), STYLES["cell"]),
                Paragraph(h.hazard_description, STYLES["cell"]),
                Paragraph(h.potential_harm, STYLES["cell"]),
                Paragraph(h.get_who_might_be_harmed_display(), STYLES["cell"]),
                _risk_cell(h.initial_risk_level, h.initial_risk_score),
                Paragraph(f"<b>{ctrl_abbr}</b><br/><font size='6'>{ctrl_full}</font>", STYLES["cell_center"]),
                Paragraph(h.controls_description.replace("\n", "<br/>"), STYLES["cell"]),
                _risk_cell(h.residual_risk_level, h.residual_risk_score) if h.residual_risk_score else _risk_cell(None, None),
                Paragraph(action_txt, STYLES["cell"]),
            ]
            rows.append(row)

        tbl = Table(rows, colWidths=cws, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header row
            ("BACKGROUND",    (0, 0), (-1, 0), BRAND_DARK),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0), 7.5),
            ("ROWHEIGHT",     (0, 0), (-1, 0), 0.75 * cm),
            # Data rows
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GREY]),
            ("FONTSIZE",       (0, 1), (-1, -1), 7.5),
            ("TOPPADDING",    (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            # Grid
            ("GRID",          (0, 0), (-1, -1), 0.5, MID_GREY),
            ("LINEBELOW",     (0, 0), (-1, 0), 1.5, BRAND_DARK),
        ]))
        story.append(tbl)

    # ── Risk matrix legend ────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
    story.append(Spacer(1, 0.3 * cm))

    legend_items = [
        ("Low (1–4)",       RISK_BG["low"],      RISK_RL["low"]),
        ("Medium (5–9)",    RISK_BG["medium"],   RISK_RL["medium"]),
        ("High (10–16)",    RISK_BG["high"],     RISK_RL["high"]),
        ("Critical (17–25)",RISK_BG["critical"], RISK_RL["critical"]),
    ]
    legend_cells = []
    for label, bg, fg in legend_items:
        p = Paragraph(f'<b>{label}</b>', ParagraphStyle("lg", fontSize=7, fontName="Helvetica-Bold",
                      textColor=fg, alignment=TA_CENTER, leading=9))
        t = Table([[p]], colWidths=[2.8 * cm], rowHeights=[0.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), bg),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("BOX",           (0, 0), (-1, -1), 0.5, MID_GREY),
        ]))
        legend_cells.append(t)

    legend_label = Paragraph("Risk Level Legend:", ParagraphStyle(
        "ll", fontSize=7, fontName="Helvetica-Bold", textColor=LABEL_GREY,
        leading=9, alignment=TA_LEFT,
    ))
    legend_row = Table(
        [[legend_label] + legend_cells],
        colWidths=[2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm],
    )
    legend_row.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 6),
    ]))
    story.append(legend_row)

    doc.build(story)
    return buf.getvalue()
