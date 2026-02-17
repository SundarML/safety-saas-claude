# permits/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


class Permit(models.Model):

    # ── Work type ────────────────────────────────────────────────────────────
    WORK_TYPE_CHOICES = [
        ("hot_work",         "Hot Work"),
        ("confined_space",   "Confined Space Entry"),
        ("electrical",       "Electrical Work"),
        ("excavation",       "Excavation"),
        ("lifting_rigging",  "Lifting & Rigging"),
        ("work_at_height",   "Work at Height"),
        ("breaking_containment", "Breaking Containment / Isolation"),
        ("general",          "General High-Risk Work"),
    ]

    # ── Workflow status ───────────────────────────────────────────────────────
    STATUS_CHOICES = [
        ("DRAFT",      "Draft"),           # Requestor fills in the form
        ("SUBMITTED",  "Submitted"),        # Sent for safety officer review
        ("APPROVED",   "Approved"),         # Safety officer approved, work may begin
        ("ACTIVE",     "Active"),           # Work is ongoing
        ("CLOSED",     "Closed"),           # Work completed, permit closed
        ("REJECTED",   "Rejected"),         # Safety officer rejected
        ("CANCELLED",  "Cancelled"),        # Requestor cancelled before work started
    ]

    # ── Tenant & basic info ───────────────────────────────────────────────────
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="permits",
    )
    permit_number = models.CharField(max_length=30, unique=True, editable=False)

    work_type    = models.CharField(max_length=30, choices=WORK_TYPE_CHOICES)
    title        = models.CharField(max_length=255)
    description  = models.TextField(help_text="Describe the work to be done in detail.")
    location     = models.ForeignKey(
        "observations.Location",
        on_delete=models.PROTECT,
        related_name="permits",
    )
    work_area    = models.CharField(
        max_length=255, blank=True,
        help_text="Specific area / equipment tag where work will take place.",
    )

    # ── People ────────────────────────────────────────────────────────────────
    requestor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="permits_requested",
        help_text="Person requesting the permit.",
    )
    contractor_name    = models.CharField(max_length=255, blank=True,
                                          help_text="Contractor / vendor name (if external).")
    contractor_contact = models.CharField(max_length=100, blank=True)
    workers_count      = models.PositiveIntegerField(
        default=1, help_text="Number of workers involved."
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="permits_approved",
        help_text="Safety Manager / Officer who approves the permit.",
    )

    # ── Schedule ──────────────────────────────────────────────────────────────
    planned_start  = models.DateTimeField()
    planned_end    = models.DateTimeField()
    actual_start   = models.DateTimeField(null=True, blank=True)
    actual_end     = models.DateTimeField(null=True, blank=True)

    # ── Risk & controls ───────────────────────────────────────────────────────
    hazards_identified = models.TextField(
        help_text="List all foreseeable hazards for this work."
    )
    risk_controls      = models.TextField(
        help_text="Controls / precautions to mitigate each hazard."
    )
    ppe_required       = models.TextField(
        blank=True,
        help_text="Personal Protective Equipment required (e.g. helmet, harness, gloves).",
    )
    isolation_required = models.BooleanField(
        default=False,
        help_text="Does this work require energy isolation / LOTO?",
    )
    isolation_details  = models.TextField(
        blank=True,
        help_text="Describe isolation / LOTO procedure if required.",
    )
    emergency_procedure = models.TextField(
        blank=True,
        help_text="Emergency response procedure specific to this work.",
    )

    # ── Checklist pre-requisites ──────────────────────────────────────────────
    # These are Boolean flags; a rich checklist can be added per work type later.
    toolbox_talk_done     = models.BooleanField(default=False, verbose_name="Toolbox talk conducted")
    area_barricaded       = models.BooleanField(default=False, verbose_name="Area barricaded / signed")
    equipment_inspected   = models.BooleanField(default=False, verbose_name="Equipment / tools inspected")
    gas_test_done         = models.BooleanField(
        default=False,
        verbose_name="Gas / atmosphere test done",
        help_text="Required for hot work and confined space.",
    )
    gas_test_result       = models.CharField(max_length=100, blank=True,
                                              verbose_name="Gas test result (e.g. O2 %, LEL %)")

    # ── Approval / rejection ──────────────────────────────────────────────────
    approval_comment  = models.TextField(blank=True)
    rejection_reason  = models.TextField(blank=True)
    approved_at       = models.DateTimeField(null=True, blank=True)

    # ── Closure ───────────────────────────────────────────────────────────────
    closure_comment    = models.TextField(blank=True)
    site_restored      = models.BooleanField(
        default=False, verbose_name="Site cleaned & restored after work"
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="permits_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    # ── Attachments ───────────────────────────────────────────────────────────
    attachment = models.FileField(
        upload_to="permits/attachments/",
        blank=True, null=True,
        help_text="Risk assessment, method statement, or drawing (PDF/image).",
    )

    # ── Audit ─────────────────────────────────────────────────────────────────
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.permit_number}] {self.get_work_type_display()} — {self.title}"

    def save(self, *args, **kwargs):
        # Auto-generate permit number on first save: PTW-YYYYMMDD-XXXXX
        if not self.permit_number:
            today = timezone.now().strftime("%Y%m%d")
            # Count today's permits + 1 for sequence
            seq = Permit.objects.filter(
                permit_number__startswith=f"PTW-{today}-"
            ).count() + 1
            self.permit_number = f"PTW-{today}-{seq:04d}"
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return (
            self.status in ("APPROVED", "ACTIVE")
            and self.planned_end < timezone.now()
        )

    @property
    def duration_hours(self):
        delta = self.planned_end - self.planned_start
        return round(delta.total_seconds() / 3600, 1)
