from django.urls import path
from . import views

app_name = "actions"

urlpatterns = [
    path("",                       views.action_list,    name="list"),
    path("mine/",                  views.my_actions,     name="mine"),
    path("new/",                   views.action_create,  name="create"),
    path("<int:pk>/",              views.action_detail,  name="detail"),
    path("<int:pk>/edit/",         views.action_edit,    name="edit"),
    path("<int:pk>/progress/",     views.action_progress,  name="progress"),
    path("<int:pk>/submit/",       views.action_submit,    name="submit"),
    path("<int:pk>/verify/",       views.action_verify,    name="verify"),
    path("<int:pk>/reopen/",       views.action_reopen,    name="reopen"),
]
