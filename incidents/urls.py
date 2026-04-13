from django.urls import path
from . import views

app_name = "incidents"

urlpatterns = [
    path("",                         views.incident_list,       name="list"),
    path("new/",                     views.incident_create,     name="create"),
    path("<int:pk>/",                views.incident_detail,     name="detail"),
    path("<int:pk>/edit/",           views.incident_edit,       name="edit"),
    path("<int:pk>/investigate/",    views.incident_investigate, name="investigate"),
    path("<int:pk>/rca/",            views.incident_rca,        name="rca"),
    path("<int:pk>/action-required/",views.incident_action_required, name="action_required"),
    path("<int:pk>/close/",          views.incident_close,      name="close"),
    path("stats/",                   views.incident_stats,      name="stats"),
]
