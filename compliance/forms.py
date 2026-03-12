from django import forms
from .models import ComplianceItem


class ComplianceItemForm(forms.ModelForm):
    due_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = ComplianceItem
        fields = ["title", "law", "authority", "frequency", "due_date", "assigned_to", "notes"]

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        if org:
            self.fields["assigned_to"].queryset = (
                self.fields["assigned_to"].queryset.filter(organization=org)
            )
        self.fields["assigned_to"].required = False
        self.fields["law"].required = False
        self.fields["authority"].required = False
        self.fields["notes"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class MarkCompliedForm(forms.ModelForm):
    complied_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = ComplianceItem
        fields = ["complied_on", "evidence", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["evidence"].required = False
        self.fields["notes"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
