"""Delivery routes: media, links, dispatch, receipts, health."""
import pathlib

from flask import abort, request, send_from_directory

from ..c2 import ratelimit
from . import carriers, health, landing, receipts

MEDIA = pathlib.Path.home() / ".pegasus" / "media"


def register(app, ok, fail):
    @app.before_request
    def _bucket():
        if request.path.startswith("/api/delivery/") and not ratelimit.allow(
                f"dl:{request.remote_addr}"):
            return fail("rate limited", 429)
        return None

    @app.get("/api/delivery/media/<name>")
    def delivery_media(name):
        MEDIA.mkdir(parents=True, exist_ok=True)
        if not (MEDIA / name).exists():
            abort(404)
        return send_from_directory(MEDIA, name)

    @app.get("/api/delivery/receipts")
    def delivery_receipts():
        return ok({"receipts": receipts.list_for(request.args.get("run_id"))})

    @app.post("/api/delivery/link")
    def delivery_link():
        body = request.get_json(silent=True) or {}
        from pegasus.core.config import public_url
        return ok({"url": f"{public_url()}/l/{landing.mint(body.get('artifacts') or {})}"})

    @app.post("/api/delivery/carrier")
    def delivery_carrier():
        body = request.get_json(silent=True) or {}
        if not body.get("target") or not body.get("channel"):
            return fail("target and channel required")
        run_id = body.get("run_id")
        try:
            res = carriers.dispatch(body["channel"], body.get("carrier", "link"),
                                    body["target"], body)
        except Exception as exc:
            receipts.record(run_id, body["channel"], body.get("carrier", "?"),
                            body["target"], {}, str(exc))
            return fail(str(exc), 502)
        receipt = receipts.record(run_id, body["channel"], res.get("carrier", "?"),
                                  body["target"], res)
        return ok({"receipt": receipt, "result": res})
