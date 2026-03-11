# users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import CustomUser

_WORKER_ROLES = [
    ("observer",     "Observer"),
    ("action_owner", "Action Owner"),
]

_2MB = 2 * 1024 * 1024
_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp"}


class EmailLoginForm(AuthenticationForm):
    """Login form using email instead of username."""
    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True}),
    )


class CustomUserChangeForm(UserChangeForm):
    """Used in admin to edit existing users."""
    class Meta:
        model = CustomUser
        fields = ("email", "full_name", "role")


class ProfileUpdateForm(forms.ModelForm):
    """Lets a user update their own editable profile fields."""

    class Meta:
        model = CustomUser
        fields = ("full_name", "phone", "employee_id")
        labels = {
            "employee_id": "Employee ID",
        }
        help_texts = {
            "employee_id": "Your organisation-issued employee number (optional).",
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

    def clean_employee_id(self):
        eid = self.cleaned_data.get("employee_id", "").strip()
        if not eid:
            return ""
        org = self.current_user.organization
        qs = CustomUser.objects.filter(organization=org, employee_id=eid).exclude(
            pk=self.current_user.pk
        )
        if qs.exists():
            raise forms.ValidationError(
                "This employee ID is already in use within your organisation."
            )
        return eid


class WorkerLoginForm(forms.Form):
    """Login form for no-email worker accounts: org domain + employee ID + PIN."""
    org_domain = forms.CharField(
        label="Organisation Code",
        max_length=100,
        widget=forms.TextInput(attrs={"placeholder": "e.g. acme-corp", "autocomplete": "organization"}),
        help_text="The code your manager gave you for your organisation.",
    )
    employee_id = forms.CharField(
        label="Employee ID",
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "e.g. EMP-001", "autocomplete": "username"}),
    )
    pin = forms.CharField(
        label="PIN",
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "4–6 digit PIN", "autocomplete": "current-password"}),
    )

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "")
        if not pin.isdigit():
            raise forms.ValidationError("PIN must contain digits only.")
        return pin


class CreateWorkerForm(forms.Form):
    """Manager creates a no-email worker account."""
    full_name = forms.CharField(
        label="Full Name",
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Raju Kumar"}),
    )
    employee_id = forms.CharField(
        label="Employee ID",
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "e.g. EMP-001"}),
        help_text="Must be unique within your organisation.",
    )
    role = forms.ChoiceField(
        label="Role",
        choices=_WORKER_ROLES,
    )
    pin = forms.CharField(
        label="PIN",
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "4–6 digits"}),
        help_text="4 to 6 digits. Share this securely with the worker.",
    )
    confirm_pin = forms.CharField(
        label="Confirm PIN",
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat PIN"}),
    )

    def clean_pin(self):
        pin = self.cleaned_data.get("pin", "")
        if not pin.isdigit():
            raise forms.ValidationError("PIN must contain digits only.")
        return pin

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("pin") and cleaned.get("confirm_pin"):
            if cleaned["pin"] != cleaned["confirm_pin"]:
                self.add_error("confirm_pin", "PINs do not match.")
        return cleaned


class ResetWorkerPinForm(forms.Form):
    """Manager resets a worker's PIN."""
    new_pin = forms.CharField(
        label="New PIN",
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "4–6 digits"}),
    )
    confirm_pin = forms.CharField(
        label="Confirm New PIN",
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat PIN"}),
    )

    def clean_new_pin(self):
        pin = self.cleaned_data.get("new_pin", "")
        if not pin.isdigit():
            raise forms.ValidationError("PIN must contain digits only.")
        return pin

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_pin") and cleaned.get("confirm_pin"):
            if cleaned["new_pin"] != cleaned["confirm_pin"]:
                self.add_error("confirm_pin", "PINs do not match.")
        return cleaned


class OrgLogoForm(forms.Form):
    """Manager-only form to upload or remove the organisation logo."""
    logo = forms.ImageField(
        required=False,
        label="Organisation Logo",
        help_text="PNG, JPG or WebP · Max 2 MB · Recommended: at least 200×200 px",
        widget=forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
    )
    remove_logo = forms.BooleanField(required=False, label="Remove current logo")

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo:
            if logo.size > _2MB:
                raise forms.ValidationError("Logo file must be under 2 MB.")
            if logo.content_type not in _LOGO_TYPES:
                raise forms.ValidationError("Only PNG, JPG and WebP formats are accepted.")
        return logo
