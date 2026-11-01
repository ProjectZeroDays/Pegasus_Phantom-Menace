"""Report routes."""
import pathlib

from flask import request, send_file

from . import pdf_report

OUT = pathlib.Path.home() / ".pegasus" / "reports"


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
