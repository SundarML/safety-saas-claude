from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("core", "0008_demorequest_status_notes"),
        ("hira", "0002_phase2"),
        ("observations", "0003_alter_location_options"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HoursWorked",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("year",  models.PositiveSmallIntegerField()),
                ("month", models.PositiveSmallIntegerField()),
                ("hours", models.DecimalField(max_digits=10, decimal_places=1)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="hours_worked", to="core.organization",
                )),
            ],
            options={"ordering": ["year", "month"], "unique_together": {("organization", "year", "month")}},
        ),
        migrations.CreateModel(
            name="Incident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("reference_no",    models.CharField(blank=True, editable=False, max_length=20)),
                ("incident_type",   models.CharField(
                    choices=[("injury","Injury"),("near_miss","Near-Miss"),
                             ("dangerous_occurrence","Dangerous Occurrence"),
                             ("property_damage","Property Damage"),
                             ("environmental","Environmental"),
                             ("occ_illness","Occupational Illness")],
                    default="near_miss", max_length=25,
                )),
                ("severity", models.CharField(
                    choices=[("fatality","Fatality"),("lti","Lost Time Injury (LTI)"),
                             ("mtc","Medical Treatment Case (MTC)"),
                             ("fac","First Aid Case (FAC)"),
                             ("near_miss","Near-Miss"),
                             ("property","Property / Equipment Damage")],
                    default="near_miss", max_length=15,
                )),
                ("status", models.CharField(
                    choices=[("reported","Reported"),("under_investigation","Under Investigation"),
                             ("action_required","Action Required"),("closed","Closed")],
                    default="reported", max_length=25,
                )),
                ("title",               models.CharField(max_length=300)),
                ("description",         models.TextField()),
                ("immediate_cause",     models.TextField(blank=True)),
                ("contributing_factors",models.TextField(blank=True)),
                ("date_occurred",       models.DateTimeField(default=django.utils.timezone.now)),
                ("location_text",       models.CharField(blank=True, max_length=200)),
                ("injured_person_name", models.CharField(blank=True, max_length=200)),
                ("injured_person_type", models.CharField(
                    blank=True,
                    choices=[("employee","Employee"),("contractor","Contractor"),
                             ("visitor","Visitor"),("public","Public")],
                    default="employee", max_length=15,
                )),
                ("body_part_affected",  models.CharField(
                    blank=True,
                    choices=[("head","Head / Skull"),("eye","Eye"),("neck","Neck"),
                             ("shoulder","Shoulder / Arm"),("hand_wrist","Hand / Wrist / Fingers"),
                             ("back","Back / Spine"),("chest","Chest / Torso"),
                             ("leg_knee","Leg / Knee"),("foot_ankle","Foot / Ankle / Toes"),
                             ("multiple","Multiple Areas"),("other","Other")],
                    max_length=20,
                )),
                ("days_lost",           models.PositiveIntegerField(default=0)),
                ("property_damage_est", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("first_aid_given",     models.BooleanField(default=False)),
                ("emergency_services",  models.BooleanField(default=False)),
                ("photo_1",             models.ImageField(blank=True, null=True, upload_to="incidents/photos/")),
                ("photo_2",             models.ImageField(blank=True, null=True, upload_to="incidents/photos/")),
                ("investigation_date",  models.DateField(blank=True, null=True)),
                ("rca_why_1",           models.TextField(blank=True)),
                ("rca_why_2",           models.TextField(blank=True)),
                ("rca_why_3",           models.TextField(blank=True)),
                ("rca_why_4",           models.TextField(blank=True)),
                ("rca_why_5",           models.TextField(blank=True)),
                ("rca_root_cause",      models.TextField(blank=True)),
                ("preventive_measures", models.TextField(blank=True)),
                ("closed_at",           models.DateTimeField(blank=True, null=True)),
                ("created_at",          models.DateTimeField(auto_now_add=True)),
                ("updated_at",          models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="incidents", to="core.organization",
                )),
                ("reported_by", models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="incidents_reported", to=settings.AUTH_USER_MODEL,
                )),
                ("investigated_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="incidents_investigated", to=settings.AUTH_USER_MODEL,
                )),
                ("closed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="incidents_closed", to=settings.AUTH_USER_MODEL,
                )),
                ("location", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="incidents", to="observations.location",
                )),
                ("linked_hazard", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="incidents", to="hira.hazard",
                )),
                ("source_observation", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="converted_incidents", to="observations.observation",
                )),
            ],
            options={"ordering": ["-date_occurred"]},
        ),
    ]
