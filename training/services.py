from django.db import transaction
from django.utils import timezone

from .models import AssessmentAttempt, SkillProficiency


def handle_assessment_submission(user, assessment, submitted_answers: dict) -> AssessmentAttempt:
    """
    Process a completed assessment submission.

    Args:
        user: The CustomUser instance taking the assessment.
        assessment: The Assessment model instance.
        submitted_answers: dict mapping str(question_id) → str(choice_id),
                           e.g. {"1": "3", "2": "7"}.

    Returns:
        AssessmentAttempt instance with score and passed status set.

    Rules:
        - Score = (correct answers / total questions) * 100
        - Passed = score >= assessment.passing_score
        - On pass: SkillProficiency is created or upgraded (never downgraded).
    """
    questions = assessment.questions.prefetch_related("choices").all()
    total = questions.count()

    if total == 0:
        raise ValueError("This assessment has no questions yet.")

    correct = 0
    answers_snapshot = {}

    for question in questions:
        chosen_id_str = submitted_answers.get(str(question.id))
        if chosen_id_str:
            try:
                chosen_id = int(chosen_id_str)
                answers_snapshot[str(question.id)] = chosen_id
                if question.choices.filter(id=chosen_id, is_correct=True).exists():
                    correct += 1
            except (ValueError, TypeError):
                pass

    score = round((correct / total) * 100, 1)
    passed = score >= assessment.passing_score

    with transaction.atomic():
        attempt = AssessmentAttempt.objects.create(
            organization=user.organization,
            user=user,
            assessment=assessment,
            score=score,
            passed=passed,
            answers=answers_snapshot,
        )

        # Only update skill proficiency on a passing attempt
        if passed and assessment.skill:
            proficiency, created = SkillProficiency.objects.select_for_update().get_or_create(
                user=user,
                skill=assessment.skill,
                defaults={
                    "organization": user.organization,
                    "level": assessment.grants_proficiency_level,
                    "last_assessed_at": timezone.now(),
                },
            )
            if not created and assessment.grants_proficiency_level > proficiency.level:
                # Upgrade only — never downgrade an existing proficiency
                proficiency.level = assessment.grants_proficiency_level
                proficiency.last_assessed_at = timezone.now()
                proficiency.save(update_fields=["level", "last_assessed_at"])

    return attempt
