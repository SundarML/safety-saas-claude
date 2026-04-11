# actions/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="hira.Hazard")
def sync_hira_corrective_action(sender, instance, created, **kwargs):
    """
    When a Hazard with action_required=True is saved, ensure a CorrectiveAction exists.
    When action_required is set back to False, leave the action in place (don't delete).
    """
    from .models import CorrectiveAction

    hazard = instance

    if not hazard.action_required:
        return  # Nothing to do — action already exists or was never needed

    # Determine priority from hazard's effective risk level
    level_to_priority = {
        "critical": CorrectiveAction.PRIORITY_CRITICAL,
        "high":     CorrectiveAction.PRIORITY_HIGH,
        "medium":   CorrectiveAction.PRIORITY_MEDIUM,
        "low":      CorrectiveAction.PRIORITY_LOW,
    }
    priority = level_to_priority.get(
        hazard.effective_risk_level, CorrectiveAction.PRIORITY_MEDIUM
    )

    title = f"[HIRA] {hazard.hazard_description[:200]}"

    existing = CorrectiveAction.objects.filter(
        source_hira=hazard,
        source_module=CorrectiveAction.SOURCE_HIRA,
    ).first()

    if existing:
        # Sync fields that may have changed in the hazard edit
        changed = False
        if existing.assigned_to_id != (hazard.action_owner_id or None):
            existing.assigned_to_id = hazard.action_owner_id
            changed = True
        if hazard.action_due_date and existing.due_date != hazard.action_due_date:
            existing.due_date = hazard.action_due_date
            changed = True
        if existing.priority != priority:
            existing.priority = priority
            changed = True
        if changed:
            existing.save(update_fields=["assigned_to_id", "due_date", "priority", "updated_at"])
    else:
        # Create a new CorrectiveAction for this hazard
        CorrectiveAction.objects.create(
            organization    = hazard.register.organization,
            title           = title,
            description     = (
                f"Hazard: {hazard.hazard_description}\n"
                f"Potential harm: {hazard.potential_harm}\n"
                f"Controls: {hazard.controls_description}"
            ),
            priority        = priority,
            source_module   = CorrectiveAction.SOURCE_HIRA,
            source_hira     = hazard,
            raised_by       = hazard.register.assessed_by,
            assigned_to     = hazard.action_owner,
            due_date        = hazard.action_due_date,
        )
