from django.contrib import admin
from .models import ComplianceItem


@admin.register(ComplianceItem)
class ComplianceItemAdmin(admin.ModelAdmin):
    list_display  = ("title", "organization", "law", "frequency", "due_date", "status", "assigned_to")
    list_filter   = ("status", "frequency", "organization")
    search_fields = ("title", "law", "authority")
    ordering      = ("due_date",)
    date_hierarchy = "due_date"
