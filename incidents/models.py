# incidents/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import datetime


class Incident(models.Model):

    # ── Type ──────────────────────────────────────────────────────────────────
    TYPE_INJURY          = "injury"
    TYPE_NEAR_MISS       = "near_miss"
    TYPE_DANGEROUS_OCC   = "dangerous_occurrence"
    TYPE_PROPERTY_DAMAGE = "property_damage"
    TYPE_ENVIRONMENTAL   = "environmental"
    TYPE_OCC_ILLNESS     = "occ_illness"

    TYPE_CHOICES = [
        (TYPE_INJURY,          "Injury"),
        (TYPE_NEAR_MISS,       "Near-Miss"),
        (TYPE_DANGEROUS_OCC,   "Dangerous Occurrence"),
        (TYPE_PROPERTY_DAMAGE, "Property Damage"),
        (TYPE_ENVIRONMENTAL,   "Environmental"),
        (TYPE_OCC_ILLNESS,     "Occupational Illness"),
    ]

    # ── Severity ──────────────────────────────────────────────────────────────
    SEV_FATALITY   = "fatality"
    SEV_LTI        = "lti"
    SEV_MTC        = "mtc"
    SEV_FAC        = "fac"
    SEV_NEAR_MISS  = "near_miss"
    SEV_PROPERTY   = "property"

    SEVERITY_CHOICES = [
        (SEV_FATALITY,  "Fatality"),
        (SEV_LTI,       "Lost Time Injury (LTI)"),
        (SEV_MTC,       "Medical Treatment Case (MTC)"),
        (SEV_FAC,       "First Aid Case (FAC)"),
        (SEV_NEAR_MISS, "Near-Miss"),
        (SEV_PROPERTY,  "Property / Equipment Damage"),
    ]

    # ── Status ────────────────────────────────────────────────────────────────
    STATUS_REPORTED      = "reported"
    STATUS_INVESTIGATING = "under_investigation"
    STATUS_ACTION_REQ    = "action_required"
    STATUS_CLOSED        = "closed"

    STATUS_CHOICES = [
        (STATUS_REPORTED,      "Reported"),
        (STATUS_INVESTIGATING, "Under Investigation"),
        (STATUS_ACTION_REQ,    "Action Required"),
        (STATUS_CLOSED,        "Closed"),
    ]

    # ── Injured person type ───────────────────────────────────────────────────
    PERSON_EMPLOYEE   = "employee"
    PERSON_CONTRACTOR = "contractor"
    PERSON_VISITOR    = "visitor"
    PERSON_PUBLIC     = "public"

    PERSON_CHOICES = [
        (PERSON_EMPLOYEE,   "Employee"),
        (PERSON_CONTRACTOR, "Contractor"),
        (PERSON_VISITOR,    "Visitor"),
        (PERSON_PUBLIC,     "Public"),
    ]

    BODY_PART_CHOICES = [
        ("head",        "Head / Skull"),
        ("eye",         "Eye"),
        ("neck",        "Neck"),
        ("shoulder",    "Shoulder / Arm"),
        ("hand_wrist",  "Hand / Wrist / Fingers"),
        ("back",        "Back / Spine"),
        ("chest",       "Chest / Torso"),
        ("leg_knee",    "Leg / Knee"),
        ("foot_ankle",  "Foot / Ankle / Toes"),
        ("multiple",    "Multiple Areas"),
        ("other",       "Other"),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    organization   = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="incidents"
    )
    reference_no   = models.CharField(max_length=20, blank=True, editable=False)
    incident_type  = models.CharField(max_length=25, choices=TYPE_CHOICES, default=TYPE_NEAR_MISS)
    severity       = models.CharField(max_length=15, choices=SEVERITY_CHOICES, default=SEV_NEAR_MISS)
    status         = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_REPORTED)

    # ── What happened ─────────────────────────────────────────────────────────
    title              = models.CharField(max_length=300)
    description        = models.TextField()
    immediate_cause    = models.TextField(
        blank=True, help_text="Unsafe act or unsafe condition that directly caused the incident"
    )
    contributing_factors = models.TextField(
        blank=True, help_text="Environmental, organisational or human factors that contributed"
    )

    # ── Where / When ──────────────────────────────────────────────────────────
    date_occurred  = models.DateTimeField(default=timezone.now)
    location_text  = models.CharField(max_length=200, blank=True)
    location       = models.ForeignKey(
        "observations.Location", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="incidents"
    )

    # ── Who ───────────────────────────────────────────────────────────────────
    reported_by           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="incidents_reported"
    )
    injured_person_name   = models.CharField(max_length=200, blank=True)
    injured_person_type   = models.CharField(
        max_length=15, choices=PERSON_CHOICES, default=PERSON_EMPLOYEE, blank=True
    )
    body_part_affected    = models.CharField(
        max_length=20, choices=BODY_PART_CHOICES, blank=True
    )

    # ── Impact ────────────────────────────────────────────────────────────────
    days_lost            = models.PositiveIntegerField(default=0)
    property_damage_est  = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Estimated cost of property/equipment damage"
    )
    first_aid_given      = models.BooleanField(default=False)
    emergency_services   = models.BooleanField(default=False)

    # ── Evidence ──────────────────────────────────────────────────────────────
    photo_1 = models.ImageField(upload_to="incidents/photos/", blank=True, null=True)
    photo_2 = models.ImageField(upload_to="incidents/photos/", blank=True, null=True)

    # ── Investigation ─────────────────────────────────────────────────────────
    investigated_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="incidents_investigated"
    )
    investigation_date = models.DateField(null=True, blank=True)

    # ── 5-Whys RCA ───────────────────────────────────────────────────────────
    rca_why_1      = models.TextField(blank=True)
    rca_why_2      = models.TextField(blank=True)
    rca_why_3      = models.TextField(blank=True)
    rca_why_4      = models.TextField(blank=True)
    rca_why_5      = models.TextField(blank=True)
    rca_root_cause = models.TextField(blank=True, help_text="Final root cause conclusion")

    # ── Cross-module ──────────────────────────────────────────────────────────
    linked_hazard = models.ForeignKey(
        "hira.Hazard", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="incidents"
    )
    source_observation = models.ForeignKey(
        "observations.Observation", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="converted_incidents"
    )

    # ── Closure ───────────────────────────────────────────────────────────────
    preventive_measures = models.TextField(blank=True)
    closed_by           = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="incidents_closed"
    )
    closed_at           = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date_occurred"]

    def __str__(self):
        return f"{self.reference_no}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference_no:
            year = self.date_occurred.year if self.date_occurred else timezone.now().year
            # Will be set properly after first save gives us pk
            super().save(*args, **kwargs)
            self.reference_no = f"INC-{year}-{self.pk:04d}"
            kwargs["update_fields"] = ["reference_no"] if "update_fields" not in kwargs else kwargs["update_fields"] + ["reference_no"]
            super().save(update_fields=["reference_no"])
        else:
            super().save(*args, **kwargs)

    @property
    def is_recordable(self):
        """LTI, MTC, FAC, Fatality — used in TRIFR calculation."""
        return self.severity in (
            self.SEV_FATALITY, self.SEV_LTI, self.SEV_MTC, self.SEV_FAC
        )

    @property
    def severity_color(self):
        return {
            "fatality":  "#991b1b",
            "lti":       "#dc2626",
            "mtc":       "#ea580c",
            "fac":       "#ca8a04",
            "near_miss": "#2563eb",
            "property":  "#7c3aed",
        }.get(self.severity, "#64748b")


class HoursWorked(models.Model):
    """Monthly hours worked — denominator for LTIFR / TRIFR calculations."""
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="hours_worked"
    )
    year  = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()   # 1–12
    hours = models.DecimalField(max_digits=10, decimal_places=1)

    class Meta:
        unique_together = ("organization", "year", "month")
        ordering = ["year", "month"]

    def __str__(self):
        return f"{self.organization} — {self.year}/{self.month:02d}: {self.hours}h"
