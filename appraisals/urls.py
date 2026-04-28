from django.urls import path
from . import views

app_name = "appraisals"

urlpatterns = [
    # Manager views
    path("",                                              views.cycle_list,      name="cycle_list"),
    path("new/",                                          views.cycle_create,    name="cycle_create"),
    path("<int:pk>/",                                     views.cycle_detail,    name="cycle_detail"),
    path("<int:pk>/advance/",                             views.cycle_advance,   name="cycle_advance"),
    path("<int:cycle_pk>/records/<int:record_pk>/goals/", views.record_goals,    name="record_goals"),
    path("<int:cycle_pk>/pending-goals/",                 views.pending_goals,   name="pending_goals"),

    # Phase 2 — manager review, scoring, stats
    path("<int:cycle_pk>/records/<int:record_pk>/review/", views.record_review,   name="record_review"),
    path("<int:pk>/stats/",                                views.cycle_stats,     name="cycle_stats"),

    # Phase 2 — employee final view, acknowledge, PDF
    path("records/<int:record_pk>/",                       views.record_view,      name="record_view"),
    path("records/<int:record_pk>/acknowledge/",           views.record_acknowledge, name="record_acknowledge"),
    path("records/<int:record_pk>/pdf/",                   views.record_pdf,       name="record_pdf"),

    # Phase 3 — calibration dashboard + dev plan links
    path("<int:pk>/calibrate/",                           views.cycle_calibrate,    name="cycle_calibrate"),
    path("records/<int:record_pk>/dev-plan/",             views.dev_plan_links,     name="dev_plan_links"),

    # Employee views
    path("my/",                                           views.my_appraisals,      name="my_appraisals"),
    path("my/<int:record_pk>/",                           views.my_record_detail,   name="my_record_detail"),
]
