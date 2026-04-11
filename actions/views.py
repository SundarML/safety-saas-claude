# actions/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import CorrectiveActionForm, SubmitEvidenceForm, VerifyActionForm
from .models import CorrectiveAction


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


# ── Notification helper ───────────────────────────────────────────────────────

def _notify(action, event):
    """Fire email notification asynchronously (best-effort, never raises)."""
    try:
        from .notifications import send_action_notification
        send_action_notification(action, event)
    except Exception:
        pass


# ── Action list ───────────────────────────────────────────────────────────────

@login_required
def action_list(request):
    org = _org(request)
    qs  = (
        CorrectiveAction.objects
        .filter(organization=org)
        .select_related("assigned_to", "raised_by", "source_hira__register",
                        "source_observation", "source_compliance")
    )

    status_filter   = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    source_filter   = request.GET.get("source", "")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if priority_filter:
        qs = qs.filter(priority=priority_filter)
    if source_filter:
        qs = qs.filter(source_module=source_filter)

    today   = timezone.now().date()
    overdue = qs.filter(due_date__lt=today).exclude(status=CorrectiveAction.STATUS_CLOSED).count()

    return render(request, "actions/action_list.html", {
        "actions":         qs,
        "status_filter":   status_filter,
        "priority_filter": priority_filter,
        "source_filter":   source_filter,
        "overdue_count":   overdue,
        "today":           today,
        "STATUS_CHOICES":  CorrectiveAction.STATUS_CHOICES,
        "PRIORITY_CHOICES": CorrectiveAction.PRIORITY_CHOICES,
        "SOURCE_CHOICES":  CorrectiveAction.SOURCE_CHOICES,
    })


@login_required
def my_actions(request):
    org = _org(request)
    qs  = (
        CorrectiveAction.objects
        .filter(organization=org, assigned_to=request.user)
        .exclude(status=CorrectiveAction.STATUS_CLOSED)
        .select_related("raised_by", "source_hira__register",
                        "source_observation", "source_compliance")
    )
    today = timezone.now().date()
    return render(request, "actions/action_list.html", {
        "actions":       qs,
        "my_actions_view": True,
        "today":         today,
        "STATUS_CHOICES":  CorrectiveAction.STATUS_CHOICES,
        "PRIORITY_CHOICES": CorrectiveAction.PRIORITY_CHOICES,
        "SOURCE_CHOICES":  CorrectiveAction.SOURCE_CHOICES,
    })


# ── Create ────────────────────────────────────────────────────────────────────

@login_required
def action_create(request):
    org = _org(request)
    _manager_required(request)
    org_users = _get_org_users(org)

    # Pre-fill from query params (when raised from another module)
    initial = {}
    for key in ("source_module", "source_hira", "source_observation",
                "source_compliance", "title", "description", "priority"):
        val = request.GET.get(key)
        if val:
            initial[key] = val

    if request.method == "POST":
        form = CorrectiveActionForm(request.POST)
        form.fields["assigned_to"].queryset = org_users
        if form.is_valid():
            action = form.save(commit=False)
            action.organization = org
            action.raised_by    = request.user
            # Attach source FK if provided via hidden POST field
            for fk in ("source_hira", "source_observation", "source_compliance"):
                pk = request.POST.get(fk)
                if pk:
                    setattr(action, f"{fk}_id", pk)
            action.save()
            _notify(action, "assigned")
            messages.success(request, f"Action CA-{action.pk:04d} created.")
            return redirect("actions:detail", pk=action.pk)
    else:
        form = CorrectiveActionForm(initial=initial)
        form.fields["assigned_to"].queryset = org_users

    # Hidden source FK values passed through from GET
    source_fk_fields = {k: request.GET.get(k) for k in
                        ("source_hira", "source_observation", "source_compliance")}

    return render(request, "actions/action_form.html", {
        "form":            form,
        "page_title":      "New Corrective Action",
        "source_fk_fields": source_fk_fields,
    })


# ── Detail ────────────────────────────────────────────────────────────────────

@login_required
def action_detail(request, pk):
    org    = _org(request)
    action = get_object_or_404(
        CorrectiveAction.objects.select_related(
            "assigned_to", "raised_by", "closed_by",
            "source_hira__register", "source_observation", "source_compliance",
        ),
        pk=pk, organization=org,
    )
    today        = timezone.now().date()
    can_progress = (
        action.assigned_to == request.user and
        action.status == CorrectiveAction.STATUS_OPEN
    )
    can_submit   = (
        action.assigned_to == request.user and
        action.status in (CorrectiveAction.STATUS_OPEN, CorrectiveAction.STATUS_IN_PROGRESS)
    )
    can_verify   = (
        (request.user.is_manager or request.user.is_safety_manager) and
        action.status == CorrectiveAction.STATUS_PENDING_VERIFICATION
    )
    can_reopen   = (
        (request.user.is_manager or request.user.is_safety_manager) and
        action.status == CorrectiveAction.STATUS_CLOSED
    )
    can_edit     = (request.user.is_manager or request.user.is_safety_manager)

    submit_form = SubmitEvidenceForm(instance=action) if can_submit else None
    verify_form = VerifyActionForm() if can_verify else None

    return render(request, "actions/action_detail.html", {
        "action":        action,
        "today":         today,
        "can_progress":  can_progress,
        "can_submit":    can_submit,
        "can_verify":    can_verify,
        "can_reopen":    can_reopen,
        "can_edit":      can_edit,
        "submit_form":   submit_form,
        "verify_form":   verify_form,
    })


# ── Edit ──────────────────────────────────────────────────────────────────────

@login_required
def action_edit(request, pk):
    org    = _org(request)
    _manager_required(request)
    action = get_object_or_404(CorrectiveAction, pk=pk, organization=org)
    org_users = _get_org_users(org)

    if request.method == "POST":
        form = CorrectiveActionForm(request.POST, instance=action)
        form.fields["assigned_to"].queryset = org_users
        if form.is_valid():
            old_assignee = action.assigned_to_id
            action = form.save()
            if action.assigned_to_id != old_assignee:
                _notify(action, "assigned")
            messages.success(request, "Action updated.")
            return redirect("actions:detail", pk=action.pk)
    else:
        form = CorrectiveActionForm(instance=action)
        form.fields["assigned_to"].queryset = org_users

    return render(request, "actions/action_form.html", {
        "form":       form,
        "action":     action,
        "page_title": f"Edit CA-{action.pk:04d}",
    })


# ── Workflow transitions ──────────────────────────────────────────────────────

@login_required
def action_progress(request, pk):
    """Assigned user marks action as In Progress."""
    org    = _org(request)
    action = get_object_or_404(CorrectiveAction, pk=pk, organization=org)

    if request.method == "POST":
        if (action.assigned_to == request.user and
                action.status == CorrectiveAction.STATUS_OPEN):
            action.status = CorrectiveAction.STATUS_IN_PROGRESS
            action.save(update_fields=["status", "updated_at"])
            messages.success(request, "Action marked as In Progress.")

    return redirect("actions:detail", pk=pk)


@login_required
def action_submit(request, pk):
    """Assigned user submits evidence and requests verification."""
    org    = _org(request)
    action = get_object_or_404(CorrectiveAction, pk=pk, organization=org)

    can_submit = (
        action.assigned_to == request.user and
        action.status in (CorrectiveAction.STATUS_OPEN, CorrectiveAction.STATUS_IN_PROGRESS)
    )
    if not can_submit:
        raise PermissionDenied

    if request.method == "POST":
        form = SubmitEvidenceForm(request.POST, request.FILES, instance=action)
        if form.is_valid():
            action = form.save(commit=False)
            action.status = CorrectiveAction.STATUS_PENDING_VERIFICATION
            action.save()
            _notify(action, "submitted")
            messages.success(request, "Action submitted for verification.")
            return redirect("actions:detail", pk=pk)

    return redirect("actions:detail", pk=pk)


@login_required
def action_verify(request, pk):
    """Manager closes or rejects (reopens) a pending-verification action."""
    org = _org(request)
    _manager_required(request)
    action = get_object_or_404(CorrectiveAction, pk=pk, organization=org)

    if action.status != CorrectiveAction.STATUS_PENDING_VERIFICATION:
        return redirect("actions:detail", pk=pk)

    if request.method == "POST":
        form = VerifyActionForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            if decision == VerifyActionForm.DECISION_CLOSE:
                action.status    = CorrectiveAction.STATUS_CLOSED
                action.closed_at = timezone.now()
                action.closed_by = request.user
                action.save()
                _notify(action, "closed")
                messages.success(request, "Action closed.")
            else:
                action.status         = CorrectiveAction.STATUS_IN_PROGRESS
                action.reopen_comment = form.cleaned_data["reopen_comment"]
                action.save()
                _notify(action, "reopened")
                messages.warning(request, "Action sent back for rework.")

    return redirect("actions:detail", pk=pk)


@login_required
def action_reopen(request, pk):
    """Manager reopens a closed action."""
    org = _org(request)
    _manager_required(request)
    action = get_object_or_404(CorrectiveAction, pk=pk, organization=org)

    if request.method == "POST" and action.status == CorrectiveAction.STATUS_CLOSED:
        action.status    = CorrectiveAction.STATUS_IN_PROGRESS
        action.closed_at = None
        action.closed_by = None
        action.reopen_comment = request.POST.get("reopen_comment", "")
        action.save()
        _notify(action, "reopened")
        messages.info(request, "Action reopened.")

    return redirect("actions:detail", pk=pk)
