# users/performance.py
"""
Pure aggregation and scoring functions for user performance profiles.
No Django HTTP — fully testable in isolation.
"""
from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from typing import Optional

from django.db.models import Avg, Count, F, FloatField, Q
from django.db.models.functions import Cast
from django.utils import timezone


# ---------------------------------------------------------------------------
# Observation stats
# ---------------------------------------------------------------------------

def get_observation_stats(user, org) -> dict:
    from observations.models import Observation

    base_obs = Observation.objects.filter(organization=org)
    today = date.today()
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # --- reported by user (observer) ---
    reported = base_obs.filter(observer=user)
    total_reported = reported.count()

    reported_by_severity = {
        "LOW": reported.filter(severity="LOW").count(),
        "MEDIUM": reported.filter(severity="MEDIUM").count(),
        "HIGH": reported.filter(severity="HIGH").count(),
    }
    reported_by_status = {
        "OPEN": reported.filter(status="OPEN").count(),
        "IN_PROGRESS": reported.filter(status="IN_PROGRESS").count(),
        "AWAITING_VERIFICATION": reported.filter(status="AWAITING_VERIFICATION").count(),
        "CLOSED": reported.filter(status="CLOSED").count(),
    }
    reported_closed = reported_by_status["CLOSED"]
    closure_rate_reported = (reported_closed / total_reported * 100) if total_reported else 0
    last_30_days = reported.filter(date_observed__gte=thirty_days_ago).count()

    # --- assigned to user (action owner) ---
    assigned = base_obs.filter(assigned_to=user)
    total_assigned = assigned.count()

    assigned_by_status = {
        "OPEN": assigned.filter(status="OPEN").count(),
        "IN_PROGRESS": assigned.filter(status="IN_PROGRESS").count(),
        "AWAITING_VERIFICATION": assigned.filter(status="AWAITING_VERIFICATION").count(),
        "CLOSED": assigned.filter(status="CLOSED").count(),
    }
    assigned_closed = assigned_by_status["CLOSED"]
    closure_rate_assigned = (assigned_closed / total_assigned * 100) if total_assigned else 0

    # avg days to close (only for closed with date_closed)
    closed_with_dates = assigned.filter(status="CLOSED", date_closed__isnull=False)
    avg_days_to_close = 0.0
    if closed_with_dates.exists():
        total_days = sum(
            (obs.date_closed.date() - obs.date_observed.date()).days
            for obs in closed_with_dates.only("date_closed", "date_observed")
            if obs.date_closed
        )
        avg_days_to_close = total_days / closed_with_dates.count()

    overdue_count = assigned.filter(
        ~Q(status="CLOSED"),
        target_date__lt=today,
        target_date__isnull=False,
    ).count()

    return {
        "total_reported": total_reported,
        "by_severity": reported_by_severity,
        "reported_by_status": reported_by_status,
        "closure_rate_reported": round(closure_rate_reported, 1),
        "last_30_days": last_30_days,
        "total_assigned": total_assigned,
        "assigned_by_status": assigned_by_status,
        "closure_rate_assigned": round(closure_rate_assigned, 1),
        "avg_days_to_close": round(avg_days_to_close, 1),
        "overdue_count": overdue_count,
    }


# ---------------------------------------------------------------------------
# Training stats
# ---------------------------------------------------------------------------

def get_training_stats(user, org) -> dict:
    from training.models import AssessmentAttempt, SkillProficiency

    attempts = AssessmentAttempt.objects.filter(organization=org, user=user)
    total_attempts = attempts.count()
    passed_attempts = attempts.filter(passed=True).count()
    pass_rate = (passed_attempts / total_attempts * 100) if total_attempts else 0
    avg_score = attempts.aggregate(avg=Avg("score"))["avg"] or 0.0

    distinct_assessments = attempts.values("assessment").distinct().count()

    proficiencies = SkillProficiency.objects.filter(organization=org, user=user)
    skills_certified = proficiencies.count()
    skill_levels = {i: proficiencies.filter(level=i).count() for i in range(1, 6)}
    avg_skill_level = proficiencies.aggregate(avg=Avg("level"))["avg"] or 0.0

    return {
        "total_modules_taken": distinct_assessments,
        "total_attempts": total_attempts,
        "passed_attempts": passed_attempts,
        "pass_rate": round(pass_rate, 1),
        "avg_score": round(avg_score, 1),
        "skills_certified": skills_certified,
        "skill_levels": skill_levels,
        "avg_skill_level": round(avg_skill_level, 2),
    }


# ---------------------------------------------------------------------------
# Star rating helpers
# ---------------------------------------------------------------------------

def _percentile_to_stars(score: float, all_scores: list[float]) -> float:
    """Map a score to 1–5 stars based on percentile rank within all_scores."""
    if not all_scores:
        return 3.0
    rank = sum(1 for s in all_scores if s < score)
    percentile = rank / len(all_scores) * 100
    if percentile < 20:
        return 1.0
    elif percentile < 40:
        return 2.0
    elif percentile < 60:
        return 3.0
    elif percentile < 80:
        return 4.0
    else:
        return 5.0


def _observer_raw(total_reported: int, high: int, medium: int, low: int, closure_rate: float) -> float:
    quality = (high * 3 + medium * 2 + low * 1) * 0.4
    closure = closure_rate * 0.4
    volume = min(total_reported, 50) / 50 * 100 * 0.2
    return quality + closure + volume


def _action_owner_raw(closure_rate: float, avg_days_to_close: float, overdue_count: int, total_assigned: int) -> float:
    closure = closure_rate * 0.5
    speed = (1 / max(avg_days_to_close, 1)) * 100 * 0.3
    punctuality = (1 - overdue_count / max(total_assigned, 1)) * 100 * 0.2
    return closure + speed + punctuality


def _training_raw(pass_rate: float, avg_score: float, avg_skill_level: float) -> float:
    return pass_rate * 0.4 + avg_score * 0.2 + avg_skill_level / 5 * 100 * 0.4


def calculate_observer_stars(user, org) -> Optional[tuple[float, str]]:
    """Return (stars, rank_label) or None if user has 0 observations."""
    from observations.models import Observation

    base = Observation.objects.filter(organization=org)

    # All org users who have reported at least 1
    from django.contrib.auth import get_user_model
    User = get_user_model()
    org_users = User.objects.filter(organization=org)

    user_scores = {}
    for u in org_users:
        reported = base.filter(observer=u)
        total = reported.count()
        if total == 0:
            continue
        sev = {
            "HIGH": reported.filter(severity="HIGH").count(),
            "MEDIUM": reported.filter(severity="MEDIUM").count(),
            "LOW": reported.filter(severity="LOW").count(),
        }
        closed = reported.filter(status="CLOSED").count()
        cr = closed / total * 100
        user_scores[u.pk] = _observer_raw(total, sev["HIGH"], sev["MEDIUM"], sev["LOW"], cr)

    if user.pk not in user_scores:
        return None

    all_scores = list(user_scores.values())
    stars = _percentile_to_stars(user_scores[user.pk], all_scores)
    rank = sorted(user_scores.keys(), key=lambda pk: user_scores[pk], reverse=True).index(user.pk) + 1
    total_observers = len(user_scores)
    return stars, f"{rank} of {total_observers} observers"


def calculate_action_owner_stars(user, org) -> Optional[tuple[float, str]]:
    """Return (stars, rank_label) or None if user has 0 assigned observations."""
    from observations.models import Observation

    base = Observation.objects.filter(organization=org)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    org_users = User.objects.filter(organization=org)

    today = date.today()
    user_scores = {}
    for u in org_users:
        assigned = base.filter(assigned_to=u)
        total = assigned.count()
        if total == 0:
            continue
        closed_qs = assigned.filter(status="CLOSED", date_closed__isnull=False)
        closed = assigned.filter(status="CLOSED").count()
        cr = closed / total * 100

        avg_days = 0.0
        if closed_qs.exists():
            total_days = sum(
                (obs.date_closed.date() - obs.date_observed.date()).days
                for obs in closed_qs.only("date_closed", "date_observed")
                if obs.date_closed
            )
            avg_days = total_days / closed_qs.count()

        from django.db.models import Q
        overdue = assigned.filter(
            ~Q(status="CLOSED"), target_date__lt=today, target_date__isnull=False
        ).count()

        user_scores[u.pk] = _action_owner_raw(cr, avg_days, overdue, total)

    if user.pk not in user_scores:
        return None

    all_scores = list(user_scores.values())
    stars = _percentile_to_stars(user_scores[user.pk], all_scores)
    rank = sorted(user_scores.keys(), key=lambda pk: user_scores[pk], reverse=True).index(user.pk) + 1
    total_owners = len(user_scores)
    return stars, f"{rank} of {total_owners} action owners"


def calculate_training_stars(user, org) -> Optional[tuple[float, str]]:
    """Return (stars, rank_label) or None if user has 0 attempts."""
    from training.models import AssessmentAttempt, SkillProficiency

    from django.contrib.auth import get_user_model
    User = get_user_model()
    org_users = User.objects.filter(organization=org)

    user_scores = {}
    for u in org_users:
        attempts = AssessmentAttempt.objects.filter(organization=org, user=u)
        if not attempts.exists():
            continue
        total = attempts.count()
        passed = attempts.filter(passed=True).count()
        pass_rate = passed / total * 100
        avg_score = attempts.aggregate(avg=Avg("score"))["avg"] or 0.0
        profs = SkillProficiency.objects.filter(organization=org, user=u)
        avg_skill = profs.aggregate(avg=Avg("level"))["avg"] or 0.0
        user_scores[u.pk] = _training_raw(pass_rate, avg_score, avg_skill)

    if user.pk not in user_scores:
        return None

    all_scores = list(user_scores.values())
    stars = _percentile_to_stars(user_scores[user.pk], all_scores)
    rank = sorted(user_scores.keys(), key=lambda pk: user_scores[pk], reverse=True).index(user.pk) + 1
    total_learners = len(user_scores)
    return stars, f"{rank} of {total_learners} learners"


# ---------------------------------------------------------------------------
# PDF Certificate
# ---------------------------------------------------------------------------

def generate_certificate_pdf(user, obs_stats: dict, training_stats: dict,
                              observer_result, action_owner_result, training_result) -> bytes:
    """Return PDF bytes for a performance certificate."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER

    buffer = BytesIO()
    page_w, page_h = landscape(A4)
    margin = 22 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
    )

    NAVY = colors.HexColor("#0e1729")
    GOLD = colors.HexColor("#f59e0b")
    TEAL_LIGHT = colors.HexColor("#f0fdf4")
    GREY = colors.HexColor("#64748b")
    SLATE = colors.HexColor("#f8fafc")
    BORDER = colors.HexColor("#99f6e4")

    # ------------------------------------------------------------------
    # Paragraph styles — every style has an explicit leading so lines
    # never collapse onto each other regardless of font size.
    # Rule of thumb: leading ≈ fontSize * 1.35–1.5
    # ------------------------------------------------------------------
    base = getSampleStyleSheet()["Normal"]

    def ps(name, fontSize, fontName="Helvetica", textColor=GREY,
           leading=None, alignment=TA_CENTER, spaceBefore=0, spaceAfter=0):
        return ParagraphStyle(
            name, parent=base,
            fontSize=fontSize,
            leading=leading if leading is not None else round(fontSize * 1.4),
            fontName=fontName,
            textColor=textColor,
            alignment=alignment,
            spaceBefore=spaceBefore,
            spaceAfter=spaceAfter,
        )

    org_style    = ps("Org",    10, "Helvetica-Bold", GREY,  leading=15)
    title_style  = ps("Title",  24, "Helvetica-Bold", NAVY,  leading=32)
    certify_style= ps("Certify",10, textColor=GREY,   leading=15)
    name_style   = ps("Name",   26, "Helvetica-Bold", NAVY,  leading=36)
    role_style   = ps("Role",   11, textColor=GREY,   leading=16)
    small_style  = ps("Small",   9, textColor=GREY,   leading=14)
    footer_style = ps("Footer",  9, textColor=GREY,   leading=13)

    # Star-cell inner paragraph styles
    star_label_ps = ps("StarLbl",  8, "Helvetica-Bold", GREY, leading=12)
    star_stars_ps = ps("StarStars",17, textColor=GOLD, leading=24)
    star_rank_ps  = ps("StarRank", 8, textColor=GREY, leading=12)

    # Metrics-cell inner paragraph styles
    metric_hdr_ps = ps("MetHdr", 8, "Helvetica-Bold", colors.white, leading=12)
    metric_val_ps = ps("MetVal",18, "Helvetica-Bold", colors.white,   leading=26)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def star_str(stars_val) -> str:
        if stars_val is None:
            return "N/A"
        filled = int(stars_val)
        return "\u2605" * filled + "\u2606" * (5 - filled)

    def star_cell(label: str, stars_val, rank_label: str) -> list:
        """Return a list of Paragraphs for one star-rating table cell."""
        return [
            Paragraph(label, star_label_ps),
            Spacer(1, 2 * mm),
            Paragraph(star_str(stars_val), star_stars_ps),
            Spacer(1, 1.5 * mm),
            Paragraph(rank_label or "&nbsp;", star_rank_ps),
        ]

    def metric_cell(header: str, value: str) -> list:
        """Return a list of Paragraphs for one metrics table cell."""
        return [
            Paragraph(header, metric_hdr_ps),
            Spacer(1, 3 * mm),
            Paragraph(value, metric_val_ps),
        ]

    org = user.organization
    org_name = org.name if org else "—"

    observer_stars   = observer_result[0]    if observer_result    else None
    action_stars     = action_owner_result[0] if action_owner_result else None
    training_stars   = training_result[0]    if training_result    else None
    observer_rank    = observer_result[1]    if observer_result    else ""
    action_rank      = action_owner_result[1] if action_owner_result else ""
    training_rank    = training_result[1]    if training_result    else ""

    # Skills list
    from training.models import SkillProficiency
    profs = SkillProficiency.objects.filter(
        organization=org, user=user
    ).select_related("skill").order_by("-level")[:8]
    skill_labels = {1: "L1", 2: "L2", 3: "L3", 4: "L4", 5: "L5"}
    skills_text = ", ".join(
        f"{p.skill.name} ({skill_labels.get(p.level, p.level)})" for p in profs
    ) or "No skills assessed yet"

    role_display = dict(user.ROLE_CHOICES).get(user.role, user.role.replace("_", " ").title())

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    # -- Logo + org header row --
    from core.logo_utils import get_logo_for_pdf as _get_logo

    content = []

    # Logo + org name side by side if logo exists, else text only
    logo_img = _get_logo(org, max_width_pt=6 * mm * 10, max_height_pt=14 * mm)  # ~60mm × 14mm
    if logo_img:
        header_data = [[logo_img, Paragraph(f"<b>{org_name}</b><br/>safety-desk.com", org_style)]]
        header_table = Table(
            header_data,
            colWidths=[logo_img.drawWidth + 6 * mm, page_w - 2 * margin - logo_img.drawWidth - 6 * mm],
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (0, 0), (0, 0),  "LEFT"),
            ("ALIGN",  (1, 0), (1, 0),  "RIGHT"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        content.append(header_table)
    else:
        content.append(Paragraph(f"<b>{org_name}</b> &nbsp;·&nbsp; safety-desk.com", org_style))
    content.append(Spacer(1, 5 * mm))

    content.append(Paragraph("CERTIFICATE OF PERFORMANCE", title_style))
    content.append(Spacer(1, 4 * mm))
    content.append(Paragraph("This certifies the outstanding contributions of", certify_style))
    content.append(Spacer(1, 5 * mm))

    content.append(Paragraph(user.get_full_name(), name_style))
    content.append(Spacer(1, 2 * mm))
    content.append(Paragraph(f"{role_display} &nbsp;·&nbsp; {org_name}", role_style))
    content.append(Spacer(1, 6 * mm))

    # -- Star rating table (each cell = list of Paragraphs) --
    col_w = (page_w - 2 * margin) / 3
    star_data = [[
        star_cell("OBSERVER",     observer_stars, observer_rank),
        star_cell("ACTION OWNER", action_stars,   action_rank),
        star_cell("TRAINING",     training_stars, training_rank),
    ]]
    star_table = Table(star_data, colWidths=[col_w] * 3, rowHeights=None)
    star_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), TEAL_LIGHT),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("BOX",           (0, 0), (-1, -1), 1,   BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    content.append(star_table)
    content.append(Spacer(1, 6 * mm))

    # -- Key metrics table (each cell = list of Paragraphs) --
    content.append(Paragraph(
        "KEY METRICS",
        ps("MetHdrTitle", 8, "Helvetica-Bold", GREY, leading=12, spaceAfter=3)
    ))
    content.append(Spacer(1, 2 * mm))

    metric_col_w = (page_w - 2 * margin) / 4
    metrics_data = [[
        metric_cell("Observations\nReported",  str(obs_stats.get("total_reported", 0))),
        metric_cell("Closure Rate\n(Observer)", f"{obs_stats.get('closure_rate_reported', 0):.0f}%"),
        metric_cell("Assessment\nPass Rate",    f"{training_stats.get('pass_rate', 0):.0f}%"),
        metric_cell("Skills\nCertified",        str(training_stats.get("skills_certified", 0))),
    ]]
    metrics_table = Table(metrics_data, colWidths=[metric_col_w] * 4)
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 1,   BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.5, BORDER),
    ]))
    content.append(metrics_table)
    content.append(Spacer(1, 5 * mm))

    # Skills line
    content.append(Paragraph(f"<b>Skills Certified:</b> {skills_text}", small_style))
    content.append(Spacer(1, 6 * mm))

    content.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    content.append(Spacer(1, 3 * mm))

    now = timezone.now()
    issued = now.strftime("%d %B %Y").lstrip("0")
    content.append(Paragraph(f"Issued: {issued} &nbsp;&nbsp;&nbsp;&nbsp; safety-desk.com", footer_style))

    # -- Decorative double border drawn on canvas --
    def draw_border(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(3)
        canvas.rect(10 * mm, 10 * mm, page_w - 20 * mm, page_h - 20 * mm)
        canvas.setLineWidth(0.8)
        canvas.setStrokeColor(NAVY)
        canvas.rect(13 * mm, 13 * mm, page_w - 26 * mm, page_h - 26 * mm)
        canvas.restoreState()

    doc.build(content, onFirstPage=draw_border, onLaterPages=draw_border)
    return buffer.getvalue()
