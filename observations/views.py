# observations/views.py
import csv
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.io as pio
from openpyxl import Workbook

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import LocationForm, ObservationCreateForm, RectificationForm, VerificationForm
from .models import Location, Observation


# ---------------------------------------------------------------------------
# Reusable mixins
# ---------------------------------------------------------------------------

class OrgRequiredMixin:
    """
    Blocks access if the user has no organization.
    Used by all CBVs that touch tenant data.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.organization:
            raise PermissionDenied("You are not associated with any organization.")
        return super().dispatch(request, *args, **kwargs)


class OrgQuerySetMixin:
    """
    Scopes every CBV queryset to the current organization.
    Prevents any cross-tenant data leakage at the queryset level.
    """
    def get_queryset(self):
        if not self.request.organization:
            raise PermissionDenied("You are not associated with any organization.")
        return Observation.objects.filter(organization=self.request.organization)


def _org_required(request):
    """Shared guard for function-based views."""
    if not request.organization:
        raise PermissionDenied("You are not associated with any organization.")


# ---------------------------------------------------------------------------
# Observation CRUD
# ---------------------------------------------------------------------------

class ObservationCreateView(LoginRequiredMixin, OrgRequiredMixin, CreateView):
    model = Observation
    form_class = ObservationCreateForm
    template_name = "observations/observation_form.html"
    success_url = reverse_lazy("observations:observation_list")

    def dispatch(self, request, *args, **kwargs):
        # OrgRequiredMixin.dispatch already runs; this checks plan limits on top.
        response = super().dispatch(request, *args, **kwargs)

        org = request.organization
        sub = getattr(org, "subscription", None)
        if sub and sub.plan.max_observations is not None:
            count = Observation.objects.filter(organization=org).count()
            if count >= sub.plan.max_observations:
                messages.error(
                    request,
                    "Observation limit reached for your current plan. Please upgrade.",
                )
                return redirect("observations:observation_list")

        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Scope location dropdown and assigned_to dropdown to this org only
        form.fields["location"].queryset = Location.objects.filter(
            organization=self.request.organization
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        form.fields["assigned_to"].queryset = User.objects.filter(
            organization=self.request.organization
        )
        return form

    def form_valid(self, form):
        form.instance.organization = self.request.organization
        form.instance.observer = self.request.user
        form.instance.status = "OPEN"
        return super().form_valid(form)


@login_required
def observation_list(request):
    _org_required(request)

    q = request.GET.get("q", "").strip()

    observations = (
        Observation.objects
        .filter(is_archived=False, organization=request.organization)
        .select_related("location", "assigned_to", "observer")
        .order_by("-date_observed")
    )

    if q:
        observations = observations.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(location__name__icontains=q)
            | Q(observer__email__icontains=q)        # email, not username
            | Q(observer__full_name__icontains=q)
        )

    paginator = Paginator(observations, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "observations/observation_list.html", {
        "observations": page_obj,
        "page_obj": page_obj,
        "q": q,
        "today": date.today(),
    })


class ObservationDetailView(LoginRequiredMixin, OrgRequiredMixin, OrgQuerySetMixin, DetailView):
    model = Observation
    template_name = "observations/observation_detail.html"


class RectificationUpdateView(LoginRequiredMixin, OrgRequiredMixin, OrgQuerySetMixin, UpdateView):
    model = Observation
    form_class = RectificationForm
    template_name = "observations/observation_form.html"
    success_url = reverse_lazy("observations:observation_list")

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        # Only the assigned action owner may rectify
        obs = self.get_object()
        if request.user != obs.assigned_to:
            raise PermissionDenied("Only the assigned action owner can submit rectification.")
        return response

    def form_valid(self, form):
        observation = form.save(commit=False)
        observation.status = "AWAITING_VERIFICATION"
        observation.save()
        messages.success(
            self.request,
            "Rectification submitted — pending verification.",
        )
        return redirect(self.success_url)


class VerificationView(LoginRequiredMixin, OrgRequiredMixin, OrgQuerySetMixin, UpdateView):
    model = Observation
    template_name = "observations/observation_verify.html"
    form_class = VerificationForm

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not (request.user.is_safety_manager or request.user.is_manager):
            raise PermissionDenied("Only Safety Managers can verify observations.")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["observation"] = self.object
        return ctx

    def form_valid(self, form):
        observation = form.save(commit=False)
        action = form.cleaned_data.get("verification_action")

        if action == "approve":
            observation.status = "CLOSED"
            observation.date_closed = timezone.now()
            messages.success(self.request, "Observation verified and closed.")
        else:
            observation.status = "IN_PROGRESS"
            messages.warning(self.request, "Observation sent back for rework.")

        observation.save()
        return redirect("observations:observation_list")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@login_required
def delete_observation(request, pk):
    _org_required(request)

    if not (request.user.is_superuser or request.user.is_manager):
        raise PermissionDenied("Only managers can delete observations.")

    obs = get_object_or_404(Observation, pk=pk, organization=request.organization)

    if request.method == "POST":
        obs.delete()
        messages.success(request, "Observation deleted.")
        return redirect("observations:observation_list")

    return render(request, "observations/confirm_delete.html", {"observation": obs})


# ---------------------------------------------------------------------------
# Archive / Restore
# ---------------------------------------------------------------------------

@login_required
def archived_observations_list(request):
    _org_required(request)

    archived = (
        Observation.objects
        .filter(is_archived=True, organization=request.organization)
        .order_by("-id")
    )

    paginator = Paginator(archived, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "observations/archived_list.html", {
        "observations": page_obj,
        "page_obj": page_obj,
        "today": timezone.now().date(),
        "is_archive_page": True,
    })


@login_required
def archive_observation(request, pk):
    _org_required(request)

    if not (request.user.is_safety_manager or request.user.is_manager):
        raise PermissionDenied("Only Safety Managers can archive observations.")

    obs = get_object_or_404(Observation, pk=pk, organization=request.organization)
    obs.is_archived = True
    obs.save()
    messages.success(request, "Observation archived.")
    return redirect("observations:observation_list")


@login_required
def restore_observation(request, pk):
    _org_required(request)

    if not (request.user.is_safety_manager or request.user.is_manager):
        raise PermissionDenied("Only Safety Managers can restore observations.")

    obs = get_object_or_404(Observation, pk=pk, organization=request.organization)
    obs.is_archived = False
    obs.save()
    messages.success(request, "Observation restored.")
    return redirect("observations:archived_list")


# ---------------------------------------------------------------------------
# Exports  (login + org scoped)
# ---------------------------------------------------------------------------

@login_required
def export_observations_excel(request):
    _org_required(request)

    wb = Workbook()
    ws = wb.active
    ws.title = "Observations"
    ws.append(["ID", "Title", "Description", "Location", "Status", "Observer", "Created At"])

    qs = (
        Observation.objects
        .filter(organization=request.organization)
        .select_related("observer", "location")
        .order_by("-date_observed")
    )

    for obs in qs:
        ws.append([
            obs.id,
            obs.title,
            obs.description,
            str(obs.location),
            obs.status,
            obs.observer.email if obs.observer else "",
            obs.date_observed.strftime("%Y-%m-%d %H:%M"),
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="observations.xlsx"'
    wb.save(response)
    return response


@login_required
def export_observations_csv(request):
    _org_required(request)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="observations.csv"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Title", "Description", "Location", "Status", "Observer", "Created At"])

    qs = (
        Observation.objects
        .filter(organization=request.organization)
        .select_related("observer", "location")
        .order_by("-date_observed")
    )

    for obs in qs:
        writer.writerow([
            obs.id,
            obs.title,
            obs.description,
            str(obs.location),
            obs.status,
            obs.observer.email if obs.observer else "",
            obs.date_observed.strftime("%Y-%m-%d %H:%M"),
        ])

    return response


# ---------------------------------------------------------------------------
# AJAX — add location (org-scoped)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def ajax_add_location(request):
    _org_required(request)

    form = LocationForm(request.POST)
    if form.is_valid():
        location = form.save(commit=False)
        location.organization = request.organization
        location.save()
        return JsonResponse({"success": True, "id": location.id, "name": location.name})

    return JsonResponse({"success": False, "errors": form.errors}, status=400)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def observations_dashboard(request):
    _org_required(request)

    org = request.organization
    qs = Observation.objects.filter(is_archived=False, organization=org)
    today = date.today()

    # KPI cards
    total_obs   = qs.count()
    open_obs    = qs.filter(status__in=["OPEN", "IN_PROGRESS"]).count()
    closed_obs  = qs.filter(status="CLOSED").count()
    overdue_obs = qs.filter(target_date__lt=today).exclude(status="CLOSED").count()

    # Trend selector
    trend = request.GET.get("trend", "monthly")
    trunc_map = {
        "daily":   TruncDay("date_observed"),
        "weekly":  TruncWeek("date_observed"),
        "monthly": TruncMonth("date_observed"),
    }
    trunc_func = trunc_map.get(trend, TruncMonth("date_observed"))

    trend_qs = (
        qs.annotate(period=trunc_func)
          .values("period")
          .annotate(count=Count("id"))
          .order_by("period")
    )
    labels = [row["period"].strftime("%Y-%m-%d") for row in trend_qs if row["period"]]
    values = [row["count"] for row in trend_qs]

    fig = px.line(
        x=labels, y=values, markers=True,
        title=f"{trend.capitalize()} Observation Trend",
        labels={"x": "Date", "y": "Observations"},
    )
    fig.update_layout(modebar_add=["toImage"])
    chart_html = fig.to_html(full_html=False)

    # Severity breakdown
    severity_qs = qs.values("severity").annotate(count=Count("id")).order_by("severity")
    severity_fig = px.bar(
        x=[r["severity"] for r in severity_qs],
        y=[r["count"]    for r in severity_qs],
        title="Observations by Severity",
        labels={"x": "Severity", "y": "Count"},
    )
    severity_fig.update_layout(modebar_add=["toImage"])

    # Status pie
    status_qs = qs.values("status").annotate(count=Count("id"))
    status_fig = px.pie(
        names=[r["status"] for r in status_qs],
        values=[r["count"] for r in status_qs],
        title="Observations by Status",
    )
    status_fig.update_layout(modebar_add=["toImage"])

    # Observer performance (org-scoped)
    observer_qs = (
        Observation.objects.filter(organization=org)
        .values(Observer=F("observer__email"))
        .annotate(total=Count("id"))
        .filter(observer__isnull=False)
        .order_by("-total")
    )
    observer_df = pd.DataFrame(list(observer_qs))
    if not observer_df.empty:
        observer_fig = px.bar(
            observer_df, x="Observer", y="total",
            title="Observers – Observations Reported",
            labels={"Observer": "Observer", "total": "Observations"},
            color="total",
        )
    else:
        observer_fig = px.bar(
            pd.DataFrame(columns=["Observer", "total"]),
            x="Observer", y="total",
            title="Observers – Observations Reported",
        )

    # Action owner performance (org-scoped)
    owner_qs = (
        Observation.objects.filter(organization=org)
        .values(owner=F("assigned_to__email"))
        .annotate(total=Count("id"))
        .filter(assigned_to__isnull=False)
        .order_by("-total")
    )
    owner_df = pd.DataFrame(list(owner_qs))
    if not owner_df.empty:
        owner_fig = px.bar(
            owner_df, x="owner", y="total",
            title="Action Owners – Tasks Assigned",
            labels={"owner": "Action Owner", "total": "Assigned Tasks"},
            color="total",
        )
    else:
        owner_fig = px.bar(
            pd.DataFrame(columns=["owner", "total"]),
            x="owner", y="total",
            title="Action Owners – Tasks Assigned",
        )

    # Safety manager close performance (org-scoped)
    manager_qs = (
        Observation.objects.filter(organization=org, status="CLOSED")
        .values(safety_manager=F("assigned_to__email"))
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    manager_df = pd.DataFrame(list(manager_qs))
    if not manager_df.empty:
        manager_fig = px.bar(
            manager_df, x="safety_manager", y="total",
            title="Safety Managers – Observations Closed",
            labels={"safety_manager": "Manager", "total": "Closed Observations"},
            color="total",
        )
    else:
        manager_fig = px.bar(
            pd.DataFrame(columns=["safety_manager", "total"]),
            x="safety_manager", y="total",
            title="Safety Managers – Observations Closed",
        )

    return render(request, "observations/dashboard.html", {
        "total_obs":      total_obs,
        "open_obs":       open_obs,
        "closed_obs":     closed_obs,
        "overdue_obs":    overdue_obs,
        "chart_html":     chart_html,
        "trend":          trend,
        "severity_plot":  pio.to_html(severity_fig, full_html=False),
        "status_plot":    pio.to_html(status_fig,   full_html=False),
        "observer_plot":  pio.to_html(observer_fig, full_html=False),
        "owner_plot":     pio.to_html(owner_fig,    full_html=False),
        "manager_plot":   pio.to_html(manager_fig,  full_html=False),
    })
