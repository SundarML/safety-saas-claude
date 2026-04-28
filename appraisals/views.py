from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import timezone
from django.db import transaction

from .models import (
    AppraisalCycle, AppraisalCategory, AppraisalRecord,
    AppraisalItem, AppraisalRating, CalibrateNote, DevPlanLink,
)

User = None  # resolved lazily via get_user_model()


def _get_user_model():
    from django.contrib.auth import get_user_model
    return get_user_model()


def _org(request):
    org = getattr(request, "organization", None)
    if not org and request.user.is_authenticated:
        org = request.user.organization
    if not org:
        raise PermissionDenied
    return org


def _manager_required(request):
    if not (request.user.is_manager or request.user.is_safety_manager):
        raise PermissionDenied


def _can_manage_cycle(request, cycle):
    """True if the user owns this cycle or is a safety manager in same org."""
    return (
        request.user.is_safety_manager
        or cycle.created_by_id == request.user.pk
    )


def _direct_reports(manager, org):
    U = _get_user_model()
    return U.objects.filter(
        organization=org,
        reports_to=manager,
        is_active=True,
    ).order_by("full_name")


# ─────────────────────────────────────────────────────────────
# CYCLE LIST
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_list(request):
    org = _org(request)

    if request.user.is_safety_manager:
        cycles = AppraisalCycle.objects.filter(organization=org)
    elif request.user.is_manager:
        cycles = AppraisalCycle.objects.filter(organization=org, created_by=request.user)
    else:
        # Employee — see only cycles they're enrolled in
        enrolled_ids = AppraisalRecord.objects.filter(
            employee=request.user
        ).values_list("cycle_id", flat=True)
        cycles = AppraisalCycle.objects.filter(id__in=enrolled_ids)

    cycles = cycles.prefetch_related("records", "categories").order_by("-created_at")

    return render(request, "appraisals/cycle_list.html", {
        "cycles": cycles,
        "is_manager": request.user.is_manager or request.user.is_safety_manager,
        "STATUS_ORDER": AppraisalCycle.STATUS_ORDER,
        "STATUS_LABELS": dict(AppraisalCycle.STATUS_CHOICES),
    })


# ─────────────────────────────────────────────────────────────
# CYCLE CREATE
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_create(request):
    _manager_required(request)
    org = _org(request)
    U = _get_user_model()
    if request.user.is_safety_manager:
        direct_reports = U.objects.filter(
            organization=org, is_active=True
        ).exclude(role__in=["safety_manager"]).order_by("full_name")
    else:
        direct_reports = _direct_reports(request.user, org)

    if request.method == "POST":
        name           = request.POST.get("name", "").strip()
        period         = request.POST.get("period", AppraisalCycle.PERIOD_ANNUAL)
        start_date     = request.POST.get("start_date")
        end_date       = request.POST.get("end_date")
        goal_dl        = request.POST.get("goal_setting_deadline")
        self_dl        = request.POST.get("self_assessment_deadline")
        review_dl      = request.POST.get("review_deadline")
        cat_names      = request.POST.getlist("cat_name")
        cat_types      = request.POST.getlist("cat_type")
        cat_weights    = request.POST.getlist("cat_weight")
        employee_ids   = request.POST.getlist("employees")

        errors = []
        if not name:
            errors.append("Cycle name is required.")
        if not start_date or not end_date:
            errors.append("Start date and end date are required.")
        if not any(n.strip() for n in cat_names):
            errors.append("At least one category is required.")

        # Validate weight sum
        try:
            filled = [(n.strip(), t, w) for n, t, w in zip(cat_names, cat_types, cat_weights) if n.strip()]
            total_w = sum(float(w) for _, _, w in filled if w)
            if filled and abs(total_w - 100) > 0.01:
                errors.append(f"Category weights must sum to 100% (currently {total_w:.1f}%).")
        except (ValueError, TypeError):
            errors.append("Invalid weight values — enter numbers only.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            with transaction.atomic():
                cycle = AppraisalCycle.objects.create(
                    organization=org,
                    name=name,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    goal_setting_deadline=goal_dl,
                    self_assessment_deadline=self_dl,
                    review_deadline=review_dl,
                    status=AppraisalCycle.STATUS_GOAL_SETTING,
                    created_by=request.user,
                )

                for i, (cname, ctype, cweight) in enumerate(filled):
                    AppraisalCategory.objects.create(
                        cycle=cycle,
                        name=cname,
                        category_type=ctype,
                        weight=float(cweight) if cweight else 0,
                        order=i,
                    )

                U = _get_user_model()
                for emp_id in employee_ids:
                    try:
                        emp = U.objects.get(pk=emp_id, organization=org, is_active=True)
                        AppraisalRecord.objects.create(
                            cycle=cycle,
                            employee=emp,
                            reviewer=request.user,
                            status=AppraisalRecord.STATUS_PENDING_GOALS,
                        )
                    except U.DoesNotExist:
                        pass

                messages.success(request, f"Appraisal cycle '{cycle.name}' created. Now set goals for each employee.")
                return redirect("appraisals:cycle_detail", pk=cycle.pk)

    return render(request, "appraisals/cycle_form.html", {
        "direct_reports": direct_reports,
        "period_choices": AppraisalCycle.PERIOD_CHOICES,
        "category_type_choices": AppraisalCategory.TYPE_CHOICES,
        "mode": "create",
    })


# ─────────────────────────────────────────────────────────────
# CYCLE DETAIL
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_detail(request, pk):
    org = _org(request)
    cycle = get_object_or_404(AppraisalCycle, pk=pk, organization=org)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    records    = cycle.records.select_related("employee", "reviewer").all()
    categories = cycle.categories.all()

    status_counts = {s: records.filter(status=s).count() for s, _ in AppraisalRecord.STATUS_CHOICES}
    pending_approvals = AppraisalItem.objects.filter(
        record__cycle=cycle,
        goal_type=AppraisalItem.GOAL_SELF_SET,
        approved_by_manager=False,
        rejection_reason="",
    ).count()

    return render(request, "appraisals/cycle_detail.html", {
        "cycle": cycle,
        "records": records,
        "categories": categories,
        "status_counts": status_counts,
        "pending_approvals": pending_approvals,
        "STATUS_ORDER": AppraisalCycle.STATUS_ORDER,
        "STATUS_LABELS": dict(AppraisalCycle.STATUS_CHOICES),
    })


# ─────────────────────────────────────────────────────────────
# CYCLE ADVANCE STATUS
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_advance(request, pk):
    org = _org(request)
    _manager_required(request)
    cycle = get_object_or_404(AppraisalCycle, pk=pk, organization=org)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    if request.method == "POST":
        next_s = cycle.next_status
        if next_s:
            cycle.status = next_s
            cycle.save(update_fields=["status", "updated_at"])

            if next_s == AppraisalCycle.STATUS_SELF_ASSESSMENT:
                cycle.records.filter(
                    status=AppraisalRecord.STATUS_PENDING_GOALS
                ).update(status=AppraisalRecord.STATUS_GOALS_SET)
                cycle.records.filter(
                    status=AppraisalRecord.STATUS_GOALS_SET
                ).update(status=AppraisalRecord.STATUS_SELF_ASSESS)

            messages.success(request, f"Cycle advanced to: {cycle.get_status_display()}")
        else:
            messages.warning(request, "Cycle is already at the final stage.")

    return redirect("appraisals:cycle_detail", pk=cycle.pk)


# ─────────────────────────────────────────────────────────────
# RECORD GOALS — manager sets goals per employee
# ─────────────────────────────────────────────────────────────

@login_required
def record_goals(request, cycle_pk, record_pk):
    org    = _org(request)
    _manager_required(request)
    cycle  = get_object_or_404(AppraisalCycle, pk=cycle_pk, organization=org)
    record = get_object_or_404(AppraisalRecord, pk=record_pk, cycle=cycle)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    categories = cycle.categories.all()

    # Items grouped by category id
    items_by_cat = {
        cat.id: list(AppraisalItem.objects.filter(record=record, category=cat).order_by("created_at"))
        for cat in categories
    }

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_item":
            cat_id      = request.POST.get("category_id")
            title       = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            item_type   = request.POST.get("item_type", AppraisalItem.ITEM_RATING)
            weight      = request.POST.get("weight", "0")
            target_val  = request.POST.get("target_value") or None
            target_unit = request.POST.get("target_unit", "").strip()

            try:
                cat = AppraisalCategory.objects.get(pk=cat_id, cycle=cycle)
            except AppraisalCategory.DoesNotExist:
                messages.error(request, "Invalid category.")
                return redirect("appraisals:record_goals", cycle_pk=cycle.pk, record_pk=record.pk)

            if not title:
                messages.error(request, "Title is required.")
            else:
                try:
                    w = float(weight) if weight else 0
                except ValueError:
                    w = 0
                AppraisalItem.objects.create(
                    record=record,
                    category=cat,
                    title=title,
                    description=description,
                    item_type=item_type,
                    weight=w,
                    target_value=target_val,
                    target_unit=target_unit,
                    goal_type=AppraisalItem.GOAL_MANAGER_SET,
                    created_by=request.user,
                    approved_by_manager=True,
                    approved_by=request.user,
                    approved_at=timezone.now(),
                )
                messages.success(request, f"Item '{title}' added.")

        elif action == "delete_item":
            item_id = request.POST.get("item_id")
            AppraisalItem.objects.filter(
                pk=item_id,
                record=record,
                goal_type=AppraisalItem.GOAL_MANAGER_SET,
            ).delete()
            messages.success(request, "Item removed.")

        elif action == "mark_goals_set":
            record.status = AppraisalRecord.STATUS_GOALS_SET
            record.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Goals finalised for {record.employee.full_name}.")
            return redirect("appraisals:cycle_detail", pk=cycle.pk)

        return redirect("appraisals:record_goals", cycle_pk=cycle.pk, record_pk=record.pk)

    # Compute weight totals per category to show warnings
    weight_totals = {}
    for cat in categories:
        items = items_by_cat.get(cat.id, [])
        approved = [i for i in items if i.approved_by_manager]
        weight_totals[cat.id] = sum(float(i.weight) for i in approved)

    pending_approvals = AppraisalItem.objects.filter(
        record__cycle=cycle,
        goal_type=AppraisalItem.GOAL_SELF_SET,
        approved_by_manager=False,
        rejection_reason="",
    ).count()

    return render(request, "appraisals/record_goals.html", {
        "cycle": cycle,
        "record": record,
        "categories": categories,
        "items_by_cat": items_by_cat,
        "weight_totals": weight_totals,
        "item_type_choices": AppraisalItem.ITEM_TYPE_CHOICES,
        "ITEM_MEASURABLE": AppraisalItem.ITEM_MEASURABLE,
        "pending_approvals": pending_approvals,
    })


# ─────────────────────────────────────────────────────────────
# MY APPRAISALS — employee's own records
# ─────────────────────────────────────────────────────────────

@login_required
def my_appraisals(request):
    records = (
        AppraisalRecord.objects
        .filter(employee=request.user)
        .select_related("cycle", "reviewer")
        .order_by("-cycle__created_at")
    )
    return render(request, "appraisals/my_appraisals.html", {"records": records})


# ─────────────────────────────────────────────────────────────
# MY RECORD DETAIL — employee view: propose goals + self-assess
# ─────────────────────────────────────────────────────────────

@login_required
def my_record_detail(request, record_pk):
    record = get_object_or_404(AppraisalRecord, pk=record_pk, employee=request.user)
    cycle  = record.cycle
    cats   = cycle.categories.all()

    items_by_cat = {
        cat.id: list(
            AppraisalItem.objects.filter(record=record, category=cat).order_by("goal_type", "created_at")
        )
        for cat in cats
    }

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Propose a goal ──
        if action == "propose_goal" and cycle.status == AppraisalCycle.STATUS_GOAL_SETTING:
            cat_id      = request.POST.get("category_id")
            title       = request.POST.get("title", "").strip()
            description = request.POST.get("description", "").strip()
            item_type   = request.POST.get("item_type", AppraisalItem.ITEM_RATING)
            target_val  = request.POST.get("target_value") or None
            target_unit = request.POST.get("target_unit", "").strip()

            try:
                cat = AppraisalCategory.objects.get(pk=cat_id, cycle=cycle)
            except AppraisalCategory.DoesNotExist:
                messages.error(request, "Invalid category.")
                return redirect("appraisals:my_record_detail", record_pk=record.pk)

            if not title:
                messages.error(request, "Title is required.")
            else:
                AppraisalItem.objects.create(
                    record=record,
                    category=cat,
                    title=title,
                    description=description,
                    item_type=item_type,
                    weight=0,
                    target_value=target_val,
                    target_unit=target_unit,
                    goal_type=AppraisalItem.GOAL_SELF_SET,
                    created_by=request.user,
                    approved_by_manager=False,
                )
                messages.success(request, "Goal proposed — awaiting manager approval.")

        # ── Delete own proposed goal (before approval) ──
        elif action == "delete_proposed":
            item_id = request.POST.get("item_id")
            AppraisalItem.objects.filter(
                pk=item_id,
                record=record,
                goal_type=AppraisalItem.GOAL_SELF_SET,
                approved_by_manager=False,
            ).delete()
            messages.success(request, "Proposed goal removed.")

        # ── Submit self-assessment ──
        elif action == "submit_self_assessment" and cycle.status == AppraisalCycle.STATUS_SELF_ASSESSMENT:
            approved_items = AppraisalItem.objects.filter(record=record, approved_by_manager=True)
            for item in approved_items:
                sr  = request.POST.get(f"self_rating_{item.pk}")
                sc  = request.POST.get(f"self_comment_{item.pk}", "")
                av  = request.POST.get(f"actual_value_{item.pk}") or None
                rating, _ = AppraisalRating.objects.get_or_create(record=record, item=item)
                if sr:
                    rating.self_rating = int(sr)
                rating.self_comment = sc
                if av is not None and item.item_type == AppraisalItem.ITEM_MEASURABLE:
                    try:
                        rating.actual_value = float(av)
                    except ValueError:
                        pass
                rating.save()

            record.status = AppraisalRecord.STATUS_PENDING_REVIEW
            record.save(update_fields=["status", "updated_at"])
            messages.success(request, "Self-assessment submitted successfully.")
            return redirect("appraisals:my_appraisals")

        return redirect("appraisals:my_record_detail", record_pk=record.pk)

    # Pre-load existing ratings for display
    ratings_by_item = {
        r.item_id: r
        for r in AppraisalRating.objects.filter(record=record)
    }

    return render(request, "appraisals/my_record_detail.html", {
        "record": record,
        "cycle": cycle,
        "categories": cats,
        "items_by_cat": items_by_cat,
        "ratings_by_item": ratings_by_item,
        "item_type_choices": AppraisalItem.ITEM_TYPE_CHOICES,
        "ITEM_MEASURABLE": AppraisalItem.ITEM_MEASURABLE,
        "ITEM_RATING": AppraisalItem.ITEM_RATING,
        "ITEM_YESNO": AppraisalItem.ITEM_YESNO,
        "GOAL_SELF_SET": AppraisalItem.GOAL_SELF_SET,
        "GOAL_MANAGER_SET": AppraisalItem.GOAL_MANAGER_SET,
        "STATUS_GOAL_SETTING": AppraisalCycle.STATUS_GOAL_SETTING,
        "STATUS_SELF_ASSESSMENT": AppraisalCycle.STATUS_SELF_ASSESSMENT,
    })


# ─────────────────────────────────────────────────────────────
# PENDING GOALS — manager approves / rejects employee proposals
# ─────────────────────────────────────────────────────────────

@login_required
def pending_goals(request, cycle_pk):
    org   = _org(request)
    _manager_required(request)
    cycle = get_object_or_404(AppraisalCycle, pk=cycle_pk, organization=org)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    pending_items = (
        AppraisalItem.objects
        .filter(
            record__cycle=cycle,
            goal_type=AppraisalItem.GOAL_SELF_SET,
            approved_by_manager=False,
            rejection_reason="",
        )
        .select_related("record__employee", "category")
        .order_by("record__employee__full_name", "created_at")
    )

    if request.method == "POST":
        action   = request.POST.get("action")
        item_ids = request.POST.getlist("item_ids")

        if not item_ids:
            messages.warning(request, "No items selected.")
            return redirect("appraisals:pending_goals", cycle_pk=cycle.pk)

        items_qs = AppraisalItem.objects.filter(
            pk__in=item_ids,
            record__cycle=cycle,
            goal_type=AppraisalItem.GOAL_SELF_SET,
        )

        if action in ("bulk_approve", "approve_one"):
            now   = timezone.now()
            count = 0
            for item in items_qs.filter(approved_by_manager=False):
                weight_val = request.POST.get(f"weight_{item.pk}", "0") if action == "approve_one" else "0"
                try:
                    w = float(weight_val)
                except ValueError:
                    w = 0
                item.approved_by_manager = True
                item.approved_by         = request.user
                item.approved_at         = now
                if w:
                    item.weight = w
                item.save(update_fields=["approved_by_manager", "approved_by", "approved_at", "weight"])
                count += 1
            messages.success(request, f"{count} goal(s) approved.")

        elif action in ("bulk_reject", "reject_one"):
            reason = request.POST.get("rejection_reason", "").strip() or "Rejected by manager."
            items_qs.filter(approved_by_manager=False).update(rejection_reason=reason)
            messages.success(request, f"{items_qs.count()} goal(s) rejected.")

        return redirect("appraisals:pending_goals", cycle_pk=cycle.pk)

    return render(request, "appraisals/pending_goals.html", {
        "cycle": cycle,
        "pending_items": pending_items,
    })


# ─────────────────────────────────────────────────────────────
# RECORD REVIEW — manager rates items side-by-side with self-ratings
# ─────────────────────────────────────────────────────────────

@login_required
def record_review(request, cycle_pk, record_pk):
    org    = _org(request)
    _manager_required(request)
    cycle  = get_object_or_404(AppraisalCycle, pk=cycle_pk, organization=org)
    record = get_object_or_404(AppraisalRecord, pk=record_pk, cycle=cycle)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    categories    = cycle.categories.all()
    approved_items = list(
        AppraisalItem.objects
        .filter(record=record, approved_by_manager=True)
        .select_related("category")
        .order_by("category__order", "created_at")
    )
    ratings_by_item = {r.item_id: r for r in AppraisalRating.objects.filter(record=record)}

    items_by_cat = {cat.id: [i for i in approved_items if i.category_id == cat.id] for cat in categories}

    if request.method == "POST":
        with transaction.atomic():
            for item in approved_items:
                mr = request.POST.get(f"manager_rating_{item.pk}")
                mc = request.POST.get(f"manager_comment_{item.pk}", "")
                av = request.POST.get(f"actual_value_{item.pk}") or None

                rating, _ = AppraisalRating.objects.get_or_create(record=record, item=item)
                if mr:
                    rating.manager_rating = int(mr)
                rating.manager_comment = mc
                if av is not None and item.item_type == AppraisalItem.ITEM_MEASURABLE:
                    try:
                        rating.actual_value = float(av)
                    except ValueError:
                        pass
                rating.save()

            record.manager_summary  = request.POST.get("manager_summary", "").strip()
            record.development_plan = request.POST.get("development_plan", "").strip()
            record.status           = AppraisalRecord.STATUS_MANAGER_REVIEWED
            record.save(update_fields=["manager_summary", "development_plan", "status", "updated_at"])
            record.compute_and_save_score()

        messages.success(
            request,
            f"Review submitted for {record.employee.full_name}. "
            f"Final score: {record.overall_score}% ({record.get_overall_rating_display()})."
        )
        return redirect("appraisals:cycle_detail", pk=cycle.pk)

    return render(request, "appraisals/record_review.html", {
        "cycle": cycle,
        "record": record,
        "categories": categories,
        "items_by_cat": items_by_cat,
        "ratings_by_item": ratings_by_item,
        "ITEM_MEASURABLE": AppraisalItem.ITEM_MEASURABLE,
        "ITEM_YESNO": AppraisalItem.ITEM_YESNO,
    })


# ─────────────────────────────────────────────────────────────
# RECORD VIEW — read-only result for employee (+ manager)
# ─────────────────────────────────────────────────────────────

@login_required
def record_view(request, record_pk):
    record = get_object_or_404(AppraisalRecord, pk=record_pk)
    org    = getattr(request, "organization", None) or request.user.organization

    user_is_employee = record.employee_id == request.user.pk
    user_is_manager  = (
        (request.user.is_manager or request.user.is_safety_manager)
        and record.cycle.organization == org
    )
    if not user_is_employee and not user_is_manager:
        raise PermissionDenied

    categories     = record.cycle.categories.all()
    approved_items = list(
        AppraisalItem.objects
        .filter(record=record, approved_by_manager=True)
        .select_related("category")
        .order_by("category__order", "created_at")
    )
    ratings_by_item = {r.item_id: r for r in AppraisalRating.objects.filter(record=record)}
    items_by_cat    = {cat.id: [i for i in approved_items if i.category_id == cat.id] for cat in categories}

    # Build radar chart: items that have both self and manager ratings
    radar_html = ""
    radar_items = [
        (item, ratings_by_item[item.pk])
        for item in approved_items
        if item.pk in ratings_by_item
        and ratings_by_item[item.pk].self_rating is not None
        and ratings_by_item[item.pk].manager_rating is not None
    ]
    if len(radar_items) >= 3:
        import plotly.graph_objects as go
        import plotly.io as pio
        labels     = [item.title[:30] for item, _ in radar_items]
        self_vals  = [float(r.self_rating) for _, r in radar_items]
        mgr_vals   = [float(r.manager_rating) for _, r in radar_items]
        # Close the polygon
        labels    += [labels[0]]
        self_vals += [self_vals[0]]
        mgr_vals  += [mgr_vals[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=self_vals, theta=labels, fill="toself",
            name="Self Rating",
            line=dict(color="#0ea5e9"), fillcolor="rgba(14,165,233,.15)",
        ))
        fig.add_trace(go.Scatterpolar(
            r=mgr_vals, theta=labels, fill="toself",
            name="Manager Rating",
            line=dict(color="#6366f1"), fillcolor="rgba(99,102,241,.15)",
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5])),
            showlegend=True,
            margin=dict(t=30, b=30, l=50, r=50),
            height=380,
            paper_bgcolor="#ffffff",
            font=dict(size=11),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15),
        )
        radar_html = pio.to_html(fig, full_html=False)

    # Dev plan linked training modules
    dev_links = DevPlanLink.objects.filter(record=record).select_related("training_module")

    return render(request, "appraisals/record_view.html", {
        "record": record,
        "cycle": record.cycle,
        "categories": categories,
        "items_by_cat": items_by_cat,
        "ratings_by_item": ratings_by_item,
        "user_is_employee": user_is_employee,
        "ITEM_MEASURABLE": AppraisalItem.ITEM_MEASURABLE,
        "RATING_COLORS": AppraisalRecord.RATING_COLORS,
        "radar_html": radar_html,
        "dev_links": dev_links,
    })


# ─────────────────────────────────────────────────────────────
# RECORD ACKNOWLEDGE — employee signs off on final review
# ─────────────────────────────────────────────────────────────

@login_required
def record_acknowledge(request, record_pk):
    record = get_object_or_404(AppraisalRecord, pk=record_pk, employee=request.user)

    if request.method == "POST":
        if record.status == AppraisalRecord.STATUS_MANAGER_REVIEWED:
            record.status          = AppraisalRecord.STATUS_ACKNOWLEDGED
            record.acknowledged_at = timezone.now()
            record.save(update_fields=["status", "acknowledged_at", "updated_at"])
            messages.success(request, "Appraisal acknowledged. Your record is now complete.")
        return redirect("appraisals:record_view", record_pk=record.pk)

    raise PermissionDenied


# ─────────────────────────────────────────────────────────────
# RECORD PDF — download appraisal report
# ─────────────────────────────────────────────────────────────

@login_required
def record_pdf(request, record_pk):
    record = get_object_or_404(AppraisalRecord, pk=record_pk)
    org    = getattr(request, "organization", None) or request.user.organization

    user_is_employee = record.employee_id == request.user.pk
    user_is_manager  = (
        (request.user.is_manager or request.user.is_safety_manager)
        and record.cycle.organization == org
    )
    if not user_is_employee and not user_is_manager:
        raise PermissionDenied

    from .pdf import generate_appraisal_pdf
    pdf_bytes = generate_appraisal_pdf(record)

    safe_name = (
        f"appraisal_{record.employee.full_name.replace(' ', '_')}"
        f"_{record.cycle.name.replace(' ', '_')}.pdf"
    )
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{safe_name}"'
    return response


# ─────────────────────────────────────────────────────────────
# CYCLE STATS — score table + Plotly bar chart
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_stats(request, pk):
    org   = _org(request)
    _manager_required(request)
    cycle = get_object_or_404(AppraisalCycle, pk=pk, organization=org)

    if not _can_manage_cycle(request, cycle):
        raise PermissionDenied

    records = (
        cycle.records
        .select_related("employee")
        .filter(overall_score__isnull=False)
        .order_by("-overall_score")
    )
    all_records = cycle.records.select_related("employee").order_by("employee__full_name")

    chart_html = ""
    if records.exists():
        import plotly.graph_objects as go
        import plotly.io as pio

        names  = [r.employee.full_name for r in records]
        scores = [float(r.overall_score) for r in records]
        bar_colors = []
        for s in scores:
            if s >= 90:   bar_colors.append("#16a34a")
            elif s >= 75: bar_colors.append("#0ea5e9")
            elif s >= 60: bar_colors.append("#6366f1")
            elif s >= 40: bar_colors.append("#f59e0b")
            else:         bar_colors.append("#ef4444")

        fig = go.Figure(go.Bar(
            x=names, y=scores,
            marker_color=bar_colors,
            text=[f"{s:.1f}%" for s in scores],
            textposition="outside",
        ))
        fig.add_hline(y=60, line_dash="dot", line_color="#94a3b8",
                      annotation_text="Meets threshold (60%)", annotation_position="right")
        fig.update_layout(
            yaxis=dict(range=[0, 115], title="Score (%)"),
            xaxis_title="",
            plot_bgcolor="#f8f9fb",
            paper_bgcolor="#ffffff",
            margin=dict(t=20, b=40, l=50, r=30),
            height=360,
            font=dict(size=12),
        )
        chart_html = pio.to_html(fig, full_html=False)

    dist  = {r: all_records.filter(overall_rating=r).count() for r, _ in AppraisalRecord.RATING_CHOICES}
    avg_score = None
    if records.exists():
        from decimal import Decimal
        avg_score = sum(float(r.overall_score) for r in records) / records.count()

    return render(request, "appraisals/cycle_stats.html", {
        "cycle": cycle,
        "records": all_records,
        "reviewed_records": records,
        "chart_html": chart_html,
        "rating_dist": dist,
        "avg_score": avg_score,
        "RATING_CHOICES": AppraisalRecord.RATING_CHOICES,
        "RATING_COLORS": AppraisalRecord.RATING_COLORS,
    })


# ─────────────────────────────────────────────────────────────
# CYCLE CALIBRATE — Safety Manager adjusts scores with audit trail
# ─────────────────────────────────────────────────────────────

@login_required
def cycle_calibrate(request, pk):
    org   = _org(request)
    cycle = get_object_or_404(AppraisalCycle, pk=pk, organization=org)

    if not request.user.is_safety_manager:
        raise PermissionDenied

    reviewed_records = (
        cycle.records
        .filter(overall_score__isnull=False)
        .select_related("employee", "reviewer")
        .prefetch_related("calibrate_notes__calibrated_by")
        .order_by("-overall_score")
    )

    if request.method == "POST":
        record_pk   = request.POST.get("record_pk")
        new_score   = request.POST.get("new_score", "").strip()
        note_text   = request.POST.get("note", "").strip()

        try:
            rec = AppraisalRecord.objects.get(pk=record_pk, cycle=cycle)
        except AppraisalRecord.DoesNotExist:
            messages.error(request, "Record not found.")
            return redirect("appraisals:cycle_calibrate", pk=cycle.pk)

        if not note_text:
            messages.error(request, "A calibration note is required to justify any adjustment.")
            return redirect("appraisals:cycle_calibrate", pk=cycle.pk)

        old_score  = rec.overall_score
        old_rating = rec.overall_rating

        if new_score:
            try:
                ns = float(new_score)
                if not (0 <= ns <= 100):
                    raise ValueError
            except ValueError:
                messages.error(request, "Score must be a number between 0 and 100.")
                return redirect("appraisals:cycle_calibrate", pk=cycle.pk)
            from decimal import Decimal
            rec.overall_score  = Decimal(str(ns)).quantize(Decimal("0.01"))
            rec.overall_rating = AppraisalRecord._rating_label(rec.overall_score)
            rec.save(update_fields=["overall_score", "overall_rating", "updated_at"])
        else:
            ns = None

        CalibrateNote.objects.create(
            record        = rec,
            calibrated_by = request.user,
            old_score     = old_score,
            new_score     = rec.overall_score if new_score else None,
            old_rating    = old_rating,
            new_rating    = rec.overall_rating if new_score else "",
            note          = note_text,
        )
        messages.success(request, f"Calibration note saved for {rec.employee.full_name}.")
        return redirect("appraisals:cycle_calibrate", pk=cycle.pk)

    # Scatter chart: score vs employee
    scatter_html = ""
    if reviewed_records.exists():
        import plotly.graph_objects as go
        import plotly.io as pio

        names  = [r.employee.full_name for r in reviewed_records]
        scores = [float(r.overall_score) for r in reviewed_records]
        colors = []
        for s in scores:
            if s >= 90:   colors.append("#16a34a")
            elif s >= 75: colors.append("#0ea5e9")
            elif s >= 60: colors.append("#6366f1")
            elif s >= 40: colors.append("#f59e0b")
            else:         colors.append("#ef4444")

        fig = go.Figure(go.Scatter(
            x=list(range(1, len(names) + 1)),
            y=scores,
            mode="markers+text",
            text=names,
            textposition="top center",
            marker=dict(color=colors, size=14, line=dict(width=1.5, color="#fff")),
        ))
        fig.add_hline(y=90, line_dash="dot", line_color="#16a34a", annotation_text="Exceptional (90%)")
        fig.add_hline(y=75, line_dash="dot", line_color="#0ea5e9", annotation_text="Exceeds (75%)")
        fig.add_hline(y=60, line_dash="dot", line_color="#6366f1", annotation_text="Meets (60%)")
        fig.update_layout(
            yaxis=dict(range=[0, 115], title="Score (%)", dtick=10),
            xaxis=dict(visible=False),
            plot_bgcolor="#f8f9fb",
            paper_bgcolor="#ffffff",
            margin=dict(t=30, b=50, l=50, r=30),
            height=400,
            font=dict(size=11),
            showlegend=False,
        )
        scatter_html = pio.to_html(fig, full_html=False)

    return render(request, "appraisals/cycle_calibrate.html", {
        "cycle": cycle,
        "reviewed_records": reviewed_records,
        "scatter_html": scatter_html,
        "RATING_CHOICES": AppraisalRecord.RATING_CHOICES,
    })


# ─────────────────────────────────────────────────────────────
# DEV PLAN LINKS — manager links training modules to a record
# ─────────────────────────────────────────────────────────────

@login_required
def dev_plan_links(request, record_pk):
    record = get_object_or_404(AppraisalRecord, pk=record_pk)
    org    = getattr(request, "organization", None) or request.user.organization

    user_is_manager = (
        (request.user.is_manager or request.user.is_safety_manager)
        and record.cycle.organization == org
    )
    if not user_is_manager:
        raise PermissionDenied

    from training.models import TrainingModule
    modules      = TrainingModule.objects.filter(organization=org).order_by("title")
    existing_ids = set(record.dev_plan_links.values_list("training_module_id", flat=True))

    if request.method == "POST":
        action    = request.POST.get("action")
        module_id = request.POST.get("module_id")
        note_text = request.POST.get("note", "").strip()

        if action == "add" and module_id:
            try:
                mod = TrainingModule.objects.get(pk=module_id, organization=org)
                DevPlanLink.objects.get_or_create(
                    record=record, training_module=mod,
                    defaults={"note": note_text, "created_by": request.user},
                )
                messages.success(request, f"'{mod.title}' linked to development plan.")
            except TrainingModule.DoesNotExist:
                messages.error(request, "Training module not found.")

        elif action == "remove" and module_id:
            DevPlanLink.objects.filter(record=record, training_module_id=module_id).delete()
            messages.success(request, "Link removed.")

        return redirect("appraisals:dev_plan_links", record_pk=record.pk)

    existing_links = DevPlanLink.objects.filter(record=record).select_related("training_module", "created_by")

    return render(request, "appraisals/dev_plan_links.html", {
        "record": record,
        "cycle": record.cycle,
        "modules": modules,
        "existing_links": existing_links,
        "existing_ids": existing_ids,
    })
