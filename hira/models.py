# hira/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone


LIKELIHOOD_CHOICES = [
    (1, "1 – Rare"),
    (2, "2 – Unlikely"),
    (3, "3 – Possible"),
    (4, "4 – Likely"),
    (5, "5 – Almost Certain"),
]

SEVERITY_CHOICES = [
    (1, "1 – Insignificant"),
    (2, "2 – Minor"),
    (3, "3 – Moderate"),
    (4, "4 – Major"),
    (5, "5 – Catastrophic"),
]


def compute_risk_level(score):
    """Return risk level string for a given L×S score (1–25)."""
    if score is None:
        return None
    if score <= 4:
        return "low"
    if score <= 9:
        return "medium"
    if score <= 16:
        return "high"
    return "critical"


RISK_LEVEL_LABELS = {
    "low":      "Low",
    "medium":   "Medium",
    "high":     "High",
    "critical": "Critical",
}

RISK_LEVEL_COLORS = {
    "low":      "#198754",
    "medium":   "#ca8a04",
    "high":     "#ea580c",
    "critical": "#dc2626",
}


class HazardRegister(models.Model):
    STATUS_DRAFT        = "draft"
    STATUS_UNDER_REVIEW = "under_review"
    STATUS_APPROVED     = "approved"
    STATUS_EXPIRED      = "expired"

    STATUS_CHOICES = [
        (STATUS_DRAFT,        "Draft"),
        (STATUS_UNDER_REVIEW, "Under Review"),
        (STATUS_APPROVED,     "Approved"),
        (STATUS_EXPIRED,      "Expired"),
    ]

    organization    = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="hazard_registers"
    )
    title           = models.CharField(max_length=300)
    activity        = models.CharField(
        max_length=300, help_text="Job / task / work area being assessed"
    )
    location_text   = models.CharField(max_length=200, blank=True)
    assessment_date = models.DateField(default=timezone.now)
    next_review_date= models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    assessed_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="hira_assessed"
    )
    approved_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hira_approved"
    )
    approved_at     = models.DateTimeField(null=True, blank=True)
    revision_no     = models.PositiveSmallIntegerField(default=1)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assessment_date", "-created_at"]

    def __str__(self):
        return f"{self.title} (Rev {self.revision_no})"

    @property
    def highest_risk_level(self):
        """Highest effective risk level across all hazards in this register."""
        hazards = list(self.hazards.all())
        if not hazards:
            return None
        priority = ["critical", "high", "medium", "low"]
        for level in priority:
            if any(h.effective_risk_level == level for h in hazards):
                return level
        return None

    @property
    def is_review_due(self):
        if self.next_review_date and self.status == self.STATUS_APPROVED:
            return self.next_review_date <= timezone.now().date()
        return False

    @property
    def days_until_review(self):
        if self.next_review_date:
            return (self.next_review_date - timezone.now().date()).days
        return None


class Hazard(models.Model):
    CATEGORY_CHOICES = [
        ("physical",         "Physical"),
        ("chemical",         "Chemical"),
        ("biological",       "Biological"),
        ("ergonomic",        "Ergonomic"),
        ("electrical",       "Electrical"),
        ("fire_explosion",   "Fire / Explosion"),
        ("working_at_height","Working at Height"),
        ("confined_space",   "Confined Space"),
        ("mechanical",       "Mechanical"),
        ("psychosocial",     "Psychosocial"),
        ("environmental",    "Environmental"),
        ("other",            "Other"),
    ]

    WHO_CHOICES = [
        ("all_personnel", "All Personnel"),
        ("workers",       "Workers"),
        ("contractors",   "Contractors"),
        ("visitors",      "Visitors"),
        ("public",        "Public"),
    ]

    CONTROL_TYPE_CHOICES = [
        ("elimination",    "Elimination"),
        ("substitution",   "Substitution"),
        ("engineering",    "Engineering Controls"),
        ("administrative", "Administrative Controls"),
        ("ppe",            "PPE"),
    ]

    register              = models.ForeignKey(HazardRegister, on_delete=models.CASCADE, related_name="hazards")
    order                 = models.PositiveSmallIntegerField(default=0)
    category              = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="physical")
    hazard_description    = models.TextField(help_text="Describe the hazard source or situation")
    potential_harm        = models.TextField(help_text="Injury / illness / consequence that could result")
    who_might_be_harmed   = models.CharField(max_length=20, choices=WHO_CHOICES, default="all_personnel")

    # ── Initial (pre-control) risk ─────────────────────────────────────────
    initial_likelihood    = models.PositiveSmallIntegerField(choices=LIKELIHOOD_CHOICES, default=3)
    initial_severity      = models.PositiveSmallIntegerField(choices=SEVERITY_CHOICES,   default=3)

    # ── Controls (Hierarchy of Controls) ──────────────────────────────────
    primary_control_type  = models.CharField(max_length=20, choices=CONTROL_TYPE_CHOICES, default="administrative")
    controls_description  = models.TextField(help_text="Describe controls in place or planned (one per line)")

    # ── Residual (post-control) risk ───────────────────────────────────────
    residual_likelihood   = models.PositiveSmallIntegerField(choices=LIKELIHOOD_CHOICES, null=True, blank=True)
    residual_severity     = models.PositiveSmallIntegerField(choices=SEVERITY_CHOICES,   null=True, blank=True)

    # ── Action ────────────────────────────────────────────────────────────
    action_required       = models.BooleanField(default=False)
    action_owner          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hira_actions"
    )
    action_due_date       = models.DateField(null=True, blank=True)

    # ── Phase 2: cross-module linkage ─────────────────────────────────────
    linked_observations   = models.ManyToManyField(
        "observations.Observation",
        blank=True,
        related_name="linked_hazards",
    )
    compliance_item       = models.ForeignKey(
        "compliance.ComplianceItem",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="hira_hazards",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.get_category_display()}: {self.hazard_description[:60]}"

    # ── Risk computations ──────────────────────────────────────────────────

    @property
    def initial_risk_score(self):
        return self.initial_likelihood * self.initial_severity

    @property
    def initial_risk_level(self):
        return compute_risk_level(self.initial_risk_score)

    @property
    def residual_risk_score(self):
        if self.residual_likelihood and self.residual_severity:
            return self.residual_likelihood * self.residual_severity
        return None

    @property
    def residual_risk_level(self):
        return compute_risk_level(self.residual_risk_score)

    @property
    def effective_risk_level(self):
        """Residual if assessed, else initial."""
        return self.residual_risk_level or self.initial_risk_level
