"""
Unit tests for the users app.
Covers: CustomUserManager, CustomUser model properties and methods.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------------------------------------------------------------------------
# CustomUserManager
# ---------------------------------------------------------------------------

class CustomUserManagerTests(TestCase):

    def test_create_user_requires_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="pass1234")

    def test_create_user_normalizes_email(self):
        # normalize_email() lowercases the domain part only, not the local part
        user = User.objects.create_user(email="Test@Example.COM", password="pass1234")
        self.assertEqual(user.email, "Test@example.com")

    def test_create_user_sets_password(self):
        user = User.objects.create_user(email="u@example.com", password="securepass")
        self.assertTrue(user.check_password("securepass"))

    def test_create_user_is_not_staff_by_default(self):
        user = User.objects.create_user(email="u@example.com", password="pass1234")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser_sets_is_staff_and_is_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com", password="adminpass"
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)


# ---------------------------------------------------------------------------
# CustomUser.__str__ and name helpers
# ---------------------------------------------------------------------------

class CustomUserStrTests(TestCase):

    def test_str_returns_full_name_when_set(self):
        user = User.objects.create_user(
            email="jane@example.com", password="pass1234", full_name="Jane Smith"
        )
        self.assertEqual(str(user), "Jane Smith")

    def test_str_returns_email_when_no_full_name(self):
        user = User.objects.create_user(email="noname@example.com", password="pass1234")
        self.assertEqual(str(user), "noname@example.com")


class CustomUserNameMethodTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="jane@example.com", password="pass1234", full_name="Jane Smith"
        )

    def test_get_full_name_returns_full_name(self):
        self.assertEqual(self.user.get_full_name(), "Jane Smith")

    def test_get_full_name_falls_back_to_email(self):
        self.user.full_name = ""
        self.assertEqual(self.user.get_full_name(), "jane@example.com")

    def test_get_short_name_returns_first_word(self):
        self.assertEqual(self.user.get_short_name(), "Jane")

    def test_get_short_name_falls_back_to_email_when_no_full_name(self):
        self.user.full_name = ""
        self.assertEqual(self.user.get_short_name(), "jane@example.com")


# ---------------------------------------------------------------------------
# CustomUser role properties
# ---------------------------------------------------------------------------

class CustomUserRolePropertyTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(email="u@example.com", password="pass1234")

    def test_default_role_is_observer(self):
        self.assertTrue(self.user.is_observer)

    def test_is_manager_true_only_for_manager_role(self):
        self.user.role = "manager"
        self.assertTrue(self.user.is_manager)
        self.assertFalse(self.user.is_safety_manager)
        self.assertFalse(self.user.is_action_owner)
        self.assertFalse(self.user.is_observer)

    def test_is_safety_manager_true_only_for_safety_manager_role(self):
        self.user.role = "safety_manager"
        self.assertTrue(self.user.is_safety_manager)
        self.assertFalse(self.user.is_manager)
        self.assertFalse(self.user.is_action_owner)
        self.assertFalse(self.user.is_observer)

    def test_is_action_owner_true_only_for_action_owner_role(self):
        self.user.role = "action_owner"
        self.assertTrue(self.user.is_action_owner)
        self.assertFalse(self.user.is_manager)
        self.assertFalse(self.user.is_safety_manager)
        self.assertFalse(self.user.is_observer)

    def test_is_observer_true_only_for_observer_role(self):
        self.user.role = "observer"
        self.assertTrue(self.user.is_observer)
        self.assertFalse(self.user.is_manager)
        self.assertFalse(self.user.is_safety_manager)
        self.assertFalse(self.user.is_action_owner)
