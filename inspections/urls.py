from django.urls import path
from . import views

app_name = "inspections"

urlpatterns = [
    # Inspections
    path("",                         views.inspection_list,    name="list"),
    path("new/",                     views.inspection_create,  name="inspection_create"),
    path("<int:pk>/",                views.inspection_detail,  name="detail"),
    path("<int:pk>/conduct/",        views.inspection_conduct, name="conduct"),
    path("<int:pk>/pdf/",            views.inspection_pdf,     name="pdf"),
    path("stats/",                   views.inspection_stats,   name="stats"),

    # Templates
    path("templates/",               views.template_list,      name="template_list"),
    path("templates/new/",           views.template_create,    name="template_create"),
    path("templates/<int:pk>/",      views.template_detail,    name="template_detail"),
    path("templates/<int:pk>/edit/", views.template_edit,      name="template_edit"),
]
