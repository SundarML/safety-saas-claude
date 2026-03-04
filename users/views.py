# users/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from users.forms import EmailLoginForm, ProfileUpdateForm


class CustomLoginView(LoginView):
    template_name = "users/login.html"
    authentication_form = EmailLoginForm


@login_required
def profile_view(request):
    """User profile page — view and edit own account details."""
    subscription = None
    if request.organization:
        subscription = getattr(request.organization, "subscription", None)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=request.user, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("users:profile")
    else:
        form = ProfileUpdateForm(instance=request.user, user=request.user)

    return render(request, "users/profile.html", {
        "subscription": subscription,
        "form": form,
    })


