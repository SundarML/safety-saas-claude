# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("app-dashboard/", views.app_dashboard_view, name="app_dashboard"),
    path("request-demo/", views.request_demo_view, name="request_demo"),
    path("request-free-plan/", views.request_free_plan_view, name="request_free_plan"),
    path("signup/", views.organization_signup, name="organization_signup"),
    path("invite/", views.invite_user, name="invite_user"),
    path("accept-invite/<uuid:token>/", views.accept_invite, name="accept_invite"),
    path("invite-contractor/", views.invite_contractor, name="invite_contractor"),
    path("accept-contractor-invite/<uuid:token>/", views.accept_contractor_invite, name="accept_contractor_invite"),
    path("billing/", views.billing_view, name="billing"),
    path("help/", views.help_view, name="help"),
    path("workers/", views.worker_list_view, name="worker_list"),
    path("workers/create/", views.create_worker_view, name="create_worker"),
    path("workers/<int:worker_id>/reset-pin/", views.reset_worker_pin_view, name="reset_worker_pin"),
    path("workers/<int:worker_id>/toggle-active/", views.toggle_worker_active_view, name="toggle_worker_active"),
]
