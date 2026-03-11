# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, authenticate, login
from django.http import HttpResponse, Http404

from users.forms import EmailLoginForm, ProfileUpdateForm, OrgLogoForm, WorkerLoginForm

User = get_user_model()


def worker_login_view(request):
    """
    Login page for no-email worker accounts.
    Accepts: org_domain + employee_id + PIN.
    Managers can share a pre-filled URL: /users/worker-login/?org=<domain>
    """
    # Pre-fill org from URL param (shareable link)
    prefill_org = request.GET.get("org", "")

    if request.method == "POST":
        form = WorkerLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                employee_id=form.cleaned_data["employee_id"],
                pin=form.cleaned_data["pin"],
                org_domain=form.cleaned_data["org_domain"],
            )
            if user is not None:
                login(request, user, backend="users.backends.EmployeeIdPinBackend")
                next_url = request.GET.get("next") or "training:module_list"
                return redirect(next_url)
            else:
                form.add_error(None, "Invalid Organisation Code, Employee ID, or PIN.")
    else:
        initial = {"org_domain": prefill_org} if prefill_org else {}
        form = WorkerLoginForm(initial=initial)

    return render(request, "users/worker_login.html", {
        "form": form,
        "prefill_org": prefill_org,
    })


@login_required
def profile_redirect_view(request):
    """Redirect to own profile detail page."""
    return redirect("users:profile_detail", user_id=request.user.pk)


@login_required
def profile_view(request):
    """Legacy redirect — kept so any existing links still work."""
    return redirect("users:profile_detail", user_id=request.user.pk)


@login_required
def profile_detail_view(request, user_id):
    """User profile page — own profile editable, others visible to managers only."""
    profile_user = get_object_or_404(User, pk=user_id)
    is_own_profile = (request.user.pk == profile_user.pk)

    # Access control
    if not is_own_profile:
        viewer = request.user
        can_view = (
            (viewer.is_manager or viewer.is_safety_manager)
            and viewer.organization == profile_user.organization
        )
        if not can_view:
            raise Http404

    org = profile_user.organization

    # Edit form (own profile only)
    form = None
    if is_own_profile:
        if request.method == "POST":
            form = ProfileUpdateForm(request.POST, instance=profile_user, user=profile_user)
            if form.is_valid():
                form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect("users:profile_detail", user_id=user_id)
        else:
            form = ProfileUpdateForm(instance=profile_user, user=profile_user)

    # Performance stats
    obs_stats = {}
    training_stats = {}
    observer_result = None
    action_owner_result = None
    training_result = None

    if org:
        from users.performance import (
            get_observation_stats, get_training_stats,
            calculate_observer_stars, calculate_action_owner_stars, calculate_training_stars,
        )
        obs_stats = get_observation_stats(profile_user, org)
        training_stats = get_training_stats(profile_user, org)
        observer_result = calculate_observer_stars(profile_user, org)
        action_owner_result = calculate_action_owner_stars(profile_user, org)
        training_result = calculate_training_stars(profile_user, org)

    # Plotly charts — only build if there's data
    observer_severity_chart = ""
    observer_status_chart = ""
    action_status_chart = ""
    training_skills_chart = ""

    if org and obs_stats.get("total_reported", 0) > 0:
        import plotly.graph_objects as go
        import plotly.io as pio

        sev = obs_stats["by_severity"]
        fig = go.Figure(go.Pie(
            labels=["Low", "Medium", "High"],
            values=[sev["LOW"], sev["MEDIUM"], sev["HIGH"]],
            hole=0.45,
            marker_colors=["#198754", "#fd7e14", "#dc3545"],
            textinfo="label+percent",
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), showlegend=False, height=240)
        observer_severity_chart = pio.to_html(fig, full_html=False, include_plotlyjs="cdn")

        rbs = obs_stats["reported_by_status"]
        fig2 = go.Figure(go.Bar(
            x=["Open", "In Progress", "Awaiting", "Closed"],
            y=[rbs["OPEN"], rbs["IN_PROGRESS"], rbs["AWAITING_VERIFICATION"], rbs["CLOSED"]],
            marker_color=["#6c757d", "#0d6efd", "#ffc107", "#198754"],
        ))
        fig2.update_layout(margin=dict(l=10, r=10, t=10, b=30), height=240,
                           yaxis_title="Count", xaxis_title=None)
        observer_status_chart = pio.to_html(fig2, full_html=False, include_plotlyjs=False)

    if org and obs_stats.get("total_assigned", 0) > 0:
        import plotly.graph_objects as go
        import plotly.io as pio

        abs_ = obs_stats["assigned_by_status"]
        fig3 = go.Figure(go.Bar(
            x=["Open", "In Progress", "Awaiting", "Closed"],
            y=[abs_["OPEN"], abs_["IN_PROGRESS"], abs_["AWAITING_VERIFICATION"], abs_["CLOSED"]],
            marker_color=["#6c757d", "#0d6efd", "#ffc107", "#198754"],
        ))
        fig3.update_layout(margin=dict(l=10, r=10, t=10, b=30), height=240,
                           yaxis_title="Count", xaxis_title=None)
        action_status_chart = pio.to_html(fig3, full_html=False, include_plotlyjs=False)

    if org and training_stats.get("skills_certified", 0) > 0:
        import plotly.graph_objects as go
        import plotly.io as pio

        sl = training_stats["skill_levels"]
        labels = ["Beginner (L1)", "Basic (L2)", "Intermediate (L3)", "Advanced (L4)", "Expert (L5)"]
        values = [sl[1], sl[2], sl[3], sl[4], sl[5]]
        fig4 = go.Figure(go.Bar(
            y=labels, x=values,
            orientation="h",
            marker_color=["#adb5bd", "#0d6efd", "#0dcaf0", "#fd7e14", "#198754"],
        ))
        fig4.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=240,
                           xaxis_title="Count", yaxis_title=None)
        training_skills_chart = pio.to_html(fig4, full_html=False, include_plotlyjs=False)

    # Subscription
    subscription = None
    if org:
        subscription = getattr(org, "subscription", None)

    # Skills proficiencies for Tab 3
    from training.models import SkillProficiency
    skill_proficiencies = []
    if org:
        skill_proficiencies = SkillProficiency.objects.filter(
            organization=org, user=profile_user
        ).select_related("skill", "skill__category").order_by("-level", "skill__name")

    def star_html(result):
        """Return rendered star HTML string or empty string."""
        from django.utils.html import format_html
        if not result:
            return ""
        stars_val = int(result[0])
        filled = "&#9733;" * stars_val
        empty = "&#9734;" * (5 - stars_val)
        return (
            f'<span class="star-filled">{filled}</span>'
            f'<span class="star-empty">{empty}</span>'
        )

    # Logo upload form (manager + own org only)
    logo_form = OrgLogoForm() if (is_own_profile and request.user.is_manager and org) else None

    from django.utils.safestring import mark_safe
    return render(request, "users/profile_detail.html", {
        "profile_user": profile_user,
        "is_own_profile": is_own_profile,
        "form": form,
        "obs_stats": obs_stats,
        "training_stats": training_stats,
        "observer_result": observer_result,
        "action_owner_result": action_owner_result,
        "training_result": training_result,
        "observer_stars_html": mark_safe(star_html(observer_result)),
        "action_stars_html": mark_safe(star_html(action_owner_result)),
        "training_stars_html": mark_safe(star_html(training_result)),
        "observer_severity_chart": observer_severity_chart,
        "observer_status_chart": observer_status_chart,
        "action_status_chart": action_status_chart,
        "training_skills_chart": training_skills_chart,
        "subscription": subscription,
        "skill_proficiencies": skill_proficiencies,
        "logo_form": logo_form,
    })


@login_required
def profile_certificate_pdf(request, user_id):
    """Download performance certificate PDF."""
    profile_user = get_object_or_404(User, pk=user_id)
    is_own_profile = (request.user.pk == profile_user.pk)

    if not is_own_profile:
        viewer = request.user
        can_view = (
            (viewer.is_manager or viewer.is_safety_manager)
            and viewer.organization == profile_user.organization
        )
        if not can_view:
            raise Http404

    org = profile_user.organization
    if not org:
        raise Http404("User has no organisation.")

    from users.performance import (
        get_observation_stats, get_training_stats,
        calculate_observer_stars, calculate_action_owner_stars,
        calculate_training_stars, generate_certificate_pdf,
    )
    obs_stats = get_observation_stats(profile_user, org)
    training_stats = get_training_stats(profile_user, org)
    observer_result = calculate_observer_stars(profile_user, org)
    action_owner_result = calculate_action_owner_stars(profile_user, org)
    training_result = calculate_training_stars(profile_user, org)

    pdf_bytes = generate_certificate_pdf(
        profile_user, obs_stats, training_stats,
        observer_result, action_owner_result, training_result,
    )

    safe_name = (profile_user.full_name or profile_user.email).replace(" ", "_")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="performance_certificate_{safe_name}.pdf"'
    return response


@login_required
def org_logo_view(request):
    """
    Proxy view: reads the org logo through Django's storage API and returns it
    as an HTTP image response.  Works whether media is on S3 or local disk,
    and whether the bucket is public or private.
    """
    org = getattr(request, "organization", None) or getattr(request.user, "organization", None)
    if not org or not getattr(org, "logo", None) or not org.logo.name:
        raise Http404

    import mimetypes
    try:
        with org.logo.open("rb") as f:
            data = f.read()
    except Exception:
        raise Http404

    content_type, _ = mimetypes.guess_type(org.logo.name)
    response = HttpResponse(data, content_type=content_type or "image/png")
    # Cache for 1 hour in browser; revalidate after logo changes via ETags
    response["Cache-Control"] = "private, max-age=3600"
    return response


@login_required
def upload_org_logo_view(request):
    """Manager-only: upload or remove the organisation logo."""
    if not request.user.is_manager:
        raise Http404
    org = request.organization
    if not org:
        raise Http404

    if request.method == "POST":
        form = OrgLogoForm(request.POST, request.FILES)
        if form.is_valid():
            if form.cleaned_data.get("remove_logo"):
                if org.logo:
                    org.logo.delete(save=False)
                    org.logo = None
                    org.save(update_fields=["logo"])
                messages.success(request, "Organisation logo removed.")
            elif form.cleaned_data.get("logo"):
                # Delete old logo file before replacing
                if org.logo:
                    org.logo.delete(save=False)
                org.logo = form.cleaned_data["logo"]
                org.save(update_fields=["logo"])
                messages.success(request, "Organisation logo updated successfully.")
            else:
                messages.info(request, "No changes made.")
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

    return redirect("users:profile")
