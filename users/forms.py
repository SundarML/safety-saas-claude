# users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from .models import CustomUser


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
        # We need the current user to exclude them from the uniqueness check.
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
