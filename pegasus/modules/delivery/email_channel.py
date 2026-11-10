"""Email: mailto link with optional SMTP send when credentials are configured."""
import os
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from .adapter import Adapter


class Email(Adapter):
    channel, kinds = "email", frozenset({"link", "apk", "pdf", "photo"})

    def deliver(self, kind, target, body):
        subject = body.get("subject") or "Document"
        message = body.get("message") or "Please review the attached document."
        link = self.link(body)
        if kind == "link":
            return {"mailto": f"mailto:{quote(target)}?subject={quote(subject)}&body={quote(message)}",
                    "link": link}
        # Optional real SMTP delivery when credentials are present
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        if smtp_host and smtp_user and smtp_pass:
            try:
                msg = EmailMessage()
                msg["Subject"] = subject
                msg["From"] = smtp_user
                msg["To"] = target
                msg.set_content(message)
                attachment = body.get("path")
                if attachment:
                    import pathlib, mimetypes
                    data = pathlib.Path(attachment).read_bytes()
                    ctype, _ = mimetypes.guess_type(attachment)
                    maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
                    msg.add_attachment(data, maintype=maintype, subtype=subtype,
                                       filename=pathlib.Path(attachment).name)
                with smtplib.SMTP(smtp_host, 587, timeout=60) as s:
                    s.starttls()
                    s.login(smtp_user, smtp_pass)
                    s.send_message(msg)
                return {"sent": True, "to": target, "via": "smtp", "link": link}
            except Exception as exc:  # noqa: BLE001 -- defensive, fall back to link
                return {"error": f"{type(exc).__name__}: {exc}", "link": link,
                        "note": "SMTP send failed; link fallback included"}
        return {"mailto": f"mailto:{quote(target)}?subject={quote(subject)}&body={quote(message)}",
                "link": link,
                "note": "no SMTP credentials configured; mailto/link fallback used"}
