# observations/pdf_report.py
"""
Generate a single-observation PDF report using ReportLab.
"""
from __future__ import annotations

from io import BytesIO
from datetime import datetime

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from core.logo_utils import get_logo_for_pdf

# ── Colour palette ────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1a2c52")
BRAND_ORANGE = colors.HexColor("#f97316")
SEVERITY_COLORS = {
    "HIGH":   colors.HexColor("#dc3545"),
    "MEDIUM": colors.HexColor("#fd7e14"),
    "LOW":    colors.HexColor("#198754"),
}
STATUS_COLORS = {
    "OPEN":                  colors.HexColor("#6c757d"),
    "IN_PROGRESS":           colors.HexColor("#0d6efd"),
    "AWAITING_VERIFICATION": colors.HexColor("#ffc107"),
    "CLOSED":                colors.HexColor("#198754"),
}
LIGHT_GREY  = colors.HexColor("#f8f9fb")
MID_GREY    = colors.HexColor("#dee2e6")
LABEL_GREY  = colors.HexColor("#6c757d")

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm


def _styles():
    base = getSampleStyleSheet()
    return {
        "org_name": ParagraphStyle(
            "org_name",
            fontSize=13, fontName="Helvetica-Bold",
            textColor=BRAND_DARK, leading=16,
        ),
        "report_title": ParagraphStyle(
            "report_title",
            fontSize=9, fontName="Helvetica",
            textColor=LABEL_GREY, leading=12,
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontSize=9, fontName="Helvetica-Bold",
            textColor=BRAND_DARK, leading=12,
            spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "label",
            fontSize=7.5, fontName="Helvetica-Bold",
            textColor=LABEL_GREY, leading=10,
        ),
        "value": ParagraphStyle(
            "value",
            fontSize=9, fontName="Helvetica",
            textColor=colors.HexColor("#212529"), leading=13,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=9, fontName="Helvetica",
            textColor=colors.HexColor("#343a40"), leading=14,
            spaceAfter=0,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontSize=7, fontName="Helvetica",
            textColor=LABEL_GREY, leading=10,
        ),
        "photo_caption": ParagraphStyle(
            "photo_caption",
            fontSize=7.5, fontName="Helvetica-Bold",
            textColor=LABEL_GREY, alignment=TA_CENTER, leading=10,
        ),
        "obs_id": ParagraphStyle(
            "obs_id",
            fontSize=22, fontName="Helvetica-Bold",
            textColor=BRAND_DARK, leading=26,
        ),
        "obs_title": ParagraphStyle(
            "obs_title",
            fontSize=14, fontName="Helvetica-Bold",
            textColor=colors.HexColor("#212529"), leading=18,
        ),
    }


def _badge_cell(text, bg_color, text_color=colors.white):
    """Return a single-cell Table that renders as a coloured badge."""
    t = Table([[Paragraph(
        f'<font name="Helvetica-Bold" size="8" color="#{text_color.hexval()[2:]}">{text}</font>',
        ParagraphStyle("b", fontSize=8, fontName="Helvetica-Bold",
                       textColor=text_color, leading=10, alignment=TA_CENTER),
    )]], colWidths=[3.5 * cm], rowHeights=[0.55 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("ROUNDEDCORNERS", [4]),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 2),
    ]))
    return t


def _photo_image(field, max_w, max_h):
    """Return a ReportLab Image from a Django ImageField, or None."""
    if not field or not field.name:
        return None
    try:
        from PIL import Image as PILImage
        from io import BytesIO as _BytesIO

        with field.open("rb") as f:
            raw = f.read()
        pil = PILImage.open(_BytesIO(raw))
        orig_w, orig_h = pil.size
        ratio = min(max_w / orig_w, max_h / orig_h)
        return Image(_BytesIO(raw), width=orig_w * ratio, height=orig_h * ratio)
    except Exception:
        return None


def generate_observation_pdf(observation) -> bytes:
    """Return PDF bytes for a single Observation."""

    buf = BytesIO()
    st  = _styles()
    org = observation.organization

    # ── Page template with header/footer ─────────────────────────────────────
    generated_at = timezone.localtime(timezone.now()).strftime("%d %b %Y  %H:%M")

    def _draw_header_footer(canvas, doc):
        canvas.saveState()
        usable_w = PAGE_W - 2 * MARGIN

        # ── TOP HEADER BAR ──
        canvas.setFillColor(BRAND_DARK)
        canvas.rect(0, PAGE_H - 2.4 * cm, PAGE_W, 2.4 * cm, fill=1, stroke=0)

        # Logo (left)
        logo_img = get_logo_for_pdf(org, 3.5 * cm, 1.6 * cm)
        logo_x = MARGIN
        if logo_img:
            logo_img.drawOn(canvas, logo_x, PAGE_H - 2.2 * cm)
            text_x = logo_x + logo_img.drawWidth + 0.4 * cm
        else:
            # orange square fallback
            canvas.setFillColor(BRAND_ORANGE)
            canvas.roundRect(logo_x, PAGE_H - 2.05 * cm, 1.4 * cm, 1.4 * cm, 4, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 18)
            canvas.drawCentredString(logo_x + 0.7 * cm, PAGE_H - 1.55 * cm, "V")
            text_x = logo_x + 1.8 * cm

        # Org name + report type
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(text_x, PAGE_H - 1.25 * cm,
                          org.name if org else "Safety Observation Report")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#adb5bd"))
        canvas.drawString(text_x, PAGE_H - 1.75 * cm, "Safety Observation Report")

        # Obs # (right)
        canvas.setFillColor(BRAND_ORANGE)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.3 * cm,
                               f"#{observation.pk:04d}")

        # ── FOOTER ──
        canvas.setFillColor(MID_GREY)
        canvas.rect(0, 0, PAGE_W, 1.1 * cm, fill=1, stroke=0)
        canvas.setFillColor(LABEL_GREY)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(MARGIN, 0.42 * cm,
                          "Generated by Vigilo Safety Platform · safety-desk.com")
        canvas.drawRightString(PAGE_W - MARGIN, 0.42 * cm,
                               f"Generated: {generated_at}  ·  Page {doc.page}")

        canvas.restoreState()

    frame = Frame(
        MARGIN, 1.4 * cm,
        PAGE_W - 2 * MARGIN, PAGE_H - 2.4 * cm - 1.4 * cm,
        leftPadding=0, rightPadding=0, topPadding=0.3 * cm, bottomPadding=0,
    )
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.4 * cm, bottomMargin=1.4 * cm,
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame],
                                       onPage=_draw_header_footer)])

    story = []
    usable_w = PAGE_W - 2 * MARGIN

    # ── SECTION 1 — Title + badges ────────────────────────────────────────────
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(observation.title, st["obs_title"]))
    story.append(Spacer(1, 0.35 * cm))

    sev_color    = SEVERITY_COLORS.get(observation.severity, LABEL_GREY)
    status_color = STATUS_COLORS.get(observation.status, LABEL_GREY)
    sev_label    = observation.get_severity_display() + " Severity"
    status_label = observation.get_status_display()

    # For MEDIUM status badge use dark text (yellow bg)
    status_txt = colors.HexColor("#212529") if observation.status == "AWAITING_VERIFICATION" else colors.white

    badge_row = Table(
        [[_badge_cell(sev_label, sev_color),
          _badge_cell(status_label, status_color, status_txt),
          ""]],
        colWidths=[3.7 * cm, 4.5 * cm, usable_w - 8.2 * cm],
    )
    badge_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(badge_row)
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=MID_GREY))
    story.append(Spacer(1, 0.4 * cm))

    # ── SECTION 2 — Key info grid ─────────────────────────────────────────────
    story.append(Paragraph("OBSERVATION DETAILS", st["section_heading"]))

    def _lv(label, value):
        return [
            Paragraph(label, st["label"]),
            Paragraph(str(value) if value else "—", st["value"]),
        ]

    col1 = usable_w * 0.5 - 0.3 * cm
    col2 = usable_w * 0.5 - 0.3 * cm
    lbl_w = 3.2 * cm
    val1  = col1 - lbl_w
    val2  = col2 - lbl_w

    date_obs = observation.date_observed
    if date_obs:
        date_obs_str = timezone.localtime(date_obs).strftime("%d %b %Y  %H:%M")
    else:
        date_obs_str = "—"

    date_closed_str = "—"
    if observation.date_closed:
        date_closed_str = timezone.localtime(observation.date_closed).strftime("%d %b %Y")

    observer_name    = observation.observer.get_full_name()    if observation.observer    else "—"
    assigned_name    = observation.assigned_to.get_full_name() if observation.assigned_to else "Not assigned"
    target_date_str  = str(observation.target_date) if observation.target_date else "—"
    location_str     = str(observation.location)

    grid_data = [
        [Paragraph("LOCATION",      st["label"]), Paragraph(location_str,    st["value"]),
         Paragraph("DATE OBSERVED", st["label"]), Paragraph(date_obs_str,    st["value"])],
        [Paragraph("OBSERVER",      st["label"]), Paragraph(observer_name,   st["value"]),
         Paragraph("ASSIGNED TO",   st["label"]), Paragraph(assigned_name,   st["value"])],
        [Paragraph("TARGET DATE",   st["label"]), Paragraph(target_date_str, st["value"]),
         Paragraph("CLOSED ON",     st["label"]), Paragraph(date_closed_str, st["value"])],
    ]

    grid = Table(grid_data,
                 colWidths=[lbl_w, val1, lbl_w, val2],
                 rowHeights=[0.85 * cm] * len(grid_data))
    grid.setStyle(TableStyle([
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [LIGHT_GREY, colors.white]),
        ("LINEBELOW",    (0, 0), (-1, -1), 0.5, MID_GREY),
        ("LINEAFTER",    (1, 0), (1, -1), 0.5, MID_GREY),   # centre divider
    ]))
    story.append(grid)
    story.append(Spacer(1, 0.6 * cm))

    # ── SECTION 3 — Description ───────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("DESCRIPTION", st["section_heading"]))
    desc_text = (observation.description or "").replace("\n", "<br/>")
    story.append(Paragraph(desc_text, st["body"]))
    story.append(Spacer(1, 0.6 * cm))

    # ── SECTION 4 — Rectification ─────────────────────────────────────────────
    if observation.rectification_details or observation.verification_comment:
        story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("RECTIFICATION", st["section_heading"]))
        if observation.rectification_details:
            rect_text = observation.rectification_details.replace("\n", "<br/>")
            story.append(Paragraph(rect_text, st["body"]))
            story.append(Spacer(1, 0.35 * cm))
        if observation.verification_comment:
            story.append(Paragraph("VERIFICATION COMMENT", st["section_heading"]))
            vc_text = observation.verification_comment.replace("\n", "<br/>")
            story.append(Paragraph(vc_text, st["body"]))
        story.append(Spacer(1, 0.6 * cm))

    # ── SECTION 5 — Photos ────────────────────────────────────────────────────
    has_before = bool(observation.photo_before and observation.photo_before.name)
    has_after  = bool(observation.photo_after  and observation.photo_after.name)

    if has_before or has_after:
        story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph("PHOTOS", st["section_heading"]))
        story.append(Spacer(1, 0.25 * cm))

        max_photo_w = (usable_w - 0.6 * cm) / 2 if (has_before and has_after) else usable_w
        max_photo_h = 8 * cm

        before_img = _photo_image(observation.photo_before, max_photo_w, max_photo_h) if has_before else None
        after_img  = _photo_image(observation.photo_after,  max_photo_w, max_photo_h) if has_after  else None

        if has_before and has_after:
            photo_table = Table(
                [[before_img or "", after_img or ""],
                 [Paragraph("BEFORE RECTIFICATION", st["photo_caption"]),
                  Paragraph("AFTER RECTIFICATION",  st["photo_caption"])]],
                colWidths=[max_photo_w, max_photo_w],
            )
        elif has_before:
            photo_table = Table(
                [[before_img or ""],
                 [Paragraph("BEFORE RECTIFICATION", st["photo_caption"])]],
                colWidths=[max_photo_w],
            )
        else:
            photo_table = Table(
                [[after_img or ""],
                 [Paragraph("AFTER RECTIFICATION", st["photo_caption"])]],
                colWidths=[max_photo_w],
            )

        photo_table.setStyle(TableStyle([
            ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
            ("VALIGN",       (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ]))
        story.append(photo_table)

    doc.build(story)
    return buf.getvalue()
