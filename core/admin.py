from django.contrib import admin
from django.utils import timezone
from .models import Organization, Subscription, DemoRequest, FreePlanRequest, ContractorInvite
from users.models import CustomUser


@admin.register(DemoRequest)
class DemoRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email", "whatsapp_number", "created_at", "message")
    search_fields = ("full_name", "email", "company")


def approve_requests(modeladmin, request, queryset):
    queryset.update(status="approved", reviewed_at=timezone.now())
approve_requests.short_description = "Approve selected requests"


def reject_requests(modeladmin, request, queryset):
    queryset.update(status="rejected", reviewed_at=timezone.now())
reject_requests.short_description = "Reject selected requests"


@admin.register(FreePlanRequest)
class FreePlanRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email", "whatsapp_number", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("full_name", "email", "company")
    actions = [approve_requests, reject_requests]


# ---------- INLINE USERS ----------
class UserInline(admin.TabularInline):
    model = CustomUser
    extra = 0
    fields = ("email", "is_manager")
    readonly_fields = ("email",)
    show_change_link = True


# ---------- ORGANIZATION ADMIN ----------
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "domain")
    search_fields = ("name", "domain")

    # ⭐ This enables inline users
    inlines = [UserInline]


# # Optional (recommended)
# @admin.register(Plan)
# class PlanAdmin(admin.ModelAdmin):
#     list_display = ("name", "max_users", "max_observations")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    # list_display = ("organization", "plan", "start_date", "end_date")
    list_display = ("organization", "plan")


@admin.register(ContractorInvite)
class ContractorInviteAdmin(admin.ModelAdmin):
    list_display = ("email", "organization", "is_used", "access_validity_days", "created_at", "expires_at")
    list_filter = ("is_used", "organization")
    search_fields = ("email",)
