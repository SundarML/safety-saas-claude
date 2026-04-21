from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("training", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingmodule",
            name="content_url",
            field=models.URLField(
                blank=True,
                help_text="YouTube video, Google Drive file, or Google Slides presentation link.",
            ),
        ),
    ]
