"""
Appraisal PDF report — ReportLab A4 portrait.
Returns bytes suitable for HttpResponse(content_type="application/pdf").
"""
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)

from .models import AppraisalItem, AppraisalRating


# ── Palette ─────────────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#0e1729")
DARK_BLUE = colors.HexColor("#1a2c52")
GREEN     = colors.HexColor("#16a34a")
BLUE      = colors.HexColor("#3b82f6")
GOLD      = colors.HexColor("#f59e0b")
GREY_BG   = colors.HexColor("#f8f9fb")
GREY_DARK = colors.HexColor("#64748b")
BORDER    = colors.HexColor("#e2e8f0")
WHITE     = colors.white
RED       = colors.HexColor("#ef4444")
AMBER     = colors.HexColor("#f59e0b")
TEAL      = colors.HexColor("#0ea5e9")
VIOLET    = colors.HexColor("#6366f1")

RATING_COLORS = {
    "exceptional":       GREEN,
    "exceeds":           TEAL,
    "meets":             VIOLET,
    "needs_improvement": GOLD,
    "unsatisfactory":    RED,
}

SCORE_BAND_COLOR = {
    (90, 110): GREEN,
    (75,  89): TEAL,
    (60,  74): VIOLET,
    (40,  59): GOLD,
    ( 0,  39): RED,
}


def _score_color(score):
    s = float(score or 0)
    for (lo, hi), c in SCORE_BAND_COLOR.items():
        if lo <= s <= hi:
            return c
    return GREY_DARK


def generate_appraisal_pdf(record) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm,
    )

    base = getSampleStyleSheet()["Normal"]

    def ps(name, size, bold=False, color=NAVY, align=TA_LEFT, leading=None, after=2):
        return ParagraphStyle(
            name, parent=base,
            fontSize=size,
            leading=leading or round(size * 1.4),
            fontName="Helvetica-Bold" if bold else "Helvetica",
            textColor=color,
            alignment=align,
            spaceAfter=after,
        )

    h1        = ps("H1",   18, bold=True, color=NAVY,      after=4)
    h2        = ps("H2",   12, bold=True, color=DARK_BLUE,  after=3)
    h3        = ps("H3",   10, bold=True, color=DARK_BLUE,  after=2)
    label_s   = ps("Lbl",   7, bold=True, color=GREY_DARK, after=1)
    body_s    = ps("Body",  9, color=NAVY, after=2)
    small_s   = ps("Sm",    8, color=GREY_DARK, after=1)
    right_s   = ps("Rt",   10, bold=True, color=NAVY, align=TA_RIGHT, after=2)
    center_s  = ps("Ctr",   9, color=GREY_DARK, align=TA_CENTER, after=2)

    story = []
    cycle = record.cycle
    org   = cycle.organization

    # ── Header ──────────────────────────────────────────────────────────────
    org_name  = org.name if org else "Vigilo"
    hdr_data  = [[
        Paragraph(org_name, ps("OrgN", 13, bold=True, color=NAVY)),
        Paragraph("PERFORMANCE APPRAISAL REPORT",
                  ps("Rpt", 8, bold=True, color=GREY_DARK, align=TA_RIGHT)),
    ]]
    hdr_tbl = Table(hdr_data, colWidths=["65%", "35%"])
    hdr_tbl.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "BOTTOM")]))
    story.append(hdr_tbl)
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK_BLUE, spaceAfter=8))

    # ── Cycle title ─────────────────────────────────────────────────────────
    story.append(Paragraph(cycle.name, h1))
    story.append(Spacer(1, 2*mm))

    # ── Meta grid ───────────────────────────────────────────────────────────
    def cell(lbl, val):
        return [Paragraph(lbl, label_s), Paragraph(str(val), body_s)]

    reviewer_name = record.reviewer.full_name if record.reviewer else "—"
    meta = [
        [cell("EMPLOYEE",  record.employee.full_name),
         cell("ROLE",      record.employee.get_role_display()),
         cell("REVIEWER",  reviewer_name)],
        [cell("PERIOD",    f"{cycle.start_date.strftime('%d %b %Y')} – {cycle.end_date.strftime('%d %b %Y')}"),
         cell("CYCLE",     cycle.get_period_display()),
         cell("REPORT DATE", record.updated_at.strftime("%d %b %Y"))],
    ]
    meta_tbl = Table(meta, colWidths=["33%", "33%", "34%"])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), GREY_BG),
        ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("RIGHTPADDING",  (0,0), (-1,-1), 7),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Overall score banner ─────────────────────────────────────────────────
    if record.overall_score is not None:
        score_val   = float(record.overall_score)
        score_color = _score_color(score_val)
        rating_lbl  = record.get_overall_rating_display() or "—"

        banner_data = [[
            [Paragraph("OVERALL SCORE", label_s),
             Paragraph(f"{score_val:.1f}%",
                       ps("Score", 28, bold=True, color=score_color, leading=34))],
            [Paragraph("RATING", label_s),
             Paragraph(rating_lbl,
                       ps("Rtng", 16, bold=True, color=score_color, leading=22))],
            [Paragraph("STATUS", label_s),
             Paragraph(record.get_status_display(), body_s)],
        ]]
        banner_tbl = Table(banner_data, colWidths=["30%", "40%", "30%"])
        banner_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
            ("BOX",           (0,0), (-1,-1), 1.0, score_color),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("RIGHTPADDING",  (0,0), (-1,-1), 10),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ]))
        story.append(banner_tbl)
        story.append(Spacer(1, 6*mm))

    # ── Category + item ratings ──────────────────────────────────────────────
    categories    = cycle.categories.all()
    approved_items = list(
        AppraisalItem.objects
        .filter(record=record, approved_by_manager=True)
        .select_related("category")
        .order_by("category__order", "created_at")
    )
    ratings_map = {r.item_id: r for r in AppraisalRating.objects.filter(record=record)}

    for cat in categories:
        cat_items = [i for i in approved_items if i.category_id == cat.id]
        if not cat_items:
            continue

        # Category header
        cat_hdr = Table(
            [[Paragraph(cat.name, h2),
              Paragraph(f"Weight: {cat.weight}%",
                        ps("CW", 9, color=GREY_DARK, align=TA_RIGHT))]],
            colWidths=["75%", "25%"]
        )
        cat_hdr.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), DARK_BLUE),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("RIGHTPADDING",  (0,0), (-1,-1), 8),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TEXTCOLOR",     (0,0), (-1,-1), WHITE),
        ]))
        story.append(cat_hdr)

        # Items table header row
        item_rows = [[
            Paragraph("Goal / Competency", ps("ITH", 8, bold=True, color=GREY_DARK)),
            Paragraph("Type",              ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
            Paragraph("Target",            ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
            Paragraph("Actual",            ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
            Paragraph("Self",              ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
            Paragraph("Manager",           ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
            Paragraph("Wt%",              ps("ITH", 8, bold=True, color=GREY_DARK, align=TA_CENTER)),
        ]]

        for item in cat_items:
            r_obj = ratings_map.get(item.pk)
            self_r = str(r_obj.self_rating) + "/5"    if r_obj and r_obj.self_rating    else "—"
            mgr_r  = str(r_obj.manager_rating) + "/5" if r_obj and r_obj.manager_rating else "—"
            actual = str(r_obj.actual_value) + (f" {item.target_unit}" if item.target_unit else "") \
                     if r_obj and r_obj.actual_value is not None else "—"
            target = str(item.target_value) + (f" {item.target_unit}" if item.target_unit else "") \
                     if item.target_value else "—"

            # Highlight gap > 1
            mgr_color = NAVY
            if r_obj and r_obj.self_rating and r_obj.manager_rating:
                if abs(r_obj.manager_rating - r_obj.self_rating) > 1:
                    mgr_color = colors.HexColor("#d97706")

            item_rows.append([
                [Paragraph(item.title, ps("IT", 8, color=NAVY)),
                 Paragraph(item.get_goal_type_display(),
                           ps("GT", 7, color=GREY_DARK)) if item.goal_type == AppraisalItem.GOAL_SELF_SET else Paragraph("", small_s)],
                Paragraph(item.get_item_type_display(), center_s),
                Paragraph(target, center_s),
                Paragraph(actual, center_s),
                Paragraph(self_r,  ps("SR", 9, color=GREY_DARK, align=TA_CENTER)),
                Paragraph(mgr_r,   ps("MR", 9, bold=True, color=mgr_color, align=TA_CENTER)),
                Paragraph(f"{item.weight:.0f}%", center_s),
            ])

        item_tbl = Table(
            item_rows,
            colWidths=["38%", "12%", "10%", "10%", "8%", "10%", "7%"],
        )
        row_styles = [
            ("BACKGROUND",    (0,0), (-1,0),  GREY_BG),
            ("BOX",           (0,0), (-1,-1), 0.5, BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ]
        # Zebra rows
        for idx in range(1, len(item_rows)):
            if idx % 2 == 0:
                row_styles.append(("BACKGROUND", (0, idx), (-1, idx), GREY_BG))
        item_tbl.setStyle(TableStyle(row_styles))
        story.append(item_tbl)
        story.append(Spacer(1, 4*mm))

    # ── Manager summary ──────────────────────────────────────────────────────
    if record.manager_summary:
        story.append(KeepTogether([
            Paragraph("Manager Summary", h2),
            HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4),
            Paragraph(record.manager_summary, body_s),
            Spacer(1, 4*mm),
        ]))

    # ── Development plan ─────────────────────────────────────────────────────
    if record.development_plan:
        story.append(KeepTogether([
            Paragraph("Development Plan", h2),
            HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=4),
            Paragraph(record.development_plan, body_s),
            Spacer(1, 4*mm),
        ]))

    # ── Acknowledgment section ───────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))

    ack_data = [[
        [Paragraph("Employee Acknowledgment", label_s),
         Paragraph(
             f"Acknowledged on {record.acknowledged_at.strftime('%d %b %Y at %H:%M')}"
             if record.acknowledged_at else "Pending acknowledgment",
             ps("AckV", 9, color=GREEN if record.acknowledged_at else GREY_DARK)
         )],
        [Paragraph("Reviewed by", label_s),
         Paragraph(reviewer_name, body_s)],
    ]]
    ack_tbl = Table(ack_data, colWidths=["50%", "50%"])
    ack_tbl.setStyle(TableStyle([
        ("INNERGRID",     (0,0), (-1,-1), 0.5, BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(ack_tbl)

    # ── Footer note ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Generated by Vigilo · {org_name} · Confidential",
        ps("Ftr", 7, color=GREY_DARK, align=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()
