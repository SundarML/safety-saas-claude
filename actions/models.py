# actions/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


class CorrectiveAction(models.Model):

    SOURCE_HIRA        = "hira"
    SOURCE_OBSERVATION = "observation"
    SOURCE_COMPLIANCE  = "compliance"
    SOURCE_MANUAL      = "manual"

    SOURCE_INCIDENT    = "incident"
    SOURCE_INSPECTION  = "inspection"

    SOURCE_CHOICES = [
        (SOURCE_HIRA,        "HIRA Hazard"),
        (SOURCE_OBSERVATION, "Observation"),
        (SOURCE_COMPLIANCE,  "Legal Compliance"),
        (SOURCE_INCIDENT,    "Incident"),
        (SOURCE_INSPECTION,  "Inspection Finding"),
        (SOURCE_MANUAL,      "Manual"),
    ]

    PRIORITY_CRITICAL = "critical"
    PRIORITY_HIGH     = "high"
    PRIORITY_MEDIUM   = "medium"
    PRIORITY_LOW      = "low"

    PRIORITY_CHOICES = [
        (PRIORITY_CRITICAL, "Critical"),
        (PRIORITY_HIGH,     "High"),
        (PRIORITY_MEDIUM,   "Medium"),
        (PRIORITY_LOW,      "Low"),
    ]

    STATUS_OPEN                 = "open"
    STATUS_IN_PROGRESS          = "in_progress"
    STATUS_PENDING_VERIFICATION = "pending_verification"
    STATUS_CLOSED               = "closed"

    STATUS_CHOICES = [
        (STATUS_OPEN,                 "Open"),
        (STATUS_IN_PROGRESS,          "In Progress"),
        (STATUS_PENDING_VERIFICATION, "Pending Verification"),
        (STATUS_CLOSED,               "Closed"),
    ]

    # ── Core fields ───────────────────────────────────────────────────────────
    organization  = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="corrective_actions"
    )
    title         = models.CharField(max_length=300)
    description   = models.TextField(blank=True)
    priority      = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status        = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_OPEN)

    # ── Source linkage ────────────────────────────────────────────────────────
    source_module      = models.CharField(max_length=15, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    source_hira        = models.ForeignKey(
        "hira.Hazard", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="corrective_actions"
    )
    source_observation = models.ForeignKey(
        "observations.Observation", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="corrective_actions"
    )
    source_compliance  = models.ForeignKey(
        "compliance.ComplianceItem", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="corrective_actions"
    )

    # ── People ────────────────────────────────────────────────────────────────
    raised_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="actions_raised"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="actions_assigned"
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    due_date   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Closure / evidence ────────────────────────────────────────────────────
    evidence       = models.FileField(upload_to="action_evidence/", blank=True, null=True)
    closure_notes  = models.TextField(blank=True)
    closed_at      = models.DateTimeField(null=True, blank=True)
    closed_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="actions_closed"
    )
    reopen_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "-created_at"]

    def __str__(self):
        return f"CA-{self.pk:04d}: {self.title}"

    @property
    def is_overdue(self):
        if self.due_date and self.status != self.STATUS_CLOSED:
            return self.due_date < timezone.now().date()
        return False

    @property
    def source_label(self):
        if self.source_hira_id:
            return f"HIRA #{self.source_hira.register_id:04d}"
        if self.source_observation_id:
            return f"Observation #{self.source_observation_id}"
        if self.source_compliance_id:
            return f"Compliance: {self.source_compliance.title[:40]}"
        return "Manual"
