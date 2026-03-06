# users/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import profile_view, profile_redirect_view, profile_detail_view, profile_certificate_pdf, upload_org_logo_view, org_logo_view
from .forms import EmailLoginForm

app_name = "users"

urlpatterns = [
    # Profile — own profile redirect and detail view
    path("profile/", profile_redirect_view, name="profile"),
    path("profile/<int:user_id>/", profile_detail_view, name="profile_detail"),
    path("profile/<int:user_id>/certificate.pdf", profile_certificate_pdf, name="profile_certificate"),
    path("org/logo/", upload_org_logo_view, name="upload_org_logo"),
    path("org/logo/current/", org_logo_view, name="org_logo"),

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
