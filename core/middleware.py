# core/middleware.py
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone


class OrganizationMiddleware:
    """Attach the user's organization to every request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.organization = getattr(request.user, "organization", None)
        else:
            request.organization = None
        return self.get_response(request)


class SubscriptionMiddleware:
    """Check subscription limits (users, observations) before allowing actions."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Not enforced currently — placeholder for future enforcement
        return self.get_response(request)


class ContractorAccessMiddleware:
    """
    Restrict contractor users to ONLY the Permits module.
    Contractors cannot access:
    - Observations (create, list, detail, dashboard, export, archive)
    - Core (invite users, billing, demo requests)
    - Users (profile changes beyond basic info)
    - Admin panel
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip middleware for non-authenticated users or non-contractors
        if not request.user.is_authenticated or not request.user.is_contractor:
            return self.get_response(request)

        # ── Check if contractor access has expired ────────────────────────
        if request.user.is_contractor_expired:
            messages.error(
                request,
                f"Your contractor access expired on {request.user.contractor_access_expiry:%d %b %Y}. "
                "Please contact the site administrator to renew access.",
            )
            from django.contrib.auth import logout
            logout(request)
            return redirect("users:login")

        # ── Allow access to these paths ────────────────────────────────────
        allowed_paths = [
            "/permits/",               # Permits module
            "/users/accounts/login/",  # Login
            "/users/accounts/logout/", # Logout
            "/logout/",                # Legacy logout
            "/users/profile/",         # Basic profile (read-only)
            "/static/",                # Static files
            "/media/",                 # Media files
        ]

        path = request.path
        for allowed in allowed_paths:
            if path.startswith(allowed):
                return self.get_response(request)

        # ── Block access to everything else ────────────────────────────────
        blocked_areas = {
            "/observations/": "Safety Observations",
            "/core/": "Organization Management",
            "/billing/": "Billing & Plans",
            "/admin/": "Admin Panel",
            "/": "Home Dashboard",
        }

        for blocked_path, area_name in blocked_areas.items():
            if path.startswith(blocked_path):
                messages.warning(
                    request,
                    f"Contractor users do not have access to {area_name}. "
                    "You can only create and manage your own permit requests.",
                )
                return redirect("permits:permit_list")

        # Default: if unsure, redirect to permits
        return self.get_response(request)
