from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0008_demorequest_status_notes"),
        ("hira", "0002_phase2"),
        ("observations", "0003_alter_location_options"),
        ("compliance", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CorrectiveAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300)),
                ("description", models.TextField(blank=True)),
                ("priority", models.CharField(
                    choices=[("critical","Critical"),("high","High"),("medium","Medium"),("low","Low")],
                    default="medium", max_length=10,
                )),
                ("status", models.CharField(
                    choices=[("open","Open"),("in_progress","In Progress"),
                             ("pending_verification","Pending Verification"),("closed","Closed")],
                    default="open", max_length=25,
                )),
                ("source_module", models.CharField(
                    choices=[("hira","HIRA Hazard"),("observation","Observation"),
                             ("compliance","Legal Compliance"),("manual","Manual")],
                    default="manual", max_length=15,
                )),
                ("due_date", models.DateField(blank=True, null=True)),
                ("evidence", models.FileField(blank=True, null=True, upload_to="action_evidence/")),
                ("closure_notes", models.TextField(blank=True)),
                ("reopen_comment", models.TextField(blank=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="corrective_actions", to="core.organization",
                )),
                ("raised_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="actions_raised", to=settings.AUTH_USER_MODEL,
                )),
                ("assigned_to", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="actions_assigned", to=settings.AUTH_USER_MODEL,
                )),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="actions_closed", to=settings.AUTH_USER_MODEL,
                )),
                ("source_hira", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="corrective_actions", to="hira.hazard",
                )),
                ("source_observation", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="corrective_actions", to="observations.observation",
                )),
                ("source_compliance", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="corrective_actions", to="compliance.complianceitem",
                )),
            ],
            options={"ordering": ["due_date", "-created_at"]},
        ),
    ]
