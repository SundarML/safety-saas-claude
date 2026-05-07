import csv
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AssessmentForm, TrainingModuleForm
from .models import (
    Assessment,
    AssessmentAttempt,
    Choice,
    Question,
    Skill,
    SkillCategory,
    SkillProficiency,
    TrainingModule,
)
from .services import handle_assessment_submission


# ── Helpers ──────────────────────────────────────────────────────────────────

def _org_required(request):
    if not request.organization:
        raise PermissionDenied("You are not associated with any organisation.")


def _manager_required(request):
    _org_required(request)
    if not (request.user.is_manager or request.user.is_safety_manager):
        raise PermissionDenied("Only Managers and Safety Managers can perform this action.")


# ── Training Module views ─────────────────────────────────────────────────────

@login_required
def module_list(request):
    _org_required(request)
    qs = (
        TrainingModule.objects
        .filter(organization=request.organization, is_active=True)
        .prefetch_related("skills")
        .select_related("created_by")
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "training/module_list.html", {"page_obj": page_obj, "q": q})


@login_required
def module_create(request):
    _manager_required(request)
    org = request.organization

    if request.method == "POST":
        form = TrainingModuleForm(request.POST)
        form.fields["skills"].queryset = Skill.objects.filter(organization=org)
        if form.is_valid():
            module = form.save(commit=False)
            module.organization = org
            module.created_by = request.user
            module.save()
            form.save_m2m()
            messages.success(request, f"Module '{module.title}' created successfully.")
            return redirect("training:module_detail", pk=module.pk)
    else:
        form = TrainingModuleForm()
        form.fields["skills"].queryset = Skill.objects.filter(organization=org)

    return render(request, "training/module_form.html", {"form": form, "action": "Create"})


@login_required
def module_edit(request, pk):
    _manager_required(request)
    org = request.organization
    module = get_object_or_404(TrainingModule, pk=pk, organization=org)

    if request.method == "POST":
        form = TrainingModuleForm(request.POST, instance=module)
        form.fields["skills"].queryset = Skill.objects.filter(organization=org)
        if form.is_valid():
            form.save()
            messages.success(request, f"Module '{module.title}' updated.")
            return redirect("training:module_detail", pk=module.pk)
    else:
        form = TrainingModuleForm(instance=module)
        form.fields["skills"].queryset = Skill.objects.filter(organization=org)

    return render(request, "training/module_form.html", {
        "form": form,
        "action": "Edit",
        "module": module,
    })


@login_required
def module_delete(request, pk):
    _manager_required(request)
    module = get_object_or_404(TrainingModule, pk=pk, organization=request.organization)

    if request.method == "POST":
        title = module.title
        module.delete()
        messages.success(request, f"Module '{title}' deleted.")
        return redirect("training:module_list")

    return redirect("training:module_detail", pk=pk)


@login_required
def module_detail(request, pk):
    _org_required(request)
    module = get_object_or_404(TrainingModule, pk=pk, organization=request.organization)
    assessment = getattr(module, "assessment", None)

    recent_attempts = []
    user_last_attempt = None

    if assessment:
        can_see_all = request.user.is_manager or request.user.is_safety_manager
        attempts_qs = assessment.attempts.filter(organization=request.organization)
        if not can_see_all:
            attempts_qs = attempts_qs.filter(user=request.user)
        recent_attempts = (
            attempts_qs
            .select_related("user")
            .order_by("-submitted_at")[:10]
        )
        user_last_attempt = (
            assessment.attempts
            .filter(user=request.user)
            .order_by("-submitted_at")
            .first()
        )

    can_manage = request.user.is_manager or request.user.is_safety_manager
    return render(request, "training/module_detail.html", {
        "module": module,
        "assessment": assessment,
        "recent_attempts": recent_attempts,
        "user_last_attempt": user_last_attempt,
        "can_manage": can_manage,
    })


# ── Assessment views ───────────────────────────────────────────────────────────

@login_required
def assessment_create(request, module_pk):
    _manager_required(request)
    module = get_object_or_404(TrainingModule, pk=module_pk, organization=request.organization)

    if hasattr(module, "assessment"):
        messages.warning(request, "This module already has an assessment. Edit it from the module page.")
        return redirect("training:module_detail", pk=module.pk)

    org = request.organization
    if request.method == "POST":
        form = AssessmentForm(request.POST)
        form.fields["skill"].queryset = Skill.objects.filter(organization=org)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.organization = org
            assessment.training_module = module
            assessment.save()
            messages.success(request, "Assessment created. Now add your questions below.")
            return redirect("training:edit_questions", pk=assessment.pk)
    else:
        form = AssessmentForm()
        form.fields["skill"].queryset = Skill.objects.filter(organization=org)

    return render(request, "training/assessment_form.html", {
        "form": form,
        "module": module,
        "action": "Create",
    })


# ── Assessment Edit ───────────────────────────────────────────────────────────

@login_required
def assessment_edit(request, pk):
    _manager_required(request)
    assessment = get_object_or_404(Assessment, pk=pk, organization=request.organization)
    org = request.organization

    if request.method == "POST":
        form = AssessmentForm(request.POST, instance=assessment)
        form.fields["skill"].queryset = Skill.objects.filter(organization=org)
        if form.is_valid():
            form.save()
            messages.success(request, "Assessment updated.")
            return redirect("training:module_detail", pk=assessment.training_module.pk)
    else:
        form = AssessmentForm(instance=assessment)
        form.fields["skill"].queryset = Skill.objects.filter(organization=org)

    return render(request, "training/assessment_form.html", {
        "form": form,
        "module": assessment.training_module,
        "action": "Edit",
    })


# ── Question Builder (the single-page JS-powered editor) ─────────────────────

@login_required
def edit_questions(request, pk):
    _manager_required(request)
    assessment = get_object_or_404(Assessment, pk=pk, organization=request.organization)

    QuestionFormSet = inlineformset_factory(
        Assessment,
        Question,
        fields=["text", "order"],
        extra=0,
        can_delete=True,
    )

    if request.method == "POST":
        q_formset = QuestionFormSet(request.POST, instance=assessment, prefix="questions")

        if q_formset.is_valid():
            with transaction.atomic():
                # First pass: save all questions (new, updated, deleted)
                q_formset.save()

                # Second pass: save choices for each surviving question
                for i, qform in enumerate(q_formset.forms):
                    if qform.cleaned_data.get("DELETE", False):
                        # Question (and its choices) are cascade-deleted — skip
                        continue

                    question = qform.instance
                    if not question.pk:
                        continue  # empty extra form that was skipped — skip

                    ChoiceFormSet = inlineformset_factory(
                        Question,
                        Choice,
                        fields=["text", "is_correct"],
                        extra=0,
                        can_delete=True,
                    )
                    c_formset = ChoiceFormSet(
                        request.POST,
                        instance=question,
                        prefix=f"q{i}_choices",
                    )
                    if c_formset.is_valid():
                        c_formset.save()
                    # Silently skip invalid choice formsets (missing management form
                    # means the POST data for that index was absent — harmless)

            messages.success(request, "Questions saved successfully.")
            return redirect("training:module_detail", pk=assessment.training_module.pk)

        messages.error(request, "Could not save — please check the question fields and try again.")
        # Re-redirect to GET so formset re-renders from DB (simplest safe fallback)
        return redirect("training:edit_questions", pk=pk)

    # ── GET: build (question form, choice formset, index) triples ─────────────
    q_formset = QuestionFormSet(instance=assessment, prefix="questions")

    question_choice_pairs = []
    for i, qform in enumerate(q_formset.forms):
        question = qform.instance
        ChoiceFormSet = inlineformset_factory(
            Question,
            Choice,
            fields=["text", "is_correct"],
            # Show 4 empty slots when a question has no choices yet
            extra=4 if not question.choices.exists() else 0,
            can_delete=True,
        )
        c_formset = ChoiceFormSet(instance=question, prefix=f"q{i}_choices")
        question_choice_pairs.append((qform, c_formset, i))

    return render(request, "training/edit_questions.html", {
        "assessment": assessment,
        "q_formset": q_formset,
        "question_choice_pairs": question_choice_pairs,
    })


# ── Take Assessment ───────────────────────────────────────────────────────────

@login_required
def take_assessment(request, pk):
    _org_required(request)
    assessment = get_object_or_404(Assessment, pk=pk, organization=request.organization)

    if assessment.question_count == 0:
        messages.warning(request, "This assessment has no questions yet.")
        return redirect("training:module_detail", pk=assessment.training_module.pk)

    if request.method == "POST":
        submitted_answers = {
            key.replace("question_", ""): value
            for key, value in request.POST.items()
            if key.startswith("question_")
        }
        try:
            attempt = handle_assessment_submission(
                user=request.user,
                assessment=assessment,
                submitted_answers=submitted_answers,
            )
            return redirect("training:attempt_result", pk=attempt.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("training:module_detail", pk=assessment.training_module.pk)

    questions = assessment.questions.prefetch_related("choices").all()
    return render(request, "training/take_assessment.html", {
        "assessment": assessment,
        "questions": questions,
    })


@login_required
def attempt_result(request, pk):
    _org_required(request)
    attempt = get_object_or_404(
        AssessmentAttempt,
        pk=pk,
        user=request.user,
        organization=request.organization,
    )
    return render(request, "training/attempt_result.html", {"attempt": attempt})


# ── Skill Matrix ──────────────────────────────────────────────────────────────

@login_required
def skill_matrix(request):
    _manager_required(request)
    proficiencies = (
        SkillProficiency.objects
        .filter(organization=request.organization)
        .select_related("user", "skill", "skill__category")
        .order_by("user__full_name", "skill__category__name", "skill__name")
    )
    return render(request, "training/skill_matrix.html", {
        "proficiencies": proficiencies,
        "level_labels": ["Beginner", "Basic", "Intermediate", "Advanced", "Expert"],
    })


# ── Dashboard ────────────────────────────────────────────────────────────────

LEVEL_LABELS = {1: "Beginner", 2: "Basic", 3: "Intermediate", 4: "Advanced", 5: "Expert"}
APP_COLORS   = ["#c7d2fe", "#a5b4fc", "#818cf8", "#6366f1", "#4338ca"]


def _empty_figure(message="No data yet"):
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=13, color="#adb5bd"),
    )
    fig.update_layout(
        xaxis_visible=False, yaxis_visible=False,
        plot_bgcolor="#f8f9fb", paper_bgcolor="#f8f9fb",
        margin=dict(l=20, r=20, t=40, b=20), height=300,
    )
    return fig


def _base_layout(fig, height=320):
    fig.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="system-ui, sans-serif", size=12),
        margin=dict(l=20, r=20, t=44, b=20),
        height=height,
        title_font=dict(size=14, color="#1a2c52"),
    )
    return fig


@login_required
def training_dashboard(request):
    _org_required(request)
    org = request.organization
    is_manager = request.user.is_manager or request.user.is_safety_manager

    if is_manager:
        # ── KPIs ─────────────────────────────────────────────────────────
        total_modules   = TrainingModule.objects.filter(organization=org, is_active=True).count()
        total_attempts  = AssessmentAttempt.objects.filter(organization=org).count()
        passed_attempts = AssessmentAttempt.objects.filter(organization=org, passed=True).count()
        overall_pass_rate = (
            round(passed_attempts / total_attempts * 100, 1) if total_attempts else 0
        )
        certified_users = (
            SkillProficiency.objects.filter(organization=org)
            .values("user").distinct().count()
        )

        # ── Chart 1: Pass rate per module (horizontal bar) ────────────────
        assessments = (
            Assessment.objects
            .filter(organization=org)
            .annotate(
                total=Count("attempts"),
                passed_count=Count("attempts", filter=Q(attempts__passed=True)),
            )
            .select_related("training_module")
        )
        rows = [
            {
                "Module": a.training_module.title[:35],
                "Pass Rate": round(a.passed_count / a.total * 100, 1),
                "Attempts": a.total,
            }
            for a in assessments if a.total > 0
        ]
        if rows:
            df = pd.DataFrame(rows).sort_values("Pass Rate")
            pass_rate_fig = px.bar(
                df, x="Pass Rate", y="Module", orientation="h",
                color="Pass Rate",
                color_continuous_scale=["#ef4444", "#f97316", "#22c55e"],
                text=df["Pass Rate"].apply(lambda v: f"{v}%"),
                title="Pass Rate by Module",
                hover_data={"Attempts": True},
            )
            pass_rate_fig.update_traces(textposition="outside")
            pass_rate_fig.update_layout(
                coloraxis_showscale=False, xaxis_range=[0, 115],
            )
            _base_layout(pass_rate_fig, height=max(300, len(rows) * 52 + 90))
        else:
            pass_rate_fig = _empty_figure("No assessment attempts yet")

        # ── Chart 2: Attempts over time (multi-line) ──────────────────────
        trend_qs = (
            AssessmentAttempt.objects.filter(organization=org)
            .annotate(period=TruncMonth("submitted_at"))
            .values("period")
            .annotate(
                total=Count("id"),
                passed=Count("id", filter=Q(passed=True)),
            )
            .order_by("period")
        )
        trend_rows = [r for r in trend_qs if r["period"]]
        if trend_rows:
            trend_df = pd.DataFrame({
                "Month":  [r["period"].strftime("%b %Y") for r in trend_rows],
                "Total":  [r["total"]  for r in trend_rows],
                "Passed": [r["passed"] for r in trend_rows],
                "Failed": [r["total"] - r["passed"] for r in trend_rows],
            })
            trend_fig = px.line(
                trend_df, x="Month", y=["Total", "Passed", "Failed"],
                markers=True,
                title="Assessment Attempts Over Time",
                labels={"value": "Attempts", "variable": ""},
                color_discrete_map={
                    "Total": "#6366f1", "Passed": "#22c55e", "Failed": "#ef4444"
                },
            )
            _base_layout(trend_fig)
        else:
            trend_fig = _empty_figure("No attempt data yet")

        # ── Chart 3: Proficiency level distribution (bar) ────────────────
        prof_qs = (
            SkillProficiency.objects.filter(organization=org)
            .values("level")
            .annotate(count=Count("id"))
            .order_by("level")
        )
        if prof_qs:
            prof_df = pd.DataFrame({
                "Level":     [f"L{r['level']} {LEVEL_LABELS[r['level']]}" for r in prof_qs],
                "Employees": [r["count"] for r in prof_qs],
            })
            prof_fig = px.bar(
                prof_df, x="Level", y="Employees",
                color="Level",
                color_discrete_sequence=APP_COLORS,
                text="Employees",
                title="Proficiency Level Distribution (Org-wide)",
            )
            prof_fig.update_traces(textposition="outside")
            prof_fig.update_layout(showlegend=False)
            _base_layout(prof_fig)
        else:
            prof_fig = _empty_figure("No proficiencies recorded yet")

        # ── Chart 4: Top performers — most skills certified ───────────────
        top_qs = list(
            SkillProficiency.objects.filter(organization=org)
            .values("user__full_name", "user__email")
            .annotate(skills=Count("skill"))
            .order_by("-skills")[:10]
        )
        if top_qs:
            top_df = pd.DataFrame({
                "Employee": [
                    r["user__full_name"] or r["user__email"].split("@")[0]
                    for r in top_qs
                ],
                "Skills Certified": [r["skills"] for r in top_qs],
            }).sort_values("Skills Certified")
            top_fig = px.bar(
                top_df, x="Skills Certified", y="Employee", orientation="h",
                color="Skills Certified",
                color_continuous_scale=APP_COLORS,
                text="Skills Certified",
                title="Top Performers — Skills Certified",
            )
            top_fig.update_traces(textposition="outside")
            top_fig.update_layout(
                coloraxis_showscale=False,
                xaxis_range=[0, top_df["Skills Certified"].max() + 1.5],
            )
            _base_layout(top_fig, height=max(300, len(top_qs) * 48 + 90))
        else:
            top_fig = _empty_figure("No data yet")

        context = {
            "is_manager":       True,
            "total_modules":    total_modules,
            "total_attempts":   total_attempts,
            "overall_pass_rate": overall_pass_rate,
            "certified_users":  certified_users,
            "pass_rate_plot":   pio.to_html(pass_rate_fig, full_html=False),
            "trend_plot":       pio.to_html(trend_fig,     full_html=False),
            "prof_plot":        pio.to_html(prof_fig,      full_html=False),
            "top_plot":         pio.to_html(top_fig,       full_html=False),
        }

    else:
        # ── KPIs (personal) ───────────────────────────────────────────────
        my_attempts  = AssessmentAttempt.objects.filter(organization=org, user=request.user)
        total_attempted = my_attempts.count()
        total_passed    = my_attempts.filter(passed=True).count()
        my_skills       = SkillProficiency.objects.filter(organization=org, user=request.user).count()
        avg_score_raw   = my_attempts.aggregate(avg=Avg("score"))["avg"]
        avg_score       = round(avg_score_raw, 1) if avg_score_raw else 0

        # ── Chart 1: My skill proficiency levels ──────────────────────────
        my_profs = list(
            SkillProficiency.objects
            .filter(organization=org, user=request.user)
            .select_related("skill")
            .order_by("level")
        )
        if my_profs:
            skill_fig = px.bar(
                x=[p.level for p in my_profs],
                y=[p.skill.name for p in my_profs],
                orientation="h",
                color=[p.level for p in my_profs],
                color_continuous_scale=APP_COLORS,
                text=[f"L{p.level} – {LEVEL_LABELS[p.level]}" for p in my_profs],
                title="My Skill Proficiency Levels",
                labels={"x": "Level (1–5)", "y": "Skill", "color": "Level"},
            )
            skill_fig.update_traces(textposition="outside")
            skill_fig.update_layout(
                coloraxis_showscale=False,
                xaxis=dict(range=[0, 6.5], tickvals=[1, 2, 3, 4, 5]),
            )
            _base_layout(skill_fig, height=max(300, len(my_profs) * 52 + 90))
        else:
            skill_fig = _empty_figure("No skills certified yet — pass an assessment to earn one!")

        # ── Chart 2: My score history (scatter) ───────────────────────────
        history = list(my_attempts.select_related("assessment").order_by("submitted_at")[:30])
        if history:
            hist_fig = px.scatter(
                x=[a.submitted_at.strftime("%d %b %Y") for a in history],
                y=[a.score for a in history],
                color=["Pass" if a.passed else "Fail" for a in history],
                hover_name=[a.assessment.title for a in history],
                title="My Assessment Score History",
                labels={"x": "Date", "y": "Score (%)", "color": "Result"},
                color_discrete_map={"Pass": "#22c55e", "Fail": "#ef4444"},
            )
            hist_fig.add_hline(
                y=70, line_dash="dash", line_color="#94a3b8",
                annotation_text="Typical pass mark (70%)",
                annotation_position="bottom right",
            )
            hist_fig.update_traces(marker=dict(size=11))
            hist_fig.update_layout(yaxis=dict(range=[0, 105]))
            _base_layout(hist_fig)
        else:
            hist_fig = _empty_figure("No attempts yet — take an assessment to see your scores!")

        context = {
            "is_manager":      False,
            "total_attempted": total_attempted,
            "total_passed":    total_passed,
            "my_skills":       my_skills,
            "avg_score":       avg_score,
            "skill_plot":      pio.to_html(skill_fig, full_html=False),
            "hist_plot":       pio.to_html(hist_fig,  full_html=False),
            "recent_attempts": my_attempts.select_related("assessment").order_by("-submitted_at")[:8],
        }

    return render(request, "training/dashboard.html", context)


# ── Skills & Categories management ───────────────────────────────────────────

@login_required
def manage_skills(request):
    _manager_required(request)
    org = request.organization

    categories = (
        SkillCategory.objects
        .filter(organization=org)
        .annotate(skill_count=Count("skills"))
        .order_by("name")
    )
    skills = (
        Skill.objects
        .filter(organization=org)
        .select_related("category")
        .order_by("category__name", "name")
    )
    return render(request, "training/manage_skills.html", {
        "categories": categories,
        "skills": skills,
    })


@login_required
def category_create(request):
    _manager_required(request)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        if name:
            SkillCategory.objects.get_or_create(
                organization=request.organization,
                name=name,
                defaults={"description": description},
            )
            messages.success(request, f"Category '{name}' added.")
        else:
            messages.error(request, "Category name is required.")
    return redirect("training:manage_skills")


@login_required
def category_delete(request, pk):
    _manager_required(request)
    if request.method == "POST":
        category = get_object_or_404(SkillCategory, pk=pk, organization=request.organization)
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
    return redirect("training:manage_skills")


@login_required
def skill_create(request):
    _manager_required(request)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        category_id = request.POST.get("category") or None
        if name:
            category = None
            if category_id:
                category = SkillCategory.objects.filter(
                    pk=category_id, organization=request.organization
                ).first()
            Skill.objects.get_or_create(
                organization=request.organization,
                name=name,
                defaults={"description": description, "category": category},
            )
            messages.success(request, f"Skill '{name}' added.")
        else:
            messages.error(request, "Skill name is required.")
    return redirect("training:manage_skills")


@login_required
def skill_delete(request, pk):
    _manager_required(request)
    if request.method == "POST":
        skill = get_object_or_404(Skill, pk=pk, organization=request.organization)
        name = skill.name
        skill.delete()
        messages.success(request, f"Skill '{name}' deleted.")
    return redirect("training:manage_skills")


# ── Reports ───────────────────────────────────────────────────────────────────

@login_required
def report_skills_csv(request):
    _manager_required(request)
    org = request.organization

    proficiencies = (
        SkillProficiency.objects
        .filter(organization=org)
        .select_related("user", "skill", "skill__category")
        .order_by("user__full_name", "skill__name")
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="skill_matrix.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Employee Name", "Employee ID", "Email", "Role",
        "Skill Category", "Skill", "Proficiency Level", "Level Label", "Last Assessed",
    ])

    level_labels = {
        1: "Beginner", 2: "Basic", 3: "Intermediate", 4: "Advanced", 5: "Expert",
    }

    for prof in proficiencies:
        writer.writerow([
            prof.user.full_name or prof.user.email,
            prof.user.employee_id or "",
            prof.user.email,
            prof.user.get_role_display(),
            prof.skill.category.name if prof.skill.category else "—",
            prof.skill.name,
            prof.level,
            level_labels.get(prof.level, "—"),
            prof.last_assessed_at.strftime("%d %b %Y") if prof.last_assessed_at else "—",
        ])

    return response


@login_required
def report_effectiveness_pdf(request):
    _manager_required(request)
    org = request.organization

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    modules = (
        TrainingModule.objects
        .filter(organization=org)
        .select_related("assessment", "assessment__skill")
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Heading1"],
        fontSize=18, spaceAfter=4,
        textColor=colors.HexColor("#1a2c52"),
    )
    sub_style = ParagraphStyle(
        "Sub", parent=styles["Normal"],
        fontSize=10, textColor=colors.HexColor("#6c757d"), spaceAfter=12,
    )

    from core.logo_utils import get_logo_for_pdf as _get_logo
    from reportlab.platypus import Table as _Table, TableStyle as _TS

    logo_img = _get_logo(org, max_width_pt=5 * cm, max_height_pt=1.4 * cm)

    if logo_img:
        # Place logo left, title right on the same row
        hdr_data = [[
            logo_img,
            [
                Paragraph("Training Effectiveness Report", title_style),
                Paragraph(f"Organisation: {org.name}", sub_style),
            ],
        ]]
        page_content_w = (A4[0] - 4 * cm)   # A4 width minus margins
        hdr_table = _Table(
            hdr_data,
            colWidths=[logo_img.drawWidth + 0.5 * cm, page_content_w - logo_img.drawWidth - 0.5 * cm],
        )
        hdr_table.setStyle(_TS([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story = [hdr_table, Spacer(1, 0.4 * cm)]
    else:
        story = [
            Paragraph("Training Effectiveness Report", title_style),
            Paragraph(f"Organisation: {org.name}", sub_style),
            Spacer(1, 0.3 * cm),
        ]

    header = ["Training Module", "Assessment", "Attempts", "Pass Rate", "Avg Score", "Skill Certified"]
    data = [header]

    for module in modules:
        assessment = getattr(module, "assessment", None)
        if not assessment:
            data.append([module.title, "—", "—", "—", "—", "—"])
            continue

        agg = assessment.attempts.filter(organization=org).aggregate(
            total=Count("id"),
            passed=Count("id", filter=Q(passed=True)),
            avg_score=Avg("score"),
        )
        total = agg["total"] or 0
        if total == 0:
            pass_rate, avg_str = "—", "—"
        else:
            pass_rate = f"{round((agg['passed'] / total) * 100, 1)}%"
            avg_str = f"{round(agg['avg_score'], 1)}%" if agg["avg_score"] else "—"

        data.append([
            module.title,
            assessment.title,
            str(total),
            pass_rate,
            avg_str,
            assessment.skill.name if assessment.skill else "—",
        ])

    table = Table(data, repeatRows=1, colWidths=[5.5 * cm, 5 * cm, 2 * cm, 2.5 * cm, 2.5 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2c52")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fb")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(table)

    # ── Section 2: Employee Skill Proficiencies (with Employee IDs) ──────────
    section_style = ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"],
        fontSize=13, spaceBefore=18, spaceAfter=6,
        textColor=colors.HexColor("#1a2c52"),
    )
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Employee Skill Proficiencies", section_style))

    proficiencies = (
        SkillProficiency.objects
        .filter(organization=org)
        .select_related("user", "skill", "skill__category")
        .order_by("user__full_name", "skill__name")
    )

    level_labels = {1: "Beginner", 2: "Basic", 3: "Intermediate", 4: "Advanced", 5: "Expert"}

    prof_header = ["Employee", "Employee ID", "Skill", "Level", "Last Assessed"]
    prof_data = [prof_header]
    for p in proficiencies:
        prof_data.append([
            p.user.full_name or p.user.email,
            p.user.employee_id or "—",
            p.skill.name,
            level_labels.get(p.level, str(p.level)),
            p.last_assessed_at.strftime("%d %b %Y") if p.last_assessed_at else "—",
        ])

    if len(prof_data) > 1:
        prof_table = Table(
            prof_data, repeatRows=1,
            colWidths=[5 * cm, 3 * cm, 5 * cm, 3 * cm, 3.5 * cm],
        )
        prof_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2c52")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (3, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 0), (2, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fb")]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.append(prof_table)
    else:
        story.append(Paragraph("No skill proficiencies recorded yet.", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="training_effectiveness.pdf"'
    return response
