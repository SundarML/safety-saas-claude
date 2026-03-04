from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_customuser_access_expires_at_customuser_company_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="employee_id",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddConstraint(
            model_name="customuser",
            constraint=models.UniqueConstraint(
                condition=models.Q(employee_id__gt=""),
                fields=["organization", "employee_id"],
                name="unique_employee_id_per_org",
            ),
        ),
    ]
