from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("hira", "0001_initial"),
        ("observations", "0001_initial"),
        ("compliance", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="hazard",
            name="linked_observations",
            field=models.ManyToManyField(
                blank=True,
                related_name="linked_hazards",
                to="observations.observation",
            ),
        ),
        migrations.AddField(
            model_name="hazard",
            name="compliance_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="hira_hazards",
                to="compliance.complianceitem",
            ),
        ),
    ]
