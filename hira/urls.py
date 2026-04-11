from django.urls import path
from . import views

app_name = "hira"

urlpatterns = [
    path("",                      views.dashboard,       name="dashboard"),
    path("registers/",            views.register_list,   name="register_list"),
    path("registers/new/",        views.register_create, name="register_create"),
    path("registers/<int:pk>/",           views.register_detail,  name="register_detail"),
    path("registers/<int:pk>/edit/",      views.register_edit,    name="register_edit"),
    path("registers/<int:pk>/delete/",    views.register_delete,  name="register_delete"),
    path("registers/<int:pk>/approve/",   views.register_approve, name="register_approve"),
    path("registers/<int:pk>/pdf/",       views.register_pdf,     name="register_pdf"),
    path("export/csv/",                   views.export_csv,       name="export_csv"),
    path("export/excel/",                 views.export_excel,     name="export_excel"),
    path("risk-matrix/",                  views.risk_matrix,      name="risk_matrix"),
    path("hazard/<int:hazard_pk>/link-observation/",
         views.link_observation,   name="link_observation"),
    path("hazard/<int:hazard_pk>/unlink-observation/<int:obs_pk>/",
         views.unlink_observation, name="unlink_observation"),
]
