# incidents/forms.py
from django import forms
from .models import Incident, HoursWorked


class IncidentForm(forms.ModelForm):
    class Meta:
        model  = Incident
        fields = [
            "title", "incident_type", "severity",
            "date_occurred", "location_text", "location",
            "description", "immediate_cause", "contributing_factors",
            "injured_person_name", "injured_person_type", "body_part_affected",
            "days_lost", "property_damage_est",
            "first_aid_given", "emergency_services",
            "photo_1", "photo_2",
            "linked_hazard",
        ]
        widgets = {
            "title":                forms.TextInput(attrs={"class": "form-control", "placeholder": "Brief incident title…"}),
            "incident_type":        forms.Select(attrs={"class": "form-select"}),
            "severity":             forms.Select(attrs={"class": "form-select"}),
            "date_occurred":        forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}),
            "location_text":        forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Workshop A, Bay 3"}),
            "location":             forms.Select(attrs={"class": "form-select"}),
            "description":          forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Describe exactly what happened…"}),
            "immediate_cause":      forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Unsafe act or unsafe condition…"}),
            "contributing_factors": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Environmental, organisational or human factors…"}),
            "injured_person_name":  forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name (if applicable)"}),
            "injured_person_type":  forms.Select(attrs={"class": "form-select"}),
            "body_part_affected":   forms.Select(attrs={"class": "form-select"}),
            "days_lost":            forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "property_damage_est":  forms.NumberInput(attrs={"class": "form-control", "placeholder": "0.00", "step": "0.01"}),
            "first_aid_given":      forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "emergency_services":   forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "photo_1":              forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "photo_2":              forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "linked_hazard":        forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "linked_hazard":       "Was this hazard in your HIRA? (optional)",
            "property_damage_est": "Estimated Damage Cost",
        }


class InvestigateForm(forms.ModelForm):
    class Meta:
        model  = Incident
        fields = ["investigated_by", "investigation_date"]
        widgets = {
            "investigated_by":   forms.Select(attrs={"class": "form-select"}),
            "investigation_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }
        labels = {
            "investigated_by":   "Assign Investigator",
            "investigation_date": "Target Investigation Date",
        }


class RCAForm(forms.ModelForm):
    class Meta:
        model  = Incident
        fields = [
            "immediate_cause", "contributing_factors",
            "rca_why_1", "rca_why_2", "rca_why_3", "rca_why_4", "rca_why_5",
            "rca_root_cause",
        ]
        widgets = {
            "immediate_cause":      forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "contributing_factors": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "rca_why_1":  forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Why did the incident occur?"}),
            "rca_why_2":  forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Why? (answer to Why 1)"}),
            "rca_why_3":  forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Why? (answer to Why 2)"}),
            "rca_why_4":  forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Why? (answer to Why 3)"}),
            "rca_why_5":  forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Why? (answer to Why 4)"}),
            "rca_root_cause": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "State the root cause conclusion…"}),
        }
        labels = {
            "rca_why_1": "Why 1 — Why did the incident occur?",
            "rca_why_2": "Why 2",
            "rca_why_3": "Why 3",
            "rca_why_4": "Why 4",
            "rca_why_5": "Why 5",
            "rca_root_cause": "Root Cause Conclusion",
        }


class CloseIncidentForm(forms.ModelForm):
    class Meta:
        model  = Incident
        fields = ["preventive_measures"]
        widgets = {
            "preventive_measures": forms.Textarea(attrs={
                "class": "form-control", "rows": 4,
                "placeholder": "Describe preventive measures taken to avoid recurrence…"
            }),
        }
        labels = {"preventive_measures": "Preventive Measures Implemented"}


class HoursWorkedForm(forms.ModelForm):
    class Meta:
        model  = HoursWorked
        fields = ["year", "month", "hours"]
        widgets = {
            "year":  forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
            "month": forms.Select(attrs={"class": "form-select"},
                                  choices=[(i, f"{i:02d} — {['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][i]}") for i in range(1, 13)]),
            "hours": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.5"}),
        }
