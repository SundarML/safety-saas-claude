# core/urls.py
from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("request-demo/",                   views.request_demo_view,          name="request_demo"),
    path("signup/",                         views.organization_signup,         name="organization_signup"),
    path("invite/",                         views.invite_user,                 name="invite_user"),
    path("invite-contractor/",               views.invite_contractor,           name="invite_contractor"),
    path("accept-invite/<uuid:token>/",     views.accept_invite,               name="accept_invite"),

    # Billing
    path("billing/",                        views.billing_view,                name="billing"),
    path("billing/create-order/",           views.create_razorpay_order,       name="create_order"),
    path("billing/verify-payment/",         views.verify_razorpay_payment,     name="verify_payment"),
    path("billing/webhook/razorpay/",       views.razorpay_webhook,            name="razorpay_webhook"),
]
