"""
audit_export/pdf_sections.py
ISO 45001 Evidence Pack — PDF generators for each section + master cover.
Each function returns bytes (the complete PDF).
"""
from __future__ import annotations

from io import BytesIO
from datetime import date as date_type

from django.utils import timezone as dj_tz

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)

# ── Palette ───────────────────────────────────────────────────────────────────
DARK    = colors.HexColor("#1a2c52")
INDIGO  = colors.HexColor("#4f46e5")
GREEN   = colors.HexColor("#16a34a")
RED     = colors.HexColor("#dc2626")
ORANGE  = colors.HexColor("#ea580c")
AMBER   = colors.HexColor("#ca8a04")
GREY_BG = colors.HexColor("#f8f9fb")
BORDER  = colors.HexColor("#e2e8f0")
MUTED   = colors.HexColor("#94a3b8")
TEXT    = colors.HexColor("#1e293b")
WHITE   = colors.white

RISK_CLR = {
    "critical": RED,
    "high":     ORANGE,
    "medium":   AMBER,
    "low":      GREEN,
}
RISK_BG_CLR = {
    "critical": colors.HexColor("#fee2e2"),
    "high":     colors.HexColor("#ffedd5"),
    "medium":   colors.HexColor("#fef9c3"),
    "low":      colors.HexColor("#dcfce7"),
}
STATUS_CLR = {
    "complied":        GREEN,
    "overdue":         RED,
    "pending":         AMBER,
    "not_applicable":  MUTED,
}


# ── Shared helpers ────────────────────────────────────────────────────────────

def _S():
    """Return dict of named ParagraphStyles."""
    return {
        "cover_h":  ParagraphStyle("ch",  fontSize=22, leading=28, textColor=DARK,   fontName="Helvetica-Bold", alignment=1),
        "cover_sub":ParagraphStyle("cs",  fontSize=11, leading=15, textColor=MUTED,  fontName="Helvetica-Bold", alignment=1),
        "cover_org":ParagraphStyle("co",  fontSize=14, leading=18, textColor=DARK,   fontName="Helvetica-Bold", alignment=1),
        "h1":       ParagraphStyle("h1",  fontSize=13, leading=17, textColor=DARK,   fontName="Helvetica-Bold"),
        "h2":       ParagraphStyle("h2",  fontSize=10, leading=13, textColor=DARK,   fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=2),
        "clause":   ParagraphStyle("cls", fontSize=7,  leading=9,  textColor=INDIGO, fontName="Helvetica-Bold"),
        "label":    ParagraphStyle("lbl", fontSize=7,  leading=9,  textColor=MUTED,  fontName="Helvetica-Bold"),
        "body":     ParagraphStyle("bdy", fontSize=8,  leading=11, textColor=TEXT),
        "small":    ParagraphStyle("sml", fontSize=7,  leading=10, textColor=MUTED),
        "bold":     ParagraphStyle("bld", fontSize=8,  leading=11, textColor=TEXT,   fontName="Helvetica-Bold"),
        "footer":   ParagraphStyle("ftr", fontSize=7,  textColor=MUTED, alignment=1),
        "right":    ParagraphStyle("rt",  fontSize=8,  textColor=MUTED, alignment=2, fontName="Helvetica-Bold"),
        "center":   ParagraphStyle("ctr", fontSize=8,  textColor=TEXT,  alignment=1),
        "tag":      ParagraphStyle("tg",  fontSize=7,  leading=9,  textColor=WHITE,  fontName="Helvetica-Bold", alignment=1),
    }


def _new_doc(buf):
    return SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
    )


def _section_header(story, s, org_name, doc_ref, clause, title, from_date, to_date):
    hdr = Table(
        [[Paragraph(org_name, s["h1"]), Paragraph(doc_ref, s["right"])]],
        colWidths=["70%", "30%"],
    )
    hdr.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK, spaceAfter=5))
    story.append(Paragraph(clause, s["clause"]))
    story.append(Paragraph(title, s["h2"]))
    story.append(Paragraph(
        f"Coverage: {from_date.strftime('%d %b %Y')} \u2013 {to_date.strftime('%d %b %Y')}",
        s["small"],
    ))
    story.append(Spacer(1, 4 * mm))


def _section_footer(story, s, org_name):
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=6))
    story.append(Paragraph(
        f"Vigilo Safety Platform \u00b7 {org_name} \u00b7 ISO 45001 Evidence Pack \u00b7 Confidential",
        s["footer"],
    ))


def _tbl_style():
    return [
        ("BACKGROUND",     (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR",      (0, 0), (-1, 0), WHITE),
        ("FONTNAME",       (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 0), (-1, 0), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("BOX",            (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 4),
        ("LEFTPADDING",    (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 5),
        ("VALIGN",         (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE",       (0, 1), (-1, -1), 7),
    ]


def _stat_strip(story, items):
    """items = [(value, label, color), ...]"""
    n = len(items)
    cells = []
    for value, label, clr in items:
        cells.append([
            Paragraph(
                str(value),
                ParagraphStyle("sv", fontSize=15, fontName="Helvetica-Bold",
                               textColor=clr or DARK, leading=19, alignment=1),
            ),
            Paragraph(
                label,
                ParagraphStyle("sl", fontSize=6, textColor=MUTED,
                               fontName="Helvetica-Bold", alignment=1, leading=8),
            ),
        ])
    tbl = Table([cells], colWidths=[f"{100 // n}%"] * n)
    tbl.setStyle(TableStyle([
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
        ("BACKGROUND",    (0, 0), (-1, -1), GREY_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5 * mm))


def _no_data(story, s, msg="No records found for the selected period."):
    story.append(Paragraph(msg, s["small"]))
    story.append(Spacer(1, 3 * mm))


def _build(doc, story, buf):
    doc.build(story)
    buf.seek(0)
    return buf.read()


# ── Cover / Master Index ──────────────────────────────────────────────────────

def generate_cover(org, from_date: date_type, to_date: date_type) -> bytes:
    from hira.models import HazardRegister, Hazard
    from compliance.models import ComplianceItem
    from training.models import AssessmentAttempt
    from observations.models import Observation
    from permits.models import Permit
    from inspections.models import Inspection
    from incidents.models import Incident
    from actions.models import CorrectiveAction
    from core.logo_utils import get_logo_for_pdf

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 45 * mm))

    # Logo
    logo = get_logo_for_pdf(org, 70 * mm, 30 * mm)
    if logo:
        logo_tbl = Table([[logo]], colWidths=["100%"])
        logo_tbl.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        story.append(logo_tbl)
        story.append(Spacer(1, 8 * mm))

    story.append(Paragraph(org.name, s["cover_org"]))
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="60%", thickness=2, color=GREEN, hAlign="CENTER", spaceAfter=10))
    story.append(Paragraph("ISO 45001:2018", s["cover_h"]))
    story.append(Paragraph("Evidence Pack", s["cover_h"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Coverage Period: {from_date.strftime('%d %b %Y')} \u2013 {to_date.strftime('%d %b %Y')}",
        s["cover_sub"],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f"Generated: {dj_tz.now().strftime('%d %b %Y at %H:%M UTC')}",
        s["cover_sub"],
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="60%", thickness=1, color=BORDER, hAlign="CENTER"))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Generated by Vigilo Safety Platform \u00b7 Confidential",
        ParagraphStyle("ci", fontSize=8, textColor=MUTED, alignment=1),
    ))
    story.append(PageBreak())

    # ── CLAUSE INDEX TABLE ────────────────────────────────────────────────────
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK, spaceAfter=6))
    story.append(Paragraph("ISO 45001:2018 \u2014 Evidence Index", s["h2"]))
    story.append(Paragraph(
        f"The following sections contain auditable evidence mapped to ISO 45001:2018 clauses "
        f"for {org.name}.",
        s["small"],
    ))
    story.append(Spacer(1, 4 * mm))

    # Fetch counts for evidence status column
    hira_count = HazardRegister.objects.filter(
        organization=org,
        assessment_date__gte=from_date, assessment_date__lte=to_date,
    ).count()
    compliance_count = ComplianceItem.objects.filter(organization=org).count()
    training_count = AssessmentAttempt.objects.filter(
        organization=org,
        submitted_at__date__gte=from_date, submitted_at__date__lte=to_date,
    ).count()
    obs_count = Observation.objects.filter(
        organization=org,
        date_observed__date__gte=from_date, date_observed__date__lte=to_date,
    ).count()
    permit_count = Permit.objects.filter(
        organization=org,
        created_at__date__gte=from_date, created_at__date__lte=to_date,
    ).count()
    insp_count = Inspection.objects.filter(
        organization=org,
        conducted_date__gte=from_date, conducted_date__lte=to_date,
        status="completed",
    ).count()
    incident_count = Incident.objects.filter(
        organization=org,
        date_occurred__date__gte=from_date, date_occurred__date__lte=to_date,
    ).count()
    action_count = CorrectiveAction.objects.filter(
        organization=org,
        created_at__date__gte=from_date, created_at__date__lte=to_date,
    ).count()

    def _evidence_tag(count, label):
        if count > 0:
            return Paragraph(
                f"\u2713 {count} {label}",
                ParagraphStyle("ev", fontSize=7, fontName="Helvetica-Bold",
                               textColor=GREEN, leading=9),
            )
        return Paragraph(
            "\u26a0 No records",
            ParagraphStyle("ev0", fontSize=7, fontName="Helvetica-Bold",
                           textColor=AMBER, leading=9),
        )

    INDEX_ROWS = [
        ["File", "ISO 45001 Clause", "Evidence Section", "Status"],
        ["01", "Clause 4\nContext",
         "Organisation profile, user roster\nand active locations",
         Paragraph("\u2713 Always included", ParagraphStyle("inc", fontSize=7, fontName="Helvetica-Bold", textColor=GREEN, leading=9))],
        ["02", "Clause 6.1\nHazard ID & Risk Assessment",
         "HIRA registers, hazard inventory\nand risk level breakdown",
         _evidence_tag(hira_count, "registers")],
        ["03", "Clause 6.1.3\nLegal Requirements",
         "Full legal compliance register\nwith status and evidence notes",
         _evidence_tag(compliance_count, "items")],
        ["04", "Clause 7.2\nCompetence",
         "Skills proficiency matrix\nand training assessment records",
         _evidence_tag(training_count, "attempts")],
        ["05", "Clause 8.1\nOperational Control",
         "Safety observations log\nand Permit to Work register",
         _evidence_tag(obs_count + permit_count, "records")],
        ["06", "Clause 9.2\nInternal Audit",
         "Completed safety inspections\nwith scores and findings",
         _evidence_tag(insp_count, "inspections")],
        ["07", "Clause 9.1\nPerformance Measurement",
         "Monthly LTIFR / TRIFR metrics\nand KPI summary",
         _evidence_tag(incident_count, "incidents")],
        ["08", "Clause 10.2\nIncident Investigation",
         "Incident register with severity\nbreakdown and RCA status",
         _evidence_tag(incident_count, "incidents")],
        ["09", "Clause 10.2\nCorrective Action",
         "Corrective action register\nwith closure rate analysis",
         _evidence_tag(action_count, "actions")],
    ]

    idx_tbl = Table(INDEX_ROWS, colWidths=[10 * mm, 42 * mm, 80 * mm, 42 * mm], repeatRows=1)
    idx_style = _tbl_style() + [
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("ALIGN",          (0, 0), (0, -1), "CENTER"),
        ("FONTNAME",       (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",       (0, 1), (0, -1), 8),
        ("TEXTCOLOR",      (0, 1), (0, -1), DARK),
    ]
    idx_tbl.setStyle(TableStyle(idx_style))
    story.append(idx_tbl)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "Note: All evidence is organisation-scoped and filtered to the coverage period above. "
        "Compliance register (Section 03) and skill proficiencies (Section 04) show the complete "
        "register as these are cumulative records.",
        s["small"],
    ))

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 01 — Organisation Context (Clause 4) ─────────────────────────────

def generate_section_01_org(org, from_date: date_type, to_date: date_type) -> bytes:
    from django.contrib.auth import get_user_model
    User = get_user_model()

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-01",
        "ISO 45001:2018 — CLAUSE 4: CONTEXT OF THE ORGANISATION",
        "Organisation Profile & Team Roster",
        from_date, to_date,
    )

    users = User.objects.filter(organization=org, is_active=True).order_by("role", "full_name")
    total = users.count()
    managers = users.filter(role__in=["manager", "safety_manager"]).count()
    observers = users.filter(role__in=["observer", "action_owner"]).count()
    contractors = users.filter(role="contractor").count()

    _stat_strip(story, [
        (total,       "TOTAL ACTIVE USERS",    DARK),
        (managers,    "MANAGERS / SAFETY MGR", INDIGO),
        (observers,   "OBSERVERS / ACT. OWNERS", GREEN),
        (contractors, "CONTRACTORS",           AMBER),
    ])

    # Org details block
    story.append(Paragraph("Organisation Details", s["h2"]))
    org_rows = [
        [Paragraph("Organisation Name", s["label"]),    Paragraph(org.name, s["bold"])],
        [Paragraph("Pack Generated On", s["label"]),    Paragraph(dj_tz.now().strftime("%d %b %Y, %H:%M UTC"), s["body"])],
        [Paragraph("Coverage Period", s["label"]),      Paragraph(f"{from_date.strftime('%d %b %Y')} \u2013 {to_date.strftime('%d %b %Y')}", s["body"])],
    ]
    org_tbl = Table(org_rows, colWidths=[50 * mm, 124 * mm])
    org_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREY_BG),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
    ]))
    story.append(org_tbl)
    story.append(Spacer(1, 5 * mm))

    # Users table
    story.append(Paragraph("Team Members", s["h2"]))
    ROLE_LABELS = {
        "manager":        "Manager",
        "safety_manager": "Safety Manager",
        "action_owner":   "Action Owner",
        "observer":       "Observer",
        "contractor":     "Contractor",
    }
    rows = [["Name", "Role", "Email / Employee ID"]]
    for u in users:
        identifier = u.email or (f"Emp ID: {u.employee_id}" if u.employee_id else "—")
        rows.append([
            Paragraph(u.full_name or "—", s["body"]),
            Paragraph(ROLE_LABELS.get(u.role, u.role), s["body"]),
            Paragraph(str(identifier), s["small"]),
        ])

    if len(rows) > 1:
        tbl = Table(rows, colWidths=[60 * mm, 42 * mm, 72 * mm], repeatRows=1)
        tbl.setStyle(TableStyle(_tbl_style()))
        story.append(tbl)
    else:
        _no_data(story, s)

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 02 — HIRA (Clause 6.1) ───────────────────────────────────────────

def generate_section_02_hira(org, from_date: date_type, to_date: date_type) -> bytes:
    from hira.models import HazardRegister, Hazard

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-02",
        "ISO 45001:2018 — CLAUSE 6.1: HAZARD IDENTIFICATION & RISK ASSESSMENT",
        "HIRA Register",
        from_date, to_date,
    )

    registers = HazardRegister.objects.filter(
        organization=org,
        assessment_date__gte=from_date,
        assessment_date__lte=to_date,
    ).prefetch_related("hazards").order_by("-assessment_date")

    reg_ids = list(registers.values_list("id", flat=True))
    hazards = list(Hazard.objects.filter(register_id__in=reg_ids).select_related("register", "action_owner"))

    approved = sum(1 for r in registers if r.status == "approved")
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for h in hazards:
        lvl = h.effective_risk_level
        if lvl in risk_counts:
            risk_counts[lvl] += 1

    _stat_strip(story, [
        (registers.count(),                             "REGISTERS",          DARK),
        (approved,                                      "APPROVED",           GREEN),
        (len(hazards),                                  "TOTAL HAZARDS",      AMBER),
        (risk_counts["critical"] + risk_counts["high"], "CRITICAL / HIGH",    RED),
    ])

    # Register summary
    story.append(Paragraph("HIRA Register Summary", s["h2"]))
    STATUS_LABELS = {
        "draft": "Draft", "under_review": "Under Review",
        "approved": "Approved", "expired": "Expired",
    }
    rows = [["#", "Register Title", "Activity / Scope", "Status", "Haz.", "Highest Risk", "Assessed"]]
    for i, reg in enumerate(registers, 1):
        highest = reg.highest_risk_level or ""
        rows.append([
            Paragraph(str(i), s["small"]),
            Paragraph(reg.title[:50], s["body"]),
            Paragraph((reg.activity or "—")[:40], s["small"]),
            Paragraph(STATUS_LABELS.get(reg.status, reg.status), s["body"]),
            Paragraph(str(reg.hazards.count()), s["center"]),
            Paragraph(
                highest.upper() if highest else "—",
                ParagraphStyle("rl", fontSize=7, fontName="Helvetica-Bold",
                               textColor=RISK_CLR.get(highest, TEXT), alignment=1),
            ),
            Paragraph(reg.assessment_date.strftime("%d %b %Y"), s["small"]),
        ])

    if len(rows) > 1:
        col_w = [8 * mm, 52 * mm, 38 * mm, 22 * mm, 10 * mm, 20 * mm, 24 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, reg in enumerate(registers, 1):
            lvl = reg.highest_risk_level
            if lvl in RISK_BG_CLR:
                style.append(("BACKGROUND", (5, idx), (5, idx), RISK_BG_CLR[lvl]))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s)

    story.append(Spacer(1, 6 * mm))

    # Hazard detail table
    story.append(Paragraph("Hazard Detail Register", s["h2"]))
    rows2 = [["Category", "Hazard Description", "Potential Harm", "Initial", "Control Type", "Residual"]]
    for h in hazards:
        il = h.initial_risk_level or ""
        rl = h.residual_risk_level or ""
        rows2.append([
            Paragraph(h.get_category_display(), s["small"]),
            Paragraph(h.hazard_description[:80], s["body"]),
            Paragraph(h.potential_harm[:60], s["small"]),
            Paragraph(
                f"{h.initial_risk_score}\n{il.upper()}" if il else "—",
                ParagraphStyle("ir", fontSize=7, fontName="Helvetica-Bold",
                               textColor=RISK_CLR.get(il, TEXT), alignment=1),
            ),
            Paragraph(h.get_primary_control_type_display() if h.primary_control_type else "—", s["small"]),
            Paragraph(
                f"{h.residual_risk_score}\n{rl.upper()}" if rl else "N/A",
                ParagraphStyle("rr", fontSize=7, fontName="Helvetica-Bold",
                               textColor=RISK_CLR.get(rl, MUTED), alignment=1),
            ),
        ])

    if len(rows2) > 1:
        col_w2 = [24 * mm, 56 * mm, 42 * mm, 14 * mm, 22 * mm, 16 * mm]
        tbl2 = Table(rows2, colWidths=col_w2, repeatRows=1)
        style2 = _tbl_style()
        for idx, h in enumerate(hazards, 1):
            il = h.initial_risk_level
            rl = h.residual_risk_level
            if il in RISK_BG_CLR:
                style2.append(("BACKGROUND", (3, idx), (3, idx), RISK_BG_CLR[il]))
            if rl in RISK_BG_CLR:
                style2.append(("BACKGROUND", (5, idx), (5, idx), RISK_BG_CLR[rl]))
        tbl2.setStyle(TableStyle(style2))
        story.append(tbl2)
    else:
        _no_data(story, s)

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 03 — Compliance (Clause 6.1.3) ───────────────────────────────────

def generate_section_03_compliance(org, from_date: date_type, to_date: date_type) -> bytes:
    from compliance.models import ComplianceItem

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-03",
        "ISO 45001:2018 — CLAUSE 6.1.3: LEGAL AND OTHER REQUIREMENTS",
        "Legal Compliance Register (Full Register — all items shown)",
        from_date, to_date,
    )

    items = ComplianceItem.objects.filter(organization=org).select_related("assigned_to").order_by("due_date")
    total = items.count()
    complied = items.filter(status="complied").count()
    overdue = items.filter(status="overdue").count()
    pending = items.filter(status="pending").count()
    score = round(complied / total * 100) if total else 0

    _stat_strip(story, [
        (total,   "TOTAL ITEMS",    DARK),
        (complied, "COMPLIED",      GREEN),
        (overdue,  "OVERDUE",       RED),
        (f"{score}%", "COMPLIANCE SCORE", GREEN if score >= 80 else (AMBER if score >= 60 else RED)),
    ])

    rows = [["#", "Obligation Title", "Law / Regulation", "Frequency", "Due Date", "Status", "Assigned To"]]
    STATUS_LABELS = {
        "pending": "Pending", "complied": "Complied",
        "overdue": "Overdue", "not_applicable": "N/A",
    }
    FREQ_LABELS = {
        "one_time": "One-time", "monthly": "Monthly",
        "quarterly": "Quarterly", "half_yearly": "Half-yearly", "annual": "Annual",
    }
    for i, item in enumerate(items, 1):
        status_lbl = STATUS_LABELS.get(item.status, item.status)
        clr = STATUS_CLR.get(item.status, TEXT)
        assignee = item.assigned_to.full_name if item.assigned_to else "Unassigned"
        rows.append([
            Paragraph(str(i), s["small"]),
            Paragraph(item.title[:55], s["body"]),
            Paragraph((item.law or "—")[:45], s["small"]),
            Paragraph(FREQ_LABELS.get(item.frequency, item.frequency), s["small"]),
            Paragraph(item.due_date.strftime("%d %b %Y"), s["small"]),
            Paragraph(
                status_lbl,
                ParagraphStyle("st", fontSize=7, fontName="Helvetica-Bold", textColor=clr),
            ),
            Paragraph(assignee[:25], s["small"]),
        ])

    if len(rows) > 1:
        col_w = [8 * mm, 50 * mm, 40 * mm, 18 * mm, 18 * mm, 18 * mm, 22 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, item in enumerate(items, 1):
            bg = {
                "complied":       colors.HexColor("#dcfce7"),
                "overdue":        colors.HexColor("#fee2e2"),
                "pending":        colors.HexColor("#fef9c3"),
                "not_applicable": GREY_BG,
            }.get(item.status, WHITE)
            style.append(("BACKGROUND", (5, idx), (5, idx), bg))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s)

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 04 — Training & Competence (Clause 7.2) ──────────────────────────

def generate_section_04_training(org, from_date: date_type, to_date: date_type) -> bytes:
    from training.models import AssessmentAttempt, SkillProficiency, Skill

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-04",
        "ISO 45001:2018 — CLAUSE 7.2: COMPETENCE",
        "Training Records & Skills Proficiency Matrix",
        from_date, to_date,
    )

    attempts = AssessmentAttempt.objects.filter(
        organization=org,
        submitted_at__date__gte=from_date,
        submitted_at__date__lte=to_date,
    ).select_related("user", "assessment__training_module").order_by("-submitted_at")

    proficiencies = SkillProficiency.objects.filter(
        organization=org,
    ).select_related("user", "skill").order_by("user__full_name", "skill__name")

    total_att = attempts.count()
    passed = attempts.filter(passed=True).count()
    pass_rate = round(passed / total_att * 100) if total_att else 0
    unique_skills = proficiencies.values("skill").distinct().count()

    _stat_strip(story, [
        (total_att,        "ASSESSMENT ATTEMPTS", DARK),
        (passed,           "PASSED",              GREEN),
        (total_att - passed, "FAILED",            RED),
        (f"{pass_rate}%",  "PASS RATE",           GREEN if pass_rate >= 70 else AMBER),
    ])

    # Assessment attempts table
    story.append(Paragraph("Assessment Attempts", s["h2"]))
    rows = [["Date", "Employee", "Training Module", "Score", "Result"]]
    for att in attempts:
        rows.append([
            Paragraph(att.submitted_at.strftime("%d %b %Y"), s["small"]),
            Paragraph(att.user.full_name or att.user.email or "—", s["body"]),
            Paragraph(att.assessment.training_module.title[:50], s["body"]),
            Paragraph(f"{att.score:.1f}%", s["center"]),
            Paragraph(
                "PASS" if att.passed else "FAIL",
                ParagraphStyle("pr", fontSize=7, fontName="Helvetica-Bold",
                               textColor=GREEN if att.passed else RED, alignment=1),
            ),
        ])

    if len(rows) > 1:
        col_w = [22 * mm, 50 * mm, 65 * mm, 18 * mm, 19 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, att in enumerate(attempts, 1):
            bg = colors.HexColor("#dcfce7") if att.passed else colors.HexColor("#fee2e2")
            style.append(("BACKGROUND", (4, idx), (4, idx), bg))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s, "No assessment attempts found for the selected period.")

    story.append(Spacer(1, 6 * mm))

    # Skill proficiency table
    story.append(Paragraph("Current Skill Proficiencies (all staff)", s["h2"]))
    LEVEL_LABELS = {1: "1-Beginner", 2: "2-Basic", 3: "3-Intermediate", 4: "4-Advanced", 5: "5-Expert"}
    rows2 = [["Employee", "Skill", "Category", "Proficiency Level", "Last Assessed"]]
    for p in proficiencies:
        rows2.append([
            Paragraph(p.user.full_name or "—", s["body"]),
            Paragraph(p.skill.name, s["body"]),
            Paragraph(p.skill.category.name if p.skill.category else "—", s["small"]),
            Paragraph(LEVEL_LABELS.get(p.level, str(p.level)), s["body"]),
            Paragraph(p.last_assessed_at.strftime("%d %b %Y"), s["small"]),
        ])

    if len(rows2) > 1:
        col_w2 = [50 * mm, 45 * mm, 30 * mm, 30 * mm, 19 * mm]
        tbl2 = Table(rows2, colWidths=col_w2, repeatRows=1)
        tbl2.setStyle(TableStyle(_tbl_style()))
        story.append(tbl2)
    else:
        _no_data(story, s, "No skill proficiency records found.")

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 05 — Operations (Clause 8.1) ─────────────────────────────────────

def generate_section_05_operations(org, from_date: date_type, to_date: date_type) -> bytes:
    from observations.models import Observation
    from permits.models import Permit

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-05",
        "ISO 45001:2018 — CLAUSE 8.1: OPERATIONAL PLANNING AND CONTROL",
        "Safety Observations & Permit to Work Log",
        from_date, to_date,
    )

    observations = Observation.objects.filter(
        organization=org,
        date_observed__date__gte=from_date,
        date_observed__date__lte=to_date,
    ).select_related("location", "observer").order_by("-date_observed")

    permits = Permit.objects.filter(
        organization=org,
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
    ).select_related("location", "requestor").order_by("-created_at")

    obs_total = observations.count()
    obs_high = observations.filter(severity="HIGH").count()
    obs_closed = observations.filter(status="CLOSED").count()
    ptw_total = permits.count()
    ptw_approved = permits.filter(status__in=["APPROVED", "ACTIVE", "CLOSED"]).count()

    _stat_strip(story, [
        (obs_total,   "OBSERVATIONS",        DARK),
        (obs_high,    "HIGH SEVERITY",       RED),
        (obs_closed,  "OBSERVATIONS CLOSED", GREEN),
        (ptw_total,   "PERMITS TO WORK",     INDIGO),
    ])

    # Observations table
    story.append(Paragraph("Safety Observations", s["h2"]))
    SEV_CLR = {"HIGH": RED, "MEDIUM": AMBER, "LOW": GREEN}
    rows = [["Date", "Title", "Severity", "Status", "Location", "Observer"]]
    for obs in observations:
        sev = obs.severity
        rows.append([
            Paragraph(obs.date_observed.strftime("%d %b %Y"), s["small"]),
            Paragraph(obs.title[:50], s["body"]),
            Paragraph(
                sev,
                ParagraphStyle("sv", fontSize=7, fontName="Helvetica-Bold",
                               textColor=SEV_CLR.get(sev, TEXT), alignment=1),
            ),
            Paragraph(obs.get_status_display(), s["small"]),
            Paragraph(str(obs.location)[:25] if obs.location else "—", s["small"]),
            Paragraph(obs.observer.full_name if obs.observer else "—", s["small"]),
        ])

    if len(rows) > 1:
        col_w = [18 * mm, 58 * mm, 16 * mm, 32 * mm, 28 * mm, 22 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, obs in enumerate(observations, 1):
            sev = obs.severity
            if sev in ("HIGH",):
                style.append(("BACKGROUND", (2, idx), (2, idx), colors.HexColor("#fee2e2")))
            elif sev == "MEDIUM":
                style.append(("BACKGROUND", (2, idx), (2, idx), colors.HexColor("#fef9c3")))
            else:
                style.append(("BACKGROUND", (2, idx), (2, idx), colors.HexColor("#dcfce7")))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s)

    story.append(Spacer(1, 6 * mm))

    # Permits table
    story.append(Paragraph("Permit to Work Register", s["h2"]))
    rows2 = [["Permit No.", "Work Type", "Title", "Status", "Requestor", "Planned Start"]]
    WORK_TYPE_LABELS = {
        "hot_work": "Hot Work", "confined_space": "Confined Space",
        "electrical": "Electrical", "excavation": "Excavation",
        "lifting_rigging": "Lifting", "work_at_height": "At Height",
        "breaking_containment": "Breaking Cont.", "general": "General",
    }
    PTW_STATUS_CLR = {
        "APPROVED": GREEN, "ACTIVE": GREEN, "CLOSED": MUTED,
        "SUBMITTED": AMBER, "DRAFT": MUTED, "REJECTED": RED, "CANCELLED": RED,
    }
    for p in permits:
        st_clr = PTW_STATUS_CLR.get(p.status, TEXT)
        rows2.append([
            Paragraph(p.permit_number, s["bold"]),
            Paragraph(WORK_TYPE_LABELS.get(p.work_type, p.work_type), s["small"]),
            Paragraph(p.title[:45], s["body"]),
            Paragraph(
                p.status,
                ParagraphStyle("ps", fontSize=7, fontName="Helvetica-Bold", textColor=st_clr),
            ),
            Paragraph(p.requestor.full_name if p.requestor else "—", s["small"]),
            Paragraph(p.planned_start.strftime("%d %b %Y") if p.planned_start else "—", s["small"]),
        ])

    if len(rows2) > 1:
        col_w2 = [26 * mm, 24 * mm, 60 * mm, 20 * mm, 28 * mm, 16 * mm]
        tbl2 = Table(rows2, colWidths=col_w2, repeatRows=1)
        tbl2.setStyle(TableStyle(_tbl_style()))
        story.append(tbl2)
    else:
        _no_data(story, s, "No permits to work found for the selected period.")

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 06 — Inspections (Clause 9.2) ────────────────────────────────────

def generate_section_06_inspections(org, from_date: date_type, to_date: date_type) -> bytes:
    from inspections.models import Inspection, InspectionFinding

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-06",
        "ISO 45001:2018 — CLAUSE 9.2: INTERNAL AUDIT",
        "Safety Inspection & Audit Log",
        from_date, to_date,
    )

    inspections = Inspection.objects.filter(
        organization=org,
        conducted_date__gte=from_date,
        conducted_date__lte=to_date,
        status="completed",
    ).select_related("template", "inspector", "location").order_by("-conducted_date")

    total = inspections.count()
    scores = [i.score for i in inspections if i.score is not None]
    avg_score = round(sum(scores) / len(scores)) if scores else 0
    passed_90 = sum(1 for sc in scores if sc >= 90)
    below_70 = sum(1 for sc in scores if sc < 70)

    _stat_strip(story, [
        (total,     "COMPLETED INSPECTIONS", DARK),
        (f"{avg_score}%", "AVERAGE SCORE",  GREEN if avg_score >= 80 else (AMBER if avg_score >= 60 else RED)),
        (passed_90, "SCORED \u226590%",      GREEN),
        (below_70,  "SCORED <70%",          RED),
    ])

    rows = [["Date", "Inspection Title", "Template", "Inspector", "Location", "Score", "Findings"]]
    for insp in inspections:
        sc = insp.score
        sc_clr = GREEN if (sc or 0) >= 90 else (ORANGE if (sc or 0) >= 70 else RED)
        finding_count = insp.findings.filter(response="FAIL").count()
        rows.append([
            Paragraph(insp.conducted_date.strftime("%d %b %Y") if insp.conducted_date else "—", s["small"]),
            Paragraph(insp.title[:45], s["body"]),
            Paragraph(insp.template.title[:30] if insp.template else "—", s["small"]),
            Paragraph(insp.inspector.full_name if insp.inspector else "—", s["small"]),
            Paragraph(insp.location_display[:25], s["small"]),
            Paragraph(
                f"{sc:.0f}%" if sc is not None else "—",
                ParagraphStyle("sc", fontSize=8, fontName="Helvetica-Bold",
                               textColor=sc_clr, alignment=1),
            ),
            Paragraph(
                f"{finding_count} fail" if finding_count else "\u2713 Pass",
                ParagraphStyle("fc", fontSize=7, fontName="Helvetica-Bold",
                               textColor=RED if finding_count else GREEN, alignment=1),
            ),
        ])

    if len(rows) > 1:
        col_w = [18 * mm, 48 * mm, 30 * mm, 28 * mm, 22 * mm, 14 * mm, 14 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, insp in enumerate(inspections, 1):
            sc = insp.score or 0
            sc_bg = (colors.HexColor("#dcfce7") if sc >= 90
                     else colors.HexColor("#fef9c3") if sc >= 70
                     else colors.HexColor("#fee2e2"))
            style.append(("BACKGROUND", (5, idx), (5, idx), sc_bg))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s, "No completed inspections found for the selected period.")

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 07 — Performance (Clause 9.1) ────────────────────────────────────

def generate_section_07_performance(org, from_date: date_type, to_date: date_type) -> bytes:
    from incidents.models import Incident, HoursWorked
    from django.db.models import Count, Q

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-07",
        "ISO 45001:2018 — CLAUSE 9.1: MONITORING, MEASUREMENT & PERFORMANCE EVALUATION",
        "LTIFR / TRIFR Performance Metrics",
        from_date, to_date,
    )

    incidents = Incident.objects.filter(
        organization=org,
        date_occurred__date__gte=from_date,
        date_occurred__date__lte=to_date,
    )

    total_inc = incidents.count()
    ltis = incidents.filter(severity="lti").count()
    fatalities = incidents.filter(severity="fatality").count()
    recordable = incidents.filter(severity__in=["lti", "mtc", "fac", "fatality"]).count()
    near_misses = incidents.filter(severity="near_miss").count()

    # Total hours worked in period
    hw_qs = HoursWorked.objects.filter(
        organization=org,
        year__gte=from_date.year,
        year__lte=to_date.year,
    )
    total_hours = float(sum(hw.hours for hw in hw_qs)) if hw_qs.exists() else 0

    ltifr = round((ltis + fatalities) * 1_000_000 / total_hours, 2) if total_hours > 0 else "N/A"
    trifr = round(recordable * 1_000_000 / total_hours, 2) if total_hours > 0 else "N/A"

    _stat_strip(story, [
        (total_inc,         "TOTAL INCIDENTS",  DARK),
        (ltis + fatalities, "LTI + FATALITY",   RED),
        (recordable,        "RECORDABLE (TRIFR)", ORANGE),
        (str(ltifr),        "LTIFR",            RED if isinstance(ltifr, float) and ltifr > 0 else GREEN),
    ])

    # KPI summary
    story.append(Paragraph("Period KPI Summary", s["h2"]))
    kpi_rows = [
        [Paragraph("Total Incidents Reported", s["label"]),      Paragraph(str(total_inc), s["bold"])],
        [Paragraph("Lost Time Injuries (LTI)", s["label"]),      Paragraph(str(ltis), s["bold"])],
        [Paragraph("Fatalities", s["label"]),                    Paragraph(str(fatalities), s["bold"])],
        [Paragraph("Medical Treatment Cases (MTC)", s["label"]), Paragraph(str(incidents.filter(severity="mtc").count()), s["bold"])],
        [Paragraph("First Aid Cases (FAC)", s["label"]),         Paragraph(str(incidents.filter(severity="fac").count()), s["bold"])],
        [Paragraph("Near-Misses", s["label"]),                   Paragraph(str(near_misses), s["bold"])],
        [Paragraph("Total Hours Worked", s["label"]),            Paragraph(f"{total_hours:,.0f} hrs" if total_hours else "Not entered", s["bold"])],
        [Paragraph("LTIFR (per 1,000,000 hrs)", s["label"]),    Paragraph(str(ltifr), s["bold"])],
        [Paragraph("TRIFR (per 1,000,000 hrs)", s["label"]),    Paragraph(str(trifr), s["bold"])],
    ]
    kpi_tbl = Table(kpi_rows, colWidths=[80 * mm, 94 * mm])
    kpi_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, GREY_BG]),
        ("BOX",            (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",      (0, 0), (-1, -1), 0.3, BORDER),
        ("TOPPADDING",     (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
        ("LEFTPADDING",    (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",   (0, 0), (-1, -1), 8),
        ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE",       (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 6 * mm))

    # Monthly breakdown
    story.append(Paragraph("Monthly Breakdown", s["h2"]))
    from calendar import month_abbr
    import itertools

    # Build year/month range
    months = []
    y, m = from_date.year, from_date.month
    while (y, m) <= (to_date.year, to_date.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    rows3 = [["Month", "Incidents", "LTIs", "Near-Miss", "Recordable", "Hrs Worked", "LTIFR", "TRIFR"]]
    for y, m in months:
        mo_inc = incidents.filter(date_occurred__year=y, date_occurred__month=m)
        mo_lti = mo_inc.filter(severity__in=["lti", "fatality"]).count()
        mo_nm = mo_inc.filter(severity="near_miss").count()
        mo_rec = mo_inc.filter(severity__in=["lti", "mtc", "fac", "fatality"]).count()
        try:
            hw_obj = HoursWorked.objects.get(organization=org, year=y, month=m)
            mo_hrs = float(hw_obj.hours)
        except HoursWorked.DoesNotExist:
            mo_hrs = 0
        mo_ltifr = round(mo_lti * 1_000_000 / mo_hrs, 2) if mo_hrs > 0 else "—"
        mo_trifr = round(mo_rec * 1_000_000 / mo_hrs, 2) if mo_hrs > 0 else "—"
        rows3.append([
            Paragraph(f"{month_abbr[m]} {y}", s["small"]),
            Paragraph(str(mo_inc.count()), s["center"]),
            Paragraph(str(mo_lti), ParagraphStyle("ml", fontSize=7, textColor=RED if mo_lti > 0 else TEXT, alignment=1, fontName="Helvetica-Bold" if mo_lti > 0 else "Helvetica")),
            Paragraph(str(mo_nm), s["center"]),
            Paragraph(str(mo_rec), s["center"]),
            Paragraph(f"{mo_hrs:,.0f}" if mo_hrs else "—", s["center"]),
            Paragraph(str(mo_ltifr), s["center"]),
            Paragraph(str(mo_trifr), s["center"]),
        ])

    col_w3 = [20 * mm, 20 * mm, 14 * mm, 20 * mm, 22 * mm, 22 * mm, 28 * mm, 28 * mm]
    tbl3 = Table(rows3, colWidths=col_w3, repeatRows=1)
    tbl3.setStyle(TableStyle(_tbl_style()))
    story.append(tbl3)

    if total_hours == 0:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            "Note: Hours worked data has not been entered. Enter monthly hours in the Incidents "
            "Statistics page to enable LTIFR and TRIFR calculations.",
            s["small"],
        ))

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 08 — Incidents (Clause 10.2) ─────────────────────────────────────

def generate_section_08_incidents(org, from_date: date_type, to_date: date_type) -> bytes:
    from incidents.models import Incident

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-08",
        "ISO 45001:2018 — CLAUSE 10.2: INCIDENT INVESTIGATION",
        "Incident Register",
        from_date, to_date,
    )

    incidents = Incident.objects.filter(
        organization=org,
        date_occurred__date__gte=from_date,
        date_occurred__date__lte=to_date,
    ).select_related("reported_by", "investigated_by", "location").order_by("-date_occurred")

    total = incidents.count()
    closed = incidents.filter(status="closed").count()
    under_inv = incidents.filter(status="under_investigation").count()
    rca_done = incidents.exclude(rca_root_cause="").count()

    _stat_strip(story, [
        (total,      "TOTAL INCIDENTS",    DARK),
        (closed,     "CLOSED",             GREEN),
        (under_inv,  "UNDER INVESTIGATION",AMBER),
        (rca_done,   "RCA COMPLETED",      INDIGO),
    ])

    SEV_LABELS = {
        "fatality":  "Fatality",
        "lti":       "LTI",
        "mtc":       "MTC",
        "fac":       "FAC",
        "near_miss": "Near-Miss",
        "property":  "Property",
    }
    SEV_CLRS = {
        "fatality": RED, "lti": RED, "mtc": ORANGE,
        "fac": AMBER, "near_miss": colors.HexColor("#2563eb"), "property": INDIGO,
    }
    TYPE_LABELS = {
        "injury": "Injury", "near_miss": "Near-Miss",
        "dangerous_occurrence": "Dangerous Occ.", "property_damage": "Property Dmg",
        "environmental": "Environmental", "occ_illness": "Occ. Illness",
    }
    STATUS_LABELS = {
        "reported": "Reported", "under_investigation": "Under Inv.",
        "action_required": "Action Req.", "closed": "Closed",
    }

    rows = [["Ref", "Date", "Type", "Severity", "Status", "Location", "Investigator", "RCA"]]
    for inc in incidents:
        sev = inc.severity
        status = inc.status
        rca = "\u2713" if inc.rca_root_cause else "\u2717"
        rca_clr = GREEN if inc.rca_root_cause else RED
        investigator = inc.investigated_by.full_name if inc.investigated_by else "—"
        location = (str(inc.location) if inc.location else inc.location_text) or "—"
        rows.append([
            Paragraph(inc.reference_no or "—", s["bold"]),
            Paragraph(inc.date_occurred.strftime("%d %b %Y"), s["small"]),
            Paragraph(TYPE_LABELS.get(inc.incident_type, inc.incident_type), s["small"]),
            Paragraph(
                SEV_LABELS.get(sev, sev),
                ParagraphStyle("sv", fontSize=7, fontName="Helvetica-Bold",
                               textColor=SEV_CLRS.get(sev, TEXT)),
            ),
            Paragraph(STATUS_LABELS.get(status, status), s["small"]),
            Paragraph(location[:22], s["small"]),
            Paragraph(investigator[:20], s["small"]),
            Paragraph(
                rca,
                ParagraphStyle("rc", fontSize=9, fontName="Helvetica-Bold",
                               textColor=rca_clr, alignment=1),
            ),
        ])

    if len(rows) > 1:
        col_w = [20 * mm, 18 * mm, 22 * mm, 18 * mm, 20 * mm, 28 * mm, 28 * mm, 10 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, inc in enumerate(incidents, 1):
            sev_bg = {
                "fatality": colors.HexColor("#fca5a5"),
                "lti":      colors.HexColor("#fee2e2"),
                "mtc":      colors.HexColor("#ffedd5"),
                "fac":      colors.HexColor("#fef9c3"),
            }.get(inc.severity, WHITE)
            style.append(("BACKGROUND", (3, idx), (3, idx), sev_bg))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s)

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)


# ── Section 09 — Corrective Actions (Clause 10.2) ────────────────────────────

def generate_section_09_actions(org, from_date: date_type, to_date: date_type) -> bytes:
    from actions.models import CorrectiveAction
    from django.utils import timezone

    buf = BytesIO()
    s = _S()
    doc = _new_doc(buf)
    story = []

    _section_header(
        story, s, org.name, "IG-09",
        "ISO 45001:2018 — CLAUSE 10.2: CORRECTIVE ACTION",
        "Corrective Action Register",
        from_date, to_date,
    )

    actions = CorrectiveAction.objects.filter(
        organization=org,
        created_at__date__gte=from_date,
        created_at__date__lte=to_date,
    ).select_related("assigned_to", "raised_by").order_by("due_date", "-created_at")

    total = actions.count()
    closed = actions.filter(status="closed").count()
    overdue = sum(1 for a in actions if a.is_overdue)
    on_time = sum(
        1 for a in actions
        if a.status == "closed" and a.due_date and a.closed_at
        and a.closed_at.date() <= a.due_date
    )
    closure_rate = round(closed / total * 100) if total else 0

    _stat_strip(story, [
        (total,           "TOTAL ACTIONS",         DARK),
        (closed,          "CLOSED",                GREEN),
        (overdue,         "OVERDUE",               RED),
        (f"{closure_rate}%", "CLOSURE RATE",       GREEN if closure_rate >= 80 else (AMBER if closure_rate >= 50 else RED)),
    ])

    SOURCE_LABELS = {
        "hira": "HIRA", "observation": "Observation",
        "compliance": "Compliance", "incident": "Incident",
        "inspection": "Inspection", "manual": "Manual",
    }
    PRIORITY_CLR = {
        "critical": RED, "high": ORANGE, "medium": AMBER, "low": GREEN,
    }
    STATUS_LABELS = {
        "open": "Open", "in_progress": "In Progress",
        "pending_verification": "Pending Verif.", "closed": "Closed",
    }

    rows = [["Ref", "Source", "Action Title", "Priority", "Status", "Assigned To", "Due Date", "On Time"]]
    for a in actions:
        ref = f"CA-{a.pk:04d}"
        priority = a.priority
        status = a.status
        assignee = a.assigned_to.full_name if a.assigned_to else "Unassigned"
        due = a.due_date.strftime("%d %b %Y") if a.due_date else "—"
        if status == "closed" and a.due_date and a.closed_at:
            on_time_flag = "\u2713" if a.closed_at.date() <= a.due_date else "\u2717"
            ot_clr = GREEN if a.closed_at.date() <= a.due_date else RED
        elif a.is_overdue:
            on_time_flag = "OD"
            ot_clr = RED
        else:
            on_time_flag = "—"
            ot_clr = MUTED
        rows.append([
            Paragraph(ref, s["bold"]),
            Paragraph(SOURCE_LABELS.get(a.source_module, a.source_module), s["small"]),
            Paragraph(a.title[:55], s["body"]),
            Paragraph(
                a.priority.upper(),
                ParagraphStyle("pr", fontSize=7, fontName="Helvetica-Bold",
                               textColor=PRIORITY_CLR.get(priority, TEXT)),
            ),
            Paragraph(STATUS_LABELS.get(status, status), s["small"]),
            Paragraph(assignee[:22], s["small"]),
            Paragraph(due, s["small"]),
            Paragraph(
                on_time_flag,
                ParagraphStyle("ot", fontSize=8, fontName="Helvetica-Bold",
                               textColor=ot_clr, alignment=1),
            ),
        ])

    if len(rows) > 1:
        col_w = [14 * mm, 16 * mm, 55 * mm, 16 * mm, 26 * mm, 24 * mm, 16 * mm, 10 * mm]  # =177mm (small over is OK, RL trims)
        col_w = [14 * mm, 16 * mm, 52 * mm, 16 * mm, 26 * mm, 22 * mm, 16 * mm, 12 * mm]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        style = _tbl_style()
        for idx, a in enumerate(actions, 1):
            if a.status == "closed":
                style.append(("BACKGROUND", (4, idx), (4, idx), colors.HexColor("#dcfce7")))
            elif a.is_overdue:
                style.append(("BACKGROUND", (4, idx), (4, idx), colors.HexColor("#fee2e2")))
        tbl.setStyle(TableStyle(style))
        story.append(tbl)
    else:
        _no_data(story, s)

    _section_footer(story, s, org.name)
    return _build(doc, story, buf)
