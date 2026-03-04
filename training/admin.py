from django.contrib import admin
from .models import (
    SkillCategory, Skill, SkillProficiency,
    TrainingModule, Assessment, Question, Choice, AssessmentAttempt,
)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    fields = ["text", "is_correct"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    inlines = [ChoiceInline]
    list_display = ["assessment", "order", "text"]
    list_select_related = ["assessment"]
    ordering = ["assessment", "order"]


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    show_change_link = True
    fields = ["order", "text"]


class AssessmentInline(admin.StackedInline):
    model = Assessment
    extra = 0
    show_change_link = True
    fields = ["title", "passing_score", "skill", "grants_proficiency_level"]


@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "description"]
    list_filter = ["organization"]
    search_fields = ["name"]


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "organization"]
    list_filter = ["organization", "category"]
    search_fields = ["name"]


@admin.register(SkillProficiency)
class SkillProficiencyAdmin(admin.ModelAdmin):
    list_display = ["user", "skill", "level", "last_assessed_at", "organization"]
    list_filter = ["organization", "skill", "level"]
    list_select_related = ["user", "skill"]
    search_fields = ["user__email", "user__full_name", "skill__name"]


@admin.register(TrainingModule)
class TrainingModuleAdmin(admin.ModelAdmin):
    inlines = [AssessmentInline]
    list_display = ["title", "organization", "is_active", "created_at"]
    list_filter = ["organization", "is_active"]
    search_fields = ["title"]


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = ["title", "training_module", "passing_score", "skill", "grants_proficiency_level"]
    list_select_related = ["training_module", "skill"]


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "assessment", "score", "passed", "submitted_at"]
    list_filter = ["organization", "passed"]
    list_select_related = ["user", "assessment"]
    search_fields = ["user__email", "user__full_name"]
    readonly_fields = ["answers"]
