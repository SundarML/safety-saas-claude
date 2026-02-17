# permits/admin.py
from django.contrib import admin
from .models import Permit


@admin.register(Permit)
class PermitAdmin(admin.ModelAdmin):
    list_display  = [
        "permit_number", "work_type", "title", "organization",
        "requestor", "status", "planned_start", "planned_end",
    ]
    list_filter   = ["status", "work_type", "organization"]
    search_fields = ["permit_number", "title", "requestor__email", "contractor_name"]
    readonly_fields = [
        "permit_number", "created_at", "updated_at",
        "approved_at", "closed_at",
    ]
    fieldsets = [
        ("Identification", {
            "fields": ["permit_number", "organization", "work_type", "title", "status"],
        }),
        ("Work Details", {
            "fields": ["description", "location", "work_area",
                       "contractor_name", "contractor_contact", "workers_count"],
        }),
        ("People", {
            "fields": ["requestor", "approved_by", "closed_by"],
        }),
        ("Schedule", {
            "fields": ["planned_start", "planned_end", "actual_start", "actual_end"],
        }),
        ("Risk & Controls", {
            "fields": ["hazards_identified", "risk_controls", "ppe_required",
                       "isolation_required", "isolation_details", "emergency_procedure"],
        }),
        ("Pre-work Checklist", {
            "fields": ["toolbox_talk_done", "area_barricaded", "equipment_inspected",
                       "gas_test_done", "gas_test_result"],
        }),
        ("Approval / Rejection", {
            "fields": ["approval_comment", "rejection_reason", "approved_at"],
        }),
        ("Closure", {
            "fields": ["closure_comment", "site_restored", "closed_at"],
        }),
        ("Attachment", {"fields": ["attachment"]}),
        ("Audit", {"fields": ["created_at", "updated_at"]}),
    ]
