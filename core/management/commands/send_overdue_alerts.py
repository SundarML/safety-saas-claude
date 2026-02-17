# core/management/commands/send_overdue_alerts.py
"""
Finds all overdue observations (target_date passed, not yet closed,
has an assigned user) and sends an email alert to each assignee.

Run daily via cron or Render cron job:
    python manage.py send_overdue_alerts

Render cron schedule:  0 8 * * *   (8 AM IST every day)

Options:
    --dry-run    Print what would be sent without actually sending emails.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from observations.models import Observation
from core.utils.email import send_overdue_alert


class Command(BaseCommand):
    help = "Send overdue observation alerts to assigned action owners."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without sending any emails.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today   = timezone.now().date()

        # Overdue = target_date is in the past, not closed, not archived, has assignee
        overdue_qs = (
            Observation.objects
            .filter(
                target_date__lt=today,
                assigned_to__isnull=False,
                is_archived=False,
            )
            .exclude(status__in=["CLOSED", "AWAITING_VERIFICATION"])
            .select_related("assigned_to", "location", "organization")
            .order_by("organization", "target_date")
        )

        total  = overdue_qs.count()
        sent   = 0
        failed = 0

        if total == 0:
            self.stdout.write(self.style.SUCCESS("No overdue observations found."))
            return

        self.stdout.write(f"Found {total} overdue observation(s).\n")

        for obs in overdue_qs:
            assignee     = obs.assigned_to
            days_overdue = (today - obs.target_date).days

            self.stdout.write(
                f"  {'[DRY RUN] Would send' if dry_run else 'Sending'} → "
                f"Obs #{obs.pk} | {obs.title[:40]} | "
                f"{days_overdue}d overdue | "
                f"→ {assignee.email}"
            )

            if not dry_run:
                ok = send_overdue_alert(obs)
                if ok:
                    sent += 1
                else:
                    failed += 1
                    self.stderr.write(f"    ✗ Failed to send to {assignee.email}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDry run complete — {total} email(s) would have been sent."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nDone — {sent} sent, {failed} failed out of {total} total."
            ))
