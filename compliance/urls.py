from django.urls import path
from . import views

app_name = "compliance"

urlpatterns = [
    path("",                    views.dashboard,     name="dashboard"),
    path("add/",                views.item_create,   name="item_create"),
    path("<int:pk>/",           views.item_detail,   name="item_detail"),
    path("<int:pk>/edit/",      views.item_edit,     name="item_edit"),
    path("<int:pk>/delete/",    views.item_delete,   name="item_delete"),
    path("<int:pk>/comply/",    views.mark_complied, name="mark_complied"),
    path("<int:pk>/na/",        views.mark_na,       name="mark_na"),
]
