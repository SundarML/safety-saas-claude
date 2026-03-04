from django import forms
from .models import TrainingModule, Assessment


LEVEL_CHOICES = [
    (1, "Level 1 — Beginner"),
    (2, "Level 2 — Basic"),
    (3, "Level 3 — Intermediate"),
    (4, "Level 4 — Advanced"),
    (5, "Level 5 — Expert"),
]


class TrainingModuleForm(forms.ModelForm):
    class Meta:
        model = TrainingModule
        fields = ["title", "description", "skills", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Fire Safety Awareness"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Describe what this module covers…"}),
            "skills": forms.CheckboxSelectMultiple(),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class AssessmentForm(forms.ModelForm):
    grants_proficiency_level = forms.ChoiceField(
        choices=LEVEL_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Grants Proficiency Level",
        help_text="Level awarded to the user upon passing this assessment.",
    )

    class Meta:
        model = Assessment
        fields = ["title", "description", "passing_score", "skill", "grants_proficiency_level"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Fire Safety Assessment"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional instructions for the user…"}),
            "passing_score": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 100}),
            "skill": forms.Select(attrs={"class": "form-select"}),
        }
