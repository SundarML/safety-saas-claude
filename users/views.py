# users/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from users.forms import EmailLoginForm


class CustomLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = EmailLoginForm


@login_required
def profile_view(request):
    """User profile page — shows account and organization details."""
    subscription = None
    if request.organization:
        subscription = getattr(request.organization, "subscription", None)

    return render(request, "users/profile.html", {
        "subscription": subscription,
    })


