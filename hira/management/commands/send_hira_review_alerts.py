"""
Management command: send_hira_review_alerts

Sends email alerts to the register's assessed_by user (and all org managers)
when a HIRA register review is due in 30 or 7 days, or is overdue.

Run daily via cron / EB scheduled task:
    python manage.py send_hira_review_alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from hira.models import HazardRegister
from core.utils.email import send_brevo_email


def _site_url():
    return getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def _send_review_alert(register, days_left):
    """Send review alert email to assessed_by + org managers."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    recipients = []
    if register.assessed_by and register.assessed_by.email:
        recipients.append(register.assessed_by.email)

    # CC all active managers / safety managers in same org
    manager_emails = [
        u.email for u in User.objects.filter(
            organization=register.organization, is_active=True,
        ) if (u.is_manager or u.is_safety_manager) and u.email
    ]
    for e in manager_emails:
        if e not in recipients:
            recipients.append(e)

    if not recipients:
        return

    base = _site_url()
    detail_url = f"{base}/hira/registers/{register.pk}/"

    if days_left < 0:
        overdue_days  = abs(days_left)
        urgency_label = f"{overdue_days} day{'s' if overdue_days != 1 else ''} OVERDUE"
        header_color  = "#dc3545"
        subject       = f"HIRA Review Overdue: {register.title}"
        intro         = (
            f"The HIRA register <strong>{register.title}</strong> was due for review "
            f"{overdue_days} day{'s' if overdue_days != 1 else ''} ago and is now "
            f"<strong>expired</strong>. Please initiate a new assessment."
        )
    elif days_left <= 7:
        urgency_label = f"{days_left} day{'s' if days_left != 1 else ''} left"
        header_color  = "#dc3545"
        subject       = f"Urgent — HIRA Review Due in {days_left} Day{'s' if days_left != 1 else ''}: {register.title}"
        intro         = (
            f"The HIRA register <strong>{register.title}</strong> is due for review "
            f"in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>. "
            f"Please review and renew the risk assessment urgently."
        )
    else:
        urgency_label = f"{days_left} days left"
        header_color  = "#fd7e14"
        subject       = f"HIRA Review Due in {days_left} Days: {register.title}"
        intro         = (
            f"The HIRA register <strong>{register.title}</strong> is scheduled for "
            f"review in <strong>{days_left} days</strong> "
            f"(due {register.next_review_date.strftime('%d %b %Y')})."
        )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:{header_color};color:#fff;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="margin:0;font-size:18px;">HIRA Review Alert — {urgency_label}</h2>
      </div>
      <div style="background:#f8f9fa;padding:24px 28px;border:1px solid #dee2e6;border-top:none;border-radius:0 0 8px 8px;">
        <p style="color:#212529;">{intro}</p>
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin-bottom:16px;">
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;width:40%;">Register</td>
            <td style="padding:8px 12px;font-weight:600;">{register.title}</td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Activity</td>
            <td style="padding:8px 12px;">{register.activity}</td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Review Due</td>
            <td style="padding:8px 12px;">{register.next_review_date.strftime('%d %b %Y') if register.next_review_date else '—'}</td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Assessed By</td>
            <td style="padding:8px 12px;">{register.assessed_by.get_full_name() if register.assessed_by else '—'}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;color:#6c757d;">Organisation</td>
            <td style="padding:8px 12px;">{register.organization.name}</td>
          </tr>
        </table>
        <a href="{detail_url}"
           style="display:inline-block;background:#1a2c52;color:#fff;padding:10px 24px;
                  border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View Register
        </a>
        <p style="color:#6c757d;font-size:12px;margin-top:24px;">
          This is an automated reminder from Vigilo Safety Management System.<br>
          Do not reply to this email.
        </p>
      </div>
    </div>
    """

    for email in recipients:
        try:
            send_brevo_email(
                to_email=email,
                subject=subject,
                html_content=html_body,
            )
        except Exception:
            pass


class Command(BaseCommand):
    help = "Send HIRA review due / overdue alerts to assessed-by users and managers."

    def handle(self, *args, **options):
        today    = timezone.now().date()
        sent     = 0
        skipped  = 0

        # Only alert on approved registers with a next_review_date
        registers = (
            HazardRegister.objects
            .filter(
                next_review_date__isnull=False,
                status__in=[HazardRegister.STATUS_APPROVED, HazardRegister.STATUS_EXPIRED],
            )
            .select_related("assessed_by", "organization")
        )

        ALERT_DAYS = {30, 7}   # days-before thresholds
        for register in registers:
            days_left = (register.next_review_date - today).days

            should_alert = (days_left in ALERT_DAYS) or (days_left < 0)
            if should_alert:
                try:
                    _send_review_alert(register, days_left)
                    sent += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Sent alert for register #{register.pk} — {days_left} days"
                        )
                    )
                except Exception as exc:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(f"  Error on #{register.pk}: {exc}")
                    )

        self.stdout.write(
            self.style.SUCCESS(f"Done. {sent} alert(s) sent, {skipped} skipped.")
        )
