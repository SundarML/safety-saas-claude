from django.db import models
from django.conf import settings


class InspectionTemplate(models.Model):
    CAT_WORKPLACE   = "workplace_safety"
    CAT_FIRE        = "fire_safety"
    CAT_EQUIPMENT   = "equipment"
    CAT_ELECTRICAL  = "electrical"
    CAT_ENVIRONMENT = "environmental"
    CAT_GENERAL     = "general"

    CATEGORY_CHOICES = [
        (CAT_WORKPLACE,   "Workplace Safety"),
        (CAT_FIRE,        "Fire Safety"),
        (CAT_EQUIPMENT,   "Equipment / Machinery"),
        (CAT_ELECTRICAL,  "Electrical Safety"),
        (CAT_ENVIRONMENT, "Environmental"),
        (CAT_GENERAL,     "General"),
    ]

    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="inspection_templates"
    )
    title        = models.CharField(max_length=200)
    description  = models.TextField(blank=True)
    category     = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CAT_GENERAL)
    is_active    = models.BooleanField(default=True)
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="created_templates"
    )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def item_count(self):
        return InspectionItem.objects.filter(section__template=self).count()


class TemplateSection(models.Model):
    template = models.ForeignKey(
        InspectionTemplate, on_delete=models.CASCADE, related_name="sections"
    )
    title    = models.CharField(max_length=200)
    order    = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template.title} — {self.title}"


class InspectionItem(models.Model):
    section     = models.ForeignKey(
        TemplateSection, on_delete=models.CASCADE, related_name="items"
    )
    question    = models.CharField(max_length=500)
    is_critical = models.BooleanField(
        default=False,
        help_text="Critical items that fail will auto-raise a corrective action."
    )
    order       = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.question


class Inspection(models.Model):
    STATUS_SCHEDULED   = "scheduled"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED   = "completed"
    STATUS_OVERDUE     = "overdue"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED,   "Scheduled"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED,   "Completed"),
        (STATUS_OVERDUE,     "Overdue"),
    ]

    organization   = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="inspections"
    )
    template       = models.ForeignKey(
        InspectionTemplate, on_delete=models.PROTECT, related_name="inspections"
    )
    title          = models.CharField(max_length=200)
    inspector      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="assigned_inspections"
    )
    location       = models.ForeignKey(
        "observations.Location", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="inspections"
    )
    location_text  = models.CharField(max_length=200, blank=True)
    scheduled_date = models.DateField()
    conducted_date = models.DateField(null=True, blank=True)
    status         = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    score          = models.FloatField(null=True, blank=True)
    notes          = models.TextField(blank=True)
    created_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name="created_inspections"
    )
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_date", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def location_display(self):
        if self.location:
            return self.location.name
        return self.location_text or "—"

    @property
    def is_overdue(self):
        from django.utils.timezone import now
        return (
            self.status not in (self.STATUS_COMPLETED,)
            and self.scheduled_date < now().date()
        )

    @property
    def score_colour(self):
        if self.score is None:
            return "secondary"
        if self.score >= 90:
            return "success"
        if self.score >= 70:
            return "warning"
        return "danger"

    @property
    def has_critical_failures(self):
        return self.findings.filter(
            response=InspectionFinding.RESP_FAIL,
            template_item__is_critical=True
        ).exists()


class InspectionFinding(models.Model):
    RESP_PASS = "pass"
    RESP_FAIL = "fail"
    RESP_NA   = "na"

    RESPONSE_CHOICES = [
        (RESP_PASS, "Pass"),
        (RESP_FAIL, "Fail"),
        (RESP_NA,   "N/A"),
    ]

    inspection    = models.ForeignKey(
        Inspection, on_delete=models.CASCADE, related_name="findings"
    )
    template_item = models.ForeignKey(
        InspectionItem, on_delete=models.CASCADE, related_name="findings"
    )
    response      = models.CharField(
        max_length=4, choices=RESPONSE_CHOICES, default=RESP_NA
    )
    notes         = models.TextField(blank=True)
    photo         = models.ImageField(
        upload_to="inspection_photos/", null=True, blank=True
    )
    raised_action = models.ForeignKey(
        "actions.CorrectiveAction", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="inspection_findings"
    )

    class Meta:
        unique_together = ("inspection", "template_item")
        ordering = ["template_item__section__order", "template_item__order"]
