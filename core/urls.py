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
]
