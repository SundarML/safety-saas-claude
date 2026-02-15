# Phase 2 migration: add organization FK to Location
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('observations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='locations',
                to='core.organization',
            ),
        ),
    ]
