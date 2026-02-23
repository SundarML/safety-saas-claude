from django.db import models
from django.utils import timezone
# Create your models here.

from django.db import models
import uuid


class UserInvite(models.Model):
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=[
            ("observer", "Observer"),
            ("action_owner", "Action Owner"),
            ("manager", "Manager"),
        ]
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        # return not self.is_used and self.expires_at > timezone.now()
        return not self.is_used and (self.expires_at is None or self.expires_at > timezone.now())
    def __str__(self):
        return f"{self.email} ({self.organization})"



class ContractorInvite(models.Model):
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE
    )
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    is_used = models.BooleanField(default=False)
    # How many days the contractor can access after accepting (null = no expiry)
    access_validity_days = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Invite link expiry (7 days after creation)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        return not self.is_used and (self.expires_at is None or self.expires_at > timezone.now())

    def __str__(self):
        return f"Contractor Invite: {self.email} ({self.organization})"


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


class FreePlanRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    whatsapp_number = models.CharField(max_length=20)
    company = models.CharField(max_length=200)
    job_title = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} ({self.company})"


# core/models.py for saas application
class Organization(models.Model):
    name = models.CharField(max_length=255)
    domain = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# create model for subscription plan
class Plan(models.Model):
    name = models.CharField(max_length=50, unique=True)

    max_observations = models.IntegerField(null=True, blank=True)
    max_users = models.IntegerField(null=True, blank=True)

    price_monthly = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    razorpay_plan_id = models.CharField(max_length=120, blank=True)

    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name



class Subscription(models.Model):

    
    organization = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE
    )

    
    plan = models.ForeignKey(
        "Plan",
        on_delete=models.PROTECT
    )

    
    # status = models.CharField(
    #     max_length=20,
    #     choices=PLAN_CHOICES,
    #     default="trial"
    # )

    # Activity
    is_active = models.BooleanField(default=True)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Stripe
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)

    # Razorpay
    razorpay_customer_id = models.CharField(max_length=120, blank=True)
    razorpay_subscription_id = models.CharField(max_length=120, blank=True)

    def is_trial(self):
        return self.plan.name.lower() == "trial"

    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
        
    def __str__(self):
        return f"{self.organization} — {self.plan}"
