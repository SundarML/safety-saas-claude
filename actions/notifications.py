# actions/notifications.py
from django.conf import settings


def _site_url():
    return getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")


def _action_html(action, headline, body_html, header_color="#1a2c52"):
    base       = _site_url()
    detail_url = f"{base}/actions/{action.pk}/"

    priority_colors = {
        "critical": "#dc2626", "high": "#ea580c",
        "medium":   "#ca8a04", "low":  "#16a34a",
    }
    p_color = priority_colors.get(action.priority, "#64748b")

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:{header_color};color:#fff;padding:20px 28px;border-radius:8px 8px 0 0;">
        <h2 style="margin:0;font-size:18px;">{headline}</h2>
      </div>
      <div style="background:#f8f9fa;padding:24px 28px;border:1px solid #dee2e6;
                  border-top:none;border-radius:0 0 8px 8px;">
        {body_html}
        <table style="width:100%;border-collapse:collapse;font-size:14px;margin:16px 0;">
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;width:40%;">Action</td>
            <td style="padding:8px 12px;font-weight:600;">CA-{action.pk:04d}: {action.title}</td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Priority</td>
            <td style="padding:8px 12px;">
              <span style="background:{p_color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;">
                {action.get_priority_display()}
              </span>
            </td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Assigned To</td>
            <td style="padding:8px 12px;">{action.assigned_to.get_full_name() if action.assigned_to else "—"}</td>
          </tr>
          <tr style="border-bottom:1px solid #dee2e6;">
            <td style="padding:8px 12px;color:#6c757d;">Due Date</td>
            <td style="padding:8px 12px;">{action.due_date.strftime("%d %b %Y") if action.due_date else "—"}</td>
          </tr>
          <tr>
            <td style="padding:8px 12px;color:#6c757d;">Source</td>
            <td style="padding:8px 12px;">{action.get_source_module_display()}</td>
          </tr>
        </table>
        <a href="{detail_url}"
           style="display:inline-block;background:#1a2c52;color:#fff;padding:10px 24px;
                  border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View Action
        </a>
        <p style="color:#6c757d;font-size:12px;margin-top:24px;">
          Automated notification from Vigilo Safety Management System.
        </p>
      </div>
    </div>
    """


def send_action_notification(action, event):
    """
    event values: 'assigned', 'submitted', 'closed', 'reopened'
    """
    from core.utils.email import send_brevo_email

    configs = {
        "assigned": {
            "to":           lambda a: [a.assigned_to.email] if a.assigned_to and a.assigned_to.email else [],
            "subject":      lambda a: f"Action Assigned to You: CA-{a.pk:04d} — {a.title}",
            "headline":     "New Corrective Action Assigned",
            "body":         lambda a: f"<p>A corrective action has been assigned to you. Please review and take action by the due date.</p>",
            "header_color": "#1a2c52",
        },
        "submitted": {
            "to":           lambda a: _managers_and_raiser(a),
            "subject":      lambda a: f"Action Submitted for Verification: CA-{a.pk:04d} — {a.title}",
            "headline":     "Corrective Action Awaiting Verification",
            "body":         lambda a: f"<p><strong>{a.assigned_to.get_full_name() if a.assigned_to else 'Assignee'}</strong> has submitted this action for verification. Please review the evidence and close or send back.</p>",
            "header_color": "#ca8a04",
        },
        "closed": {
            "to":           lambda a: [a.assigned_to.email] if a.assigned_to and a.assigned_to.email else [],
            "subject":      lambda a: f"Action Closed: CA-{a.pk:04d} — {a.title}",
            "headline":     "Corrective Action Closed",
            "body":         lambda a: f"<p>Your corrective action has been verified and closed by <strong>{a.closed_by.get_full_name() if a.closed_by else 'a manager'}</strong>.</p>",
            "header_color": "#16a34a",
        },
        "reopened": {
            "to":           lambda a: [a.assigned_to.email] if a.assigned_to and a.assigned_to.email else [],
            "subject":      lambda a: f"Action Sent Back for Rework: CA-{a.pk:04d} — {a.title}",
            "headline":     "Corrective Action Requires Rework",
            "body":         lambda a: (
                f"<p>Your action has been sent back for rework.</p>"
                + (f"<blockquote style='border-left:3px solid #ea580c;padding-left:12px;color:#64748b;'>{a.reopen_comment}</blockquote>" if a.reopen_comment else "")
            ),
            "header_color": "#ea580c",
        },
    }

    cfg = configs.get(event)
    if not cfg:
        return

    recipients = cfg["to"](action)
    if not recipients:
        return

    html = _action_html(
        action,
        headline     = cfg["headline"],
        body_html    = cfg["body"](action),
        header_color = cfg["header_color"],
    )

    for email in recipients:
        try:
            send_brevo_email(
                to_email     = email,
                subject      = cfg["subject"](action),
                html_content = html,
            )
        except Exception:
            pass


def _managers_and_raiser(action):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    emails = set()
    if action.raised_by and action.raised_by.email:
        emails.add(action.raised_by.email)
    for u in User.objects.filter(organization=action.organization, is_active=True):
        if (u.is_manager or u.is_safety_manager) and u.email:
            emails.add(u.email)
    return list(emails)
