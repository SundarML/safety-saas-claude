# core/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Organization, Subscription, Plan


@receiver(post_save, sender=Organization)
def create_trial_subscription(sender, instance, created, **kwargs):
    """Auto-create a Trial subscription whenever a new Organization is created."""
    if created:
        try:
            trial_plan = Plan.objects.get(name="Trial")
        except Plan.DoesNotExist:
            raise RuntimeError(
                "Trial plan not found. Please create it in the admin or shell first."
            )
        Subscription.objects.get_or_create(
            organization=instance,
            defaults={"plan": trial_plan},
        )
