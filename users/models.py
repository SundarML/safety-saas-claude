
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

    email = models.EmailField(unique=True)
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

    # Contractor access expiry (null = no expiry / not a contractor)
    access_expires_at = models.DateTimeField(null=True, blank=True)

    # Django internals
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

