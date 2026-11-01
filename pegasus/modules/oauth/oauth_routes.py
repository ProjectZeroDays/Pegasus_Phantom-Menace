"""OAuth routes."""
from flask import redirect, request

from . import broker


def register(app, ok, fail):
    @app.get("/api/oauth/status")
    def oauth_status():
        return ok({"linked": {p: bool(broker.token(p)) for p in broker.PROVIDERS}})

    @app.post("/api/oauth/begin/<provider>")
    def oauth_begin(provider):
        if provider not in broker.PROVIDERS:
            return fail("unknown provider", 404)
        try:
            return ok(broker.begin(provider, f"{broker.callback_base()}/{provider}"))
        except KeyError as exc:
            return fail(f"missing env for {provider}: {exc}", 500)

    @app.get("/api/oauth/callback/<provider>")
    def oauth_callback(provider):
        if request.args.get("error"):
            return redirect(f"/settings?linked={provider}&error={request.args['error']}")
        try:
            broker.complete(provider, request.args["code"], request.args["state"])
        except Exception as exc:
            return redirect(f"/settings?linked={provider}&error={exc}")
        return redirect(f"/settings?linked={provider}")

    @app.post("/api/oauth/telegram/verify")
    def oauth_telegram():
        return ok({"valid": broker.telegram_verify(dict(request.get_json(silent=True) or {}))})

    @app.post("/api/oauth/signal/link")
    def oauth_signal():
        uri = (request.get_json(silent=True) or {}).get("uri", "")
        if not uri.startswith("sgnl://"):
            return fail("expected an sgnl:// device-link URI")
        return ok(broker.relay_signal(uri))
