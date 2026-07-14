"""Email service — send transactional emails via SMTP or console fallback."""

import os
import re
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Union
from dataclasses import dataclass


@dataclass
class EmailMessage:
    to: Union[str, List[str]]
    subject: str
    html: str
    text: str = ""
    from_addr: str = ""


# ── Provider config ────────────────────────────────────────────────────────────

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SENDGRID_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_ADDRESS = os.getenv("EMAIL_FROM", "noreply@54agent.app")

_smtp_configured = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
_sendgrid_configured = bool(SENDGRID_KEY)


# ── Core send functions ────────────────────────────────────────────────────────

def send_email(message: EmailMessage) -> dict:
    """Send a single email. Falls back to console log when no SMTP is configured."""
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    recipients = message.to if isinstance(message.to, list) else [message.to]

    if _smtp_configured:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = message.from_addr or FROM_ADDRESS
            msg["To"] = ", ".join(recipients)
            if message.text:
                msg.attach(MIMEText(message.text, "plain"))
            msg.attach(MIMEText(message.html, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_ADDRESS, recipients, msg.as_string())
            return {"success": True, "message_id": message_id, "provider": "smtp", "timestamp": datetime.utcnow().isoformat()}
        except Exception as exc:
            return {"success": False, "message_id": message_id, "provider": "smtp", "error": str(exc), "timestamp": datetime.utcnow().isoformat()}

    print(f"[email] to={recipients} subject={message.subject!r} id={message_id}")
    return {
        "success": True,
        "message_id": f"console_local-{message_id}",
        "provider": "console",
        "timestamp": datetime.utcnow().isoformat(),
    }


def send_batch_email(
    messages: List[Union[str, EmailMessage]],
    subject: str = "",
    html: str = "",
    batch_size: int = 50,
    delay_ms: int = 0,
) -> List[dict]:
    results = []
    for item in messages:
        if isinstance(item, str):
            msg = EmailMessage(to=item, subject=subject, html=html)
        else:
            msg = item
        results.append(send_email(msg))
    return results


# ── Provider status ────────────────────────────────────────────────────────────

def get_provider_status() -> List[dict]:
    return [
        {"name": "console", "enabled": True, "configured": True, "healthy": True},
        {"name": "smtp", "enabled": _smtp_configured, "configured": _smtp_configured, "healthy": _smtp_configured},
        {"name": "sendgrid", "enabled": _sendgrid_configured, "configured": _sendgrid_configured, "healthy": _sendgrid_configured},
    ]


# ── Template builders ──────────────────────────────────────────────────────────

def build_welcome_email(recipient: str, name: str, tenant_name: str = "54agent") -> EmailMessage:
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Welcome to {tenant_name}, {name}!</h2>
<p>Your account has been created. You can now log in and start using the platform.</p>
<p>If you did not request this account, please contact support immediately.</p>
<footer style="margin-top:32px;color:#888;font-size:12px">© {datetime.utcnow().year} {tenant_name}</footer>
</body></html>"""
    return EmailMessage(
        to=recipient,
        subject=f"Welcome to {tenant_name}",
        html=html,
        text=f"Welcome to {tenant_name}, {name}! Your account is ready.",
    )


def build_password_reset_email(recipient: str, otp: str, expiry_minutes: int = 15) -> EmailMessage:
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Password Reset Request</h2>
<p>Use the OTP below to reset your password. It expires in <strong>{expiry_minutes} minutes</strong>.</p>
<div style="font-size:36px;font-weight:bold;letter-spacing:8px;margin:24px 0;color:#1a56db">{otp}</div>
<p>If you did not request a password reset, ignore this email.</p>
</body></html>"""
    return EmailMessage(
        to=recipient,
        subject="Your password reset OTP",
        html=html,
        text=f"Your OTP: {otp}. Expires in {expiry_minutes} minutes.",
    )


def build_rate_alert_email(
    recipient: str,
    currency_pair: str,
    direction: str,
    current_rate: float,
    threshold: float,
) -> EmailMessage:
    arrow = "▲" if direction == "up" else "▼"
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Rate Alert: {currency_pair}</h2>
<p>The exchange rate has moved <strong>{direction}</strong> past your threshold.</p>
<table style="border-collapse:collapse;width:100%">
  <tr><td style="padding:8px;border:1px solid #ddd">Currency Pair</td><td style="padding:8px;border:1px solid #ddd">{currency_pair}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd">Current Rate</td><td style="padding:8px;border:1px solid #ddd">{arrow} {current_rate}</td></tr>
  <tr><td style="padding:8px;border:1px solid #ddd">Your Threshold</td><td style="padding:8px;border:1px solid #ddd">{threshold}</td></tr>
</table>
</body></html>"""
    return EmailMessage(
        to=recipient,
        subject=f"Rate Alert: {currency_pair} {arrow} {current_rate}",
        html=html,
        text=f"Rate alert: {currency_pair} is {direction} at {current_rate} (threshold: {threshold}).",
    )


def build_digest_email(
    recipient: str,
    period: str,
    tx_count: int,
    items: List[dict],
) -> EmailMessage:
    rows = "".join(
        f"<tr><td style='padding:6px;border:1px solid #ddd'>{i.get('date','')}</td>"
        f"<td style='padding:6px;border:1px solid #ddd'>{i.get('description','')}</td>"
        f"<td style='padding:6px;border:1px solid #ddd'>{i.get('amount','')}</td></tr>"
        for i in items
    )
    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:auto">
<h2>Activity Digest — {period}</h2>
<p>You had <strong>{tx_count}</strong> transaction(s) this period.</p>
<table style="border-collapse:collapse;width:100%">
  <thead><tr>
    <th style="padding:6px;border:1px solid #ddd;text-align:left">Date</th>
    <th style="padding:6px;border:1px solid #ddd;text-align:left">Description</th>
    <th style="padding:6px;border:1px solid #ddd;text-align:left">Amount</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>
</body></html>"""
    return EmailMessage(
        to=recipient,
        subject=f"Activity Digest: {period}",
        html=html,
        text=f"Activity digest for {period}: {tx_count} transaction(s).",
    )


# ── Utility ────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

def extract_email_from_string(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text)
    return match.group(0) if match else None
