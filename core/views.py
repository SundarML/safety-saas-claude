# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Organization, Plan, Subscription, UserInvite
from .forms import OrganizationSignupForm, InviteUserForm, AcceptInviteForm, DemoRequestForm
from users.models import CustomUser


# ---------------------------------------------------------------------------
# Marketing / public pages
# ---------------------------------------------------------------------------

def home_view(request):
    """Marketing homepage — redirects authenticated users to the dashboard."""
    if request.user.is_authenticated:
        return redirect("observations:observation_list")
    return render(request, "home.html", {})


def request_demo_view(request):
    if request.method == "POST":
        form = DemoRequestForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Thank you! Our team will contact you shortly to schedule the demo.",
            )
            return redirect("home")
    else:
        form = DemoRequestForm()

    return render(request, "request_demo.html", {"form": form})


# ---------------------------------------------------------------------------
# Organization sign-up (creates org + manager user, auto-assigns Free plan)
# ---------------------------------------------------------------------------

def organization_signup(request):
    """
    Onboards a new organisation.

    Flow:
    1. Validate OrganizationSignupForm.
    2. Create Organization (signal auto-creates Free Subscription).
    3. Create the manager CustomUser linked to that org.
    4. Log in and redirect to dashboard.
    """
    if request.user.is_authenticated:
        return redirect("observations:observation_list")

    if request.method == "POST":
        form = OrganizationSignupForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            # Prevent duplicate accounts
            if CustomUser.objects.filter(email=email).exists():
                form.add_error("email", "An account with this email already exists.")
                return render(request, "core/signup.html", {"form": form})

            # 1. Create Organisation (signal fires → Free Subscription created)
            org = Organization.objects.create(
                name=form.cleaned_data["organization_name"],
                domain=form.cleaned_data["domain"],
            )

            # 2. Create the manager user
            user = CustomUser.objects.create_user(
                email=email,
                password=form.cleaned_data["password1"],
                organization=org,
                is_manager=True,
            )

            # 3. Log in and go to dashboard
            login(request, user)
            messages.success(
                request,
                f"Welcome! Your organization '{org.name}' has been created.",
            )
            return redirect("observations:observation_list")

    else:
        form = OrganizationSignupForm()

    return render(request, "core/signup.html", {"form": form})


# ---------------------------------------------------------------------------
# Invite user (manager only)
# ---------------------------------------------------------------------------

@login_required
def invite_user(request):
    if not request.user.is_manager:
        raise PermissionDenied

    org = request.organization
    if org is None:
        messages.error(request, "You are not associated with any organization.")
        return redirect("home")

    # Check subscription user limit
    subscription = getattr(org, "subscription", None)
    if subscription and subscription.plan.max_users is not None:
        current_count = CustomUser.objects.filter(organization=org).count()
        if current_count >= subscription.plan.max_users:
            messages.error(
                request,
                "User limit reached for your current plan. Upgrade to invite more members.",
            )
            return redirect("core:billing")

    if request.method == "POST":
        form = InviteUserForm(request.POST)

        if form.is_valid():
            invite = form.save(commit=False)
            invite.organization = org
            invite.expires_at = timezone.now() + timezone.timedelta(days=7)
            invite.save()

            invite_link = request.build_absolute_uri(
                reverse("core:accept_invite", args=[invite.token])
            )

            try:
                from core.utils.email import send_brevo_email
                html = render_to_string(
                    "emails/invite_user.html",
                    {
                        "organization": org,
                        "invite_link": invite_link,
                    },
                )
                send_brevo_email(
                    to_email=invite.email,
                    subject=f"You're invited to join {org.name} on Safety Observation Platform",
                    html_content=html,
                )
            except Exception:
                # Email sending failure should not break the invite flow
                pass

            messages.success(request, f"Invitation sent to {invite.email}.")
            return redirect("core:invite_user")

    else:
        form = InviteUserForm()

    pending_invites = UserInvite.objects.filter(
        organization=org, is_used=False
    ).order_by("-created_at")

    return render(
        request,
        "core/invite_user.html",
        {"form": form, "pending_invites": pending_invites},
    )


# ---------------------------------------------------------------------------
# Accept invite (new team member sets their password)
# ---------------------------------------------------------------------------

def accept_invite(request, token):
    invite = get_object_or_404(UserInvite, token=token)

    if not invite.is_valid():
        return render(request, "core/invite_invalid.html")

    if request.method == "POST":
        form = AcceptInviteForm(request.POST)

        if form.is_valid():
            user = CustomUser.objects.filter(email=invite.email).first()

            if not user:
                user = CustomUser.objects.create_user(
                    email=invite.email,
                    password=form.cleaned_data["password1"],
                    full_name=form.cleaned_data.get("full_name", ""),
                    organization=invite.organization,
                )
            else:
                user.organization = invite.organization
                user.set_password(form.cleaned_data["password1"])

            # Assign role flags
            if invite.role == "manager":
                user.is_manager = True
            elif invite.role == "observer":
                user.is_observer = True
            elif invite.role == "action_owner":
                user.is_action_owner = True
            elif invite.role == "safety_manager":
                user.is_safety_manager = True

            user.save()

            invite.is_used = True
            invite.save()

            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("observations:observation_list")

    else:
        form = AcceptInviteForm()

    return render(
        request,
        "core/accept_invite.html",
        {"form": form, "invite": invite},
    )


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------

@login_required
def billing_view(request):
    subscription = None
    if request.organization:
        subscription = getattr(request.organization, "subscription", None)

    return render(request, "core/billing.html", {"subscription": subscription})
