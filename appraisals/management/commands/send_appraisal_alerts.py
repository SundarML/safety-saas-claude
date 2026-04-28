"""
Management command: send_appraisal_alerts

Sends timely reminders at key appraisal cycle milestones:
  • Goal-setting deadline approaching (3 days before)
  • Self-assessment deadline approaching (3 days before)
  • Manager review pending (daily nudge to reviewer)
  • Employee acknowledgment pending (3 days after review published)

Run daily via cron / EB scheduled task:
    python manage.py send_appraisal_alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from appraisals.models import AppraisalCycle, AppraisalRecord


HEADER_BLUE   = "#1a2c52"
HEADER_AMBER  = "#ca8a04"
HEADER_GREEN  = "#16a34a"


def _html_email(title, body_html, header_color=HEADER_BLUE):
    return f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:{header_color};padding:20px 28px;border-radius:8px 8px 0 0;">
    <h2 style="color:#fff;margin:0;font-size:1.1rem;">{title}</h2>
  </div>
  <div style="background:#f8fafc;padding:24px 28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 8px 8px;">
    {body_html}
    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
    <p style="font-size:.78rem;color:#94a3b8;margin:0;">
      Vigilo Safety Platform — automated reminder. Do not reply to this email.
    </p>
  </div>
</div>
"""


def _send(to_email, subject, html):
    from core.utils.email import send_brevo_email
    try:
        send_brevo_email(to_email=to_email, subject=subject, html_content=html)
        return True
    except Exception:
        return False


class Command(BaseCommand):
    help = "Send appraisal milestone reminder emails."

    def handle(self, *args, **options):
        today = timezone.now().date()
        total = 0

        active_cycles = AppraisalCycle.objects.filter(
            status__in=[
                AppraisalCycle.STATUS_GOAL_SETTING,
                AppraisalCycle.STATUS_SELF_ASSESSMENT,
                AppraisalCycle.STATUS_MANAGER_REVIEW,
                AppraisalCycle.STATUS_CALIBRATION,
            ]
        ).prefetch_related("records__employee", "records__reviewer")

        for cycle in active_cycles:
            # ── Goal-setting deadline reminder (3 days before) ──────────
            if cycle.status == AppraisalCycle.STATUS_GOAL_SETTING:
                days_left = (cycle.goal_setting_deadline - today).days
                if days_left == 3:
                    pending_records = cycle.records.filter(
                        status=AppraisalRecord.STATUS_PENDING_GOALS
                    ).select_related("employee")
                    for rec in pending_records:
                        emp = rec.employee
                        if not emp.email:
                            continue
                        subject = f"Action needed: Goals due in 3 days — {cycle.name}"
                        body = (
                            f"<p>Hi {emp.full_name},</p>"
                            f"<p>Your goal-setting deadline for <strong>{cycle.name}</strong> is in "
                            f"<strong>3 days</strong> ({cycle.goal_setting_deadline.strftime('%d %b %Y')}).</p>"
                            f"<p>Please log in to review your goals and propose any additional goals before the deadline.</p>"
                        )
                        if _send(emp.email, subject, _html_email(f"Goal Setting — {cycle.name}", body, HEADER_AMBER)):
                            total += 1
                            self.stdout.write(f"  [goal-deadline] → {emp.email}")

            # ── Self-assessment deadline reminder (3 days before) ────────
            if cycle.status == AppraisalCycle.STATUS_SELF_ASSESSMENT:
                days_left = (cycle.self_assessment_deadline - today).days
                if days_left == 3:
                    pending_records = cycle.records.filter(
                        status=AppraisalRecord.STATUS_SELF_ASSESS
                    ).select_related("employee")
                    for rec in pending_records:
                        emp = rec.employee
                        if not emp.email:
                            continue
                        subject = f"Reminder: Self-assessment due in 3 days — {cycle.name}"
                        body = (
                            f"<p>Hi {emp.full_name},</p>"
                            f"<p>Your self-assessment for <strong>{cycle.name}</strong> is due in "
                            f"<strong>3 days</strong> ({cycle.self_assessment_deadline.strftime('%d %b %Y')}).</p>"
                            f"<p>Please log in, rate yourself on each goal, and submit your self-assessment before the deadline.</p>"
                        )
                        if _send(emp.email, subject, _html_email(f"Self-Assessment Due — {cycle.name}", body, HEADER_AMBER)):
                            total += 1
                            self.stdout.write(f"  [self-assess-deadline] → {emp.email}")

            # ── Manager review pending — daily nudge to reviewer ─────────
            if cycle.status == AppraisalCycle.STATUS_MANAGER_REVIEW:
                days_left = (cycle.review_deadline - today).days
                # Nudge on: 7 days before, 3 days before, 1 day before, overdue
                if days_left in (7, 3, 1) or days_left < 0:
                    pending_records = (
                        cycle.records.filter(status=AppraisalRecord.STATUS_PENDING_REVIEW)
                        .select_related("employee", "reviewer")
                    )
                    # Group by reviewer to send one consolidated email
                    by_reviewer = {}
                    for rec in pending_records:
                        rv = rec.reviewer
                        if not rv or not rv.email:
                            continue
                        by_reviewer.setdefault(rv, []).append(rec.employee.full_name)

                    for reviewer, emp_names in by_reviewer.items():
                        names_html = "".join(f"<li>{n}</li>" for n in emp_names)
                        if days_left < 0:
                            urgency = f"<strong style='color:#dc2626;'>{abs(days_left)} day(s) overdue</strong>"
                            color   = "#dc2626"
                        else:
                            urgency = f"due in <strong>{days_left} day(s)</strong>"
                            color   = HEADER_AMBER
                        subject = f"Reviews pending ({len(emp_names)} employee{'s' if len(emp_names) > 1 else ''}) — {cycle.name}"
                        body = (
                            f"<p>Hi {reviewer.full_name},</p>"
                            f"<p>You have <strong>{len(emp_names)} review(s)</strong> waiting for <strong>{cycle.name}</strong>. "
                            f"The review deadline is {urgency} ({cycle.review_deadline.strftime('%d %b %Y')}).</p>"
                            f"<p>Employees awaiting your review:</p><ul>{names_html}</ul>"
                            f"<p>Please log in and complete the manager review for each employee.</p>"
                        )
                        if _send(reviewer.email, subject, _html_email(f"Reviews Pending — {cycle.name}", body, color)):
                            total += 1
                            self.stdout.write(f"  [review-pending] → {reviewer.email} ({len(emp_names)} employees)")

            # ── Acknowledgment pending — remind employee 3 days after review published ──
            unacked = (
                cycle.records.filter(status=AppraisalRecord.STATUS_MANAGER_REVIEWED)
                .select_related("employee")
            )
            for rec in unacked:
                # Nudge 3 days after the record was last updated (review submitted)
                days_since_review = (today - rec.updated_at.date()).days
                if days_since_review == 3:
                    emp = rec.employee
                    if not emp.email:
                        continue
                    subject = f"Action required: Please acknowledge your appraisal — {cycle.name}"
                    body = (
                        f"<p>Hi {emp.full_name},</p>"
                        f"<p>Your manager has completed your performance review for <strong>{cycle.name}</strong>. "
                        f"Please log in to view your results and acknowledge the appraisal to complete the process.</p>"
                    )
                    if _send(emp.email, subject, _html_email(f"Appraisal Ready to Acknowledge — {cycle.name}", body, HEADER_GREEN)):
                        total += 1
                        self.stdout.write(f"  [ack-pending] → {emp.email}")

        self.stdout.write(self.style.SUCCESS(f"\nDone. {total} appraisal alert email(s) sent."))
