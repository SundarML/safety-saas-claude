from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Subscription, Plan


class Command(BaseCommand):
    help = "Downgrade expired subscriptions to Free plan"

    def handle(self, *args, **kwargs):

        now = timezone.now()

        # `expires_at` is the correct field name on Subscription.
        # Filter only active subs that have an expiry date set and have passed it.
        expired_subs = Subscription.objects.filter(
            is_active=True,
            expires_at__isnull=False,
            expires_at__lt=now,
        )

        try:
            free_plan = Plan.objects.get(name="Free")
        except Plan.DoesNotExist:
            self.stderr.write(self.style.ERROR(
                "Free plan not found. Create it in the admin first."
            ))
            return

        count = 0

        for sub in expired_subs:
            sub.plan = free_plan
            sub.is_active = False
            sub.save(update_fields=["plan", "is_active", "updated_at"])
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{count} subscription(s) downgraded to Free."
        ))
