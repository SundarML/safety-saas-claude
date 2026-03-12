from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .models import ComplianceItem
from .forms import ComplianceItemForm, MarkCompliedForm


def _org_required(request):
    org = getattr(request, "organization", None)
    if not org:
        raise PermissionDenied
    return org


def _manager_required(request):
    if not (request.user.is_manager or request.user.is_safety_manager):
        raise PermissionDenied


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    org = _org_required(request)

    items = ComplianceItem.objects.filter(organization=org).select_related("assigned_to")

    # Auto-mark overdue items (status still 'pending' but past due date)
    today = timezone.now().date()
    pending_overdue = items.filter(status="pending", due_date__lt=today)
    pending_overdue.update(status="overdue")
    # Refresh queryset after update
    items = ComplianceItem.objects.filter(organization=org).select_related("assigned_to")

    # Stats
    total       = items.count()
    complied    = items.filter(status="complied").count()
    overdue     = items.filter(status="overdue").count()
    due_soon    = items.filter(status="pending", due_date__range=[today, today + timezone.timedelta(days=30)]).count()
    pending     = items.filter(status="pending").count()
    score       = round((complied / total * 100)) if total else 0

    # Status filter
    status_filter = request.GET.get("status", "")
    if status_filter:
        items = items.filter(status=status_filter)

    return render(request, "compliance/dashboard.html", {
        "items":         items,
        "total":         total,
        "complied":      complied,
        "overdue":       overdue,
        "due_soon":      due_soon,
        "pending":       pending,
        "score":         score,
        "status_filter": status_filter,
        "today":         today,
    })


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@login_required
def item_create(request):
    _manager_required(request)
    org = _org_required(request)

    if request.method == "POST":
        form = ComplianceItemForm(request.POST, org=org)
        if form.is_valid():
            item = form.save(commit=False)
            item.organization = org
            item.created_by   = request.user
            item.save()
            messages.success(request, f"Compliance item '{item.title}' added.")
            return redirect("compliance:dashboard")
    else:
        form = ComplianceItemForm(org=org)

    return render(request, "compliance/item_form.html", {"form": form, "action": "Add"})


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@login_required
def item_detail(request, pk):
    org  = _org_required(request)
    item = get_object_or_404(ComplianceItem, pk=pk, organization=org)
    return render(request, "compliance/item_detail.html", {"item": item})


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

@login_required
def item_edit(request, pk):
    _manager_required(request)
    org  = _org_required(request)
    item = get_object_or_404(ComplianceItem, pk=pk, organization=org)

    if request.method == "POST":
        form = ComplianceItemForm(request.POST, instance=item, org=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Compliance item updated.")
            return redirect("compliance:item_detail", pk=item.pk)
    else:
        form = ComplianceItemForm(instance=item, org=org)

    return render(request, "compliance/item_form.html", {"form": form, "action": "Edit", "item": item})


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@login_required
def item_delete(request, pk):
    _manager_required(request)
    org  = _org_required(request)
    item = get_object_or_404(ComplianceItem, pk=pk, organization=org)

    if request.method == "POST":
        title = item.title
        item.delete()
        messages.success(request, f"'{title}' deleted.")
        return redirect("compliance:dashboard")

    return render(request, "compliance/item_confirm_delete.html", {"item": item})


# ---------------------------------------------------------------------------
# Mark Complied
# ---------------------------------------------------------------------------

@login_required
def mark_complied(request, pk):
    org  = _org_required(request)
    item = get_object_or_404(ComplianceItem, pk=pk, organization=org)

    # Only manager, safety_manager, or the assigned user can mark complied
    is_manager = request.user.is_manager or request.user.is_safety_manager
    is_assigned = item.assigned_to == request.user
    if not (is_manager or is_assigned):
        raise PermissionDenied

    if request.method == "POST":
        form = MarkCompliedForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.status = "complied"
            item.save()
            messages.success(request, f"'{item.title}' marked as complied.")
            return redirect("compliance:item_detail", pk=item.pk)
    else:
        form = MarkCompliedForm(instance=item, initial={"complied_on": timezone.now().date()})

    return render(request, "compliance/mark_complied.html", {"form": form, "item": item})


# ---------------------------------------------------------------------------
# Mark Not Applicable
# ---------------------------------------------------------------------------

@login_required
def mark_na(request, pk):
    _manager_required(request)
    org  = _org_required(request)
    item = get_object_or_404(ComplianceItem, pk=pk, organization=org)

    if request.method == "POST":
        item.status = "not_applicable"
        item.save(update_fields=["status", "updated_at"])
        messages.success(request, f"'{item.title}' marked as Not Applicable.")

    return redirect("compliance:item_detail", pk=item.pk)
