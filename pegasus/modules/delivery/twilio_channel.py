#!/usr/bin/env python3
"""Twilio delivery channel — SMS / MMS / Email."""
from __future__ import annotations
import base64
import os

API = "https://api.twilio.com/2010-04-01"


def _auth() -> tuple[str, str]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    tok = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not tok:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not set")
    return sid, tok


def _post(path: str, data: dict) -> dict:
    import requests
    sid, tok = _auth()
    r = requests.post(f"{API}/Accounts/{sid}{path}", data=data, auth=(sid, tok), timeout=30)
    r.raise_for_status()
    return r.json()


def send_sms(to: str, body: str) -> dict:
    return _post("/Messages.json", {"To": to, "From": os.environ["TWILIO_FROM"], "Body": body})


def send_mms(to: str, body: str, media_url: str) -> dict:
    return _post("/Messages.json", {"To": to, "From": os.environ["TWILIO_FROM"],
                                   "Body": body, "MediaUrl": media_url})


def send_email(to: str, subject: str, body: str, attachment: str | None = None) -> dict:
    """SendGrid when present, SMTP otherwise."""
    import requests
    key = os.environ.get("SENDGRID_API_KEY")
    if key:
        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": os.environ.get("PEGASUS_MAIL_FROM", "pegasus@localhost")},
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }
        if attachment:
            with open(attachment, "rb") as fh:
                payload["attachments"] = [{
                    "content": base64.b64encode(fh.read()).decode(),
                    "filename": os.path.basename(attachment),
                }]
        r = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload,
                          headers={"Authorization": f"Bearer {key}"}, timeout=30)
        r.raise_for_status()
        return {"status": r.status_code, "transport": "sendgrid"}
    # SMTP fallback
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"], msg["Subject"], msg["From"] = to, subject, os.environ.get("PEGASUS_MAIL_FROM", "pegasus@localhost")
    msg.set_content(body)
    if attachment:
        with open(attachment, "rb") as fh:
            msg.add_attachment(fh.read(), maintype="application",
                               subtype="octet-stream", filename=os.path.basename(attachment))
    host = os.environ.get("PEGASUS_SMTP_HOST", "localhost")
    port = int(os.environ.get("PEGASUS_SMTP_PORT", "25"))
    with smtplib.SMTP(host, port) as s:
        if os.environ.get("PEGASUS_SMTP_USER"):
            s.starttls()
            s.login(os.environ["PEGASUS_SMTP_USER"], os.environ.get("PEGASUS_SMTP_PASS", ""))
        s.send_message(msg)
    return {"status": 250, "transport": "smtp"}


def carrier_for(channel: str, requested: str) -> str:
    """Guard: PDF can never be chosen for SMS — carrier stripping is silent."""
    if channel in ("sms", "mms") and requested == "pdf":
        return "link"
    if channel == "messenger" and requested == "pdf":
        return "pdf_lure"  # in-app viewer does not execute JS
    return requested


def send(channel: str, to: str, body: str, media_url: str | None = None,
         subject: str | None = None, attachment: str | None = None) -> dict:
    if channel == "sms":
        return send_sms(to, body)
    if channel == "mms":
        return send_mms(to, body, media_url or "")
    if channel == "email":
        return send_email(to, subject or "Pegasus", body, attachment)
    raise RuntimeError(f"unknown channel {channel}")
