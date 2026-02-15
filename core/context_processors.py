# core/context_processors.py
from django.utils import timezone


def trial_status(request):
    """
    Injects trial days remaining into every template.
    Safe: handles None expires_at (lifetime / no-expiry plans).
    """
    if not request.user.is_authenticated:
        return {}

    org = getattr(request, "organization", None)
    if org is None:
        return {}

    sub = getattr(org, "subscription", None)
    if sub is None:
        return {}

    if sub.expires_at is None:
        return {"trial_days_left": None}  # Not on a time-limited plan

    remaining = (sub.expires_at - timezone.now()).days
    return {"trial_days_left": max(remaining, 0)}


def organization_context(request):
    """Injects current org and user into every template."""
    org = None
    if request.user.is_authenticated:
        org = getattr(request.user, "organization", None)

    return {
        "current_org": org,
        "current_user": request.user,
    }
