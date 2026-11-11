"""Workflow routes: autonomous lifecycle run history and success rates.

The console's Mission Control and Workflow Engine panels read the run
history from ``GET /api/workflows`` and launch new lifecycle runs through
``POST /api/workflows/run``.  Both delegate to the autonomous engine
(``pegasus.modules.autonomous.engine``), which is also reachable directly
through ``/api/autonomous/*`` - so this module adds no new exposure, it
only gives the console the shape it expects.

History is persisted to ``~/.pegasus/workflow_history.json`` so the
"exploit success by vector" panel survives a restart.
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
from typing import Any, Dict, List

from flask import request

from pegasus.modules.autonomous import engine

from .jobs import jobs

HISTORY_PATH = pathlib.Path.home() / ".pegasus" / "workflow_history.json"
MAX_HISTORY = 200
TERMINAL = (engine.Phase.DONE, engine.Phase.FAILED)

_LOCK = threading.Lock()


def _load() -> List[Dict[str, Any]]:
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def _save(entries: List[Dict[str, Any]]) -> None:
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_PATH.write_text(
            json.dumps(entries[-MAX_HISTORY:], indent=2, default=str), encoding="utf-8"
        )
    except Exception:
        pass


def _record(entry: Dict[str, Any]) -> None:
    with _LOCK:
        entries = _load()
        entries.append(entry)
        _save(entries)


def _rates(history: List[Dict[str, Any]]) -> Dict[str, float]:
    """Per-vector success percentage."""
    totals: Dict[str, int] = {}
    wins: Dict[str, int] = {}
    for entry in history:
        vector = entry.get("vector")
        if not vector:
            continue
        totals[vector] = totals.get(vector, 0) + 1
        if entry.get("overall_success"):
            wins[vector] = wins.get(vector, 0) + 1
    return {v: round(100.0 * wins.get(v, 0) / n, 1) for v, n in totals.items()}


def _primary_vector(run) -> str:
    best = None
    for target in getattr(run, "targets", []) or []:
        if best is None or (getattr(target, "score", 0) or 0) > (getattr(best, "score", 0) or 0):
            best = target
    return (getattr(best, "vector", None) or "") if best is not None else ""


def _primary_target(run) -> str:
    best = None
    for target in getattr(run, "targets", []) or []:
        if best is None or (getattr(target, "score", 0) or 0) > (getattr(best, "score", 0) or 0):
            best = target
    return (getattr(best, "serial", None) or "") if best is not None else ""


def register(app, ok, fail):
    @app.get("/api/workflows")
    def workflow_history():
        """Recorded lifecycle runs plus per-vector success rates."""
        history = _load()
        return ok({
            "history": history[-MAX_HISTORY:],
            "rates": _rates(history),
        })

    @app.post("/api/workflows/run")
    def workflow_run():
        """Launch an autonomous lifecycle run and track it as a job."""
        body = request.get_json(silent=True) or {}
        target = str(body.get("target") or "").strip()
        category = str(body.get("category") or "full_lifecycle").strip()
        if not target:
            return fail("target required")

        try:
            decision_timeout = int(body.get("decision_timeout") or 3600)
        except (TypeError, ValueError):
            decision_timeout = 3600

        def _drive(ctx):
            started = time.time()
            stages: List[Dict[str, Any]] = []
            run = engine.start({
                "target": target,
                "category": category,
                "decision_timeout": decision_timeout,
            })
            ctx.log(f"workflow {run.id} started for {target}")
            last = None
            while True:
                phase = run.phase
                if phase is not last:
                    last = phase
                    stages.append({
                        "name": getattr(phase, "value", str(phase)),
                        "status": "done",
                        "output": "",
                    })
                    ctx.log(f"phase: {getattr(phase, 'value', phase)}")
                    ctx.progress(min(0.95, len(stages) / 12.0))
                if phase in TERMINAL:
                    break
                if ctx.cancelled:
                    ctx.log("cancelled by operator")
                    break
                time.sleep(1.0)

            duration_ms = int((time.time() - started) * 1000)
            success = (run.phase is engine.Phase.DONE
                       and getattr(run, "decision", None) != "abort")
            entry = {
                "id": run.id,
                "run_id": run.id,
                "workflow": category,
                "target": _primary_target(run) or target,
                "category": category,
                "status": getattr(run.phase, "value", str(run.phase)),
                "overall_success": bool(success),
                "start_time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
                "total_duration_ms": duration_ms,
                "vector": _primary_vector(run),
                "stages": stages,
            }
            _record(entry)
            ctx.progress(1.0)
            return entry

        job = jobs.submit("workflow", f"Workflow: {category}", _drive, meta={
            "target": target,
            "category": category,
        })
        return ok({"job": job.to_dict(include_output=False)})
