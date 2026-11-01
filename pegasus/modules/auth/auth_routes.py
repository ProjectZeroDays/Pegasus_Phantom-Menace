"""Auth routes."""
from flask import request

from . import operator


def register(app, ok, fail):
    @app.post("/api/auth/login")
    def auth_login():
        body = request.get_json(silent=True) or {}
        csrf = operator.login(body.get("user", ""), body.get("password", ""))
        return ok({"csrf": csrf}) if csrf else fail("bad credentials", 401)

    @app.get("/api/auth/whoami")
    def auth_whoami():
        op = operator.current()
        return ok({"operator": op}) if op else fail("auth required", 401)

    @app.post("/api/auth/bootstrap")
    def auth_bootstrap():
        body = request.get_json(silent=True) or {}
        operator.bootstrap(body.get("user", "admin"), body.get("password", "changeme"))
        return ok({"bootstrapped": True})
