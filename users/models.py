
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.contrib.auth.hashers import make_password, check_password
from django.db import models


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_worker_user(self, employee_id, pin, organization, full_name, role="observer", **extra_fields):
        """Create a no-email worker account authenticated by Employee ID + PIN."""
        if not employee_id:
            raise ValueError("Workers must have an employee ID")
        if not pin:
            raise ValueError("Workers must have a PIN")
        user = self.model(
            email=None,
            employee_id=employee_id,
            organization=organization,
            full_name=full_name,
            role=role,
            **extra_fields,
        )
        user.set_unusable_password()
        user.set_pin(pin)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_MANAGER = "manager"
    ROLE_SAFETY_MANAGER = "safety_manager"
    ROLE_ACTION_OWNER = "action_owner"
    ROLE_OBSERVER = "observer"
    ROLE_CONTRACTOR = "contractor"

    ROLE_CHOICES = [
        (ROLE_MANAGER, "Manager"),
        (ROLE_SAFETY_MANAGER, "Safety Manager"),
        (ROLE_ACTION_OWNER, "Action Owner"),
        (ROLE_OBSERVER, "Observer"),
        (ROLE_CONTRACTOR, "Contractor"),
    ]

    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    trade = models.CharField(max_length=100, blank=True)
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Single role field — replaces the four separate boolean flags.
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_OBSERVER,
    )

    # Employee ID — optional, unique within organisation (blank values are exempt)
    employee_id = models.CharField(max_length=50, blank=True)

    # PIN hash — for worker accounts that log in with Employee ID + PIN (no email)
    pin_hash = models.CharField(max_length=128, blank=True)

    # Solid-line manager — who this user reports to directly
    reports_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="direct_reports",
    )

    # Contractor access expiry (null = no expiry / not a contractor)
    access_expires_at = models.DateTimeField(null=True, blank=True)

    # Django internals
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "employee_id"],
                condition=models.Q(employee_id__gt=""),
                name="unique_employee_id_per_org",
            )
        ]

    @property
    def is_worker_account(self):
        """True for no-email accounts that authenticate via Employee ID + PIN."""
        return not self.email

    def set_pin(self, raw_pin):
        self.pin_hash = make_password(str(raw_pin))

    def check_pin(self, raw_pin):
        return bool(self.pin_hash) and check_password(str(raw_pin), self.pin_hash)

    def __str__(self):
        return self.full_name or self.email or self.employee_id or f"User {self.pk}"

    def get_full_name(self):
        return self.full_name or self.email or self.employee_id or f"Worker {self.pk}"

    def get_short_name(self):
        if self.full_name:
            return self.full_name.split()[0]
        return self.email or self.employee_id or f"Worker {self.pk}"

    # ------------------------------------------------------------------
    # Convenience properties — keep the same API so no view code breaks.
    # ------------------------------------------------------------------

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_safety_manager(self):
        return self.role == self.ROLE_SAFETY_MANAGER

    @property
    def is_action_owner(self):
        return self.role == self.ROLE_ACTION_OWNER

    @property
    def is_observer(self):
        return self.role == self.ROLE_OBSERVER

    @property
    def is_contractor(self):
        return self.role == self.ROLE_CONTRACTOR

