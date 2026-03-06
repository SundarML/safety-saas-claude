# users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import CustomUser

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
