"""Auth routes."""
from flask import request

from . import operator


def register(app, ok, fail):
    @app.post("/api/auth/login")
    def auth_login():
        body = request.get_json(silent=True) or {}
        csrf = operator.login(body.get("user", ""), body.get("password", ""))
        if not csrf:
            return fail("bad credentials", 401)
        resp = jsonify({"ok": True, "data": {"csrf": csrf}})
        resp.set_cookie("csrf_token", csrf, samesite="Strict", httponly=False)
        return resp

    @app.get("/api/auth/whoami")
    def auth_whoami():
        op = operator.current()
        return ok({"operator": op}) if op else fail("auth required", 401)

    @app.get("/api/admin/users")
    @operator.require("admin")
    def admin_users_list():
        return ok({"users": operator.list_users()})

    @app.post("/api/admin/users")
    @operator.require("admin")
    def admin_users_create():
        body = request.get_json(silent=True) or {}
        user = (body.get("user") or "").strip()
        password = body.get("password") or ""
        role = body.get("role", "operator")
        if not user or not password:
            return fail("user and password required")
        try:
            op_id = operator.create_user(user, password, role)
        except Exception as exc:
            return fail(f"create failed: {exc}")
        return ok({"id": op_id, "user": user, "role": role})

    @app.patch("/api/admin/users/<int:op_id>")
    @operator.require("admin")
    def admin_users_update(op_id: int):
        body = request.get_json(silent=True) or {}
        role = body.get("role")
        try:
            ok_chg = operator.update_user(op_id, role)
        except ValueError as exc:
            return fail(str(exc))
        return ok({"updated": ok_chg})

    @app.delete("/api/admin/users/<int:op_id>")
    @operator.require("admin")
    def admin_users_delete(op_id: int):
        try:
            ok_del = operator.delete_user(op_id)
        except ValueError as exc:
            return fail(str(exc))
        return ok({"deleted": ok_del})

    @app.post("/api/admin/users/<int:op_id>/password")
    @operator.require("admin")
    def admin_users_password(op_id: int):
        body = request.get_json(silent=True) or {}
        new_password = body.get("password") or ""
        if len(new_password) < 8:
            return fail("password must be at least 8 characters")
        ok_pw = operator.change_password(op_id, new_password)
        return ok({"changed": ok_pw})

    @app.post("/api/auth/password")
    def auth_password_change():
        op = operator.current()
        if not op:
            return fail("auth required", 401)
        body = request.get_json(silent=True) or {}
        old = body.get("old_password") or ""
        new = body.get("new_password") or ""
        if len(new) < 8:
            return fail("new password must be at least 8 characters")
        # verify old password indirectly by attempting login semantics
        csrf = operator.login(op["user"], old)
        if not csrf:
            return fail("old password incorrect", 401)
        rows = operator.list_users()
        target = next((u for u in rows if u["user"] == op["user"]), None)
        if not target:
            return fail("user not found")
        operator.change_password(target["id"], new)
        return ok({"changed": True})

    @app.post("/api/auth/bootstrap")
    def auth_bootstrap():
        body = request.get_json(silent=True) or {}
        operator.bootstrap(body.get("user", "admin"), body.get("password", "changeme"))
        return ok({"bootstrapped": True})
