from django.contrib import admin
from django.utils import timezone
from .models import Organization, Plan, Subscription, DemoRequest, FreePlanRequest, ContractorInvite
from users.models import CustomUser


# ---------------------------------------------------------------------------
# Demo Request
# ---------------------------------------------------------------------------

def mark_contacted(modeladmin, request, queryset):
    queryset.update(status="contacted")
mark_contacted.short_description = "Mark as Contacted"

def mark_scheduled(modeladmin, request, queryset):
    queryset.update(status="scheduled")
mark_scheduled.short_description = "Mark as Demo Scheduled"

def mark_done(modeladmin, request, queryset):
    queryset.update(status="done")
mark_done.short_description = "Mark as Done"

def mark_dropped(modeladmin, request, queryset):
    queryset.update(status="dropped")
mark_dropped.short_description = "Mark as Dropped"


@admin.register(DemoRequest)
class DemoRequestAdmin(admin.ModelAdmin):
    list_display  = ("full_name", "company", "job_title", "email", "whatsapp_number", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("full_name", "email", "company")
    ordering      = ("-created_at",)
    date_hierarchy = "created_at"
    actions       = [mark_contacted, mark_scheduled, mark_done, mark_dropped]
    readonly_fields = ("created_at", "updated_at")
    fields        = (
        "full_name", "company", "job_title", "email", "whatsapp_number",
        "message", "status", "notes", "created_at", "updated_at",
    )


# ---------------------------------------------------------------------------
# Free Plan Request
# ---------------------------------------------------------------------------

def approve_requests(modeladmin, request, queryset):
    queryset.update(status="approved", reviewed_at=timezone.now())
approve_requests.short_description = "Approve selected requests"

def reject_requests(modeladmin, request, queryset):
    queryset.update(status="rejected", reviewed_at=timezone.now())
reject_requests.short_description = "Reject selected requests"


@admin.register(FreePlanRequest)
class FreePlanRequestAdmin(admin.ModelAdmin):
    list_display  = ("full_name", "company", "job_title", "email", "whatsapp_number", "status", "created_at")
    list_filter   = ("status",)
    search_fields = ("full_name", "email", "company")
    ordering      = ("-created_at",)
    date_hierarchy = "created_at"
    actions       = [approve_requests, reject_requests]
    readonly_fields = ("created_at", "reviewed_at")


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class UserInline(admin.TabularInline):
    model = CustomUser
    extra = 0
    fields = ("email", "is_manager")
    readonly_fields = ("email",)
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display  = ("name", "domain")
    search_fields = ("name", "domain")
    inlines       = [UserInline]


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display  = ("name", "price_monthly", "max_users", "max_observations", "active")
    list_filter   = ("active",)
    search_fields = ("name",)
    fields        = ("name", "price_monthly", "max_users", "max_observations", "razorpay_plan_id", "active")


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

def _expires(obj):
    if obj.expires_at:
        return obj.expires_at.strftime("%Y-%m-%d")
    return "—"
_expires.short_description = "Expires"

def _trial(obj):
    return "Yes" if obj.is_trial() else "No"
_trial.short_description = "Trial?"


def extend_30_days(modeladmin, request, queryset):
    for sub in queryset:
        base = sub.expires_at if sub.expires_at and sub.expires_at > timezone.now() else timezone.now()
        sub.expires_at = base + timezone.timedelta(days=30)
        sub.is_active = True
        sub.save()
extend_30_days.short_description = "Extend expiry by 30 days"

def extend_365_days(modeladmin, request, queryset):
    for sub in queryset:
        base = sub.expires_at if sub.expires_at and sub.expires_at > timezone.now() else timezone.now()
        sub.expires_at = base + timezone.timedelta(days=365)
        sub.is_active = True
        sub.save()
extend_365_days.short_description = "Extend expiry by 1 year"

def deactivate_sub(modeladmin, request, queryset):
    queryset.update(is_active=False)
deactivate_sub.short_description = "Deactivate selected subscriptions"

def activate_sub(modeladmin, request, queryset):
    queryset.update(is_active=True)
activate_sub.short_description = "Activate selected subscriptions"


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display  = ("organization", "plan", _trial, "is_active", _expires, "updated_at")
    list_filter   = ("is_active", "plan")
    search_fields = ("organization__name",)
    ordering      = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "started_at")
    fields        = (
        "organization",
        "plan",
        "is_active",
        "expires_at",
        "started_at",
        "created_at",
        "updated_at",
        "stripe_customer_id",
        "stripe_subscription_id",
        "razorpay_customer_id",
        "razorpay_subscription_id",
    )
    actions = [extend_30_days, extend_365_days, activate_sub, deactivate_sub]


# ---------------------------------------------------------------------------
# Contractor Invite
# ---------------------------------------------------------------------------

@admin.register(ContractorInvite)
class ContractorInviteAdmin(admin.ModelAdmin):
    list_display  = ("email", "organization", "is_used", "access_validity_days", "created_at", "expires_at")
    list_filter   = ("is_used", "organization")
    search_fields = ("email",)
