# core/forms.py
from django import forms
from django.core.validators import validate_email
from .models import DemoRequest, FreePlanRequest, Organization, UserInvite, ContractorInvite


class OrganizationSignupForm(forms.Form):
    organization_name = forms.CharField(
        max_length=255,
        label="Organisation Name",
        widget=forms.TextInput(attrs={"placeholder": "Acme Steel Ltd."}),
    )
    domain = forms.CharField(
        max_length=255,
        label="Domain / Slug",
        help_text="Short unique ID for your org — letters, numbers, underscores only. E.g. acmesteel",
        widget=forms.TextInput(attrs={"placeholder": "acmesteel"}),
    )
    full_name = forms.CharField(
        max_length=255,
        label="Your Full Name",
        widget=forms.TextInput(attrs={"placeholder": "Rajesh Kumar"}),
    )
    email = forms.EmailField(
        label="Your Work Email",
        widget=forms.EmailInput(attrs={"placeholder": "you@yourcompany.com"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
    )

    def clean_domain(self):
        domain = self.cleaned_data["domain"].lower().strip()
        if not domain.isidentifier():
            raise forms.ValidationError(
                "Domain may only contain letters, numbers, and underscores."
            )
        if Organization.objects.filter(domain=domain).exists():
            raise forms.ValidationError(
                "An organization with this domain already exists. "
                "Please log in or contact support."
            )
        return domain

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


class DemoRequestForm(forms.ModelForm):
    class Meta:
        model = DemoRequest
        fields = ["full_name", "email", "whatsapp_number", "company", "job_title", "message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Tell us about your safety challenges (optional)"}
            ),
        }


class FreePlanRequestForm(forms.ModelForm):
    class Meta:
        model = FreePlanRequest
        fields = ["full_name", "email", "whatsapp_number", "company", "job_title", "message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Tell us about your safety needs (optional)"}
            ),
        }


class InviteUserForm(forms.ModelForm):
    class Meta:
        model = UserInvite
        fields = ["email", "role"]


class ContractorInviteForm(forms.Form):
    email = forms.EmailField(
        label="Contractor Email",
        widget=forms.EmailInput(attrs={"placeholder": "contractor@example.com"}),
    )
    access_validity_days = forms.IntegerField(
        label="Access valid for (days)",
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"placeholder": "Leave blank for no expiry"}),
    )


class AcceptContractorInviteForm(forms.Form):
    full_name = forms.CharField(
        max_length=255,
        label="Full Name",
        widget=forms.TextInput(attrs={"placeholder": "Jane Smith"}),
    )
    company = forms.CharField(
        max_length=255,
        label="Company / Contractor Firm",
        widget=forms.TextInput(attrs={"placeholder": "ABC Construction Ltd."}),
    )
    phone = forms.CharField(
        max_length=30,
        label="Phone / WhatsApp",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "+1 234 567 8901"}),
    )
    trade = forms.CharField(
        max_length=100,
        label="Trade / Specialization",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Electrical, Civil, Welding"}),
    )
    password1 = forms.CharField(
        label="Choose a Password",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


class AcceptInviteForm(forms.Form):
    full_name = forms.CharField(
        max_length=255,
        label="Your Full Name",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Jane Smith"}),
    )
    password1 = forms.CharField(
        label="Choose a Password",
        widget=forms.PasswordInput,
        min_length=8,
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
