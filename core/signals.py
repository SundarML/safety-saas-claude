# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Organization, Subscription, Plan


@receiver(post_save, sender=Organization)
def create_free_subscription(sender, instance, created, **kwargs):
    """Auto-create a Free subscription whenever a new Organization is created."""
    if created:
        free_plan, _ = Plan.objects.get_or_create(
            name="Free",
            defaults={
                "max_users": 5,
                "max_observations": 50,
                "price_monthly": 0,
            },
        )
        Subscription.objects.get_or_create(
            organization=instance,
            defaults={"plan": free_plan},
        )
