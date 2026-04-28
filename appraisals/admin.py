from django.contrib import admin
from .models import (
    AppraisalCycle, AppraisalCategory, AppraisalRecord,
    AppraisalItem, AppraisalRating, CalibrateNote, DevPlanLink,
)


class AppraisalCategoryInline(admin.TabularInline):
    model = AppraisalCategory
    extra = 0


@admin.register(AppraisalCycle)
class AppraisalCycleAdmin(admin.ModelAdmin):
    list_display  = ["name", "organization", "period", "status", "created_by", "created_at"]
    list_filter   = ["status", "period", "organization"]
    search_fields = ["name"]
    inlines       = [AppraisalCategoryInline]


@admin.register(AppraisalRecord)
class AppraisalRecordAdmin(admin.ModelAdmin):
    list_display  = ["employee", "cycle", "reviewer", "status", "overall_score", "overall_rating"]
    list_filter   = ["status", "overall_rating", "cycle__organization"]
    search_fields = ["employee__full_name", "cycle__name"]


@admin.register(AppraisalItem)
class AppraisalItemAdmin(admin.ModelAdmin):
    list_display  = ["title", "record", "category", "goal_type", "approved_by_manager", "weight"]
    list_filter   = ["goal_type", "approved_by_manager", "item_type"]
    search_fields = ["title"]


@admin.register(AppraisalRating)
class AppraisalRatingAdmin(admin.ModelAdmin):
    list_display = ["item", "record", "self_rating", "manager_rating", "actual_value"]


@admin.register(CalibrateNote)
class CalibrateNoteAdmin(admin.ModelAdmin):
    list_display  = ["record", "calibrated_by", "old_score", "new_score", "created_at"]
    list_filter   = ["record__cycle__organization"]
    search_fields = ["record__employee__full_name", "note"]


@admin.register(DevPlanLink)
class DevPlanLinkAdmin(admin.ModelAdmin):
    list_display  = ["record", "training_module", "created_by", "created_at"]
    search_fields = ["record__employee__full_name", "training_module__title"]
