# Generated migration for Phase 1 fixes
# - Adds full_name field to CustomUser
# - Changes organization FK to SET_NULL (was CASCADE)

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='full_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='customuser',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='core.organization',
            ),
        ),
    ]
