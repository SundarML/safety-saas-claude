from django.core.management.base import BaseCommand
from django.utils import timezone
from inspections.models import Inspection
from core.utils.email import send_brevo_email


class Command(BaseCommand):
    help = "Send inspection due and overdue alerts to inspectors and managers."

    def handle(self, *args, **options):
        today = timezone.now().date()
        sent  = 0

        pending = Inspection.objects.filter(
            status__in=[Inspection.STATUS_SCHEDULED, Inspection.STATUS_IN_PROGRESS,
                        Inspection.STATUS_OVERDUE]
        ).select_related("inspector", "template", "organization")

        for insp in pending:
            delta = (insp.scheduled_date - today).days

            if delta == 3:
                subject = f"Inspection due in 3 days: {insp.title}"
                urgency = "due in <strong>3 days</strong>"
            elif delta == 1:
                subject = f"Inspection due tomorrow: {insp.title}"
                urgency = "due <strong>tomorrow</strong>"
            elif delta <= 0:
                subject = f"OVERDUE Inspection: {insp.title}"
                urgency = "<strong>OVERDUE</strong>"
                # Update status
                if insp.status != Inspection.STATUS_OVERDUE:
                    insp.status = Inspection.STATUS_OVERDUE
                    insp.save(update_fields=["status"])
            else:
                continue

            recipients = []
            if insp.inspector and insp.inspector.email:
                recipients.append(insp.inspector.email)

            # Add org managers
            from django.contrib.auth import get_user_model
            User = get_user_model()
            managers = User.objects.filter(
                organization=insp.organization,
                is_active=True,
            ).filter(
                role__in=["manager", "safety_manager"]
            ).values_list("email", flat=True)
            recipients += [e for e in managers if e not in recipients]

            html = f"""
            <p>This is a reminder that the following inspection is {urgency}:</p>
            <table style="border-collapse:collapse;width:100%;max-width:500px;">
              <tr><td style="padding:6px 12px;background:#f8f9fb;font-weight:700;">Inspection</td>
                  <td style="padding:6px 12px;">{insp.title}</td></tr>
              <tr><td style="padding:6px 12px;background:#f8f9fb;font-weight:700;">Template</td>
                  <td style="padding:6px 12px;">{insp.template.title}</td></tr>
              <tr><td style="padding:6px 12px;background:#f8f9fb;font-weight:700;">Inspector</td>
                  <td style="padding:6px 12px;">{insp.inspector.get_full_name() if insp.inspector else "—"}</td></tr>
              <tr><td style="padding:6px 12px;background:#f8f9fb;font-weight:700;">Scheduled Date</td>
                  <td style="padding:6px 12px;">{insp.scheduled_date.strftime("%d %b %Y")}</td></tr>
              <tr><td style="padding:6px 12px;background:#f8f9fb;font-weight:700;">Location</td>
                  <td style="padding:6px 12px;">{insp.location_display}</td></tr>
            </table>
            <p style="margin-top:16px;">
              Please log in to Vigilo to conduct or review this inspection.
            </p>
            """

            for email in recipients:
                try:
                    send_brevo_email(to_email=email, subject=subject, html_content=html)
                    sent += 1
                except Exception as e:
                    self.stderr.write(f"Failed to send to {email}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} inspection alert(s)."))
