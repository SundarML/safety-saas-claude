from django.contrib import admin
from .models import Organization, Subscription
from users.models import CustomUser

# Register your models here.
from django.contrib import admin
from .models import DemoRequest

@admin.register(DemoRequest)
class DemoRequestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "email","whatsapp_number", "created_at", "message")
    search_fields = ("full_name", "email", "company")


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
