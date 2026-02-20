from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
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

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # ── Role flags ─────────────────────────────────────────────────────────
    is_manager = models.BooleanField(default=False)
    is_observer = models.BooleanField(default=False)
    is_action_owner = models.BooleanField(default=False)
    is_safety_manager = models.BooleanField(default=False)

    # ── Contractor role ────────────────────────────────────────────────────
    is_contractor = models.BooleanField(
        default=False,
        help_text="Contractor user — limited to Permits module only",
    )
    contractor_company = models.CharField(
        max_length=255, blank=True,
        help_text="Contractor company name (auto-populated in permits)",
    )
    contractor_phone = models.CharField(
        max_length=50, blank=True,
        help_text="Contractor contact phone",
    )
    contractor_access_expiry = models.DateField(
        null=True, blank=True,
        help_text="Contractor account expires on this date (optional)",
    )

    # ── Django internals ───────────────────────────────────────────────────
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.full_name or self.email

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.full_name.split()[0] if self.full_name else self.email

    @property
    def is_contractor_expired(self):
        """Check if contractor access has expired."""
        if not self.is_contractor or not self.contractor_access_expiry:
            return False
        from django.utils import timezone
        return timezone.now().date() > self.contractor_access_expiry

    @property
    def has_observation_access(self):
        """Contractors do NOT have access to observations module."""
        return not self.is_contractor

    @property
    def has_permit_full_access(self):
        """Full permit access (approve/activate/close) — managers and safety managers only."""
        return (
            not self.is_contractor
            and (self.is_manager or self.is_safety_manager)
        )
