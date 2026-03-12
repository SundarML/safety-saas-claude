from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0008_demorequest_status_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComplianceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=300)),
                ("law", models.CharField(blank=True, help_text="e.g. Factories Act 1948, Section 6", max_length=300)),
                ("authority", models.CharField(blank=True, help_text="e.g. Chief Inspector of Factories", max_length=200)),
                ("frequency", models.CharField(
                    choices=[
                        ("one_time", "One-time"),
                        ("monthly", "Monthly"),
                        ("quarterly", "Quarterly"),
                        ("half_yearly", "Half-yearly"),
                        ("annual", "Annual"),
                    ],
                    default="annual", max_length=20,
                )),
                ("due_date", models.DateField()),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"),
                        ("complied", "Complied"),
                        ("overdue", "Overdue"),
                        ("not_applicable", "Not Applicable"),
                    ],
                    default="pending", max_length=20,
                )),
                ("evidence", models.FileField(blank=True, null=True, upload_to="compliance_evidence/")),
                ("notes", models.TextField(blank=True)),
                ("complied_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="compliance_assigned", to=settings.AUTH_USER_MODEL,
                )),
                ("created_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="compliance_created", to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="compliance_items", to="core.organization",
                )),
            ],
            options={"ordering": ["due_date"]},
        ),
    ]
