# permits/forms.py
from django import forms
from django.utils import timezone

from .models import Permit


DATE_WIDGET = forms.DateTimeInput(
    attrs={"type": "datetime-local", "class": "form-control"},
    format="%Y-%m-%dT%H:%M",
)


class PermitRequestForm(forms.ModelForm):
    """Used by requestors to create or edit a DRAFT permit."""

    planned_start = forms.DateTimeField(
        widget=DATE_WIDGET,
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    planned_end = forms.DateTimeField(
        widget=DATE_WIDGET,
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    class Meta:
        model  = Permit
        fields = [
            "work_type",
            "title",
            "description",
            "location",
            "work_area",
            "contractor_name",
            "contractor_contact",
            "workers_count",
            "planned_start",
            "planned_end",
            "hazards_identified",
            "risk_controls",
            "ppe_required",
            "isolation_required",
            "isolation_details",
            "emergency_procedure",
            "toolbox_talk_done",
            "area_barricaded",
            "equipment_inspected",
            "gas_test_done",
            "gas_test_result",
            "attachment",
        ]
        widgets = {
            "description":         forms.Textarea(attrs={"rows": 3}),
            "hazards_identified":  forms.Textarea(attrs={"rows": 3}),
            "risk_controls":       forms.Textarea(attrs={"rows": 3}),
            "ppe_required":        forms.Textarea(attrs={"rows": 2}),
            "isolation_details":   forms.Textarea(attrs={"rows": 2}),
            "emergency_procedure": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        start   = cleaned.get("planned_start")
        end     = cleaned.get("planned_end")
        # Only check end > start — removed "start in past" check because
        # the time the user spent filling the form can make it appear "past"
        if start and end and end <= start:
            raise forms.ValidationError(
                "Planned end date/time must be after the planned start."
            )
        return cleaned


class PermitApprovalForm(forms.ModelForm):
    """Used by Safety Manager to approve or reject a permit."""

    DECISION_CHOICES = [
        ("approve", "Approve — work may proceed"),
        ("reject",  "Reject — send back to requestor"),
    ]
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        widget=forms.RadioSelect,
        label="Decision",
    )

    class Meta:
        model  = Permit
        fields = ["approval_comment", "rejection_reason"]
        widgets = {
            "approval_comment": forms.Textarea(attrs={"rows": 3}),
            "rejection_reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned  = super().clean()
        decision = cleaned.get("decision")
        if decision == "reject" and not cleaned.get("rejection_reason"):
            raise forms.ValidationError(
                "Please provide a rejection reason so the requestor can address it."
            )
        return cleaned


class PermitActivateForm(forms.ModelForm):
    """Requestor confirms work has started (APPROVED → ACTIVE)."""

    actual_start = forms.DateTimeField(
        widget=DATE_WIDGET,
        input_formats=["%Y-%m-%dT%H:%M"],
        initial=timezone.now,
    )

    class Meta:
        model  = Permit
        fields = ["actual_start"]


class PermitCloseForm(forms.ModelForm):
    """Close a completed permit (ACTIVE → CLOSED)."""

    actual_end = forms.DateTimeField(
        widget=DATE_WIDGET,
        input_formats=["%Y-%m-%dT%H:%M"],
        initial=timezone.now,
    )

    class Meta:
        model  = Permit
        fields = ["actual_end", "closure_comment", "site_restored"]
        widgets = {
            "closure_comment": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("site_restored"):
            raise forms.ValidationError(
                "You must confirm the site has been cleaned and restored before closing."
            )
        return cleaned
