from django.db import models
from django.conf import settings
from django.utils import timezone


class ComplianceItem(models.Model):

    FREQUENCY_CHOICES = [
        ("one_time",    "One-time"),
        ("monthly",     "Monthly"),
        ("quarterly",   "Quarterly"),
        ("half_yearly", "Half-yearly"),
        ("annual",      "Annual"),
    ]

    STATUS_CHOICES = [
        ("pending",        "Pending"),
        ("complied",       "Complied"),
        ("overdue",        "Overdue"),
        ("not_applicable", "Not Applicable"),
    ]

    organization  = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="compliance_items"
    )
    title         = models.CharField(max_length=300)
    law           = models.CharField(
        max_length=300, blank=True,
        help_text="e.g. Factories Act 1948, Section 6"
    )
    authority     = models.CharField(
        max_length=200, blank=True,
        help_text="e.g. Chief Inspector of Factories"
    )
    frequency     = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="annual")
    due_date      = models.DateField()
    assigned_to   = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="compliance_assigned"
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    evidence      = models.FileField(upload_to="compliance_evidence/", blank=True, null=True)
    notes         = models.TextField(blank=True)
    complied_on   = models.DateField(null=True, blank=True)
    created_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="compliance_created"
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return self.title

    @property
    def days_until_due(self):
        return (self.due_date - timezone.now().date()).days

    @property
    def urgency(self):
        """Returns a string used for traffic-light styling."""
        if self.status in ("complied", "not_applicable"):
            return self.status
        days = self.days_until_due
        if days < 0:
            return "overdue"
        if days <= 30:
            return "urgent"
        if days <= 60:
            return "warning"
        return "ok"
