"""Tenant routes."""
from flask import g, request

from ..auth.operator import require
from . import scope


def register(app, ok, fail):
    @app.get("/api/tenants")
    @require()
    def tenants_list():
        rows = scope._db().execute("SELECT o.id, o.name, m.role FROM orgs o"
                                   " JOIN members m ON m.org_id = o.id WHERE m.user=?",
                                   (g.operator["user"],)).fetchall()
        return ok({"orgs": [{"id": r[0], "name": r[1], "role": r[2]} for r in rows]})

    @app.post("/api/tenants")
    @require("admin")
    def tenants_create():
        name = (request.get_json(silent=True) or {}).get("name")
        if not name:
            return fail("name required")
        return ok({"id": scope.create(name)})
