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
        fields = ("email", "full_name", "is_observer", "is_action_owner", "is_safety_manager")
