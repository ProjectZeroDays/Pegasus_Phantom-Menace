"""Report routes."""
import pathlib

from flask import request, send_file

from . import pdf_report

OUT = pathlib.Path.home() / ".pegasus" / "reports"


def list_reports() -> list:
    """The report artefacts on disk, newest first."""
    if not OUT.exists():
        return []
    entries = []
    for path in sorted(OUT.glob("*.pdf"),
                       key=lambda p: p.stat().st_mtime,
                       reverse=True):
        stat = path.stat()
        entries.append({
            "name": path.stem,
            "format": path.suffix.lstrip(".").upper() or "PDF",
            "path": str(path),
            "size": stat.st_size,
            "created_at": stat.st_mtime,
        })
    return entries


def register(app, ok, fail):
    @app.post("/api/report")
    def report_build():
        run_id = (request.get_json(silent=True) or {}).get("run_id")
        if not run_id:
            return fail("run_id required")
        return ok({"path": str(pdf_report.build(run_id, OUT / f"{run_id}.pdf"))})

    @app.get("/api/report/<run_id>")
    def report_get(run_id):
        path = OUT / f"{run_id}.pdf"
        if not path.exists():
            return fail("not built", 404)
        return send_file(path, as_attachment=True)
