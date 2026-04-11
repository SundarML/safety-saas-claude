# actions/forms.py
from django import forms
from .models import CorrectiveAction


class CorrectiveActionForm(forms.ModelForm):
    class Meta:
        model  = CorrectiveAction
        fields = [
            "title", "description", "priority", "source_module",
            "assigned_to", "due_date",
        ]
        widgets = {
            "title":         forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief action title…"}),
            "description":   forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                                   "placeholder": "What needs to be done and why…"}),
            "priority":      forms.Select(attrs={"class": "form-select"}),
            "source_module": forms.Select(attrs={"class": "form-select"}),
            "assigned_to":   forms.Select(attrs={"class": "form-select"}),
            "due_date":      forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
        labels = {
            "source_module": "Source / Category",
        }


class SubmitEvidenceForm(forms.ModelForm):
    """Used by the assigned user to submit the action for verification."""
    class Meta:
        model  = CorrectiveAction
        fields = ["closure_notes", "evidence"]
        widgets = {
            "closure_notes": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                                   "placeholder": "Describe what was done to resolve this action…"}),
            "evidence":      forms.FileInput(attrs={"class": "form-control"}),
        }
        labels = {
            "closure_notes": "What was done",
            "evidence":      "Supporting evidence (photo, document…)",
        }


class VerifyActionForm(forms.Form):
    """Used by managers to close or reject (reopen) a pending-verification action."""
    DECISION_CLOSE  = "close"
    DECISION_REOPEN = "reopen"
    DECISION_CHOICES = [
        (DECISION_CLOSE,  "Accept & Close"),
        (DECISION_REOPEN, "Reject — send back"),
    ]
    decision       = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect())
    reopen_comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2,
                                     "placeholder": "Reason for rejection (required if sending back)…"}),
        label="Rejection reason",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("decision") == self.DECISION_REOPEN and not cleaned.get("reopen_comment"):
            raise forms.ValidationError("Please provide a reason for rejection.")
        return cleaned
