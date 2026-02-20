# users/migrations/0002_contractor_fields.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="is_contractor",
            field=models.BooleanField(
                default=False,
                help_text="Contractor user — limited to Permits module only",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="contractor_company",
            field=models.CharField(
                blank=True,
                max_length=255,
                help_text="Contractor company name (auto-populated in permits)",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="contractor_phone",
            field=models.CharField(
                blank=True,
                max_length=50,
                help_text="Contractor contact phone",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="contractor_access_expiry",
            field=models.DateField(
                blank=True,
                null=True,
                help_text="Contractor account expires on this date (optional)",
            ),
        ),
    ]
