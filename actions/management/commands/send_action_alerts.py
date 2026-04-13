"""
Management command: send_action_alerts

Sends overdue / due-soon reminders for open corrective actions.
Alert thresholds: 7 days before due, then daily once overdue.

Run daily via cron / EB scheduled task:
    python manage.py send_action_alerts
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from actions.models import CorrectiveAction
from actions.notifications import _action_html, _managers_and_raiser


def _send_overdue_alert(action, days_left):
    from core.utils.email import send_brevo_email

    if days_left < 0:
        overdue_days  = abs(days_left)
        header_color  = "#dc2626"
        subject       = f"Overdue Action: CA-{action.pk:04d} — {action.title}"
        body          = (
            f"<p>This corrective action is <strong>{overdue_days} day{'s' if overdue_days != 1 else ''} overdue</strong>. "
            f"Immediate attention is required.</p>"
        )
    else:
        header_color  = "#ca8a04"
        subject       = f"Action Due in {days_left} Day{'s' if days_left != 1 else ''}: CA-{action.pk:04d} — {action.title}"
        body          = (
            f"<p>This corrective action is due in <strong>{days_left} day{'s' if days_left != 1 else ''}</strong>. "
            f"Please complete and submit for verification before the due date.</p>"
        )

    recipients = set()
    if action.assigned_to and action.assigned_to.email:
        recipients.add(action.assigned_to.email)
    for e in _managers_and_raiser(action):
        recipients.add(e)

    if not recipients:
        return 0

    html = _action_html(action, subject, body, header_color)
    sent = 0
    for email in recipients:
        try:
            from core.utils.email import send_brevo_email
            send_brevo_email(to_email=email, subject=subject, html_content=html)
            sent += 1
        except Exception:
            pass
    return sent


class Command(BaseCommand):
    help = "Send overdue / due-soon reminders for open corrective actions."

    def handle(self, *args, **options):
        today   = timezone.now().date()
        total   = 0

        open_actions = CorrectiveAction.objects.filter(
            due_date__isnull=False,
        ).exclude(status=CorrectiveAction.STATUS_CLOSED).select_related(
            "assigned_to", "raised_by", "organization"
        )

        for action in open_actions:
            days_left = (action.due_date - today).days
            # Alert at 7 days before OR any overdue day
            if days_left == 7 or days_left < 0:
                sent = _send_overdue_alert(action, days_left)
                total += sent
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  CA-{action.pk:04d} ({days_left}d): {sent} email(s) sent"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"Done. {total} alert email(s) sent."))
