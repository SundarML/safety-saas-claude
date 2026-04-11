from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0008_demorequest_status_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HazardRegister",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title",            models.CharField(max_length=300)),
                ("activity",         models.CharField(help_text="Job / task / work area being assessed", max_length=300)),
                ("location_text",    models.CharField(blank=True, max_length=200)),
                ("assessment_date",  models.DateField(default=django.utils.timezone.now)),
                ("next_review_date", models.DateField(blank=True, null=True)),
                ("status",           models.CharField(
                    choices=[
                        ("draft",        "Draft"),
                        ("under_review", "Under Review"),
                        ("approved",     "Approved"),
                        ("expired",      "Expired"),
                    ],
                    default="draft", max_length=20,
                )),
                ("approved_at",  models.DateTimeField(blank=True, null=True)),
                ("revision_no",  models.PositiveSmallIntegerField(default=1)),
                ("created_at",   models.DateTimeField(auto_now_add=True)),
                ("updated_at",   models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="hazard_registers",
                    to="core.organization",
                )),
                ("assessed_by",  models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hira_assessed", to=settings.AUTH_USER_MODEL,
                )),
                ("approved_by",  models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hira_approved", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-assessment_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="Hazard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order",               models.PositiveSmallIntegerField(default=0)),
                ("category",            models.CharField(
                    choices=[
                        ("physical",          "Physical"),
                        ("chemical",          "Chemical"),
                        ("biological",        "Biological"),
                        ("ergonomic",         "Ergonomic"),
                        ("electrical",        "Electrical"),
                        ("fire_explosion",    "Fire / Explosion"),
                        ("working_at_height", "Working at Height"),
                        ("confined_space",    "Confined Space"),
                        ("mechanical",        "Mechanical"),
                        ("psychosocial",      "Psychosocial"),
                        ("environmental",     "Environmental"),
                        ("other",             "Other"),
                    ],
                    default="physical", max_length=30,
                )),
                ("hazard_description",  models.TextField(help_text="Describe the hazard source or situation")),
                ("potential_harm",      models.TextField(help_text="Injury / illness / consequence that could result")),
                ("who_might_be_harmed", models.CharField(
                    choices=[
                        ("all_personnel", "All Personnel"),
                        ("workers",       "Workers"),
                        ("contractors",   "Contractors"),
                        ("visitors",      "Visitors"),
                        ("public",        "Public"),
                    ],
                    default="all_personnel", max_length=20,
                )),
                ("initial_likelihood",   models.PositiveSmallIntegerField(
                    choices=[(1,"1 – Rare"),(2,"2 – Unlikely"),(3,"3 – Possible"),(4,"4 – Likely"),(5,"5 – Almost Certain")],
                    default=3,
                )),
                ("initial_severity",     models.PositiveSmallIntegerField(
                    choices=[(1,"1 – Insignificant"),(2,"2 – Minor"),(3,"3 – Moderate"),(4,"4 – Major"),(5,"5 – Catastrophic")],
                    default=3,
                )),
                ("primary_control_type", models.CharField(
                    choices=[
                        ("elimination",    "Elimination"),
                        ("substitution",   "Substitution"),
                        ("engineering",    "Engineering Controls"),
                        ("administrative", "Administrative Controls"),
                        ("ppe",            "PPE"),
                    ],
                    default="administrative", max_length=20,
                )),
                ("controls_description", models.TextField(help_text="Describe controls in place or planned (one per line)")),
                ("residual_likelihood",  models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    choices=[(1,"1 – Rare"),(2,"2 – Unlikely"),(3,"3 – Possible"),(4,"4 – Likely"),(5,"5 – Almost Certain")],
                )),
                ("residual_severity",    models.PositiveSmallIntegerField(
                    blank=True, null=True,
                    choices=[(1,"1 – Insignificant"),(2,"2 – Minor"),(3,"3 – Moderate"),(4,"4 – Major"),(5,"5 – Catastrophic")],
                )),
                ("action_required",  models.BooleanField(default=False)),
                ("action_due_date",  models.DateField(blank=True, null=True)),
                ("register",         models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="hazards", to="hira.hazardregister",
                )),
                ("action_owner",     models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="hira_actions", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["order", "id"]},
        ),
    ]
