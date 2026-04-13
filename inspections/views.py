from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from .models import InspectionTemplate, TemplateSection, InspectionItem, Inspection, InspectionFinding
from .forms import InspectionTemplateForm, InspectionCreateForm, ConductFindingForm
from core.utils.guards import org_required as _org_required


def _org(request):
    _org_required(request)
    return request.organization


def _manager_required(request):
    if not (request.user.is_manager or request.user.is_safety_manager):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied


# ── Template list ─────────────────────────────────────────────────────────────

@login_required
def template_list(request):
    org = _org(request)
    templates = InspectionTemplate.objects.filter(organization=org)
    return render(request, "inspections/template_list.html", {
        "templates":  templates,
        "is_manager": request.user.is_manager or request.user.is_safety_manager,
    })


# ── Template create / edit ────────────────────────────────────────────────────

@login_required
def template_create(request):
    org = _org(request)
    _manager_required(request)
    form = InspectionTemplateForm()

    if request.method == "POST":
        form = InspectionTemplateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                tmpl = form.save(commit=False)
                tmpl.organization = org
                tmpl.created_by   = request.user
                tmpl.save()
                _save_sections_items(request.POST, tmpl, existing=False)
            messages.success(request, f'Template "{tmpl.title}" created.')
            return redirect("inspections:template_detail", tmpl.pk)

    return render(request, "inspections/template_form.html", {
        "form":     form,
        "sections": [],
    })


@login_required
def template_edit(request, pk):
    org  = _org(request)
    _manager_required(request)
    tmpl = get_object_or_404(InspectionTemplate, pk=pk, organization=org)
    form = InspectionTemplateForm(instance=tmpl)

    if request.method == "POST":
        form = InspectionTemplateForm(request.POST, instance=tmpl)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                # Delete all existing sections/items and rebuild
                tmpl.sections.all().delete()
                _save_sections_items(request.POST, tmpl, existing=False)
            messages.success(request, "Template updated.")
            return redirect("inspections:template_detail", tmpl.pk)

    return render(request, "inspections/template_form.html", {
        "form":     form,
        "template": tmpl,
        "sections": tmpl.sections.prefetch_related("items").all(),
    })


def _save_sections_items(post, tmpl, existing=False):
    """Parse the flat arrays from the JS builder and create TemplateSection + InspectionItem rows."""
    titles      = post.getlist("section_title[]")
    questions   = post.getlist("item_question[]")
    sidxs       = post.getlist("item_section_idx[]")
    criticals   = post.getlist("item_critical[]")   # values like "0_0", "1_2"

    # Build set of critical (section_idx, item_within_section) pairs
    critical_set = set()
    for val in criticals:
        parts = val.split("_")
        if len(parts) == 2:
            critical_set.add((parts[0], parts[1]))

    # Create sections
    section_objs = {}
    for s_idx, title in enumerate(titles):
        title = title.strip()
        if not title:
            continue
        sec = TemplateSection.objects.create(template=tmpl, title=title, order=s_idx)
        section_objs[str(s_idx)] = sec

    # Create items — track item count per section for critical matching
    item_counts = {}
    for q_idx, (question, sidx) in enumerate(zip(questions, sidxs)):
        question = question.strip()
        if not question or sidx not in section_objs:
            continue
        sec      = section_objs[sidx]
        i_within = item_counts.get(sidx, 0)
        is_crit  = (sidx, str(i_within)) in critical_set
        InspectionItem.objects.create(
            section=sec, question=question,
            is_critical=is_crit, order=i_within,
        )
        item_counts[sidx] = i_within + 1


# ── Template detail ───────────────────────────────────────────────────────────

@login_required
def template_detail(request, pk):
    org  = _org(request)
    tmpl = get_object_or_404(InspectionTemplate, pk=pk, organization=org)
    return render(request, "inspections/template_detail.html", {
        "template":   tmpl,
        "is_manager": request.user.is_manager or request.user.is_safety_manager,
    })


# ── Inspection list ───────────────────────────────────────────────────────────

@login_required
def inspection_list(request):
    org  = _org(request)
    today = timezone.now().date()

    qs = Inspection.objects.filter(organization=org).select_related(
        "template", "inspector", "location"
    )

    # Auto-mark overdue
    qs.filter(
        scheduled_date__lt=today,
        status__in=[Inspection.STATUS_SCHEDULED, Inspection.STATUS_IN_PROGRESS],
    ).update(status=Inspection.STATUS_OVERDUE)

    # Filters
    status_filter   = request.GET.get("status", "")
    template_filter = request.GET.get("template", "")
    inspector_filter= request.GET.get("inspector", "")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if template_filter:
        qs = qs.filter(template_id=template_filter)
    if inspector_filter:
        qs = qs.filter(inspector_id=inspector_filter)

    from django.contrib.auth import get_user_model
    User = get_user_model()

    return render(request, "inspections/inspection_list.html", {
        "inspections":       qs,
        "templates":         InspectionTemplate.objects.filter(organization=org, is_active=True),
        "inspectors":        User.objects.filter(organization=org, is_active=True),
        "status_filter":     status_filter,
        "template_filter":   template_filter,
        "inspector_filter":  inspector_filter,
        "status_choices":    Inspection.STATUS_CHOICES,
        "is_manager":        request.user.is_manager or request.user.is_safety_manager,
        "today":             today,
    })


# ── Inspection create ─────────────────────────────────────────────────────────

@login_required
def inspection_create(request):
    org = _org(request)
    _manager_required(request)

    initial = {}
    if request.GET.get("template"):
        initial["template"] = request.GET.get("template")

    form = InspectionCreateForm(org, initial=initial)
    if request.method == "POST":
        form = InspectionCreateForm(org, request.POST)
        if form.is_valid():
            inspection = form.save(commit=False)
            inspection.organization = org
            inspection.created_by   = request.user
            inspection.save()
            messages.success(request, f'Inspection "{inspection.title}" scheduled.')
            return redirect("inspections:detail", inspection.pk)

    return render(request, "inspections/inspection_create.html", {
        "form": form,
    })


# ── Inspection detail ─────────────────────────────────────────────────────────

@login_required
def inspection_detail(request, pk):
    org        = _org(request)
    inspection = get_object_or_404(Inspection, pk=pk, organization=org)
    findings   = inspection.findings.select_related(
        "template_item__section", "raised_action"
    ).all()

    # Group findings by section
    sections = {}
    for f in findings:
        sec = f.template_item.section
        sections.setdefault(sec, []).append(f)

    return render(request, "inspections/inspection_detail.html", {
        "inspection":     inspection,
        "sections":       sections,
        "is_manager":     request.user.is_manager or request.user.is_safety_manager,
        "can_conduct":    (
            request.user == inspection.inspector or
            request.user.is_manager or
            request.user.is_safety_manager
        ),
    })


# ── Conduct inspection ────────────────────────────────────────────────────────

@login_required
def inspection_conduct(request, pk):
    org        = _org(request)
    inspection = get_object_or_404(Inspection, pk=pk, organization=org)

    # Only inspector or managers can conduct
    if not (request.user == inspection.inspector or
            request.user.is_manager or request.user.is_safety_manager):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    if inspection.status == Inspection.STATUS_COMPLETED:
        messages.info(request, "This inspection is already completed.")
        return redirect("inspections:detail", pk)

    # Build or fetch findings for all items
    all_items = InspectionItem.objects.filter(
        section__template=inspection.template
    ).select_related("section").order_by("section__order", "order")

    for item in all_items:
        InspectionFinding.objects.get_or_create(
            inspection=inspection, template_item=item
        )

    if inspection.status == Inspection.STATUS_SCHEDULED:
        inspection.status = Inspection.STATUS_IN_PROGRESS
        inspection.save(update_fields=["status"])

    findings = inspection.findings.select_related(
        "template_item__section"
    ).order_by("template_item__section__order", "template_item__order")

    # Group by section
    from collections import OrderedDict
    sections = OrderedDict()
    for f in findings:
        sec = f.template_item.section
        sections.setdefault(sec, []).append(f)

    if request.method == "POST":
        with transaction.atomic():
            for finding in findings:
                key_resp  = f"resp_{finding.pk}"
                key_notes = f"notes_{finding.pk}"
                key_photo = f"photo_{finding.pk}"
                resp  = request.POST.get(key_resp, InspectionFinding.RESP_NA)
                notes = request.POST.get(key_notes, "")
                photo = request.FILES.get(key_photo)
                finding.response = resp
                finding.notes    = notes
                if photo:
                    finding.photo = photo
                finding.save()

            _complete_inspection(inspection, request)

        messages.success(request, f"Inspection completed. Score: {inspection.score:.0f}%")
        return redirect("inspections:detail", pk)

    return render(request, "inspections/inspection_conduct.html", {
        "inspection":  inspection,
        "sections":    sections,
        "total_items": findings.count(),
        "RESP_PASS":   InspectionFinding.RESP_PASS,
        "RESP_FAIL":   InspectionFinding.RESP_FAIL,
        "RESP_NA":     InspectionFinding.RESP_NA,
    })


def _complete_inspection(inspection, request):
    """Calculate score, set completed status, auto-raise CAs for critical failures."""
    from django.utils.timezone import now
    from actions.models import CorrectiveAction

    findings = inspection.findings.all()
    pass_count = findings.filter(response=InspectionFinding.RESP_PASS).count()
    fail_count = findings.filter(response=InspectionFinding.RESP_FAIL).count()
    total      = pass_count + fail_count
    score      = round((pass_count / total) * 100, 1) if total else None

    inspection.score          = score
    inspection.status         = Inspection.STATUS_COMPLETED
    inspection.conducted_date = now().date()
    inspection.save(update_fields=["score", "status", "conducted_date"])

    # Auto-raise CA for every critical item that failed
    critical_fails = findings.filter(
        response=InspectionFinding.RESP_FAIL,
        template_item__is_critical=True,
        raised_action__isnull=True,
    ).select_related("template_item")

    for finding in critical_fails:
        ca = CorrectiveAction.objects.create(
            organization  = inspection.organization,
            title         = f"[Inspection] Critical failure: {finding.template_item.question}",
            description   = (
                f'Critical item failed during inspection "{inspection.title}".\n'
                f"Inspector: {inspection.inspector}\n"
                f"Notes: {finding.notes or '—'}"
            ),
            source_module = CorrectiveAction.SOURCE_INSPECTION,
            priority      = CorrectiveAction.PRIORITY_HIGH,
            assigned_to   = inspection.inspector,
            raised_by     = request.user,
        )
        finding.raised_action = ca
        finding.save(update_fields=["raised_action"])


# ── Stats ─────────────────────────────────────────────────────────────────────

@login_required
def inspection_stats(request):
    org = _org(request)
    _manager_required(request)

    import pandas as pd
    import plotly.express as px
    import plotly.io as pio
    from django.db.models import Avg, Count

    completed = Inspection.objects.filter(
        organization=org, status=Inspection.STATUS_COMPLETED, score__isnull=False
    ).select_related("template", "inspector").order_by("conducted_date")

    # ── Score trend ──
    if completed.exists():
        score_df = pd.DataFrame([
            {"Date": i.conducted_date.strftime("%Y-%m-%d"),
             "Score": i.score,
             "Title": i.title}
            for i in completed
        ])
        score_fig = px.line(
            score_df, x="Date", y="Score", markers=True,
            title="Inspection Score Trend",
            hover_data=["Title"],
            labels={"Score": "Score (%)"},
        )
        score_fig.update_layout(
            yaxis=dict(range=[0, 105], gridcolor="#f1f5f9"),
            xaxis=dict(showgrid=False),
            plot_bgcolor="white", paper_bgcolor="white",
            margin=dict(t=50, b=40, l=40, r=20),
        )
        score_fig.add_hline(y=90, line_dash="dot", line_color="#16a34a",
                            annotation_text="Target 90%", annotation_position="bottom right")
        score_fig.add_hline(y=70, line_dash="dot", line_color="#f59e0b",
                            annotation_text="Min 70%", annotation_position="bottom right")
        score_fig.update_layout(modebar_add=["toImage"])
        score_plot = pio.to_html(score_fig, full_html=False)
    else:
        score_plot = ""

    # ── Pass / fail donut ──
    all_findings = InspectionFinding.objects.filter(inspection__organization=org)
    pass_c = all_findings.filter(response=InspectionFinding.RESP_PASS).count()
    fail_c = all_findings.filter(response=InspectionFinding.RESP_FAIL).count()
    na_c   = all_findings.filter(response=InspectionFinding.RESP_NA).count()

    if pass_c + fail_c + na_c > 0:
        pf_fig = px.pie(
            names=["Pass", "Fail", "N/A"],
            values=[pass_c, fail_c, na_c],
            title="Overall Pass / Fail / N/A",
            hole=0.52,
            color_discrete_map={"Pass": "#16a34a", "Fail": "#dc2626", "N/A": "#94a3b8"},
        )
        pf_fig.update_traces(textinfo="label+percent")
        pf_fig.update_layout(showlegend=False, paper_bgcolor="white",
                             margin=dict(t=50, b=20, l=20, r=20))
        pf_fig.update_layout(modebar_add=["toImage"])
        pf_plot = pio.to_html(pf_fig, full_html=False)
    else:
        pf_plot = ""

    # ── Inspector performance ──
    insp_qs2 = (
        completed
        .values("inspector__full_name")
        .annotate(count=Count("id"), avg_score=Avg("score"))
        .order_by("-avg_score")
    )
    if insp_qs2:
        insp_df = pd.DataFrame([
            {
                "Inspector": r["inspector__full_name"] or "—",
                "Inspections": r["count"],
                "Avg Score": round(r["avg_score"], 1),
            }
            for r in insp_qs2
        ])
        insp_fig = px.bar(
            insp_df, x="Inspector", y="Avg Score",
            title="Average Score by Inspector",
            text="Avg Score",
            color="Avg Score",
            color_continuous_scale=["#fecaca", "#16a34a"],
            range_color=[0, 100],
        )
        insp_fig.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
        insp_fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            coloraxis_showscale=False,
            yaxis=dict(range=[0, 110], gridcolor="#f1f5f9"),
            xaxis=dict(showgrid=False),
            margin=dict(t=50, b=40, l=40, r=20),
        )
        insp_fig.update_layout(modebar_add=["toImage"])
        insp_plot = pio.to_html(insp_fig, full_html=False)
    else:
        insp_plot = ""

    # ── Template usage ──
    tmpl_qs = (
        Inspection.objects.filter(organization=org)
        .values("template__title")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    if tmpl_qs:
        tmpl_df = pd.DataFrame([{"Template": r["template__title"], "Count": r["count"]} for r in tmpl_qs])
        tmpl_fig = px.bar(
            tmpl_df.sort_values("Count"), x="Count", y="Template", orientation="h",
            title="Inspections by Template",
            color="Count",
            color_continuous_scale=["#dbeafe", "#1d4ed8"],
        )
        tmpl_fig.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            coloraxis_showscale=False,
            yaxis=dict(automargin=True),
            xaxis=dict(gridcolor="#f1f5f9", dtick=1),
            margin=dict(t=50, b=40, l=10, r=40),
        )
        tmpl_fig.update_traces(texttemplate="%{x}", textposition="outside")
        tmpl_fig.update_layout(modebar_add=["toImage"])
        tmpl_plot = pio.to_html(tmpl_fig, full_html=False)
    else:
        tmpl_plot = ""

    # KPIs
    total   = Inspection.objects.filter(organization=org).count()
    done    = completed.count()
    overdue = Inspection.objects.filter(
        organization=org, status=Inspection.STATUS_OVERDUE
    ).count()
    avg_score = completed.aggregate(a=Avg("score"))["a"]

    return render(request, "inspections/stats.html", {
        "total":       total,
        "completed":   done,
        "overdue":     overdue,
        "avg_score":   round(avg_score, 1) if avg_score else None,
        "score_plot":  score_plot,
        "pf_plot":     pf_plot,
        "insp_plot":   insp_plot,
        "tmpl_plot":   tmpl_plot,
    })


# ── Inspection PDF ────────────────────────────────────────────────────────────

@login_required
def inspection_pdf(request, pk):
    org        = _org(request)
    inspection = get_object_or_404(Inspection, pk=pk, organization=org)
    from .pdf import generate_inspection_pdf
    return generate_inspection_pdf(inspection, org)
