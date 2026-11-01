"""AI routes. Sync handlers; the async router is bridged per call."""
import asyncio
import dataclasses

from flask import request

from . import catalog, chain, provision, router, store


def _run(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def register(app, ok, fail, jobs):
    spend = chain.Chain(["local"])

    @app.get("/api/ai/status")
    def ai_status():
        out = {}
        for role in catalog.Role:
            try:
                repo, quant, backend = catalog.resolve(role)
            except LookupError:
                repo, quant, backend = "", "", "none"
            out[role.value] = {"model": repo, "quant": quant, "backend": backend,
                               "tier": f"{catalog.os_key()}/{round(catalog.ram_gb(), 1)}GB"}
        return ok(out)

    @app.post("/api/ai/generate")
    def ai_generate():
        body = request.get_json(silent=True) or {}
        if not body.get("prompt"):
            return fail("prompt required")
        role = catalog.Role(body.get("role", "planner"))
        res = _run(router.generate(role, body["prompt"], body.get("schema"),
                                   body.get("temp"), body.get("case")))
        return ok(res)

    @app.post("/api/ai/provision")
    def ai_provision():
        role = catalog.Role((request.get_json(silent=True) or {}).get("role", "planner"))
        repo, quant, _ = catalog.resolve(role)
        return ok({"job": jobs.submit(lambda: str(provision.fetch(repo, quant)))})

    @app.get("/api/ai/turns")
    def ai_turns():
        return ok({"turns": store.turns(request.args.get("case"))})

    @app.get("/api/ai/spend")
    def ai_spend():
        return ok(spend.snapshot())
