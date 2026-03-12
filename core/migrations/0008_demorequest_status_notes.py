from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_organization_logo"),
    ]

    operations = [
        migrations.AddField(
            model_name="demorequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("contacted", "Contacted"),
                    ("scheduled", "Demo Scheduled"),
                    ("done", "Done"),
                    ("dropped", "Dropped"),
                ],
                default="new",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="demorequest",
            name="notes",
            field=models.TextField(
                blank=True,
                help_text="Internal notes — not visible to the requester",
            ),
        ),
        migrations.AddField(
            model_name="demorequest",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
