"""
URL configuration for safety_inspection project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from core.views import home_view

urlpatterns = [
    path("admin/", admin.site.urls),

    # Home page (marketing + authenticated redirect)
    path("", home_view, name="home"),

    # Django built-in auth (password reset, etc.)
    path("accounts/", include("django.contrib.auth.urls")),

    # Users app (login, logout, profile)
    path("users/", include("users.urls")),

    # SaaS core (signup, invite, billing, demo)
    path("", include("core.urls")),

    # Observations app
    path("observations/", include("observations.urls", namespace="observations")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
