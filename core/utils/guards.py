# core/utils/guards.py
"""
Shared permission guard utilities used across all apps.
"""
from django.core.exceptions import PermissionDenied


def org_required(request):
    """
    Raise PermissionDenied if the user has no associated organization.
    Use in function-based views before any org-scoped DB access.

    Usage:
        from core.utils.guards import org_required

        @login_required
        def my_view(request):
            org_required(request)
            ...
    """
    if not request.organization:
        raise PermissionDenied("You are not associated with any organization.")
