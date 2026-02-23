"""
Unit tests for the permits app.
Covers: Permit model (auto permit_number, is_overdue, duration_hours, __str__),
PermitRequestForm, PermitApprovalForm, PermitActivateForm, PermitCloseForm.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Organization, Plan
from observations.models import Location
from permits.forms import (
    PermitActivateForm,
    PermitApprovalForm,
    PermitCloseForm,
    PermitRequestForm,
)
from permits.models import Permit

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_trial_plan():
    plan, _ = Plan.objects.get_or_create(name="Trial", defaults={"price_monthly": 0})
    return plan


def create_org_and_user(domain="permitorg"):
    create_trial_plan()
    org = Organization.objects.create(name="Test Org", domain=domain)
    user = User.objects.create_user(
        email=f"mgr@{domain}.com",
        password="pass1234",
        organization=org,
        role="manager",
    )
    return org, user


def make_permit(org, user, location, **overrides):
    """Create a Permit with sensible defaults, allowing field overrides."""
    now = timezone.now()
    defaults = dict(
        organization=org,
        work_type="hot_work",
        title="Welding Job",
        description="Welding pipes in the boiler room.",
        location=location,
        requestor=user,
        planned_start=now + timedelta(hours=1),
        planned_end=now + timedelta(hours=5),
        hazards_identified="Fire, sparks, heat.",
        risk_controls="Fire extinguisher present, hot-work permit displayed.",
    )
    defaults.update(overrides)
    return Permit.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Permit model — auto permit_number
# ---------------------------------------------------------------------------

class PermitNumberGenerationTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user()
        self.location = Location.objects.create(organization=self.org, name="Boiler Room")

    def test_permit_number_is_generated_on_create(self):
        permit = make_permit(self.org, self.user, self.location)
        self.assertIsNotNone(permit.permit_number)
        self.assertTrue(permit.permit_number.startswith("PTW-"))

    def test_permit_number_follows_format_ptw_yyyymmdd_seq(self):
        permit = make_permit(self.org, self.user, self.location)
        parts = permit.permit_number.split("-")
        self.assertEqual(parts[0], "PTW")
        self.assertEqual(len(parts[1]), 8)   # YYYYMMDD
        self.assertEqual(len(parts[2]), 4)   # zero-padded 4-digit sequence

    def test_permit_number_starts_at_0001(self):
        permit = make_permit(self.org, self.user, self.location)
        seq = int(permit.permit_number.split("-")[-1])
        self.assertEqual(seq, 1)

    def test_sequential_permits_have_unique_numbers(self):
        p1 = make_permit(self.org, self.user, self.location, title="Job A")
        p2 = make_permit(self.org, self.user, self.location, title="Job B")
        self.assertNotEqual(p1.permit_number, p2.permit_number)

    def test_sequential_permits_increment_by_one(self):
        p1 = make_permit(self.org, self.user, self.location, title="Job A")
        p2 = make_permit(self.org, self.user, self.location, title="Job B")
        seq1 = int(p1.permit_number.split("-")[-1])
        seq2 = int(p2.permit_number.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_permit_number_not_changed_on_re_save(self):
        permit = make_permit(self.org, self.user, self.location)
        original_number = permit.permit_number
        permit.title = "Updated Title"
        permit.save()
        permit.refresh_from_db()
        self.assertEqual(permit.permit_number, original_number)


# ---------------------------------------------------------------------------
# Permit model — default status
# ---------------------------------------------------------------------------

class PermitDefaultStatusTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user(domain="statusorg")
        self.location = Location.objects.create(organization=self.org, name="Site")

    def test_default_status_is_draft(self):
        permit = make_permit(self.org, self.user, self.location)
        self.assertEqual(permit.status, "DRAFT")


# ---------------------------------------------------------------------------
# Permit model — is_overdue property
# ---------------------------------------------------------------------------

class PermitIsOverdueTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user(domain="overdueorg")
        self.location = Location.objects.create(organization=self.org, name="Site")
        self.now = timezone.now()

    def _permit_with_past_end(self, status):
        permit = make_permit(
            self.org, self.user, self.location,
            planned_start=self.now - timedelta(hours=10),
            planned_end=self.now - timedelta(hours=1),
        )
        Permit.objects.filter(pk=permit.pk).update(status=status)
        permit.refresh_from_db()
        return permit

    def test_is_overdue_true_when_approved_and_planned_end_in_past(self):
        permit = self._permit_with_past_end("APPROVED")
        self.assertTrue(permit.is_overdue)

    def test_is_overdue_true_when_active_and_planned_end_in_past(self):
        permit = self._permit_with_past_end("ACTIVE")
        self.assertTrue(permit.is_overdue)

    def test_is_overdue_false_when_draft_even_if_planned_end_in_past(self):
        permit = self._permit_with_past_end("DRAFT")
        self.assertFalse(permit.is_overdue)

    def test_is_overdue_false_when_closed(self):
        permit = self._permit_with_past_end("CLOSED")
        self.assertFalse(permit.is_overdue)

    def test_is_overdue_false_when_approved_but_planned_end_in_future(self):
        permit = make_permit(
            self.org, self.user, self.location,
            planned_start=self.now + timedelta(hours=1),
            planned_end=self.now + timedelta(hours=5),
        )
        Permit.objects.filter(pk=permit.pk).update(status="APPROVED")
        permit.refresh_from_db()
        self.assertFalse(permit.is_overdue)


# ---------------------------------------------------------------------------
# Permit model — duration_hours property
# ---------------------------------------------------------------------------

class PermitDurationHoursTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user(domain="durationorg")
        self.location = Location.objects.create(organization=self.org, name="Site")
        self.now = timezone.now()

    def test_duration_exact_hours(self):
        permit = make_permit(
            self.org, self.user, self.location,
            planned_start=self.now,
            planned_end=self.now + timedelta(hours=4),
        )
        self.assertEqual(permit.duration_hours, 4.0)

    def test_duration_with_partial_hours(self):
        permit = make_permit(
            self.org, self.user, self.location,
            planned_start=self.now,
            planned_end=self.now + timedelta(hours=2, minutes=30),
        )
        self.assertEqual(permit.duration_hours, 2.5)

    def test_duration_one_hour(self):
        permit = make_permit(
            self.org, self.user, self.location,
            planned_start=self.now,
            planned_end=self.now + timedelta(hours=1),
        )
        self.assertEqual(permit.duration_hours, 1.0)


# ---------------------------------------------------------------------------
# Permit model — __str__
# ---------------------------------------------------------------------------

class PermitStrTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user(domain="strorg")
        self.location = Location.objects.create(organization=self.org, name="Site")

    def test_str_contains_permit_number(self):
        permit = make_permit(self.org, self.user, self.location)
        self.assertIn(permit.permit_number, str(permit))

    def test_str_contains_work_type_display(self):
        permit = make_permit(self.org, self.user, self.location, work_type="hot_work")
        self.assertIn("Hot Work", str(permit))

    def test_str_contains_title(self):
        permit = make_permit(self.org, self.user, self.location, title="Boiler Repair")
        self.assertIn("Boiler Repair", str(permit))


# ---------------------------------------------------------------------------
# PermitRequestForm
# ---------------------------------------------------------------------------

class PermitRequestFormTests(TestCase):

    def setUp(self):
        create_trial_plan()
        self.org = Organization.objects.create(name="Form Org", domain="reqformorg")
        self.user = User.objects.create_user(
            email="req@reqformorg.com", password="pass", organization=self.org
        )
        self.location = Location.objects.create(organization=self.org, name="Site A")

    def _valid_data(self):
        now = timezone.now()
        return {
            "work_type": "hot_work",
            "title": "Welding pipes",
            "description": "Pipe welding in boiler room.",
            "location": self.location.pk,
            "work_area": "Boiler Room B",
            "workers_count": 2,
            "planned_start": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "planned_end": (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
            "hazards_identified": "Fire, sparks",
            "risk_controls": "Fire extinguisher nearby",
        }

    def test_valid_form(self):
        form = PermitRequestForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_end_before_start_is_invalid(self):
        now = timezone.now()
        data = self._valid_data()
        data["planned_start"] = (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M")
        data["planned_end"] = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        form = PermitRequestForm(data=data)
        self.assertFalse(form.is_valid())

    def test_end_equal_to_start_is_invalid(self):
        now = timezone.now()
        same_time = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        data = self._valid_data()
        data["planned_start"] = same_time
        data["planned_end"] = same_time
        form = PermitRequestForm(data=data)
        self.assertFalse(form.is_valid())

    def test_missing_required_field_title(self):
        data = self._valid_data()
        del data["title"]
        form = PermitRequestForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_missing_hazards_is_invalid(self):
        data = self._valid_data()
        del data["hazards_identified"]
        form = PermitRequestForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("hazards_identified", form.errors)


# ---------------------------------------------------------------------------
# PermitApprovalForm
# ---------------------------------------------------------------------------

class PermitApprovalFormTests(TestCase):

    def test_approve_decision_is_valid(self):
        form = PermitApprovalForm(data={
            "decision": "approve",
            "approval_comment": "All checks passed.",
            "rejection_reason": "",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_reject_with_reason_is_valid(self):
        form = PermitApprovalForm(data={
            "decision": "reject",
            "approval_comment": "",
            "rejection_reason": "Gas test results missing.",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_reject_without_reason_is_invalid(self):
        form = PermitApprovalForm(data={
            "decision": "reject",
            "approval_comment": "",
            "rejection_reason": "",
        })
        self.assertFalse(form.is_valid())

    def test_approve_without_comment_is_valid(self):
        form = PermitApprovalForm(data={
            "decision": "approve",
            "approval_comment": "",
            "rejection_reason": "",
        })
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# PermitActivateForm
# ---------------------------------------------------------------------------

class PermitActivateFormTests(TestCase):

    def test_valid_activate_form(self):
        form = PermitActivateForm(data={
            "actual_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_actual_start_is_invalid(self):
        form = PermitActivateForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn("actual_start", form.errors)


# ---------------------------------------------------------------------------
# PermitCloseForm
# ---------------------------------------------------------------------------

class PermitCloseFormTests(TestCase):

    def test_valid_close_form_with_site_restored(self):
        form = PermitCloseForm(data={
            "actual_end": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "closure_comment": "Work completed safely.",
            "site_restored": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_close_without_site_restored_is_invalid(self):
        form = PermitCloseForm(data={
            "actual_end": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "closure_comment": "Done.",
            "site_restored": False,
        })
        self.assertFalse(form.is_valid())

    def test_close_with_site_restored_false_and_no_comment_is_invalid(self):
        form = PermitCloseForm(data={
            "actual_end": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "closure_comment": "",
            "site_restored": False,
        })
        self.assertFalse(form.is_valid())

    def test_closure_comment_is_optional(self):
        form = PermitCloseForm(data={
            "actual_end": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "closure_comment": "",
            "site_restored": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
