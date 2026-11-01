"""Flask app. Gate first, then routes."""
import pathlib
import uuid

from flask import Flask, jsonify

from pegasus.core.config import host, port
from pegasus.modules import (ai, alerts, agents, antiforensics, auth, autonomous, c2,
                             crypto, delivery, exploits, memory, oauth, ota, parity,
                             relay, report, setup_routes, tenant)

EXEMPT = ("/api/setup", "/api/health", "/api/auth", "/api/beacon", "/api/ai/status",
          "/api/delivery/health", "/static", "/assets", "/l/")
JOBS: dict[str, dict] = {}


class Jobs:
    def submit(self, fn) -> str:
        import threading
        job_id = uuid.uuid4().hex[:12]
        JOBS[job_id] = {"id": job_id, "status": "running", "output": ""}

        def run() -> None:
            try:
                JOBS[job_id]["output"] = str(fn())
                JOBS[job_id]["status"] = "done"
            except Exception as exc:
                JOBS[job_id]["output"] = str(exc)
                JOBS[job_id]["status"] = "failed"

        threading.Thread(target=run, daemon=True).start()
        return job_id


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = pathlib.Path.home().joinpath(".pegasus", ".secret").read_text() \
        if pathlib.Path.home().joinpath(".pegasus", ".secret").exists() else uuid.uuid4().hex

    ok = lambda data, code=200: (jsonify({"ok": True, "data": data}), code)  # noqa: E731
    fail = lambda err, code=400: (jsonify({"ok": False, "error": err}), code)  # noqa: E731
    jobs = Jobs()

    ai.load_schemas()

    @app.before_request
    def _gate():
        from pegasus.modules.ai import providers
        if not providers.needs_setup():
            return None
        from flask import request
        if any(request.path.startswith(p) for p in EXEMPT):
            return None
        return jsonify({"ok": False, "error": "setup required"}), 428

    @app.get("/api/health")
    def health():
        return ok({"status": "ok"})

    @app.get("/api/jobs/<job_id>")
    def job(job_id):
        return ok(JOBS.get(job_id) or {})

    setup_routes.register(app, ok, fail)
    auth.auth_routes.register(app, ok, fail)
    ai.routes.register(app, ok, fail, jobs)
    ai.model_routes.register(app, ok, fail, jobs)
    autonomous.routes.register(app, ok, fail)
    agents.agent_routes.register(app, ok, fail)
    oauth.oauth_routes.register(app, ok, fail)
    delivery.landing.register(app, ok, fail)
    delivery.carrier_routes.register(app, ok, fail)
    c2.beacon_routes.register(app, ok, fail)
    relay.relay_routes.register(app, ok, fail)
    report.report_routes.register(app, ok, fail)
    parity.parity_routes.register(app, ok, fail)
    tenant.tenant_routes.register(app, ok, fail)
    memory.routes.register(app, ok, fail)
    return app


if __name__ == "__main__":
    create_app().run(host=host(), port=port())
