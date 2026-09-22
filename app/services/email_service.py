"""
email_service.py
----------------
Sends transactional emails via the Resend API (3,000 free emails/month).
Falls back to console logging when RESEND_API_KEY is not set.
"""

import logging

from app.config import settings
from app.services.key_service import PLAN_LIMITS

logger = logging.getLogger(__name__)


def send_api_key_email(to_email: str, api_key: str, plan: str) -> None:
    """
    Send the customer their newly issued API key.
    Safe to call from async code — Resend's Python SDK is synchronous.
    """
    daily_limit = PLAN_LIMITS.get(plan, 100)
    base_url = settings.APP_BASE_URL

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f8fafc; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; background: #fff;
                  border-radius: 12px; overflow: hidden;
                  box-shadow: 0 4px 24px rgba(0,0,0,.08); }}
    .header {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
               padding: 40px 40px 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 28px; font-weight: 700; }}
    .header p  {{ color: rgba(255,255,255,.85); margin: 8px 0 0; font-size: 16px; }}
    .body {{ padding: 40px; }}
    .badge {{ display: inline-block; background: #ede9fe; color: #6d28d9;
              padding: 4px 12px; border-radius: 99px; font-size: 13px;
              font-weight: 600; margin-bottom: 20px; }}
    .key-box {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px;
                padding: 20px; margin: 20px 0; }}
    .key-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                  color: #94a3b8; margin: 0 0 6px; }}
    .key-value {{ font-family: 'Courier New', monospace; font-size: 17px;
                  color: #1e293b; word-break: break-all; margin: 0; }}
    pre  {{ background: #1e293b; color: #e2e8f0; padding: 18px; border-radius: 8px;
            overflow-x: auto; font-size: 13px; line-height: 1.6; }}
    .footer {{ padding: 24px 40px; border-top: 1px solid #f1f5f9;
               color: #94a3b8; font-size: 13px; text-align: center; }}
    a {{ color: #6366f1; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔑 RankLens API</h1>
      <p>Your API key is ready to use</p>
    </div>
    <div class="body">
      <span class="badge">{plan.title()} Plan — {daily_limit:,} req/day</span>
      <p>Welcome! Your RankLens API key has been automatically generated.
         Keep it safe — treat it like a password.</p>

      <div class="key-box">
        <p class="key-label">Your API Key</p>
        <p class="key-value">{api_key}</p>
      </div>

      <p><strong>Quick start:</strong></p>
      <pre>curl "{base_url}/api/v1/analyze?keyword=content+marketing" \\
  -H "X-API-Key: {api_key}"</pre>

      <p>📖 Full documentation: <a href="{base_url}/docs">{base_url}/docs</a></p>
      <p>Check your usage at any time:</p>
      <pre>curl "{base_url}/api/v1/usage" \\
  -H "X-API-Key: {api_key}"</pre>
    </div>
    <div class="footer">
      RankLens API &nbsp;·&nbsp; Questions? Reply to this email.<br/>
      <a href="{base_url}">ranklens.dev</a>
    </div>
  </div>
</body>
</html>
"""

    if not settings.RESEND_API_KEY:
        logger.warning(
            "[EMAIL — no RESEND_API_KEY] Would send key %s to %s",
            api_key[:16] + "...",
            to_email,
        )
        return

    try:
        import resend  # imported here so missing package doesn't break startup

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": "🔑 Your RankLens API Key is Ready",
                "html": html_body,
            }
        )
        logger.info("API key email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
