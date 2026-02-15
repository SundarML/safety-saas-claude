from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Subscription, Plan


class Command(BaseCommand):
    help = "Downgrade expired subscriptions to Free plan"

    def handle(self, *args, **kwargs):

        now = timezone.now()

        expired_subs = Subscription.objects.filter(
            is_active=True,
            end_date__lt=now
        )

        free_plan = Plan.objects.get(name="Free")

        count = 0

        for sub in expired_subs:
            sub.plan = free_plan
            sub.is_active = False
            sub.save()
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{count} subscriptions downgraded."
        ))
