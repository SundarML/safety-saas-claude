from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("appraisals", "0001_initial"),
        ("training", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CalibrateNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("new_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("old_rating", models.CharField(blank=True, max_length=25)),
                ("new_rating", models.CharField(blank=True, max_length=25)),
                ("note", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("calibrated_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="calibrate_notes_made",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("record", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="calibrate_notes",
                    to="appraisals.appraisalrecord",
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="DevPlanLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="dev_plan_links_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("record", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="dev_plan_links",
                    to="appraisals.appraisalrecord",
                )),
                ("training_module", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="appraisal_dev_links",
                    to="training.trainingmodule",
                )),
            ],
            options={
                "ordering": ["created_at"],
                "unique_together": {("record", "training_module")},
            },
        ),
    ]
