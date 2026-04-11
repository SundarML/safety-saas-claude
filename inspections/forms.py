from django import forms
from .models import InspectionTemplate, TemplateSection, InspectionItem, Inspection, InspectionFinding


class InspectionTemplateForm(forms.ModelForm):
    class Meta:
        model  = InspectionTemplate
        fields = ["title", "description", "category", "is_active"]
        widgets = {
            "title":       forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "category":    forms.Select(attrs={"class": "form-select"}),
            "is_active":   forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class InspectionCreateForm(forms.ModelForm):
    class Meta:
        model  = Inspection
        fields = ["title", "template", "inspector", "location", "location_text", "scheduled_date", "notes"]
        widgets = {
            "title":          forms.TextInput(attrs={"class": "form-control"}),
            "template":       forms.Select(attrs={"class": "form-select"}),
            "inspector":      forms.Select(attrs={"class": "form-select"}),
            "location":       forms.Select(attrs={"class": "form-select"}),
            "location_text":  forms.TextInput(attrs={"class": "form-control", "placeholder": "Or type a location name"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes":          forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from observations.models import Location
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields["template"].queryset = InspectionTemplate.objects.filter(
            organization=org, is_active=True
        )
        self.fields["inspector"].queryset = User.objects.filter(
            organization=org, is_active=True
        )
        self.fields["location"].queryset = Location.objects.filter(organization=org)
        self.fields["location"].required = False
        self.fields["location_text"].required = False
        self.fields["notes"].required = False


class ConductFindingForm(forms.ModelForm):
    class Meta:
        model  = InspectionFinding
        fields = ["response", "notes", "photo"]
        widgets = {
            "response": forms.RadioSelect(),
            "notes":    forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Optional notes…"}),
            "photo":    forms.ClearableFileInput(attrs={"class": "form-control form-control-sm", "accept": "image/*"}),
        }
