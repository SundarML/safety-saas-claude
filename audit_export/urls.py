from django.urls import path
from . import views

app_name = "audit_export"

urlpatterns = [
    path("", views.audit_export_view, name="generate"),
]
