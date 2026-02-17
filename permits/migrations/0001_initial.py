# permits/migrations/0001_initial.py
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0004_plan_alter_subscription_plan"),
        ("observations", "0002_location_organization"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Permit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("permit_number", models.CharField(editable=False, max_length=30, unique=True)),
                ("work_type", models.CharField(
                    choices=[
                        ("hot_work",            "Hot Work"),
                        ("confined_space",      "Confined Space Entry"),
                        ("electrical",          "Electrical Work"),
                        ("excavation",          "Excavation"),
                        ("lifting_rigging",     "Lifting & Rigging"),
                        ("work_at_height",      "Work at Height"),
                        ("breaking_containment","Breaking Containment / Isolation"),
                        ("general",             "General High-Risk Work"),
                    ],
                    max_length=30,
                )),
                ("title",       models.CharField(max_length=255)),
                ("description", models.TextField()),
                ("work_area",   models.CharField(blank=True, max_length=255)),
                ("contractor_name",    models.CharField(blank=True, max_length=255)),
                ("contractor_contact", models.CharField(blank=True, max_length=100)),
                ("workers_count",      models.PositiveIntegerField(default=1)),
                ("planned_start", models.DateTimeField()),
                ("planned_end",   models.DateTimeField()),
                ("actual_start",  models.DateTimeField(blank=True, null=True)),
                ("actual_end",    models.DateTimeField(blank=True, null=True)),
                ("hazards_identified",  models.TextField()),
                ("risk_controls",       models.TextField()),
                ("ppe_required",        models.TextField(blank=True)),
                ("isolation_required",  models.BooleanField(default=False)),
                ("isolation_details",   models.TextField(blank=True)),
                ("emergency_procedure", models.TextField(blank=True)),
                ("toolbox_talk_done",   models.BooleanField(default=False)),
                ("area_barricaded",     models.BooleanField(default=False)),
                ("equipment_inspected", models.BooleanField(default=False)),
                ("gas_test_done",       models.BooleanField(default=False)),
                ("gas_test_result",     models.CharField(blank=True, max_length=100)),
                ("approval_comment",  models.TextField(blank=True)),
                ("rejection_reason",  models.TextField(blank=True)),
                ("approved_at",       models.DateTimeField(blank=True, null=True)),
                ("closure_comment",   models.TextField(blank=True)),
                ("site_restored",     models.BooleanField(default=False)),
                ("closed_at",         models.DateTimeField(blank=True, null=True)),
                ("attachment", models.FileField(blank=True, null=True,
                                                upload_to="permits/attachments/")),
                ("status",     models.CharField(
                    choices=[
                        ("DRAFT",     "Draft"),
                        ("SUBMITTED", "Submitted"),
                        ("APPROVED",  "Approved"),
                        ("ACTIVE",    "Active"),
                        ("CLOSED",    "Closed"),
                        ("REJECTED",  "Rejected"),
                        ("CANCELLED", "Cancelled"),
                    ],
                    default="DRAFT", max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="permits",
                    to="core.organization",
                )),
                ("location", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="permits",
                    to="observations.location",
                )),
                ("requestor", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="permits_requested",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("approved_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="permits_approved",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="permits_closed",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
