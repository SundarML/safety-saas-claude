# core/models.py
from django.db import models
from django.utils import timezone
import uuid


class UserInvite(models.Model):
    organization = models.ForeignKey("core.Organization", on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            ("observer", "Observer"),
            ("action_owner", "Action Owner"),
            ("manager", "Manager"),
        ],
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.email} ({self.organization})"


class DemoRequest(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    whatsapp_number = models.CharField(max_length=20)
    company = models.CharField(max_length=200)
    job_title = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.company})"


class Organization(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Plan(models.Model):
    PLAN_TIERS = [
        ("trial",      "Trial"),
        ("basic",      "Basic"),
        ("pro",        "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name             = models.CharField(max_length=50, unique=True)
    tier             = models.CharField(max_length=20, choices=PLAN_TIERS, default="trial")
    max_observations = models.IntegerField(null=True, blank=True, help_text="None = unlimited")
    max_users        = models.IntegerField(null=True, blank=True, help_text="None = unlimited")

    # Pricing
    price_monthly    = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_onetime    = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                           help_text="One-time annual payment (0 = not offered)")

    # Razorpay
    razorpay_plan_id = models.CharField(max_length=120, blank=True,
                                         help_text="Razorpay Plan ID for recurring subscriptions")

    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self):
        return self.name

    @property
    def is_free(self):
        return self.price_monthly == 0 and self.price_onetime == 0

    def monthly_paise(self):
        """Razorpay amounts are in paise (1 INR = 100 paise)."""
        return int(self.price_monthly * 100)

    def onetime_paise(self):
        return int(self.price_onetime * 100)


class Subscription(models.Model):
    STATUS_CHOICES = [
        ("trial",    "Trial"),
        ("active",   "Active"),
        ("expired",  "Expired"),
        ("cancelled","Cancelled"),
    ]

    organization = models.OneToOneField(Organization, on_delete=models.CASCADE)
    plan         = models.ForeignKey(Plan, on_delete=models.PROTECT)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default="trial")
    is_active    = models.BooleanField(default=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Razorpay IDs
    razorpay_customer_id     = models.CharField(max_length=120, blank=True)
    razorpay_subscription_id = models.CharField(max_length=120, blank=True)

    def is_trial(self):
        return self.plan.tier == "trial"

    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.organization} — {self.plan}"


class RazorpayOrder(models.Model):
    """Tracks every payment attempt (one-time or first recurring payment)."""
    PAYMENT_TYPE = [
        ("onetime",   "One-time"),
        ("recurring", "Recurring"),
    ]
    STATUS = [
        ("created",  "Created"),
        ("paid",     "Paid"),
        ("failed",   "Failed"),
    ]

    organization   = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                        related_name="razorpay_orders")
    plan           = models.ForeignKey(Plan, on_delete=models.PROTECT)
    payment_type   = models.CharField(max_length=20, choices=PAYMENT_TYPE)

    razorpay_order_id   = models.CharField(max_length=120, unique=True)
    razorpay_payment_id = models.CharField(max_length=120, blank=True)
    razorpay_signature  = models.CharField(max_length=255, blank=True)

    amount_paise = models.IntegerField()
    status       = models.CharField(max_length=20, choices=STATUS, default="created")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.organization} | {self.plan} | {self.status}"
