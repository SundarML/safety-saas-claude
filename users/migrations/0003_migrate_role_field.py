"""
Migration: Replace 4 boolean role flags with a single `role` CharField.

Data migration logic:
  - is_manager=True       → role="manager"
  - is_safety_manager=True → role="safety_manager"
  - is_action_owner=True  → role="action_owner"
  - is_observer=True / default → role="observer"

Priority order (if somehow multiple flags were set): manager > safety_manager > action_owner > observer
"""
from django.db import migrations, models


def forwards_migrate_roles(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    for user in CustomUser.objects.all():
        if user.is_manager:
            user.role = "manager"
        elif user.is_safety_manager:
            user.role = "safety_manager"
        elif user.is_action_owner:
            user.role = "action_owner"
        else:
            user.role = "observer"
        user.save(update_fields=["role"])


def backwards_restore_flags(apps, schema_editor):
    CustomUser = apps.get_model("users", "CustomUser")
    for user in CustomUser.objects.all():
        user.is_manager = user.role == "manager"
        user.is_safety_manager = user.role == "safety_manager"
        user.is_action_owner = user.role == "action_owner"
        user.is_observer = user.role in ("observer", "")
        user.save(update_fields=["is_manager", "is_safety_manager", "is_action_owner", "is_observer"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_customuser_full_name_alter_customuser_organization"),
    ]

    operations = [
        # 1. Add the new role field (nullable first so existing rows don't fail)
        migrations.AddField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("manager", "Manager"),
                    ("safety_manager", "Safety Manager"),
                    ("action_owner", "Action Owner"),
                    ("observer", "Observer"),
                ],
                default="observer",
            ),
        ),

        # 2. Populate role from the old boolean flags
        migrations.RunPython(forwards_migrate_roles, backwards_restore_flags),

        # 3. Remove the old boolean flag fields
        migrations.RemoveField(model_name="customuser", name="is_manager"),
        migrations.RemoveField(model_name="customuser", name="is_safety_manager"),
        migrations.RemoveField(model_name="customuser", name="is_action_owner"),
        migrations.RemoveField(model_name="customuser", name="is_observer"),
    ]
