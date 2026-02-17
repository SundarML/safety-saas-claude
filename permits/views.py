# permits/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    PermitActivateForm,
    PermitApprovalForm,
    PermitCloseForm,
    PermitRequestForm,
)
from .models import Permit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _org_required(request):
    if not request.organization:
        raise PermissionDenied("You are not associated with any organization.")


def _get_permit(pk, org):
    return get_object_or_404(Permit, pk=pk, organization=org)


def _scope_form_location(form, org):
    """Always scope location queryset regardless of GET or POST."""
    from observations.models import Location
    form.fields["location"].queryset = Location.objects.filter(organization=org)
    return form


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@login_required
def permit_list(request):
    _org_required(request)

    q        = request.GET.get("q", "").strip()
    status_f = request.GET.get("status", "")
    type_f   = request.GET.get("work_type", "")

    qs = (
        Permit.objects
        .filter(organization=request.organization)
        .select_related("requestor", "approved_by", "location")
        .order_by("-created_at")
    )

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(permit_number__icontains=q)
            | Q(contractor_name__icontains=q)
            | Q(location__name__icontains=q)
        )
    if status_f:
        qs = qs.filter(status=status_f)
    if type_f:
        qs = qs.filter(work_type=type_f)

    paginator = Paginator(qs, 15)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "permits/permit_list.html", {
        "permits":        page_obj,
        "page_obj":       page_obj,
        "q":              q,
        "status_f":       status_f,
        "type_f":         type_f,
        "status_choices": Permit.STATUS_CHOICES,
        "type_choices":   Permit.WORK_TYPE_CHOICES,
    })


# ---------------------------------------------------------------------------
# Create (DRAFT)
# ---------------------------------------------------------------------------

@login_required
def permit_create(request):
    _org_required(request)

    if request.method == "POST":
        form = PermitRequestForm(request.POST, request.FILES)
        # CRITICAL: scope location on POST too, otherwise Django rejects the value
        _scope_form_location(form, request.organization)

        if form.is_valid():
            permit = form.save(commit=False)
            permit.organization = request.organization
            permit.requestor    = request.user
            permit.status       = "DRAFT"
            permit.save()
            messages.success(
                request,
                f"Permit {permit.permit_number} saved as Draft. "
                "Review and click 'Submit for Approval' when ready.",
            )
            return redirect("permits:detail", pk=permit.pk)
        else:
            # Show what went wrong
            messages.error(request, "Please fix the errors below and try again.")

    else:
        form = PermitRequestForm()
        _scope_form_location(form, request.organization)

    return render(request, "permits/permit_form.html", {
        "form":  form,
        "title": "Request New Permit to Work",
    })


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@login_required
def permit_detail(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    checklist = [
        ("Toolbox talk conducted",      permit.toolbox_talk_done),
        ("Area barricaded / signed",    permit.area_barricaded),
        ("Equipment / tools inspected", permit.equipment_inspected),
        ("Gas / atmosphere test done",  permit.gas_test_done),
    ]
    return render(request, "permits/permit_detail.html", {
        "permit":    permit,
        "checklist": checklist,
    })


# ---------------------------------------------------------------------------
# Edit (DRAFT only)
# ---------------------------------------------------------------------------

@login_required
def permit_edit(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    if permit.status != "DRAFT":
        messages.error(request, "Only Draft permits can be edited.")
        return redirect("permits:detail", pk=pk)

    if permit.requestor != request.user and not request.user.is_manager:
        raise PermissionDenied("Only the requestor or a manager can edit this permit.")

    if request.method == "POST":
        form = PermitRequestForm(request.POST, request.FILES, instance=permit)
        _scope_form_location(form, request.organization)

        if form.is_valid():
            form.save()
            messages.success(request, "Permit updated.")
            return redirect("permits:detail", pk=pk)
        else:
            messages.error(request, "Please fix the errors below and try again.")

    else:
        form = PermitRequestForm(instance=permit)
        _scope_form_location(form, request.organization)

    return render(request, "permits/permit_form.html", {
        "form":   form,
        "permit": permit,
        "title":  "Edit Permit",
    })


# ---------------------------------------------------------------------------
# Submit (DRAFT → SUBMITTED)
# ---------------------------------------------------------------------------

@login_required
def permit_submit(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    if permit.status != "DRAFT":
        messages.error(request, "Only Draft permits can be submitted.")
        return redirect("permits:detail", pk=pk)

    if permit.requestor != request.user and not request.user.is_manager:
        raise PermissionDenied

    permit.status = "SUBMITTED"
    permit.save()
    messages.success(request, f"Permit {permit.permit_number} submitted for approval.")
    return redirect("permits:detail", pk=pk)


# ---------------------------------------------------------------------------
# Approve / Reject (SUBMITTED → APPROVED or REJECTED)
# ---------------------------------------------------------------------------

@login_required
def permit_approve(request, pk):
    _org_required(request)

    if not (request.user.is_safety_manager or request.user.is_manager):
        raise PermissionDenied("Only Safety Managers can approve permits.")

    permit = _get_permit(pk, request.organization)

    if permit.status != "SUBMITTED":
        messages.error(request, "Only Submitted permits can be reviewed.")
        return redirect("permits:detail", pk=pk)

    if request.method == "POST":
        form = PermitApprovalForm(request.POST, instance=permit)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            permit   = form.save(commit=False)

            if decision == "approve":
                permit.status      = "APPROVED"
                permit.approved_by = request.user
                permit.approved_at = timezone.now()
                messages.success(
                    request, f"Permit {permit.permit_number} approved. Work may proceed."
                )
            else:
                permit.status = "REJECTED"
                messages.warning(
                    request, f"Permit {permit.permit_number} rejected."
                )

            permit.save()
            return redirect("permits:detail", pk=pk)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PermitApprovalForm(instance=permit)

    return render(request, "permits/permit_approve.html", {
        "form":   form,
        "permit": permit,
    })


# ---------------------------------------------------------------------------
# Activate (APPROVED → ACTIVE)
# ---------------------------------------------------------------------------

@login_required
def permit_activate(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    if permit.status != "APPROVED":
        messages.error(request, "Only Approved permits can be activated.")
        return redirect("permits:detail", pk=pk)

    if permit.requestor != request.user and not request.user.is_manager:
        raise PermissionDenied

    if request.method == "POST":
        form = PermitActivateForm(request.POST, instance=permit)
        if form.is_valid():
            permit = form.save(commit=False)
            permit.status = "ACTIVE"
            permit.save()
            messages.success(
                request,
                f"Permit {permit.permit_number} is now Active. Work in progress.",
            )
            return redirect("permits:detail", pk=pk)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PermitActivateForm(instance=permit)

    return render(request, "permits/permit_activate.html", {
        "form":   form,
        "permit": permit,
    })


# ---------------------------------------------------------------------------
# Close (ACTIVE → CLOSED)
# ---------------------------------------------------------------------------

@login_required
def permit_close(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    if permit.status != "ACTIVE":
        messages.error(request, "Only Active permits can be closed.")
        return redirect("permits:detail", pk=pk)

    if not (
        permit.requestor == request.user
        or request.user.is_safety_manager
        or request.user.is_manager
    ):
        raise PermissionDenied

    if request.method == "POST":
        form = PermitCloseForm(request.POST, instance=permit)
        if form.is_valid():
            permit = form.save(commit=False)
            permit.status    = "CLOSED"
            permit.closed_by = request.user
            permit.closed_at = timezone.now()
            permit.save()
            messages.success(
                request, f"Permit {permit.permit_number} closed. Site restored."
            )
            return redirect("permits:detail", pk=pk)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = PermitCloseForm(instance=permit)

    return render(request, "permits/permit_close.html", {
        "form":   form,
        "permit": permit,
    })


# ---------------------------------------------------------------------------
# Cancel (DRAFT / SUBMITTED → CANCELLED)
# ---------------------------------------------------------------------------

@login_required
def permit_cancel(request, pk):
    _org_required(request)
    permit = _get_permit(pk, request.organization)

    if permit.status not in ("DRAFT", "SUBMITTED"):
        messages.error(request, "Only Draft or Submitted permits can be cancelled.")
        return redirect("permits:detail", pk=pk)

    if permit.requestor != request.user and not request.user.is_manager:
        raise PermissionDenied

    if request.method == "POST":
        permit.status = "CANCELLED"
        permit.save()
        messages.warning(request, f"Permit {permit.permit_number} cancelled.")
        return redirect("permits:permit_list")

    return render(request, "permits/permit_cancel_confirm.html", {"permit": permit})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def permit_dashboard(request):
    _org_required(request)
    org = request.organization

    qs = Permit.objects.filter(organization=org)

    by_status = dict(qs.values_list("status").annotate(c=Count("id")))
    by_type   = list(
        qs.values("work_type").annotate(count=Count("id")).order_by("-count")
    )

    overdue = qs.filter(
        status__in=("APPROVED", "ACTIVE"),
        planned_end__lt=timezone.now(),
    ).select_related("requestor", "location")

    pending_approval = qs.filter(status="SUBMITTED") \
                         .select_related("requestor", "location")

    active_permits = qs.filter(status="ACTIVE") \
                       .select_related("requestor", "location")

    return render(request, "permits/permit_dashboard.html", {
        "by_status":        by_status,
        "by_type":          by_type,
        "overdue":          overdue,
        "pending_approval": pending_approval,
        "active_permits":   active_permits,
        "total":            qs.count(),
    })
