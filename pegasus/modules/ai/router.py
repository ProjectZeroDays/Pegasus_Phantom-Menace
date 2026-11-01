"""Backend ranking, retry ladder, QBrain floor."""
import asyncio
import os

from . import catalog, grammar, prompt, qbrain, store, thermal, validator
from .backends import get as get_backend

TEMP = {catalog.Role.PLANNER: 0.25, catalog.Role.CODER: 0.6}
MAXT = {catalog.Role.PLANNER: 512, catalog.Role.CODER: 2048}
STOP = {catalog.Role.PLANNER: ["\n\n"], catalog.Role.CODER: []}
ORDER = {"mlx": 0, "llamacpp": 1, "remote": 2}


def _rank(role: catalog.Role) -> list:
    if os.environ.get("PEGASUS_AI", "1") == "0":
        return []
    _, _, backend = catalog.resolve(role)
    names = [backend]
    if thermal.pressure() and "remote" not in names:
        names.insert(0, "remote")
    names.sort(key=lambda n: ORDER.get(n, 9))
    return [get_backend(n) for n in names if n in ORDER]


async def generate(role: catalog.Role, task: str, schema: dict | None = None,
                   temp: float | None = None, case: str | None = None) -> dict:
    text = store.scrub(task, case)
    repo = catalog.resolve(role)[0] if _rank(role) else ""
    full = prompt.render(role.value, text, schema, repo,
                         reference=prompt.corpus.context(text) if schema else "")
    for backend in _rank(role):
        if not await backend.health():
            continue
        if schema and not backend.supports_grammar():
            res = await _post_validate(backend, role, full, schema, temp)
        else:
            res = await _generate(backend, role, full, schema, temp)
        if res:
            store.record(role, full, res["text"], res["backend"], res["model"],
                         "n/a" if not schema else "pass", case)
            return res
    out = qbrain.fallback(role, task)
    store.record(role, full, out["text"], "qbrain", "rules", "fallback", case)
    return out


async def _generate(backend, role, full, schema, temp) -> dict | None:
    g = grammar.gbnf(schema) if schema else None
    mode = "constrained" if schema else "native"
    for attempt in range(3):
        res = await backend.generate(full, g, temp if temp is not None else TEMP[role],
                                     MAXT[role], STOP[role], mode)
        if not schema:
            return {"text": res.text, "backend": res.backend, "model": res.model}
        ok, why = validator.validate(res.text, schema)
        if ok:
            return {"text": res.text, "backend": res.backend, "model": res.model}
        full = f"{full}\n\nPrevious attempt failed: {why}. JSON only."
    return None


async def _post_validate(backend, role, full, schema, temp) -> dict | None:
    for attempt in range(3):
        t = max(0.1, (temp or TEMP[role]) - 0.1 * attempt)
        res = await backend.generate(full, None, t, MAXT[role], STOP[role], "native")
        ok, why = validator.validate(res.text, schema)
        if ok:
            return {"text": res.text, "backend": res.backend, "model": res.model}
        full = f"{full}\n\nFailed: {why}. JSON only, no prose."
        await asyncio.sleep(0.05)
    return None
