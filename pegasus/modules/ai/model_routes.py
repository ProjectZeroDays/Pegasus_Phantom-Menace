"""Compatibility routes for the old model picker."""
from flask import request

from . import catalog, provision


def register(app, ok, fail, jobs):
    @app.get("/api/models/recommended")
    def models_recommended():
        rows = []
        for role in catalog.Role:
            try:
                repo, quant, backend = catalog.resolve(role)
            except LookupError:
                continue
            rows.append({"id": repo, "quant": quant, "backend": backend,
                         "role": role.value, "files": [f"{repo}:{quant}"]})
        return ok({"tier": catalog.os_key(), "ram_gb": round(catalog.ram_gb(), 1),
                   "models": rows})

    @app.post("/api/models/download")
    def models_download():
        body = request.get_json(silent=True) or {}
        repo, quant = body.get("id"), body.get("quant", "Q4_K_M")
        if not repo:
            return fail("id required")
        return ok({"job": jobs.submit(lambda: str(provision.fetch(repo, quant)))})
