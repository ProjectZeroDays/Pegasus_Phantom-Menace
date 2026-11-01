"""Autonomous routes."""
from flask import request

from . import engine


def register(app, ok, fail):
    @app.post("/api/autonomous/start")
    def autonomous_start():
        return ok({"run": engine.start(request.get_json(silent=True) or {}).snapshot()})

    @app.get("/api/autonomous/<run_id>")
    def autonomous_status(run_id):
        run = engine.get(run_id)
        if not run:
            return fail("unknown run", 404)
        return ok({"run": run.snapshot()})

    @app.post("/api/autonomous/<run_id>/decision")
    def autonomous_decision(run_id):
        decision = (request.get_json(silent=True) or {}).get("decision")
        if decision not in ("maintain", "wipe", "abort"):
            return fail("decision must be maintain | wipe | abort")
        if not engine.decide(run_id, decision):
            return fail("not awaiting a decision", 409)
        return ok({"decision": decision})
