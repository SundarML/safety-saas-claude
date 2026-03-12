"""
Management command: send_compliance_alerts

Sends email reminders to assigned users for compliance items due in
60, 30, or 7 days. Also alerts managers for overdue items.

Run daily via cron / EB scheduled task:
    python manage.py send_compliance_alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from compliance.models import ComplianceItem
from core.utils.email import send_brevo_email


def _site_url():
    return getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def _send_reminder(item, days_left):
    if not item.assigned_to or not item.assigned_to.email:
        return

    base = _site_url()
    detail_url = f"{base}/compliance/{item.pk}/"
    comply_url = f"{base}/compliance/{item.pk}/comply/"

    if days_left < 0:
        urgency_label = f"{abs(days_left)} day{'s' if abs(days_left) != 1 else ''} OVERDUE"
        header_color  = "#dc3545"
        header_text   = "Compliance Item Overdue"
    elif days_left <= 7:
        urgency_label = f"{days_left} day{'s' if days_left != 1 else ''} left"
        header_color  = "#dc3545"
        header_text   = "Urgent: Compliance Due Very Soon"
    elif days_left <= 30:
        urgency_label = f"{days_left} days left"
        header_color  = "#fd7e14"
        header_text   = "Compliance Due Soon"
    else:
        urgency_label = f"{days_left} days left"
        header_color  = "#f59e0b"
        header_text   = "Upcoming Compliance Deadline"

    subject = f"[Compliance] {header_text}: {item.title}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:{header_color};padding:16px 24px;border-radius:6px 6px 0 0;">
        <h2 style="color:white;margin:0;">{header_text}</h2>
      </div>
      <div style="background:#fafafa;border:1px solid #e2e8f0;padding:24px;border-radius:0 0 6px 6px;">
        <p>Hi <strong>{item.assigned_to.get_full_name()}</strong>,</p>
        <p>This is a reminder about a compliance obligation assigned to you.</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          <tr><td style="padding:8px;background:#f1f5f9;font-weight:bold;width:35%;">Item</td>
              <td style="padding:8px;">{item.title}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Law / Regulation</td>
              <td style="padding:8px;">{item.law or "--"}</td></tr>
          <tr><td style="padding:8px;background:#f1f5f9;font-weight:bold;">Authority</td>
              <td style="padding:8px;background:#f1f5f9;">{item.authority or "--"}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Due Date</td>
              <td style="padding:8px;color:{header_color};font-weight:bold;">{item.due_date}</td></tr>
          <tr><td style="padding:8px;background:#f1f5f9;font-weight:bold;">Status</td>
              <td style="padding:8px;background:#f1f5f9;color:{header_color};font-weight:bold;">{urgency_label}</td></tr>
        </table>
        <p style="margin-top:20px;">
          <a href="{comply_url}"
             style="background:{header_color};color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            Mark as Complied
          </a>
          &nbsp;&nbsp;
          <a href="{detail_url}"
             style="background:#64748b;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            View Details
          </a>
        </p>
        <hr style="margin:24px 0;border:none;border-top:1px solid #e2e8f0;">
        <p style="color:#64748b;font-size:12px;">
          Vigilo Legal Compliance -- {item.organization.name}
        </p>
      </div>
    </div>
    """

    send_brevo_email(item.assigned_to.email, subject, html)


class Command(BaseCommand):
    help = "Send email reminders for upcoming and overdue compliance items"

    def handle(self, *args, **options):
        today = timezone.now().date()

        # Auto-mark overdue
        overdue_updated = ComplianceItem.objects.filter(
            status="pending", due_date__lt=today
        ).update(status="overdue")
        self.stdout.write(f"Marked {overdue_updated} items as overdue.")

        # Active items to alert on: pending (due soon) + overdue
        alert_items = ComplianceItem.objects.filter(
            status__in=["pending", "overdue"]
        ).select_related("assigned_to", "organization")

        sent = 0
        for item in alert_items:
            days_left = (item.due_date - today).days
            if days_left in (60, 30, 7) or days_left < 0:
                _send_reminder(item, days_left)
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} compliance alert emails."))
