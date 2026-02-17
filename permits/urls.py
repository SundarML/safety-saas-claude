# permits/urls.py
from django.urls import path
from . import views

app_name = "permits"

urlpatterns = [
    path("",                        views.permit_list,      name="permit_list"),
    path("dashboard/",              views.permit_dashboard, name="dashboard"),
    path("new/",                    views.permit_create,    name="create"),
    path("<int:pk>/",               views.permit_detail,    name="detail"),
    path("<int:pk>/edit/",          views.permit_edit,      name="edit"),
    path("<int:pk>/submit/",        views.permit_submit,    name="submit"),
    path("<int:pk>/approve/",       views.permit_approve,   name="approve"),
    path("<int:pk>/activate/",      views.permit_activate,  name="activate"),
    path("<int:pk>/close/",         views.permit_close,     name="close"),
    path("<int:pk>/cancel/",        views.permit_cancel,    name="cancel"),
]
