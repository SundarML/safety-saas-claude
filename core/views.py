# core/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Organization, Plan, Subscription, UserInvite, ContractorInvite
from .forms import (
    OrganizationSignupForm,
    InviteUserForm, AcceptInviteForm,
    ContractorInviteForm, AcceptContractorInviteForm,
    DemoRequestForm, FreePlanRequestForm,
)
from users.models import CustomUser
from users.forms import CreateWorkerForm, ResetWorkerPinForm


# ---------------------------------------------------------------------------
# Marketing / public pages
# ---------------------------------------------------------------------------

def home_view(request):
    """Marketing homepage — redirects authenticated users to the app dashboard."""
    if request.user.is_authenticated:
        return redirect("core:app_dashboard")
    return render(request, "home.html", {})


def pricing_view(request):
    """Public pricing page."""
    return render(request, "pricing.html", {})


def help_view(request):
    """Public help & user guide — accessible without login."""
    return render(request, "help.html", {})


@login_required
def app_dashboard_view(request):
    """Post-login landing page — live KPIs + module quick-actions."""
    user = request.user
    org  = getattr(request, "organization", None)
    today = timezone.now().date()
    ctx = {"today": today}

    if not org:
        return render(request, "app_dashboard.html", ctx)

    is_manager = user.is_manager or user.is_safety_manager

    # ── Observations ──────────────────────────────────────────────────────────
    from observations.models import Observation
    obs_qs = Observation.objects.filter(organization=org)
    ctx["obs_open"]       = obs_qs.filter(status__in=["OPEN", "IN_PROGRESS"]).count()
    ctx["obs_overdue"]    = obs_qs.filter(
        status__in=["OPEN", "IN_PROGRESS"],
        target_date__lt=today,
    ).count()
    ctx["obs_awaiting"]   = obs_qs.filter(status="AWAITING_VERIFICATION").count()
    ctx["obs_mine"]       = obs_qs.filter(
        assigned_to=user,
        status__in=["OPEN", "IN_PROGRESS"],
    ).count()
    ctx["obs_recent"]     = obs_qs.filter(
        assigned_to=user,
        status__in=["OPEN", "IN_PROGRESS"],
    ).select_related("location").order_by("-date_observed")[:3]

    # ── Permits ───────────────────────────────────────────────────────────────
    from permits.models import Permit
    permit_qs = Permit.objects.filter(organization=org)
    ctx["permit_active"]    = permit_qs.filter(status__in=["APPROVED", "ACTIVE"]).count()
    ctx["permit_submitted"] = permit_qs.filter(status="SUBMITTED").count()
    ctx["permit_mine"]      = permit_qs.filter(
        requestor=user,
        status__in=["DRAFT", "SUBMITTED", "APPROVED", "ACTIVE"],
    ).count()
    ctx["permit_recent"]    = permit_qs.filter(
        requestor=user,
        status__in=["DRAFT", "SUBMITTED", "APPROVED", "ACTIVE"],
    ).order_by("-id")[:3]

    # ── HIRA ──────────────────────────────────────────────────────────────────
    from hira.models import HazardRegister, Hazard
    hira_qs = HazardRegister.objects.filter(organization=org)
    all_hazards = Hazard.objects.filter(register__organization=org)
    ctx["hira_total"]    = hira_qs.count()
    ctx["hira_critical"] = sum(1 for h in all_hazards if h.effective_risk_level == "critical")
    ctx["hira_high"]     = sum(1 for h in all_hazards if h.effective_risk_level == "high")
    ctx["hira_actions_mine"] = all_hazards.filter(
        action_required=True, action_owner=user
    ).count()
    ctx["hira_review_due"] = hira_qs.filter(
        status="approved",
        next_review_date__lte=today,
    ).count()

    # ── Compliance ────────────────────────────────────────────────────────────
    from compliance.models import ComplianceItem
    comp_qs = ComplianceItem.objects.filter(organization=org)
    ctx["comp_overdue"]  = comp_qs.filter(status="overdue").count()
    ctx["comp_due_soon"] = comp_qs.filter(
        status="pending",
        due_date__range=[today, today + timezone.timedelta(days=30)],
    ).count()
    ctx["comp_score"]    = 0
    total_comp = comp_qs.count()
    if total_comp:
        ctx["comp_score"] = round(comp_qs.filter(status="complied").count() / total_comp * 100)

    # ── Training ──────────────────────────────────────────────────────────────
    from training.models import TrainingModule, AssessmentAttempt
    ctx["training_modules"] = TrainingModule.objects.filter(organization=org).count()
    ctx["my_attempts"]      = AssessmentAttempt.objects.filter(
        user=user
    ).select_related("assessment__training_module").order_by("-submitted_at")[:3]

    # ── Corrective Actions ────────────────────────────────────────────────────
    from actions.models import CorrectiveAction
    ca_qs = CorrectiveAction.objects.filter(organization=org)
    ctx["ca_open"]     = ca_qs.exclude(status=CorrectiveAction.STATUS_CLOSED).count()
    ctx["ca_overdue"]  = sum(1 for a in ca_qs.exclude(status=CorrectiveAction.STATUS_CLOSED) if a.is_overdue)
    ctx["ca_mine"]     = ca_qs.filter(
        assigned_to=user,
    ).exclude(status=CorrectiveAction.STATUS_CLOSED).count()
    ctx["ca_pending_verification"] = ca_qs.filter(
        status=CorrectiveAction.STATUS_PENDING_VERIFICATION
    ).count()
    ctx["ca_mine_list"] = ca_qs.filter(
        assigned_to=user,
    ).exclude(status=CorrectiveAction.STATUS_CLOSED).order_by("due_date")[:5]

    from incidents.models import Incident
    inc_qs = Incident.objects.filter(organization=org)
    ctx["inc_open"]          = inc_qs.exclude(status=Incident.STATUS_CLOSED).count()
    ctx["inc_investigating"]  = inc_qs.filter(status=Incident.STATUS_INVESTIGATING).count()
    ctx["inc_recent"]        = inc_qs.exclude(status=Incident.STATUS_CLOSED).order_by("-date_occurred")[:5]

    from inspections.models import Inspection
    insp_qs = Inspection.objects.filter(organization=org)
    today   = __import__("datetime").date.today()
    # Auto-flag overdue
    insp_qs.filter(
        scheduled_date__lt=today,
        status__in=[Inspection.STATUS_SCHEDULED, Inspection.STATUS_IN_PROGRESS],
    ).update(status=Inspection.STATUS_OVERDUE)
    ctx["insp_scheduled"] = insp_qs.filter(status=Inspection.STATUS_SCHEDULED).count()
    ctx["insp_overdue"]   = insp_qs.filter(status=Inspection.STATUS_OVERDUE).count()
    ctx["insp_upcoming"]  = insp_qs.filter(
        status=Inspection.STATUS_SCHEDULED
    ).order_by("scheduled_date")[:4]

    ctx["is_manager"] = is_manager
    return render(request, "app_dashboard.html", ctx)


def request_demo_view(request):
    if request.method == "POST":
        form = DemoRequestForm(request.POST)
        if form.is_valid():
            demo = form.save()
            from core.utils.email import notify_admin_demo_request
            notify_admin_demo_request(demo)
            messages.success(
                request,
                "Thank you! Our team will contact you shortly to schedule the demo.",
            )
            return redirect("home")
    else:
        form = DemoRequestForm()

    return render(request, "request_demo.html", {"form": form})


def request_free_plan_view(request):
    if request.method == "POST":
        form = FreePlanRequestForm(request.POST)
        if form.is_valid():
            free_req = form.save()
            from core.utils.email import notify_admin_free_plan_request
            notify_admin_free_plan_request(free_req)
            messages.success(
                request,
                "Thank you! Our team will review your request and get back to you shortly.",
            )
            return redirect("home")
    else:
        form = FreePlanRequestForm()

    return render(request, "core/request_free_plan.html", {"form": form})


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
        return redirect("core:app_dashboard")

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
                role=CustomUser.ROLE_MANAGER,
            )

            # 3. Log in and go to dashboard
            login(request, user)
            messages.success(
                request,
                f"Welcome! Your organization '{org.name}' has been created.",
            )
            return redirect("core:app_dashboard")

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

            # send_brevo_email() already logs internally on failure and never raises,
            # so no try/except is needed — just call it directly.
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

            # Assign role
            role_map = {
                "manager":      CustomUser.ROLE_MANAGER,
                "safety_manager": CustomUser.ROLE_SAFETY_MANAGER,
                "observer":     CustomUser.ROLE_OBSERVER,
                "action_owner": CustomUser.ROLE_ACTION_OWNER,
            }
            user.role = role_map.get(invite.role, CustomUser.ROLE_OBSERVER)

            user.save()

            invite.is_used = True
            invite.save()

            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("core:app_dashboard")

    else:
        form = AcceptInviteForm()

    return render(
        request,
        "core/accept_invite.html",
        {"form": form, "invite": invite},
    )


# ---------------------------------------------------------------------------
# Invite contractor (manager only)
# ---------------------------------------------------------------------------

@login_required
def invite_contractor(request):
    if not request.user.is_manager:
        raise PermissionDenied

    org = request.organization
    if org is None:
        messages.error(request, "You are not associated with any organization.")
        return redirect("home")

    if request.method == "POST":
        form = ContractorInviteForm(request.POST)

        if form.is_valid():
            invite = ContractorInvite(
                organization=org,
                email=form.cleaned_data["email"],
                access_validity_days=form.cleaned_data.get("access_validity_days"),
                expires_at=timezone.now() + timezone.timedelta(days=7),
            )
            invite.save()

            invite_link = request.build_absolute_uri(
                reverse("core:accept_contractor_invite", args=[invite.token])
            )

            from core.utils.email import send_brevo_email
            html = render_to_string(
                "emails/invite_contractor.html",
                {
                    "organization": org,
                    "invite_link": invite_link,
                    "access_validity_days": invite.access_validity_days,
                },
            )
            send_brevo_email(
                to_email=invite.email,
                subject=f"Contractor Invitation — {org.name}",
                html_content=html,
            )

            messages.success(request, f"Contractor invitation sent to {invite.email}.")
            return redirect("core:invite_contractor")

    else:
        form = ContractorInviteForm()

    pending_invites = ContractorInvite.objects.filter(
        organization=org, is_used=False
    ).order_by("-created_at")

    return render(
        request,
        "core/invite_contractor.html",
        {"form": form, "pending_invites": pending_invites},
    )


# ---------------------------------------------------------------------------
# Accept contractor invite
# ---------------------------------------------------------------------------

def accept_contractor_invite(request, token):
    invite = get_object_or_404(ContractorInvite, token=token)

    if not invite.is_valid():
        return render(request, "core/invite_invalid.html")

    if request.method == "POST":
        form = AcceptContractorInviteForm(request.POST)

        if form.is_valid():
            user = CustomUser.objects.filter(email=invite.email).first()

            if not user:
                user = CustomUser.objects.create_user(
                    email=invite.email,
                    password=form.cleaned_data["password1"],
                    full_name=form.cleaned_data["full_name"],
                    company=form.cleaned_data.get("company", ""),
                    phone=form.cleaned_data.get("phone", ""),
                    trade=form.cleaned_data.get("trade", ""),
                    organization=invite.organization,
                    role=CustomUser.ROLE_CONTRACTOR,
                )
            else:
                user.organization = invite.organization
                user.role = CustomUser.ROLE_CONTRACTOR
                user.full_name = form.cleaned_data["full_name"]
                user.company = form.cleaned_data.get("company", "")
                user.phone = form.cleaned_data.get("phone", "")
                user.trade = form.cleaned_data.get("trade", "")
                user.set_password(form.cleaned_data["password1"])

            # Set contractor access expiry if specified
            if invite.access_validity_days:
                user.access_expires_at = timezone.now() + timezone.timedelta(
                    days=invite.access_validity_days
                )

            user.save()

            invite.is_used = True
            invite.save()

            login(request, user)
            messages.success(request, "Account created. Welcome to Vigilo!")
            return redirect("permits:permit_list")

    else:
        form = AcceptContractorInviteForm()

    return render(
        request,
        "core/accept_contractor_invite.html",
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


# ---------------------------------------------------------------------------
# Worker management (no-email accounts with Employee ID + PIN)
# ---------------------------------------------------------------------------

def _manager_required(request):
    if not request.user.is_authenticated or not request.user.is_manager:
        raise PermissionDenied


@login_required
def worker_list_view(request):
    """Manager: list all worker (no-email) accounts in the organisation."""
    _manager_required(request)
    org = request.organization
    workers = CustomUser.objects.filter(
        organization=org, email__isnull=True
    ).order_by("full_name", "employee_id")
    reset_form = ResetWorkerPinForm()
    return render(request, "core/worker_list.html", {
        "workers": workers,
        "reset_form": reset_form,
        "org": org,
    })


@login_required
def create_worker_view(request):
    """Manager: create a new no-email worker account."""
    _manager_required(request)
    org = request.organization

    if request.method == "POST":
        form = CreateWorkerForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Duplicate employee ID check
            if CustomUser.objects.filter(organization=org, employee_id=cd["employee_id"]).exists():
                form.add_error("employee_id", "This Employee ID already exists in your organisation.")
            else:
                CustomUser.objects.create_worker_user(
                    employee_id=cd["employee_id"],
                    pin=cd["pin"],
                    organization=org,
                    full_name=cd["full_name"],
                    role=cd["role"],
                )
                messages.success(
                    request,
                    f"Worker account created for {cd['full_name']} (ID: {cd['employee_id']})."
                )
                return redirect("core:worker_list")
    else:
        form = CreateWorkerForm()

    return render(request, "core/create_worker.html", {"form": form})


@login_required
def reset_worker_pin_view(request, worker_id):
    """Manager: reset PIN for a worker account."""
    _manager_required(request)
    org = request.organization
    worker = get_object_or_404(CustomUser, pk=worker_id, organization=org, email__isnull=True)

    if request.method == "POST":
        form = ResetWorkerPinForm(request.POST)
        if form.is_valid():
            worker.set_pin(form.cleaned_data["new_pin"])
            worker.save(update_fields=["pin_hash"])
            messages.success(request, f"PIN reset for {worker.get_full_name()}.")
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.error(request, e)

    return redirect("core:worker_list")


@login_required
def toggle_worker_active_view(request, worker_id):
    """Manager: activate or deactivate a worker account."""
    _manager_required(request)
    org = request.organization
    worker = get_object_or_404(CustomUser, pk=worker_id, organization=org, email__isnull=True)

    if request.method == "POST":
        worker.is_active = not worker.is_active
        worker.save(update_fields=["is_active"])
        state = "activated" if worker.is_active else "deactivated"
        messages.success(request, f"{worker.get_full_name()} has been {state}.")

    return redirect("core:worker_list")
