from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class AppraisalCycle(models.Model):

    STATUS_DRAFT           = "draft"
    STATUS_GOAL_SETTING    = "goal_setting"
    STATUS_SELF_ASSESSMENT = "self_assessment"
    STATUS_MANAGER_REVIEW  = "manager_review"
    STATUS_CALIBRATION     = "calibration"
    STATUS_COMPLETED       = "completed"

    STATUS_CHOICES = [
        (STATUS_DRAFT,           "Draft"),
        (STATUS_GOAL_SETTING,    "Goal Setting"),
        (STATUS_SELF_ASSESSMENT, "Self Assessment"),
        (STATUS_MANAGER_REVIEW,  "Manager Review"),
        (STATUS_CALIBRATION,     "Calibration"),
        (STATUS_COMPLETED,       "Completed"),
    ]

    STATUS_ORDER = [
        STATUS_DRAFT, STATUS_GOAL_SETTING, STATUS_SELF_ASSESSMENT,
        STATUS_MANAGER_REVIEW, STATUS_CALIBRATION, STATUS_COMPLETED,
    ]

    PERIOD_ANNUAL      = "annual"
    PERIOD_SEMI_ANNUAL = "semi_annual"
    PERIOD_QUARTERLY   = "quarterly"
    PERIOD_CUSTOM      = "custom"

    PERIOD_CHOICES = [
        (PERIOD_ANNUAL,      "Annual"),
        (PERIOD_SEMI_ANNUAL, "Semi-Annual"),
        (PERIOD_QUARTERLY,   "Quarterly"),
        (PERIOD_CUSTOM,      "Custom"),
    ]

    organization             = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="appraisal_cycles"
    )
    name                     = models.CharField(max_length=200)
    period                   = models.CharField(max_length=20, choices=PERIOD_CHOICES, default=PERIOD_ANNUAL)
    start_date               = models.DateField()
    end_date                 = models.DateField()
    goal_setting_deadline    = models.DateField()
    self_assessment_deadline = models.DateField()
    review_deadline          = models.DateField()
    status                   = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_by               = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="appraisal_cycles_created"
    )
    created_at               = models.DateTimeField(auto_now_add=True)
    updated_at               = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def status_index(self):
        try:
            return self.STATUS_ORDER.index(self.status)
        except ValueError:
            return 0

    @property
    def next_status(self):
        idx = self.status_index
        if idx < len(self.STATUS_ORDER) - 1:
            return self.STATUS_ORDER[idx + 1]
        return None

    @property
    def next_status_label(self):
        ns = self.next_status
        if ns:
            return dict(self.STATUS_CHOICES).get(ns, ns)
        return None

    @property
    def categories_weight_total(self):
        result = self.categories.aggregate(total=models.Sum("weight"))["total"]
        return result or Decimal("0")


class AppraisalCategory(models.Model):

    TYPE_GOALS      = "goals"
    TYPE_COMPETENCY = "competency"
    TYPE_CUSTOM     = "custom"

    TYPE_CHOICES = [
        (TYPE_GOALS,      "Goals & Targets"),
        (TYPE_COMPETENCY, "Competency"),
        (TYPE_CUSTOM,     "Custom Rating"),
    ]

    cycle         = models.ForeignKey(AppraisalCycle, on_delete=models.CASCADE, related_name="categories")
    name          = models.CharField(max_length=100)
    category_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_GOALS)
    weight        = models.DecimalField(max_digits=5, decimal_places=2)
    order         = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.name} ({self.weight}%)"


class AppraisalRecord(models.Model):

    STATUS_PENDING_GOALS    = "pending_goals"
    STATUS_GOALS_SET        = "goals_set"
    STATUS_SELF_ASSESS      = "self_assessment"
    STATUS_PENDING_REVIEW   = "pending_review"
    STATUS_MANAGER_REVIEWED = "manager_reviewed"
    STATUS_ACKNOWLEDGED     = "acknowledged"

    STATUS_CHOICES = [
        (STATUS_PENDING_GOALS,    "Pending Goals"),
        (STATUS_GOALS_SET,        "Goals Set"),
        (STATUS_SELF_ASSESS,      "Self Assessment"),
        (STATUS_PENDING_REVIEW,   "Pending Review"),
        (STATUS_MANAGER_REVIEWED, "Manager Reviewed"),
        (STATUS_ACKNOWLEDGED,     "Acknowledged"),
    ]

    RATING_EXCEPTIONAL       = "exceptional"
    RATING_EXCEEDS           = "exceeds"
    RATING_MEETS             = "meets"
    RATING_NEEDS_IMPROVEMENT = "needs_improvement"
    RATING_UNSATISFACTORY    = "unsatisfactory"

    RATING_CHOICES = [
        (RATING_EXCEPTIONAL,       "Exceptional"),
        (RATING_EXCEEDS,           "Exceeds Expectations"),
        (RATING_MEETS,             "Meets Expectations"),
        (RATING_NEEDS_IMPROVEMENT, "Needs Improvement"),
        (RATING_UNSATISFACTORY,    "Unsatisfactory"),
    ]

    RATING_COLORS = {
        RATING_EXCEPTIONAL:       "success",
        RATING_EXCEEDS:           "info",
        RATING_MEETS:             "primary",
        RATING_NEEDS_IMPROVEMENT: "warning",
        RATING_UNSATISFACTORY:    "danger",
    }

    cycle           = models.ForeignKey(AppraisalCycle, on_delete=models.CASCADE, related_name="records")
    employee        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="appraisal_records"
    )
    reviewer        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="appraisal_reviews"
    )
    status          = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_PENDING_GOALS)
    overall_score   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    overall_rating  = models.CharField(max_length=25, choices=RATING_CHOICES, blank=True)
    manager_summary = models.TextField(blank=True)
    development_plan = models.TextField(blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("cycle", "employee")]
        ordering = ["employee__full_name"]

    def __str__(self):
        return f"{self.employee} — {self.cycle.name}"

    def compute_and_save_score(self):
        """Recompute overall_score from manager ratings and persist."""
        score = self._compute_score()
        self.overall_score = score
        self.overall_rating = self._rating_label(score)
        self.save(update_fields=["overall_score", "overall_rating", "updated_at"])
        return score

    def _compute_score(self):
        total_weighted = Decimal("0")
        total_weight   = Decimal("0")

        for category in self.cycle.categories.all():
            approved_items = list(
                self.items.filter(category=category, approved_by_manager=True)
            )
            if not approved_items:
                continue

            cat_score        = Decimal("0")
            cat_weight_used  = Decimal("0")

            for item in approved_items:
                rating_obj = self.ratings.filter(item=item).first()
                if rating_obj and rating_obj.manager_rating:
                    score = Decimal(str(rating_obj.manager_rating)) / Decimal("5") * Decimal("100")
                    cat_score       += score * (Decimal(str(item.weight)) / Decimal("100"))
                    cat_weight_used += Decimal(str(item.weight))

            if cat_weight_used > 0:
                normalized     = cat_score / (cat_weight_used / Decimal("100"))
                total_weighted += normalized * (Decimal(str(category.weight)) / Decimal("100"))
                total_weight   += Decimal(str(category.weight))

        if total_weight > 0:
            return (total_weighted / (total_weight / Decimal("100"))).quantize(Decimal("0.01"))
        return Decimal("0")

    @staticmethod
    def _rating_label(score):
        if score >= 90:
            return AppraisalRecord.RATING_EXCEPTIONAL
        if score >= 75:
            return AppraisalRecord.RATING_EXCEEDS
        if score >= 60:
            return AppraisalRecord.RATING_MEETS
        if score >= 40:
            return AppraisalRecord.RATING_NEEDS_IMPROVEMENT
        return AppraisalRecord.RATING_UNSATISFACTORY

    @property
    def rating_color(self):
        return self.RATING_COLORS.get(self.overall_rating, "secondary")


class AppraisalItem(models.Model):

    ITEM_MEASURABLE = "measurable"
    ITEM_RATING     = "rating"
    ITEM_YESNO      = "yes_no"

    ITEM_TYPE_CHOICES = [
        (ITEM_MEASURABLE, "Measurable (has target value)"),
        (ITEM_RATING,     "Rating (1–5 scale)"),
        (ITEM_YESNO,      "Yes / No"),
    ]

    GOAL_MANAGER_SET = "manager_set"
    GOAL_SELF_SET    = "self_set"

    GOAL_TYPE_CHOICES = [
        (GOAL_MANAGER_SET, "Manager Assigned"),
        (GOAL_SELF_SET,    "Employee Proposed"),
    ]

    record            = models.ForeignKey(AppraisalRecord, on_delete=models.CASCADE, related_name="items")
    category          = models.ForeignKey(AppraisalCategory, on_delete=models.CASCADE, related_name="items")
    title             = models.CharField(max_length=300)
    description       = models.TextField(blank=True)
    item_type         = models.CharField(max_length=15, choices=ITEM_TYPE_CHOICES, default=ITEM_RATING)
    weight            = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    target_value      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    target_unit       = models.CharField(max_length=50, blank=True)
    goal_type         = models.CharField(max_length=15, choices=GOAL_TYPE_CHOICES, default=GOAL_MANAGER_SET)
    created_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="appraisal_items_created"
    )
    approved_by_manager  = models.BooleanField(default=False)
    approved_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="appraisal_items_approved"
    )
    approved_at          = models.DateTimeField(null=True, blank=True)
    rejection_reason     = models.TextField(blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__order", "created_at"]

    def __str__(self):
        return self.title

    @property
    def is_pending_approval(self):
        return (
            self.goal_type == self.GOAL_SELF_SET
            and not self.approved_by_manager
            and not self.rejection_reason
        )

    @property
    def is_rejected(self):
        return bool(self.rejection_reason)


class CalibrateNote(models.Model):
    """Audit trail entry when a Safety Manager adjusts a score during calibration."""
    record         = models.ForeignKey(AppraisalRecord, on_delete=models.CASCADE, related_name="calibrate_notes")
    calibrated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="calibrate_notes_made"
    )
    old_score      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    new_score      = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    old_rating     = models.CharField(max_length=25, blank=True)
    new_rating     = models.CharField(max_length=25, blank=True)
    note           = models.TextField()
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Calibration: {self.record} by {self.calibrated_by}"


class DevPlanLink(models.Model):
    """Links a development plan item on an appraisal record to a TrainingModule."""
    record          = models.ForeignKey(AppraisalRecord, on_delete=models.CASCADE, related_name="dev_plan_links")
    training_module = models.ForeignKey(
        "training.TrainingModule", on_delete=models.CASCADE, related_name="appraisal_dev_links"
    )
    note            = models.TextField(blank=True)
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="dev_plan_links_created"
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("record", "training_module")]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.record.employee.full_name} → {self.training_module}"


class AppraisalRating(models.Model):

    record         = models.ForeignKey(AppraisalRecord, on_delete=models.CASCADE, related_name="ratings")
    item           = models.ForeignKey(AppraisalItem, on_delete=models.CASCADE, related_name="ratings")
    actual_value   = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    self_rating    = models.PositiveSmallIntegerField(null=True, blank=True)
    self_comment   = models.TextField(blank=True)
    manager_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    manager_comment = models.TextField(blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("record", "item")]

    def __str__(self):
        return f"Rating: {self.item.title[:40]}"

    @property
    def achievement_pct(self):
        if (
            self.item.item_type == AppraisalItem.ITEM_MEASURABLE
            and self.item.target_value
            and self.actual_value is not None
        ):
            pct = (self.actual_value / self.item.target_value) * 100
            return min(pct, Decimal("150"))
        return None
