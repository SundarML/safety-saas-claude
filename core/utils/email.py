# core/utils/email.py
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base sender
# ---------------------------------------------------------------------------

def send_brevo_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send a transactional email via Brevo.
    Returns True on success, False on failure (never raises).
    """
    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = settings.BREVO_API_KEY

        api = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )

        from_raw = settings.DEFAULT_FROM_EMAIL
        if "<" in from_raw:
            from_name, from_addr = from_raw.split("<", 1)
            from_addr = from_addr.rstrip(">").strip()
            from_name = from_name.strip()
        else:
            from_addr = from_raw.strip()
            from_name = "SafetySuite"

        message = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": to_email}],
            subject=subject,
            html_content=html_content,
            sender={"name": from_name, "email": from_addr},
        )

        api.send_transac_email(message)
        logger.info("Email sent to %s -- %s", to_email, subject)
        return True

    except Exception as exc:
        logger.error("Brevo email failed to %s: %s", to_email, exc)
        return False


# ---------------------------------------------------------------------------
# Observation email helpers
# ---------------------------------------------------------------------------

def _site_url() -> str:
    """Return base URL with no trailing slash."""
    return getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def send_high_risk_alert(observation) -> bool:
    """
    Alert the assigned user immediately when a HIGH severity
    observation is created and they are assigned to it.

    Called from ObservationCreateView.form_valid().
    Does nothing if no one is assigned or severity is not HIGH.
    """
    if not observation.assigned_to:
        return False
    if observation.severity != "HIGH":
        return False

    to_email = observation.assigned_to.email
    name     = observation.assigned_to.get_full_name()
    base     = _site_url()

    detail_url      = f"{base}/observations/{observation.pk}/"
    rectify_url     = f"{base}/observations/{observation.pk}/rectify/"

    subject = f"HIGH Risk Observation Assigned -- {observation.title}"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#dc3545;padding:16px 24px;border-radius:6px 6px 0 0;">
        <h2 style="color:white;margin:0;">High Risk Observation Assigned to You</h2>
      </div>
      <div style="background:#fff8f8;border:1px solid #dc3545;padding:24px;border-radius:0 0 6px 6px;">

        <p>Hi <strong>{name}</strong>,</p>

        <p>A <strong style="color:#dc3545;">HIGH severity</strong> safety observation has been
        reported and assigned to you. Immediate action is required.</p>

        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;width:35%;">Observation ID</td>
              <td style="padding:8px;">#{observation.pk}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Title</td>
              <td style="padding:8px;">{observation.title}</td></tr>
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;">Location</td>
              <td style="padding:8px;">{observation.location}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Severity</td>
              <td style="padding:8px;color:#dc3545;font-weight:bold;">HIGH</td></tr>
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;">Target Date</td>
              <td style="padding:8px;">{observation.target_date or "Not set"}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Description</td>
              <td style="padding:8px;">{observation.description[:300]}</td></tr>
        </table>

        <p style="margin-top:24px;">
          <a href="{rectify_url}"
             style="background:#dc3545;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            Submit Rectification
          </a>
          &nbsp;&nbsp;
          <a href="{detail_url}"
             style="background:#6c757d;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            View Full Details
          </a>
        </p>

        <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
        <p style="color:#888;font-size:12px;">
          You are receiving this because you are assigned as Action Owner.<br>
          SafetySuite -- Safety Observation Management
        </p>
      </div>
    </div>
    """

    return send_brevo_email(to_email, subject, html)


def send_overdue_alert(observation) -> bool:
    """
    Notify the assigned user that their observation is overdue.

    Called from the send_overdue_alerts management command (daily cron).
    """
    if not observation.assigned_to:
        return False

    to_email = observation.assigned_to.email
    name     = observation.assigned_to.get_full_name()
    base     = _site_url()

    detail_url  = f"{base}/observations/{observation.pk}/"
    rectify_url = f"{base}/observations/{observation.pk}/rectify/"

    days_overdue = (timezone.now().date() - observation.target_date).days

    severity_color = {
        "HIGH":   "#dc3545",
        "MEDIUM": "#fd7e14",
        "LOW":    "#6c757d",
    }.get(observation.severity, "#6c757d")

    subject = (
        f"Overdue Observation ({days_overdue} day{'s' if days_overdue != 1 else ''}) "
        f"-- {observation.title}"
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#fd7e14;padding:16px 24px;border-radius:6px 6px 0 0;">
        <h2 style="color:white;margin:0;">Overdue Safety Observation</h2>
      </div>
      <div style="background:#fffdf8;border:1px solid #fd7e14;padding:24px;border-radius:0 0 6px 6px;">

        <p>Hi <strong>{name}</strong>,</p>

        <p>The following safety observation assigned to you is
        <strong style="color:#dc3545;">{days_overdue} day{'s' if days_overdue != 1 else ''} overdue</strong>.
        Please submit your rectification as soon as possible.</p>

        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;width:35%;">Observation ID</td>
              <td style="padding:8px;">#{observation.pk}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Title</td>
              <td style="padding:8px;">{observation.title}</td></tr>
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;">Location</td>
              <td style="padding:8px;">{observation.location}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Severity</td>
              <td style="padding:8px;color:{severity_color};font-weight:bold;">{observation.get_severity_display()}</td></tr>
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;">Target Date</td>
              <td style="padding:8px;color:#dc3545;font-weight:bold;">{observation.target_date}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Days Overdue</td>
              <td style="padding:8px;color:#dc3545;font-weight:bold;">{days_overdue} day{'s' if days_overdue != 1 else ''}</td></tr>
          <tr><td style="padding:8px;background:#f9f9f9;font-weight:bold;">Current Status</td>
              <td style="padding:8px;">{observation.get_status_display()}</td></tr>
        </table>

        <p style="margin-top:24px;">
          <a href="{rectify_url}"
             style="background:#fd7e14;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            Submit Rectification
          </a>
          &nbsp;&nbsp;
          <a href="{detail_url}"
             style="background:#6c757d;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            View Details
          </a>
        </p>

        <hr style="margin:24px 0;border:none;border-top:1px solid #eee;">
        <p style="color:#888;font-size:12px;">
          You are receiving this because you are assigned as Action Owner.<br>
          SafetySuite -- Safety Observation Management
        </p>
      </div>
    </div>
    """

    return send_brevo_email(to_email, subject, html)


# ---------------------------------------------------------------------------
# Admin notifications -- demo & free plan requests
# ---------------------------------------------------------------------------

def notify_admin_demo_request(demo_request) -> bool:
    """
    Email the site admin when a new demo request is submitted.
    Silently skips if ADMIN_EMAIL is not configured.
    """
    admin_email = settings.ADMIN_EMAIL
    if not admin_email:
        return False

    base = _site_url()
    admin_url = f"{base}/admin/core/demorequest/"

    subject = f"New Demo Request -- {demo_request.full_name} ({demo_request.company})"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#16a34a;padding:16px 24px;border-radius:6px 6px 0 0;">
        <h2 style="color:white;margin:0;">New Demo Request on Vigilo</h2>
      </div>
      <div style="background:#f0fdf4;border:1px solid #bbf7d0;padding:24px;border-radius:0 0 6px 6px;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
          <tr><td style="padding:8px;background:#fff;font-weight:bold;width:35%;">Name</td>
              <td style="padding:8px;background:#fff;">{demo_request.full_name}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Company</td>
              <td style="padding:8px;">{demo_request.company}</td></tr>
          <tr><td style="padding:8px;background:#fff;font-weight:bold;">Job Title</td>
              <td style="padding:8px;background:#fff;">{demo_request.job_title or "--"}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Email</td>
              <td style="padding:8px;"><a href="mailto:{demo_request.email}">{demo_request.email}</a></td></tr>
          <tr><td style="padding:8px;background:#fff;font-weight:bold;">WhatsApp</td>
              <td style="padding:8px;background:#fff;">{demo_request.whatsapp_number}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Message</td>
              <td style="padding:8px;">{demo_request.message or "--"}</td></tr>
        </table>
        <p style="margin-top:20px;">
          <a href="{admin_url}"
             style="background:#16a34a;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            View in Admin
          </a>
        </p>
        <hr style="margin:24px 0;border:none;border-top:1px solid #bbf7d0;">
        <p style="color:#64748b;font-size:12px;">Vigilo -- Safety Management Platform</p>
      </div>
    </div>
    """

    return send_brevo_email(admin_email, subject, html)


def notify_admin_free_plan_request(free_request) -> bool:
    """
    Email the site admin when a new free plan request is submitted.
    Silently skips if ADMIN_EMAIL is not configured.
    """
    admin_email = settings.ADMIN_EMAIL
    if not admin_email:
        return False

    base = _site_url()
    admin_url = f"{base}/admin/core/freeplanrequest/"

    subject = f"New Free Plan Request -- {free_request.full_name} ({free_request.company})"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;">
      <div style="background:#0d9488;padding:16px 24px;border-radius:6px 6px 0 0;">
        <h2 style="color:white;margin:0;">New Free Plan Request on Vigilo</h2>
      </div>
      <div style="background:#f0fdfa;border:1px solid #99f6e4;padding:24px;border-radius:0 0 6px 6px;">
        <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
          <tr><td style="padding:8px;background:#fff;font-weight:bold;width:35%;">Name</td>
              <td style="padding:8px;background:#fff;">{free_request.full_name}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Company</td>
              <td style="padding:8px;">{free_request.company}</td></tr>
          <tr><td style="padding:8px;background:#fff;font-weight:bold;">Job Title</td>
              <td style="padding:8px;background:#fff;">{free_request.job_title or "--"}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Email</td>
              <td style="padding:8px;"><a href="mailto:{free_request.email}">{free_request.email}</a></td></tr>
          <tr><td style="padding:8px;background:#fff;font-weight:bold;">WhatsApp</td>
              <td style="padding:8px;background:#fff;">{free_request.whatsapp_number}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;">Message</td>
              <td style="padding:8px;">{free_request.message or "--"}</td></tr>
        </table>
        <p style="margin-top:20px;">
          <a href="{admin_url}"
             style="background:#0d9488;color:white;padding:12px 28px;
                    text-decoration:none;border-radius:4px;font-weight:bold;display:inline-block;">
            Review in Admin
          </a>
        </p>
        <hr style="margin:24px 0;border:none;border-top:1px solid #99f6e4;">
        <p style="color:#64748b;font-size:12px;">Vigilo -- Safety Management Platform</p>
      </div>
    </div>
    """

    return send_brevo_email(admin_email, subject, html)
