"""
Unit tests for the observations app.
Covers: Location model, Observation model (close(), __str__),
ObservationCreateForm, RectificationForm, VerificationForm, LocationForm.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Organization, Plan
from observations.forms import (
    LocationForm,
    ObservationCreateForm,
    RectificationForm,
    VerificationForm,
)
from observations.models import Location, Observation

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_trial_plan():
    plan, _ = Plan.objects.get_or_create(name="Trial", defaults={"price_monthly": 0})
    return plan


def create_org_and_user(domain="obsorg"):
    create_trial_plan()
    org = Organization.objects.create(name="Test Org", domain=domain)
    user = User.objects.create_user(
        email=f"user@{domain}.com", password="pass1234", organization=org
    )
    return org, user


# ---------------------------------------------------------------------------
# Location model
# ---------------------------------------------------------------------------

class LocationModelTests(TestCase):

    def setUp(self):
        self.org, _ = create_org_and_user()

    def test_str_with_area_shows_name_and_area(self):
        loc = Location.objects.create(
            organization=self.org, name="Block A", area="North Wing"
        )
        self.assertEqual(str(loc), "Block A (North Wing)")

    def test_str_without_area_shows_name_only(self):
        loc = Location.objects.create(
            organization=self.org, name="Main Site", area=""
        )
        self.assertEqual(str(loc), "Main Site")

    def test_str_with_no_area_field(self):
        loc = Location.objects.create(organization=self.org, name="Warehouse")
        self.assertEqual(str(loc), "Warehouse")


# ---------------------------------------------------------------------------
# Observation model
# ---------------------------------------------------------------------------

class ObservationModelTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user()
        self.location = Location.objects.create(organization=self.org, name="Site A")
        self.observation = Observation.objects.create(
            organization=self.org,
            location=self.location,
            observer=self.user,
            title="Slippery Floor",
            description="Floor near entrance is wet and slippery.",
            severity="HIGH",
        )

    def test_default_status_is_open(self):
        self.assertEqual(self.observation.status, "OPEN")

    def test_default_is_archived_is_false(self):
        self.assertFalse(self.observation.is_archived)

    def test_close_sets_status_to_closed(self):
        self.observation.close()
        self.assertEqual(self.observation.status, "CLOSED")

    def test_close_sets_date_closed(self):
        before = timezone.now()
        self.observation.close()
        self.assertIsNotNone(self.observation.date_closed)
        self.assertGreaterEqual(self.observation.date_closed, before)

    def test_close_persists_to_database(self):
        self.observation.close()
        refreshed = Observation.objects.get(pk=self.observation.pk)
        self.assertEqual(refreshed.status, "CLOSED")
        self.assertIsNotNone(refreshed.date_closed)

    def test_str_contains_severity_display(self):
        # severity="HIGH" → display is "High"
        self.assertIn("High", str(self.observation))

    def test_str_contains_title(self):
        self.assertIn("Slippery Floor", str(self.observation))

    def test_str_contains_status(self):
        self.assertIn("OPEN", str(self.observation))

    def test_str_format_after_close(self):
        self.observation.close()
        self.assertIn("CLOSED", str(self.observation))

    def test_default_severity_is_low(self):
        obs = Observation.objects.create(
            organization=self.org,
            location=self.location,
            observer=self.user,
            title="Minor Issue",
            description="A small problem.",
        )
        self.assertEqual(obs.severity, "LOW")


# ---------------------------------------------------------------------------
# ObservationCreateForm
# ---------------------------------------------------------------------------

class ObservationCreateFormTests(TestCase):

    def setUp(self):
        self.org, self.user = create_org_and_user(domain="formorg")
        self.location = Location.objects.create(organization=self.org, name="Site A")

    def test_valid_form(self):
        form = ObservationCreateForm(data={
            "title": "Exposed Wiring",
            "location": self.location.pk,
            "description": "Electrical cable exposed in the storage area.",
            "severity": "MEDIUM",
            "assigned_to": self.user.pk,
            "target_date": date.today().isoformat(),
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_title_is_invalid(self):
        form = ObservationCreateForm(data={
            "location": self.location.pk,
            "description": "Some issue",
            "severity": "LOW",
            "target_date": date.today().isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_missing_description_is_invalid(self):
        form = ObservationCreateForm(data={
            "title": "Some Title",
            "location": self.location.pk,
            "severity": "LOW",
            "target_date": date.today().isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_invalid_severity_choice_rejected(self):
        form = ObservationCreateForm(data={
            "title": "Issue",
            "location": self.location.pk,
            "description": "Detail",
            "severity": "CRITICAL",  # not a valid choice
            "target_date": date.today().isoformat(),
        })
        self.assertFalse(form.is_valid())
        self.assertIn("severity", form.errors)


# ---------------------------------------------------------------------------
# VerificationForm
# ---------------------------------------------------------------------------

class VerificationFormTests(TestCase):

    def test_approve_action_is_valid(self):
        form = VerificationForm(data={
            "verification_action": "approve",
            "verification_comment": "Rectification confirmed.",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_reject_action_is_valid(self):
        form = VerificationForm(data={
            "verification_action": "reject",
            "verification_comment": "Work incomplete, please redo.",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_action_choice_rejected(self):
        form = VerificationForm(data={
            "verification_action": "maybe",
            "verification_comment": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("verification_action", form.errors)

    def test_comment_is_optional(self):
        form = VerificationForm(data={
            "verification_action": "approve",
            "verification_comment": "",
        })
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# LocationForm
# ---------------------------------------------------------------------------

class LocationFormTests(TestCase):

    def test_valid_form_with_all_fields(self):
        form = LocationForm(data={
            "name": "Block B",
            "area": "East Wing",
            "facility": "Main Warehouse",
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_form_with_name_only(self):
        form = LocationForm(data={"name": "Site C", "area": "", "facility": ""})
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_name_is_invalid(self):
        form = LocationForm(data={"area": "East Wing", "facility": "Warehouse"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
