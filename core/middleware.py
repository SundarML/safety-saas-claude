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

class SubscriptionMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if hasattr(request, "organization"):
            sub = getattr(request.organization, "subscription", None)

            if sub is not None and sub.is_expired():

                allowed = [
                    reverse("core:billing"),
                    reverse("logout"),
                ]

                if request.path not in allowed:
                    return redirect("core:billing")

        return self.get_response(request)
