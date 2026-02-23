"""
Unit tests for the core app.
Covers: Organization, Plan, Subscription, UserInvite, DemoRequest models;
OrganizationSignupForm, AcceptInviteForm; OrganizationMiddleware,
SubscriptionMiddleware; org_required guard; create_trial_subscription signal;
downgrade_expired_subscriptions management command.
"""
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.forms import AcceptInviteForm, OrganizationSignupForm
from core.middleware import OrganizationMiddleware, SubscriptionMiddleware
from core.models import DemoRequest, Organization, Plan, Subscription, UserInvite
from core.utils.guards import org_required

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_trial_plan():
    plan, _ = Plan.objects.get_or_create(name="Trial", defaults={"price_monthly": 0})
    return plan


def create_free_plan():
    plan, _ = Plan.objects.get_or_create(name="Free", defaults={"price_monthly": 0})
    return plan


def create_organization(name="Test Org", domain="testorg"):
    """Create an Organization. Requires Trial plan to exist (signal dependency)."""
    create_trial_plan()
    return Organization.objects.create(name=name, domain=domain)


# ---------------------------------------------------------------------------
# Organization model
# ---------------------------------------------------------------------------

class OrganizationModelTests(TestCase):

    def test_str_returns_name(self):
        org = create_organization(name="Acme Corp", domain="acme")
        self.assertEqual(str(org), "Acme Corp")


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------

class PlanModelTests(TestCase):

    def test_str_returns_name(self):
        plan = Plan.objects.create(name="Enterprise", price_monthly=100)
        self.assertEqual(str(plan), "Enterprise")


# ---------------------------------------------------------------------------
# Subscription model
# ---------------------------------------------------------------------------

class SubscriptionModelTests(TestCase):

    def setUp(self):
        self.trial_plan = create_trial_plan()
        self.org = create_organization()
        self.sub = Subscription.objects.get(organization=self.org)

    def test_is_trial_true_when_plan_is_trial(self):
        self.assertTrue(self.sub.is_trial())

    def test_is_trial_false_when_plan_is_not_trial(self):
        free = create_free_plan()
        self.sub.plan = free
        self.assertFalse(self.sub.is_trial())

    def test_is_expired_false_when_expires_at_is_none(self):
        self.sub.expires_at = None
        self.assertFalse(self.sub.is_expired())

    def test_is_expired_false_when_expires_at_is_in_future(self):
        self.sub.expires_at = timezone.now() + timedelta(days=30)
        self.assertFalse(self.sub.is_expired())

    def test_is_expired_true_when_expires_at_is_in_past(self):
        self.sub.expires_at = timezone.now() - timedelta(days=1)
        self.assertTrue(self.sub.is_expired())

    def test_str_contains_org_name_and_plan(self):
        s = str(self.sub)
        self.assertIn(self.org.name, s)
        self.assertIn("Trial", s)


# ---------------------------------------------------------------------------
# UserInvite model
# ---------------------------------------------------------------------------

class UserInviteModelTests(TestCase):

    def setUp(self):
        self.org = create_organization()

    def test_is_valid_true_when_not_used_and_not_expired(self):
        invite = UserInvite.objects.create(
            organization=self.org,
            email="user@example.com",
            role="observer",
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertTrue(invite.is_valid())

    def test_is_valid_false_when_used(self):
        invite = UserInvite.objects.create(
            organization=self.org,
            email="user@example.com",
            role="observer",
            is_used=True,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertFalse(invite.is_valid())

    def test_is_valid_false_when_expired(self):
        invite = UserInvite.objects.create(
            organization=self.org,
            email="user@example.com",
            role="observer",
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertFalse(invite.is_valid())

    def test_is_valid_true_when_no_expiry_date(self):
        invite = UserInvite.objects.create(
            organization=self.org,
            email="user@example.com",
            role="observer",
            expires_at=None,
        )
        self.assertTrue(invite.is_valid())

    def test_str_contains_email(self):
        invite = UserInvite.objects.create(
            organization=self.org, email="user@example.com", role="observer"
        )
        self.assertIn("user@example.com", str(invite))


# ---------------------------------------------------------------------------
# DemoRequest model
# ---------------------------------------------------------------------------

class DemoRequestModelTests(TestCase):

    def test_str_returns_name_and_company(self):
        demo = DemoRequest.objects.create(
            full_name="Alice Smith",
            email="alice@example.com",
            whatsapp_number="1234567890",
            company="Acme",
        )
        self.assertEqual(str(demo), "Alice Smith (Acme)")


# ---------------------------------------------------------------------------
# OrganizationSignupForm
# ---------------------------------------------------------------------------

class OrganizationSignupFormTests(TestCase):

    def _valid_data(self):
        return {
            "organization_name": "Test Org",
            "domain": "testorg",
            "email": "admin@example.com",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        }

    def test_valid_form(self):
        form = OrganizationSignupForm(data=self._valid_data())
        self.assertTrue(form.is_valid())

    def test_domain_with_hyphen_rejected(self):
        data = self._valid_data()
        data["domain"] = "test-org"
        form = OrganizationSignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("domain", form.errors)

    def test_domain_with_space_rejected(self):
        data = self._valid_data()
        data["domain"] = "test org"
        form = OrganizationSignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("domain", form.errors)

    def test_duplicate_domain_rejected(self):
        create_organization(name="Existing Org", domain="existing")
        data = self._valid_data()
        data["domain"] = "existing"
        form = OrganizationSignupForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn("domain", form.errors)

    def test_password_mismatch_rejected(self):
        data = self._valid_data()
        data["password2"] = "differentpass"
        form = OrganizationSignupForm(data=data)
        self.assertFalse(form.is_valid())

    def test_domain_normalized_to_lowercase(self):
        data = self._valid_data()
        data["domain"] = "TestOrg"
        form = OrganizationSignupForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["domain"], "testorg")

    def test_domain_with_underscores_allowed(self):
        data = self._valid_data()
        data["domain"] = "test_org"
        form = OrganizationSignupForm(data=data)
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# AcceptInviteForm
# ---------------------------------------------------------------------------

class AcceptInviteFormTests(TestCase):

    def test_valid_form(self):
        form = AcceptInviteForm(data={
            "full_name": "Jane Smith",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertTrue(form.is_valid())

    def test_password_mismatch_rejected(self):
        form = AcceptInviteForm(data={
            "full_name": "Jane",
            "password1": "pass1234",
            "password2": "different",
        })
        self.assertFalse(form.is_valid())

    def test_full_name_is_optional(self):
        form = AcceptInviteForm(data={
            "full_name": "",
            "password1": "SecurePass123!",
            "password2": "SecurePass123!",
        })
        self.assertTrue(form.is_valid())


# ---------------------------------------------------------------------------
# OrganizationMiddleware
# ---------------------------------------------------------------------------

class OrganizationMiddlewareTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.org = create_organization()
        self.user = User.objects.create_user(
            email="u@example.com", password="pass", organization=self.org
        )
        self.middleware = OrganizationMiddleware(MagicMock(return_value="response"))

    def test_sets_organization_for_authenticated_user(self):
        request = self.factory.get("/")
        request.user = self.user
        self.middleware(request)
        self.assertEqual(request.organization, self.org)

    def test_sets_none_for_anonymous_user(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.middleware(request)
        self.assertIsNone(request.organization)

    def test_sets_none_when_user_has_no_organization(self):
        user_no_org = User.objects.create_user(
            email="noorg@example.com", password="pass"
        )
        request = self.factory.get("/")
        request.user = user_no_org
        self.middleware(request)
        self.assertIsNone(request.organization)


# ---------------------------------------------------------------------------
# SubscriptionMiddleware
# ---------------------------------------------------------------------------

class SubscriptionMiddlewareTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.org = create_organization()
        self.user = User.objects.create_user(
            email="u@example.com", password="pass", organization=self.org
        )
        self.get_response = MagicMock(return_value="response")
        self.middleware = SubscriptionMiddleware(self.get_response)

    def _make_request(self, path="/some/view/"):
        request = self.factory.get(path)
        request.user = self.user
        # Re-fetch org so there is no stale cached reverse subscription relation
        request.organization = Organization.objects.get(pk=self.org.pk)
        return request

    def test_passes_through_when_subscription_not_expired(self):
        sub = Subscription.objects.get(organization=self.org)
        sub.expires_at = timezone.now() + timedelta(days=30)
        sub.save()
        request = self._make_request()
        response = self.middleware(request)
        self.assertEqual(response, "response")

    def test_passes_through_when_no_expiry_date(self):
        sub = Subscription.objects.get(organization=self.org)
        sub.expires_at = None
        sub.save()
        request = self._make_request()
        response = self.middleware(request)
        self.assertEqual(response, "response")

    def test_redirects_to_billing_when_subscription_expired(self):
        sub = Subscription.objects.get(organization=self.org)
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.save()
        request = self._make_request()
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("billing", response["Location"])

    def test_no_redirect_on_billing_page_even_when_expired(self):
        sub = Subscription.objects.get(organization=self.org)
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.save()
        billing_url = reverse("core:billing")
        request = self._make_request(path=billing_url)
        response = self.middleware(request)
        self.assertEqual(response, "response")

    def test_passes_through_for_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get("/some/view/")
        request.user = AnonymousUser()
        request.organization = None
        response = self.middleware(request)
        self.assertEqual(response, "response")


# ---------------------------------------------------------------------------
# org_required guard
# ---------------------------------------------------------------------------

class OrgRequiredGuardTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_raises_permission_denied_when_no_organization(self):
        request = self.factory.get("/")
        request.organization = None
        with self.assertRaises(PermissionDenied):
            org_required(request)

    def test_does_not_raise_when_organization_is_set(self):
        request = self.factory.get("/")
        request.organization = MagicMock()  # any non-None object
        org_required(request)  # should not raise


# ---------------------------------------------------------------------------
# create_trial_subscription signal
# ---------------------------------------------------------------------------

class CreateTrialSubscriptionSignalTests(TestCase):

    def test_creates_trial_subscription_on_org_creation(self):
        create_trial_plan()
        org = Organization.objects.create(name="New Org", domain="neworg")
        self.assertTrue(Subscription.objects.filter(organization=org).exists())
        sub = Subscription.objects.get(organization=org)
        self.assertTrue(sub.is_trial())

    def test_signal_raises_runtime_error_when_trial_plan_missing(self):
        # No Trial plan created — signal must raise RuntimeError
        with self.assertRaises(RuntimeError):
            Organization.objects.create(name="No Plan Org", domain="noplan")

    def test_does_not_create_duplicate_subscription_on_re_save(self):
        create_trial_plan()
        org = Organization.objects.create(name="Re-save Org", domain="resave")
        org.name = "Re-save Org Updated"
        org.save()  # signal only acts on created=True
        self.assertEqual(Subscription.objects.filter(organization=org).count(), 1)


# ---------------------------------------------------------------------------
# downgrade_expired_subscriptions management command
# ---------------------------------------------------------------------------

class DowngradeExpiredSubscriptionsCommandTests(TestCase):

    def setUp(self):
        self.trial_plan = create_trial_plan()
        self.free_plan = create_free_plan()

    def test_downgrades_expired_active_subscriptions_to_free(self):
        org = create_organization(name="Expired Org", domain="expiredorg")
        sub = Subscription.objects.get(organization=org)
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.is_active = True
        sub.save()

        out = StringIO()
        call_command("downgrade_expired_subscriptions", stdout=out)

        sub.refresh_from_db()
        self.assertEqual(sub.plan, self.free_plan)
        self.assertFalse(sub.is_active)
        self.assertIn("1 subscription(s)", out.getvalue())

    def test_skips_subscriptions_with_future_expiry(self):
        org = create_organization(name="Active Org", domain="activeorg")
        sub = Subscription.objects.get(organization=org)
        sub.expires_at = timezone.now() + timedelta(days=30)
        sub.save()

        out = StringIO()
        call_command("downgrade_expired_subscriptions", stdout=out)

        sub.refresh_from_db()
        self.assertEqual(sub.plan, self.trial_plan)
        self.assertIn("0 subscription(s)", out.getvalue())

    def test_skips_subscriptions_with_no_expiry_date(self):
        org = create_organization(name="No Expiry Org", domain="noexpiry")
        sub = Subscription.objects.get(organization=org)
        sub.expires_at = None
        sub.save()

        out = StringIO()
        call_command("downgrade_expired_subscriptions", stdout=out)

        sub.refresh_from_db()
        self.assertEqual(sub.plan, self.trial_plan)

    def test_outputs_error_when_free_plan_missing(self):
        self.free_plan.delete()
        org = create_organization(name="Org2", domain="org2")
        sub = Subscription.objects.get(organization=org)
        sub.expires_at = timezone.now() - timedelta(days=1)
        sub.save()

        err = StringIO()
        call_command("downgrade_expired_subscriptions", stderr=err)
        self.assertIn("Free plan not found", err.getvalue())
