import re

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class SkillCategory(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="skill_categories"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("organization", "name")]
        verbose_name_plural = "Skill Categories"

    def __str__(self):
        return self.name


class Skill(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="skills"
    )
    category = models.ForeignKey(
        SkillCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="skills",
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("organization", "name")]

    def __str__(self):
        return self.name


class SkillProficiency(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="skill_proficiencies"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_proficiencies",
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="proficiencies"
    )
    level = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Proficiency level: 1=Beginner, 2=Basic, 3=Intermediate, 4=Advanced, 5=Expert",
    )
    last_assessed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "skill")]
        verbose_name_plural = "Skill Proficiencies"

    def __str__(self):
        return f"{self.user.email} — {self.skill.name} (Level {self.level})"

    def get_level_display_label(self):
        labels = {
            1: "Beginner",
            2: "Basic",
            3: "Intermediate",
            4: "Advanced",
            5: "Expert",
        }
        return labels.get(self.level, str(self.level))


class TrainingModule(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="training_modules"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    skills = models.ManyToManyField(Skill, blank=True, related_name="training_modules")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_modules",
    )
    content_url = models.URLField(
        blank=True,
        help_text="YouTube video, Google Drive file, or Google Slides presentation link.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def has_assessment(self):
        return hasattr(self, "assessment")

    def get_embed_url(self):
        """Return an iframe-safe embed URL, or '' if the URL can't be embedded."""
        url = self.content_url or ""
        # YouTube: watch?v= or youtu.be/
        yt = re.search(r"(?:youtube\.com/watch\?.*v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        if yt:
            return f"https://www.youtube.com/embed/{yt.group(1)}"
        # Google Slides
        if "docs.google.com/presentation" in url:
            base = re.sub(r"/(edit|pub|view|present)[^/]*$", "", url.split("?")[0])
            return f"{base}/embed?start=false&loop=false"
        # Google Drive file preview
        m = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
        if m:
            return f"https://drive.google.com/file/d/{m.group(1)}/preview"
        return ""

    @property
    def content_type(self):
        """Returns 'youtube', 'slides', 'drive', 'link', or '' for labelling."""
        url = self.content_url or ""
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "docs.google.com/presentation" in url:
            return "slides"
        if "drive.google.com" in url:
            return "drive"
        if url:
            return "link"
        return ""


class Assessment(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="assessments"
    )
    training_module = models.OneToOneField(
        TrainingModule, on_delete=models.CASCADE, related_name="assessment"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    passing_score = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Minimum percentage score required to pass (e.g. 70 means 70%)",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assessments",
        help_text="The skill this assessment certifies upon passing",
    )
    grants_proficiency_level = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Proficiency level (1–5) awarded to the user upon passing",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()


class Question(models.Model):
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="questions"
    )
    text = models.TextField()
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class Choice(models.Model):
    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="choices"
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        marker = "✓" if self.is_correct else "✗"
        return f"{marker} {self.text[:60]}"


class AssessmentAttempt(models.Model):
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="assessment_attempts"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assessment_attempts",
    )
    assessment = models.ForeignKey(
        Assessment, on_delete=models.CASCADE, related_name="attempts"
    )
    score = models.FloatField(help_text="Percentage score, e.g. 75.0")
    passed = models.BooleanField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    answers = models.JSONField(
        default=dict,
        help_text="Audit snapshot: {question_id: chosen_choice_id}",
    )

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"{self.user.email} — {self.assessment.title} [{status} {self.score:.1f}%]"
