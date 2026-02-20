# core/forms.py
from django import forms
from django.contrib.auth import get_user_model
from .models import Organization

User = get_user_model()


# ---------------------------------------------------------------------------
# Organization Signup
# ---------------------------------------------------------------------------

class OrganizationSignupForm(forms.Form):
    """Step 1: Create organization + first user (manager)."""
    organization_name = forms.CharField(max_length=255, label="Organization Name")
    email = forms.EmailField(label="Your Email (will be the admin)")
    full_name = forms.CharField(max_length=255, label="Your Full Name")
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get("password")
        pw2 = cleaned.get("password_confirm")
        if pw1 and pw2 and pw1 != pw2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


# ---------------------------------------------------------------------------
# Invite Staff Users
# ---------------------------------------------------------------------------

class InviteUserForm(forms.Form):
    """Manager invites staff users to the organization."""
    email = forms.EmailField(label="Email Address")
    full_name = forms.CharField(max_length=255, label="Full Name")

    is_manager = forms.BooleanField(required=False, label="Manager")
    is_observer = forms.BooleanField(required=False, label="Observer")
    is_action_owner = forms.BooleanField(required=False, label="Action Owner")
    is_safety_manager = forms.BooleanField(required=False, label="Safety Manager")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


# ---------------------------------------------------------------------------
# Accept Invite (set password)
# ---------------------------------------------------------------------------

class AcceptInviteForm(forms.Form):
    """User sets their password when accepting an invite."""
    password = forms.CharField(widget=forms.PasswordInput, label="Choose a Password")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")

    def clean(self):
        cleaned = super().clean()
        pw1 = cleaned.get("password")
        pw2 = cleaned.get("password_confirm")
        if pw1 and pw2 and pw1 != pw2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


# ---------------------------------------------------------------------------
# Invite Contractor (limited Permit-only access)
# ---------------------------------------------------------------------------

class InviteContractorForm(forms.Form):
    """
    Invite a contractor user with limited permit-only access.
    Industry best practice: contractors get temporary, restricted access.
    """
    email = forms.EmailField(
        label="Contractor Email",
        help_text="Contractor will receive login credentials via email",
    )
    full_name = forms.CharField(
        max_length=255,
        label="Contact Person Name",
        help_text="Name of the contractor representative",
    )
    contractor_company = forms.CharField(
        max_length=255,
        label="Contractor Company Name",
        help_text="Company name will auto-populate in all permits this user creates",
    )
    contractor_phone = forms.CharField(
        max_length=50,
        label="Contact Phone",
        help_text="Phone number for emergency contact",
    )
    contractor_access_expiry = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Access Expiry Date (Optional)",
        help_text="Contractor account will be automatically disabled after this date",
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_contractor_access_expiry(self):
        expiry = self.cleaned_data.get("contractor_access_expiry")
        if expiry:
            from django.utils import timezone
            if expiry < timezone.now().date():
                raise forms.ValidationError("Expiry date cannot be in the past.")
        return expiry


# ---------------------------------------------------------------------------
# Demo Request
# ---------------------------------------------------------------------------

class DemoRequestForm(forms.Form):
    """Prospect requests a demo of the platform."""
    company_name = forms.CharField(max_length=255, label="Company Name")
    contact_name = forms.CharField(max_length=255, label="Your Name")
    email = forms.EmailField(label="Work Email")
    phone = forms.CharField(max_length=50, required=False, label="Phone (Optional)")
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        label="Tell us about your safety management needs (Optional)",
    )
