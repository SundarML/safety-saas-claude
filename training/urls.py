from django.urls import path
from . import views

app_name = "training"

urlpatterns = [
    # Dashboard
    path("dashboard/", views.training_dashboard, name="dashboard"),

    # Training Modules
    path("", views.module_list, name="module_list"),
    path("new/", views.module_create, name="module_create"),
    path("<int:pk>/", views.module_detail, name="module_detail"),

    # Assessment management (manager/safety_manager only)
    path("<int:module_pk>/assessment/create/", views.assessment_create, name="assessment_create"),
    path("assessment/<int:pk>/edit/", views.assessment_edit, name="assessment_edit"),
    path("assessment/<int:pk>/questions/", views.edit_questions, name="edit_questions"),

    # Taking assessments (all authenticated users)
    path("assessment/<int:pk>/take/", views.take_assessment, name="take_assessment"),
    path("attempt/<int:pk>/result/", views.attempt_result, name="attempt_result"),

    # Skill matrix (read-only view)
    path("skills/matrix/", views.skill_matrix, name="skill_matrix"),

    # Skills & categories management (manager only)
    path("skills/manage/", views.manage_skills, name="manage_skills"),
    path("skills/categories/create/", views.category_create, name="category_create"),
    path("skills/categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("skills/create/", views.skill_create, name="skill_create"),
    path("skills/<int:pk>/delete/", views.skill_delete, name="skill_delete"),

    # Reports (manager/safety_manager only)
    path("reports/skills.csv/", views.report_skills_csv, name="report_skills_csv"),
    path("reports/effectiveness.pdf/", views.report_effectiveness_pdf, name="report_effectiveness_pdf"),
]
