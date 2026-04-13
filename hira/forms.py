# hira/forms.py
from django import forms
from django.forms import inlineformset_factory

from .models import Hazard, HazardRegister


class HazardRegisterForm(forms.ModelForm):
    class Meta:
        model  = HazardRegister
        fields = ["title", "activity", "location_text", "assessment_date", "next_review_date"]
        widgets = {
            "title":            forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Welding Operations – Workshop A"}),
            "activity":         forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Hot work, lifting operations…"}),
            "location_text":    forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Workshop A, Block 3"}),
            "assessment_date":  forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "next_review_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
        labels = {
            "title":            "Assessment Title",
            "activity":         "Activity / Work Area",
            "location_text":    "Location",
            "assessment_date":  "Assessment Date",
            "next_review_date": "Next Review Date",
        }


class HazardForm(forms.ModelForm):
    class Meta:
        model  = Hazard
        fields = [
            "order", "category", "hazard_description", "potential_harm",
            "who_might_be_harmed",
            "initial_likelihood", "initial_severity",
            "primary_control_type", "controls_description",
            "residual_likelihood", "residual_severity",
            "action_required", "action_owner", "action_due_date",
            "compliance_item",
        ]
        widgets = {
            "order":                forms.HiddenInput(),
            "category":             forms.Select(attrs={"class": "form-select form-select-sm"}),
            "hazard_description":   forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2,
                                                          "placeholder": "Describe the hazard…"}),
            "potential_harm":       forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 2,
                                                          "placeholder": "Potential injury or consequence…"}),
            "who_might_be_harmed":  forms.Select(attrs={"class": "form-select form-select-sm"}),
            "initial_likelihood":   forms.Select(attrs={"class": "form-select form-select-sm risk-input"}),
            "initial_severity":     forms.Select(attrs={"class": "form-select form-select-sm risk-input"}),
            "primary_control_type": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "controls_description": forms.Textarea(attrs={"class": "form-control form-control-sm", "rows": 3,
                                                          "placeholder": "List controls (one per line)…"}),
            "residual_likelihood":  forms.Select(attrs={"class": "form-select form-select-sm risk-input"}),
            "residual_severity":    forms.Select(attrs={"class": "form-select form-select-sm risk-input"}),
            "action_required":      forms.CheckboxInput(attrs={"class": "form-check-input action-required-cb"}),
            "action_owner":         forms.Select(attrs={"class": "form-select form-select-sm"}),
            "action_due_date":      forms.DateInput(attrs={"class": "form-control form-control-sm", "type": "date"}),
            "compliance_item":      forms.Select(attrs={"class": "form-select form-select-sm"}),
        }


HazardFormSet = inlineformset_factory(
    HazardRegister,
    Hazard,
    form=HazardForm,
    extra=0,
    can_delete=True,
)
