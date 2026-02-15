# users/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import profile_view
from .forms import EmailLoginForm

app_name = "users"

urlpatterns = [
    path("profile/", profile_view, name="profile"),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="users/login.html",
            authentication_form=EmailLoginForm,
        ),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(next_page="home"),
        name="logout",
    ),
]
