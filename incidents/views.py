# incidents/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    CloseIncidentForm, HoursWorkedForm, IncidentForm,
    InvestigateForm, RCAForm,
)
from .models import HoursWorked, Incident


# ── Guards ────────────────────────────────────────────────────────────────────

def _org(request):
    org = getattr(request, "organization", None)
    if not org:
        raise PermissionDenied
    return org


def _manager_required(request):
    if not (request.user.is_manager or request.user.is_safety_manager):
        raise PermissionDenied


def _get_org_users(org):
    from django.contrib.auth import get_user_model
    return get_user_model().objects.filter(
        organization=org, is_active=True
    ).order_by("full_name", "email")


def _get_org_hazards(org):
    from hira.models import Hazard
    return Hazard.objects.filter(
        register__organization=org
    ).select_related("register").order_by("register__title", "order")


def _get_org_locations(org):
    from observations.models import Location
    return Location.objects.filter(organization=org).order_by("name")


# ── List ──────────────────────────────────────────────────────────────────────

@login_required
def incident_list(request):
    org = _org(request)
    qs  = Incident.objects.filter(organization=org).select_related(
        "reported_by", "investigated_by"
    )

    type_filter     = request.GET.get("type", "")
    severity_filter = request.GET.get("severity", "")
    status_filter   = request.GET.get("status", "")

    if type_filter:
        qs = qs.filter(incident_type=type_filter)
    if severity_filter:
        qs = qs.filter(severity=severity_filter)
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "incidents/incident_list.html", {
        "incidents":       qs,
        "type_filter":     type_filter,
        "severity_filter": severity_filter,
        "status_filter":   status_filter,
        "TYPE_CHOICES":     Incident.TYPE_CHOICES,
        "SEVERITY_CHOICES": Incident.SEVERITY_CHOICES,
        "STATUS_CHOICES":   Incident.STATUS_CHOICES,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@login_required
def incident_create(request):
    org = _org(request)

    initial = {}
    # Pre-fill from observation conversion
    src_obs_pk = request.GET.get("source_observation")
    if src_obs_pk:
        from observations.models import Observation
        try:
            obs = Observation.objects.get(pk=src_obs_pk, organization=org)
            initial["title"]       = obs.title
            initial["description"] = obs.description
            initial["location"]    = obs.location_id
        except Observation.DoesNotExist:
            src_obs_pk = None

    if request.method == "POST":
        form = IncidentForm(request.POST, request.FILES)
        form.fields["location"].queryset     = _get_org_locations(org)
        form.fields["linked_hazard"].queryset = _get_org_hazards(org)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.organization = org
            incident.reported_by  = request.user
            if src_obs_pk:
                incident.source_observation_id = src_obs_pk
            incident.save()
            messages.success(request, f"Incident {incident.reference_no} reported.")
            return redirect("incidents:detail", pk=incident.pk)
    else:
        form = IncidentForm(initial=initial)
        form.fields["location"].queryset      = _get_org_locations(org)
        form.fields["linked_hazard"].queryset = _get_org_hazards(org)

    return render(request, "incidents/incident_form.html", {
        "form":       form,
        "page_title": "Report New Incident",
        "is_edit":    False,
    })


# ── Detail ────────────────────────────────────────────────────────────────────

@login_required
def incident_detail(request, pk):
    org      = _org(request)
    incident = get_object_or_404(
        Incident.objects.select_related(
            "reported_by", "investigated_by", "closed_by",
            "linked_hazard__register", "location",
            "source_observation",
        ),
        pk=pk, organization=org,
    )
    is_manager = request.user.is_manager or request.user.is_safety_manager

    return render(request, "incidents/incident_detail.html", {
        "incident":    incident,
        "is_manager":  is_manager,
        "today":       timezone.now().date(),
        "ca_list":     incident.corrective_actions.all() if hasattr(incident, "corrective_actions") else [],
    })


# ── Edit ──────────────────────────────────────────────────────────────────────

@login_required
def incident_edit(request, pk):
    org      = _org(request)
    _manager_required(request)
    incident = get_object_or_404(Incident, pk=pk, organization=org)

    if request.method == "POST":
        form = IncidentForm(request.POST, request.FILES, instance=incident)
        form.fields["location"].queryset      = _get_org_locations(org)
        form.fields["linked_hazard"].queryset = _get_org_hazards(org)
        if form.is_valid():
            form.save()
            messages.success(request, "Incident updated.")
            return redirect("incidents:detail", pk=pk)
    else:
        form = IncidentForm(instance=incident)
        form.fields["location"].queryset      = _get_org_locations(org)
        form.fields["linked_hazard"].queryset = _get_org_hazards(org)

    return render(request, "incidents/incident_form.html", {
        "form":       form,
        "incident":   incident,
        "page_title": f"Edit — {incident.reference_no}",
        "is_edit":    True,
    })


# ── Workflow: Investigate ─────────────────────────────────────────────────────

@login_required
def incident_investigate(request, pk):
    org = _org(request)
    _manager_required(request)
    incident = get_object_or_404(Incident, pk=pk, organization=org)

    if incident.status != Incident.STATUS_REPORTED:
        return redirect("incidents:detail", pk=pk)

    if request.method == "POST":
        form = InvestigateForm(request.POST, instance=incident)
        form.fields["investigated_by"].queryset = _get_org_users(org)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.status = Incident.STATUS_INVESTIGATING
            incident.save()
            messages.success(request, "Investigation started.")
            return redirect("incidents:detail", pk=pk)
    else:
        form = InvestigateForm(instance=incident)
        form.fields["investigated_by"].queryset = _get_org_users(org)

    return render(request, "incidents/investigate_form.html", {
        "form":     form,
        "incident": incident,
    })


# ── Workflow: RCA ─────────────────────────────────────────────────────────────

@login_required
def incident_rca(request, pk):
    org      = _org(request)
    incident = get_object_or_404(Incident, pk=pk, organization=org)

    can_edit_rca = (
        request.user == incident.investigated_by or
        request.user.is_manager or request.user.is_safety_manager
    )
    if not can_edit_rca:
        raise PermissionDenied

    if request.method == "POST":
        form = RCAForm(request.POST, instance=incident)
        if form.is_valid():
            form.save()
            messages.success(request, "Root cause analysis saved.")
            return redirect("incidents:detail", pk=pk)
    else:
        form = RCAForm(instance=incident)

    return render(request, "incidents/rca_form.html", {
        "form":     form,
        "incident": incident,
    })


# ── Workflow: Action Required ─────────────────────────────────────────────────

@login_required
def incident_action_required(request, pk):
    """Transition to ACTION REQUIRED and auto-raise a corrective action."""
    org = _org(request)
    _manager_required(request)
    incident = get_object_or_404(Incident, pk=pk, organization=org)

    if request.method == "POST" and incident.status == Incident.STATUS_INVESTIGATING:
        incident.status = Incident.STATUS_ACTION_REQ
        incident.save(update_fields=["status", "updated_at"])

        # Auto-raise a corrective action
        from actions.models import CorrectiveAction
        priority_map = {
            Incident.SEV_FATALITY:  CorrectiveAction.PRIORITY_CRITICAL,
            Incident.SEV_LTI:       CorrectiveAction.PRIORITY_CRITICAL,
            Incident.SEV_MTC:       CorrectiveAction.PRIORITY_HIGH,
            Incident.SEV_FAC:       CorrectiveAction.PRIORITY_MEDIUM,
            Incident.SEV_NEAR_MISS: CorrectiveAction.PRIORITY_MEDIUM,
            Incident.SEV_PROPERTY:  CorrectiveAction.PRIORITY_LOW,
        }
        CorrectiveAction.objects.get_or_create(
            source_module="incident",
            source_observation=None,
            source_hira=None,
            source_compliance=None,
            organization=org,
            title=f"[Incident] {incident.title}",
            defaults={
                "description": (
                    f"Incident: {incident.reference_no}\n"
                    f"Root cause: {incident.rca_root_cause or 'TBD'}\n"
                    f"Preventive measures required."
                ),
                "priority":    priority_map.get(incident.severity, CorrectiveAction.PRIORITY_MEDIUM),
                "raised_by":   request.user,
            }
        )
        messages.success(request, "Incident moved to Action Required. Corrective action auto-raised.")

    return redirect("incidents:detail", pk=pk)


# ── Workflow: Close ───────────────────────────────────────────────────────────

@login_required
def incident_close(request, pk):
    org = _org(request)
    _manager_required(request)
    incident = get_object_or_404(Incident, pk=pk, organization=org)

    if incident.status not in (Incident.STATUS_INVESTIGATING, Incident.STATUS_ACTION_REQ):
        return redirect("incidents:detail", pk=pk)

    if request.method == "POST":
        form = CloseIncidentForm(request.POST, instance=incident)
        if form.is_valid():
            incident = form.save(commit=False)
            incident.status    = Incident.STATUS_CLOSED
            incident.closed_by = request.user
            incident.closed_at = timezone.now()
            incident.save()
            messages.success(request, f"Incident {incident.reference_no} closed.")
            return redirect("incidents:detail", pk=pk)
    else:
        form = CloseIncidentForm(instance=incident)

    return render(request, "incidents/close_form.html", {
        "form":     form,
        "incident": incident,
    })


# ── Stats ─────────────────────────────────────────────────────────────────────

@login_required
def incident_stats(request):
    org = _org(request)
    _manager_required(request)

    from .stats import calculate_stats, get_monthly_trend, get_type_breakdown, get_location_breakdown
    from django.utils import timezone as tz
    import pandas as pd
    import plotly.express as px
    import plotly.io as pio

    current_year = tz.now().year
    year = int(request.GET.get("year", current_year))

    stats         = calculate_stats(org, year)
    monthly_rows  = get_monthly_trend(org, year)
    type_rows     = get_type_breakdown(org, year)
    location_rows = get_location_breakdown(org, year)

    # ── 1. Monthly stacked bar ────────────────────────────────────────────────
    months = [r["month"] for r in monthly_rows]
    monthly_fig = px.bar(
        pd.DataFrame({
            "Month":           months * 4,
            "Count":           (
                [r["lti"]       for r in monthly_rows] +
                [r["mtc_fac"]   for r in monthly_rows] +
                [r["near_miss"] for r in monthly_rows] +
                [r["property"]  for r in monthly_rows]
            ),
            "Category": (
                ["LTI / Fatality"] * 12 +
                ["MTC / FAC"]      * 12 +
                ["Near-Miss"]      * 12 +
                ["Property"]       * 12
            ),
        }),
        x="Month", y="Count", color="Category", barmode="stack",
        title=f"Monthly Incident Trend — {year}",
        color_discrete_map={
            "LTI / Fatality": "#dc2626",
            "MTC / FAC":      "#ea580c",
            "Near-Miss":      "#2563eb",
            "Property":       "#7c3aed",
        },
    )
    monthly_fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        margin=dict(t=50, b=60, l=40, r=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#f1f5f9", dtick=1),
    )
    monthly_fig.update_layout(modebar_add=["toImage"])

    # ── 2. Type donut ─────────────────────────────────────────────────────────
    if type_rows:
        type_fig = px.pie(
            pd.DataFrame(type_rows),
            names="label", values="count",
            title="Incidents by Type",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        type_fig.update_traces(textinfo="label+percent", textfont_size=12)
        type_fig.update_layout(
            paper_bgcolor="white",
            showlegend=False,
            margin=dict(t=50, b=20, l=20, r=20),
        )
        type_fig.update_layout(modebar_add=["toImage"])
        type_plot = pio.to_html(type_fig, full_html=False)
    else:
        type_plot = ""

    # ── 3. Location horizontal bar ────────────────────────────────────────────
    if location_rows:
        loc_df = pd.DataFrame(location_rows).sort_values("count")
        loc_fig = px.bar(
            loc_df, x="count", y="label", orientation="h",
            title="Top Locations",
            labels={"count": "Incidents", "label": "Location"},
            color="count",
            color_continuous_scale=["#fecaca", "#dc2626"],
        )
        loc_fig.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            coloraxis_showscale=False,
            yaxis=dict(automargin=True),
            margin=dict(t=50, b=40, l=10, r=40),
            xaxis=dict(gridcolor="#f1f5f9", dtick=1),
        )
        loc_fig.update_traces(texttemplate="%{x}", textposition="outside")
        loc_fig.update_layout(modebar_add=["toImage"])
        location_plot = pio.to_html(loc_fig, full_html=False)
    else:
        location_plot = ""

    # ── Hours worked form ─────────────────────────────────────────────────────
    hw_form = HoursWorkedForm(initial={"year": year, "month": tz.now().month})
    if request.method == "POST":
        hw_form = HoursWorkedForm(request.POST)
        if hw_form.is_valid():
            HoursWorked.objects.update_or_create(
                organization=org,
                year=hw_form.cleaned_data["year"],
                month=hw_form.cleaned_data["month"],
                defaults={"hours": hw_form.cleaned_data["hours"]},
            )
            messages.success(request, "Hours worked updated.")
            return redirect(f"{request.path}?year={year}")

    return render(request, "incidents/stats.html", {
        "stats":          stats,
        "monthly_plot":   pio.to_html(monthly_fig, full_html=False),
        "type_plot":      type_plot,
        "location_plot":  location_plot,
        "hw_form":        hw_form,
        "year":           year,
        "year_range":     range(current_year - 3, current_year + 1),
    })
