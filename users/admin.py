# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    ordering = ("email",)

    list_display = (
        "email",
        "full_name",
        "organization",
        "is_manager",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "is_manager",
        "is_active",
        "is_staff",
        "is_superuser",
        "organization",
    )

    search_fields = ("email", "full_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Info", {"fields": ("full_name",)}),
        ("Organization", {"fields": ("organization",)}),
        (
            "Roles",
            {
                "fields": (
                    "is_manager",
                    "is_observer",
                    "is_action_owner",
                    "is_safety_manager",
                )
            },
        ),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "password1",
                    "password2",
                    "organization",
                    "is_manager",
                ),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")
