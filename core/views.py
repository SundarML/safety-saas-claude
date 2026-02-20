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
    """
    Unauthenticated: full SaaS marketing landing page.
    Authenticated: app quick-launch dashboard.
    """
    steps = [
        {"icon": "🔍", "title": "Observe",  "desc": "Report hazard with description, photo, location and severity."},
        {"icon": "👤", "title": "Assign",   "desc": "Manager assigns action owner with a target rectification date."},
        {"icon": "🔧", "title": "Rectify",  "desc": "Action owner fixes the issue and submits before & after photos."},
        {"icon": "✅", "title": "Verify",   "desc": "Safety Manager approves closure or sends back for rework."},
        {"icon": "📁", "title": "Archive",  "desc": "Closed observations archived — audit-ready, permanent record."},
    ]
    ptw_steps = [
        {"icon": "📝", "title": "Draft",    "desc": "Requestor fills in work details, hazards, controls and PPE requirements."},
        {"icon": "📤", "title": "Submit",   "desc": "Permit submitted to Safety Manager for formal review."},
        {"icon": "✅", "title": "Approve",  "desc": "Safety Manager reviews and approves. Work is now authorised to begin."},
        {"icon": "⚡", "title": "Active",   "desc": "Requestor confirms work has physically started on site."},
        {"icon": "🔒", "title": "Close",    "desc": "Work complete. Site restored. Permit closed with full audit record."},
    ]
    return render(request, "home.html", {"steps": steps, "ptw_steps": ptw_steps})


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
# Organization sign-up (creates org + manager user, auto-assigns Trial plan)
# ---------------------------------------------------------------------------

def organization_signup(request):
    """
    Onboards a new organisation.

    Flow:
    1. Validate OrganizationSignupForm.
    2. Create Organization (signal auto-creates Trial Subscription).
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

            # 1. Create Organisation (signal fires → Trial Subscription created)
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


# ---------------------------------------------------------------------------
# Billing — Razorpay
# ---------------------------------------------------------------------------

import json
import hmac
import hashlib

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Plan, RazorpayOrder


@login_required
def billing_view(request):
    """
    Pricing page — shows all active plans with upgrade buttons.
    Passes current subscription so template can highlight active plan.
    """
    subscription = None
    if request.organization:
        subscription = getattr(request.organization, "subscription", None)

    plans = Plan.objects.filter(active=True).order_by("price_monthly")

    return render(request, "core/billing.html", {
        "subscription": subscription,
        "plans": plans,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    })


@login_required
@require_POST
def create_razorpay_order(request):
    """
    Creates a Razorpay order for a one-time payment.
    Called via AJAX when user clicks 'Pay Once'.
    Returns order_id and amount to the frontend JS.
    """
    import razorpay

    try:
        data     = json.loads(request.body)
        plan_id  = data.get("plan_id")
        pay_type = data.get("payment_type", "onetime")   # 'onetime' or 'recurring'

        plan = Plan.objects.get(id=plan_id, active=True)
        org  = request.organization

        if not org:
            return JsonResponse({"error": "No organization found."}, status=400)

        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        if pay_type == "onetime":
            amount = plan.onetime_paise()
            if amount == 0:
                return JsonResponse({"error": "One-time payment not available for this plan."}, status=400)

            rz_order = client.order.create({
                "amount":   amount,
                "currency": "INR",
                "receipt":  f"org_{org.id}_plan_{plan.id}",
                "notes": {
                    "organization_id": str(org.id),
                    "plan_id":         str(plan.id),
                    "payment_type":    "onetime",
                },
            })

        else:
            # Recurring — use Razorpay Subscription
            if not plan.razorpay_plan_id:
                return JsonResponse(
                    {"error": "Recurring not configured for this plan. Please contact support."},
                    status=400,
                )

            rz_sub = client.subscription.create({
                "plan_id":        plan.razorpay_plan_id,
                "total_count":    12,   # 12 months
                "quantity":       1,
                "customer_notify": 1,
                "notes": {
                    "organization_id": str(org.id),
                    "plan_id":         str(plan.id),
                },
            })

            # For recurring we return subscription_id instead of order_id
            return JsonResponse({
                "payment_type":          "recurring",
                "razorpay_subscription_id": rz_sub["id"],
                "amount":                plan.monthly_paise(),
                "plan_name":             plan.name,
                "org_name":              org.name,
                "email":                 request.user.email,
            })

        # Save the pending order
        RazorpayOrder.objects.create(
            organization=org,
            plan=plan,
            payment_type="onetime",
            razorpay_order_id=rz_order["id"],
            amount_paise=amount,
            status="created",
        )

        return JsonResponse({
            "payment_type":       "onetime",
            "razorpay_order_id":  rz_order["id"],
            "amount":             amount,
            "plan_name":          plan.name,
            "org_name":           org.name,
            "email":              request.user.email,
        })

    except Plan.DoesNotExist:
        return JsonResponse({"error": "Plan not found."}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_POST
def verify_razorpay_payment(request):
    """
    Called after Razorpay checkout succeeds on the frontend.
    Verifies the payment signature, then upgrades the subscription.
    """
    import razorpay

    try:
        data         = json.loads(request.body)
        pay_type     = data.get("payment_type", "onetime")
        plan_id      = data.get("plan_id")
        org          = request.organization

        plan = Plan.objects.get(id=plan_id)
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        if pay_type == "onetime":
            razorpay_order_id   = data.get("razorpay_order_id")
            razorpay_payment_id = data.get("razorpay_payment_id")
            razorpay_signature  = data.get("razorpay_signature")

            # Verify signature
            client.utility.verify_payment_signature({
                "razorpay_order_id":   razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature":  razorpay_signature,
            })

            # Mark order paid
            RazorpayOrder.objects.filter(
                razorpay_order_id=razorpay_order_id
            ).update(
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                status="paid",
            )

            # Upgrade subscription — one-time = 1 year access
            sub = org.subscription
            sub.plan       = plan
            sub.status     = "active"
            sub.is_active  = True
            sub.started_at = timezone.now()
            sub.expires_at = timezone.now() + timezone.timedelta(days=365)
            sub.save()

        else:
            # Recurring subscription verified
            razorpay_subscription_id = data.get("razorpay_subscription_id")
            razorpay_payment_id      = data.get("razorpay_payment_id")
            razorpay_signature       = data.get("razorpay_signature")

            client.utility.verify_subscription_payment_signature({
                "razorpay_subscription_id": razorpay_subscription_id,
                "razorpay_payment_id":      razorpay_payment_id,
                "razorpay_signature":       razorpay_signature,
            })

            # Upgrade subscription — recurring = no hard expiry (Razorpay manages it)
            sub = org.subscription
            sub.plan                     = plan
            sub.status                   = "active"
            sub.is_active                = True
            sub.started_at               = timezone.now()
            sub.expires_at               = None   # Razorpay webhook will update this
            sub.razorpay_subscription_id = razorpay_subscription_id
            sub.save()

        return JsonResponse({"success": True, "message": f"Upgraded to {plan.name}!"})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay webhook — handles subscription renewals, cancellations, failures.
    Configure this URL in your Razorpay dashboard under Webhooks.
    URL: https://yourdomain.com/billing/webhook/razorpay/
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    # Verify webhook signature
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    received_sig   = request.headers.get("X-Razorpay-Signature", "")
    body           = request.body

    expected_sig = hmac.new(
        webhook_secret.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, received_sig):
        return HttpResponse("Invalid signature", status=400)

    try:
        event = json.loads(body)
        event_type = event.get("event")

        if event_type == "subscription.charged":
            # Recurring payment succeeded — extend subscription
            payload     = event["payload"]["subscription"]["entity"]
            rz_sub_id   = payload["id"]
            sub = Subscription.objects.filter(
                razorpay_subscription_id=rz_sub_id
            ).first()
            if sub:
                sub.status    = "active"
                sub.is_active = True
                sub.expires_at = timezone.now() + timezone.timedelta(days=32)
                sub.save()

        elif event_type == "subscription.cancelled":
            payload   = event["payload"]["subscription"]["entity"]
            rz_sub_id = payload["id"]
            sub = Subscription.objects.filter(
                razorpay_subscription_id=rz_sub_id
            ).first()
            if sub:
                sub.status    = "cancelled"
                sub.is_active = False
                sub.save()

        elif event_type == "subscription.halted":
            # Payment failed repeatedly — downgrade to Trial
            payload   = event["payload"]["subscription"]["entity"]
            rz_sub_id = payload["id"]
            sub = Subscription.objects.filter(
                razorpay_subscription_id=rz_sub_id
            ).first()
            if sub:
                trial_plan = Plan.objects.filter(tier="trial").first()
                if trial_plan:
                    sub.plan      = trial_plan
                sub.status    = "expired"
                sub.is_active = False
                sub.save()

    except Exception:
        pass   # Never return 500 to Razorpay — it will keep retrying

    return HttpResponse(status=200)


from django.http import HttpResponse
from .models import Subscription


# ---------------------------------------------------------------------------
# Contractor Invite (Manager only)
# ---------------------------------------------------------------------------

@login_required
def invite_contractor(request):
    """
    Manager-only view to invite contractor users.
    Contractors get limited access: Permits module only, no approval rights.
    """
    if not request.user.is_manager:
        raise PermissionDenied("Only managers can invite contractor users.")

    if not request.organization:
        messages.error(request, "You must be part of an organization to invite contractors.")
        return redirect("home")

    if request.method == "POST":
        from .forms import InviteContractorForm
        form = InviteContractorForm(request.POST)

        if form.is_valid():
            from django.contrib.auth import get_user_model
            from django.contrib.auth.hashers import get_random_string

            User = get_user_model()
            email = form.cleaned_data["email"]
            temp_password = get_random_string(length=12)

            # Create contractor user
            contractor = User.objects.create(
                email=email,
                full_name=form.cleaned_data["full_name"],
                organization=request.organization,
                is_contractor=True,
                contractor_company=form.cleaned_data["contractor_company"],
                contractor_phone=form.cleaned_data["contractor_phone"],
                contractor_access_expiry=form.cleaned_data.get("contractor_access_expiry"),
                is_active=True,
            )
            contractor.set_password(temp_password)
            contractor.save()

            # Send email with credentials
            from core.utils.email import send_brevo_email
            subject = f"Contractor Access — {request.organization.name}"
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px;">
              <h2 style="color:#0a2540;">Contractor Access Granted</h2>
              <p>You have been granted contractor access to <strong>{request.organization.name}</strong> 
              safety management system.</p>
              
              <div style="background:#f6f9fc;border-left:4px solid #635bff;padding:16px;margin:20px 0;">
                <p style="margin:0;"><strong>Company:</strong> {contractor.contractor_company}</p>
                <p style="margin:8px 0 0 0;"><strong>Login Email:</strong> {email}</p>
                <p style="margin:8px 0 0 0;"><strong>Temporary Password:</strong> <code style="background:#e3e8ee;padding:4px 8px;border-radius:4px;">{temp_password}</code></p>
              </div>

              <p><strong>What you can do:</strong></p>
              <ul>
                <li>Create Permit to Work requests for high-risk activities</li>
                <li>Edit and submit your draft permits for approval</li>
                <li>View the status of your submitted permits</li>
              </ul>

              <p><strong>Access restrictions:</strong></p>
              <ul>
                <li>You cannot approve, activate, or close permits (site team does this)</li>
                <li>You cannot access Safety Observations or other modules</li>
                <li>You can only see your own permit requests</li>
              </ul>

              {f'<p style="color:#cd3d64;"><strong>Access expires:</strong> {contractor.contractor_access_expiry:%d %b %Y}</p>' if contractor.contractor_access_expiry else ''}

              <p style="margin-top:24px;">
                <a href="{getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')}/users/accounts/login/" 
                   style="background:#635bff;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;display:inline-block;">
                  Login Now
                </a>
              </p>

              <hr style="margin:32px 0;border:none;border-top:1px solid #e3e8ee;">
              <p style="font-size:12px;color:#697386;">
                For support, contact {request.organization.name} safety team.<br>
                Vigilo — Safety Observation & Permit Management
              </p>
            </div>
            """

            email_sent = send_brevo_email(email, subject, html)

            if email_sent:
                messages.success(
                    request,
                    f"Contractor {contractor.contractor_company} invited successfully. "
                    f"Login credentials sent to {email}.",
                )
            else:
                messages.warning(
                    request,
                    f"Contractor created but email failed to send. "
                    f"Please share credentials manually: {email} / {temp_password}",
                )

            return redirect("core:invite_contractor")

    else:
        from .forms import InviteContractorForm
        form = InviteContractorForm()

    # List existing contractors
    from django.contrib.auth import get_user_model
    User = get_user_model()
    contractors = User.objects.filter(
        organization=request.organization,
        is_contractor=True,
    ).order_by("-id")

    return render(request, "core/invite_contractor.html", {
        "form": form,
        "contractors": contractors,
    })
