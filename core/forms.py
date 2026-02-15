# core/forms.py
from django import forms
from django.core.validators import validate_email
from .models import DemoRequest, Organization, UserInvite


class OrganizationSignupForm(forms.Form):
    organization_name = forms.CharField(
        max_length=255,
        label="Organization Name",
        widget=forms.TextInput(attrs={"placeholder": "Acme Safety Ltd."}),
    )
    domain = forms.CharField(
        max_length=255,
        label="Domain / Slug",
        help_text="A unique identifier for your organization, e.g. acme",
        widget=forms.TextInput(attrs={"placeholder": "acme"}),
    )
    email = forms.EmailField(
        label="Your Email",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
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


class InviteUserForm(forms.ModelForm):
    class Meta:
        model = UserInvite
        fields = ["email", "role"]


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
