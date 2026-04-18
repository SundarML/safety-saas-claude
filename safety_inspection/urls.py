"""
URL configuration for safety_inspection project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.http import JsonResponse
from core.views import home_view


def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("health/", health_check, name="health_check"),
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

    # Permit to Work app
    path("permits/", include("permits.urls", namespace="permits")),

    # Training & Skills app
    path("training/", include("training.urls", namespace="training")),

    # Legal Compliance app
    path("compliance/", include("compliance.urls", namespace="compliance")),

    # HIRA app
    path("hira/", include("hira.urls", namespace="hira")),

    # Corrective Actions
    path("actions/", include("actions.urls", namespace="actions")),

    # Incidents
    path("incidents/", include("incidents.urls", namespace="incidents")),

    # Inspections
    path("inspections/", include("inspections.urls", namespace="inspections")),

    # ISO 45001 Audit Export
    path("audit/", include("audit_export.urls", namespace="audit_export")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
