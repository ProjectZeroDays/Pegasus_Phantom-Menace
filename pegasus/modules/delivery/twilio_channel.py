"""Twilio SMS/MMS and SendGrid email."""
import base64
import os

import requests

from pegasus.core.config import public_url

API = "https://api.twilio.com/2010-04-01"


def _creds() -> tuple[str, str]:
    sid, token = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN unset")
    return sid, token


def _post(path: str, data: dict) -> dict:
    sid, token = _creds()
    r = requests.post(f"{API}/Accounts/{sid}{path}", data=data, auth=(sid, token),
                      timeout=30)
    r.raise_for_status()
    return r.json()


def send_sms(to: str, body: str) -> dict:
    return _post("/Messages.json", {"To": to, "From": os.environ["TWILIO_FROM"],
                                    "Body": body})


def send_mms(to: str, body: str, media_url: str) -> dict:
    return _post("/Messages.json", {"To": to, "From": os.environ["TWILIO_FROM"],
                                    "Body": body, "MediaUrl": media_url})


def send_file(channel: str, to: str, path: str, body: str = "",
              js_capable: bool = True) -> dict:
    url = f"{public_url()}/api/delivery/media/{os.path.basename(path)}"
    if channel in ("sms", "mms"):
        return send_mms(to, body or "Document attached.", url)
    if channel == "email":
        return send_email(to, "Document", body or "See attached.", path)
    raise ValueError(f"{channel} needs its own adapter")


def send_email(to: str, subject: str, body: str, attachment: str | None = None) -> dict:
    key = os.environ.get("SENDGRID_API_KEY")
    if not key:
        raise RuntimeError("SENDGRID_API_KEY unset")
    payload = {"personalizations": [{"to": [{"email": to}]}],
               "from": {"email": os.environ.get("PEGASUS_MAIL_FROM", "pegasus@localhost")},
               "subject": subject,
               "content": [{"type": "text/plain", "value": body}]}
    if attachment:
        with open(attachment, "rb") as fh:
            payload["attachments"] = [{"content": base64.b64encode(fh.read()).decode(),
                                       "filename": os.path.basename(attachment)}]
    r = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload,
                      headers={"Authorization": f"Bearer {key}"}, timeout=30)
    r.raise_for_status()
    return {"status": r.status_code}


def carrier_of(number: str) -> str | None:
    try:
        sid, token = _creds()
    except RuntimeError:
        return None
    r = requests.get(f"https://lookups.twilio.com/v2/PhoneNumbers/{number}",
                     params={"Fields": "line_type_intelligence"},
                     auth=(sid, token), timeout=20)
    if r.status_code != 200:
        return None
    name = ((r.json().get("line_type_intelligence") or {}).get("carrier_name") or "")
    return name.lower() or None
