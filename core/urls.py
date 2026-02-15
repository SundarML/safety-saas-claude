# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("request-demo/", views.request_demo_view, name="request_demo"),
    path("signup/", views.organization_signup, name="organization_signup"),
    path("invite/", views.invite_user, name="invite_user"),
    path("accept-invite/<uuid:token>/", views.accept_invite, name="accept_invite"),
    path("billing/", views.billing_view, name="billing"),
]
