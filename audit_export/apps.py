from django.apps import AppConfig


class AuditExportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "audit_export"
    verbose_name = "Audit Export"
