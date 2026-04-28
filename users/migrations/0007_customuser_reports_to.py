from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_worker_pin'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='reports_to',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='direct_reports',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
