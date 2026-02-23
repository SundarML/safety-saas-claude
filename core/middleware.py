from django.shortcuts import redirect
from django.urls import reverse

# core/middleware.py
class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.organization = request.user.organization
        else:
            request.organization = None
        return self.get_response(request)

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class SubscriptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.organization:

            # ── Contractor checks ────────────────────────────────────────
            if request.user.is_contractor:
                # Block access to Observations entirely
                if request.path.startswith("/observations/"):
                    return redirect("permits:permit_list")

                # Block access to admin area
                if request.path.startswith("/admin/"):
                    return redirect("permits:permit_list")

                # Check contractor access expiry
                exp = request.user.access_expires_at
                if exp and timezone.now() > exp:
                    from django.contrib.auth import logout as _logout
                    _logout(request)
                    return redirect(reverse("login") + "?contractor_expired=1")

            # ── Subscription expiry check ────────────────────────────────
            else:
                sub = getattr(request.organization, "subscription", None)

                if sub is not None and sub.is_expired():
                    allowed = [
                        reverse("core:billing"),
                        reverse("logout"),
                    ]
                    if request.path not in allowed:
                        return redirect("core:billing")

        return self.get_response(request)
