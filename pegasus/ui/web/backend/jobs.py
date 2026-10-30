"""Background job runner with captured output.

Every GUI action that can block (ADB, nmap, workflow runs, payload generation)
is dispatched through :class:`JobManager`. Jobs run on worker threads, stream
their console output into a buffer, and are polled by the front end.
"""
from __future__ import annotations

import asyncio
import inspect
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .capture import StreamCapture

MAX_JOBS = 120


@dataclass
class Job:
    id: str
    kind: str
    title: str
    status: str = "queued"  # queued | running | succeeded | failed | cancelled
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress: float = 0.0
    output: str = ""
    error: Optional[str] = None
    result: Any = None
    meta: Dict[str, Any] = field(default_factory=dict)
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self, include_output: bool = True, tail: Optional[int] = None) -> Dict[str, Any]:
        output = self.output
        if tail is not None and len(output) > tail:
            output = "…\n" + output[-tail:]
        data = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "status": self.status,
            "progress": round(self.progress, 4),
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "durationMs": (
                int(((self.finished_at or time.time()) - self.started_at) * 1000)
                if self.started_at
                else None
            ),
            "error": self.error,
            "cancelRequested": self._cancel.is_set(),
            "meta": self.meta,
        }
        if include_output:
            data["output"] = output
        data["result"] = _jsonable(self.result)
        return data


def _jsonable(value: Any, depth: int = 0) -> Any:
    """Best-effort conversion of dataclasses/SQLAlchemy models to JSON."""
    if depth > 4:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v, depth + 1) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            f: _jsonable(getattr(value, f, None), depth + 1)
            for f in value.__dataclass_fields__
        }
    if hasattr(value, "value") and isinstance(getattr(value, "value"), (str, int)):
        return value.value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    if hasattr(value, "model_dump"):
        try:
            return _jsonable(value.model_dump(), depth + 1)
        except Exception:
            return str(value)
    if hasattr(value, "__dict__") and not isinstance(value, type):
        data = {
            k: _jsonable(v, depth + 1)
            for k, v in vars(value).items()
            if not k.startswith("_")
        }
        if data:
            return data
    return str(value)


class JobManager:
    """Thread-pool-free job manager (one thread per job, bounded history)."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()

    # -- submission ------------------------------------------------------
    def submit(
        self,
        kind: str,
        title: str,
        fn: Callable[["JobContext"], Any],
        meta: Optional[Dict[str, Any]] = None,
        answers: Optional[Dict[str, List[str]]] = None,
    ) -> Job:
        job = Job(id=uuid4().hex[:12], kind=kind, title=title, meta=meta or {})
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > MAX_JOBS:
                stale = self._order.pop(0)
                self._jobs.pop(stale, None)

        thread = threading.Thread(
            target=self._run,
            args=(job, fn, answers or {}),
            name=f"pegasus-job-{job.id}",
            daemon=True,
        )
        thread.start()
        return job

    # -- execution -------------------------------------------------------
    def _run(self, job: Job, fn: Callable[["JobContext"], Any], answers: Dict[str, List[str]]) -> None:
        job.status = "running"
        job.started_at = time.time()
        capture = StreamCapture()
        try:
            with capture:
                ctx = JobContext(job=job, capture=capture, answers=answers)
                result = fn(ctx)
                if inspect.iscoroutine(result):
                    result = _run_coro(result)
                job.result = result
            job.output = _clean(capture.getvalue())
            if job._cancel.is_set():
                job.status = "cancelled"
            else:
                job.status = "succeeded"
                job.progress = 1.0
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            job.output = _clean(capture.getvalue())
            job.error = f"{type(exc).__name__}: {exc}"
            job.status = "cancelled" if job._cancel.is_set() else "failed"
            if not job._cancel.is_set():
                tb = traceback.format_exc(limit=6)
                job.output += ("\n" if job.output else "") + tb
        finally:
            capture.close()
            job.finished_at = time.time()

    # -- queries ---------------------------------------------------------
    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self, limit: int = 30, kind: Optional[str] = None) -> List[Job]:
        with self._lock:
            ids = list(reversed(self._order))
        jobs = [self._jobs[i] for i in ids if i in self._jobs]
        if kind:
            jobs = [j for j in jobs if j.kind == kind]
        return jobs[:limit]

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job._cancel.set()
        return True

    def active(self) -> List[Job]:
        return [j for j in self._jobs.values() if j.status in ("queued", "running")]

    def stats(self) -> Dict[str, Any]:
        jobs = list(self._jobs.values())
        return {
            "total": len(jobs),
            "running": sum(1 for j in jobs if j.status == "running"),
            "queued": sum(1 for j in jobs if j.status == "queued"),
            "succeeded": sum(1 for j in jobs if j.status == "succeeded"),
            "failed": sum(1 for j in jobs if j.status == "failed"),
        }


class JobContext:
    """Handed to job functions: progress, cancellation, log writes."""

    def __init__(self, job: Job, capture: StreamCapture, answers: Dict[str, List[str]]):
        self.job = job
        self.capture = capture
        self.answers = answers
        self._answer_index: Dict[str, int] = {}

    # logging ------------------------------------------------------------
    def log(self, message: str) -> None:
        self.capture.buffer.write(message.rstrip("\n") + "\n")

    def progress(self, value: float) -> None:
        self.job.progress = max(0.0, min(1.0, value))

    @property
    def cancelled(self) -> bool:
        return self.job._cancel.is_set()

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelled("Job cancelled by user")

    # interactive prompts -------------------------------------------------
    def answer(self, prompt: str, default: Optional[str] = None) -> str:
        key = _answer_key(prompt)
        bucket = self.answers.get(key) or self.answers.get("*") or []
        idx = self._answer_index.get(key, 0)
        if idx < len(bucket):
            self._answer_index[key] = idx + 1
            return bucket[idx]
        return default or ""

    def console(self):
        return self.capture.console()


class JobCancelled(RuntimeError):
    """Raised inside a job when the user requests cancellation."""


def _answer_key(prompt: str) -> str:
    cleaned = "".join(ch for ch in prompt.lower() if ch.isalnum() or ch == " ")
    return "_".join(cleaned.split())[:80]


def _clean(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _run_coro(coro):
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    finally:
        pass


jobs = JobManager()


def patch_prompts(ctx: JobContext) -> None:
    """Make Rich prompts answer from job answers instead of blocking on stdin."""
    import rich.prompt as rich_prompt

    def _ask(prompt_obj, prompt="", *, choices=None, default=None, show_default=True,
             show_choices=True, password=False, console=None, **kwargs):
        text = _extract_text(prompt)
        value = ctx.answer(text, str(default) if default is not None else "")
        ctx.log(f"> {text} {value}")
        if choices and value not in choices:
            return str(default if default is not None else choices[0])
        return value

    rich_prompt.Prompt.ask = lambda prompt="", **kw: _ask(None, prompt, **kw)
    rich_prompt.Confirm.ask = lambda prompt="", **kw: _truthy(
        _ask(None, prompt, **kw)
    )
    rich_prompt.IntPrompt.ask = lambda prompt="", **kw: _int(
        _ask(None, prompt, **kw), kw.get("default", 0)
    )


def restore_prompts() -> None:
    import importlib

    import rich.prompt as rich_prompt

    importlib.reload(rich_prompt)


def _extract_text(prompt: Any) -> str:
    if isinstance(prompt, str):
        return prompt
    text = getattr(prompt, "plain", None)
    if text:
        return text
    return str(prompt)


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("y", "yes", "true", "1", "on")


def _int(value: str, default: Any) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        try:
            return int(default)
        except (TypeError, ValueError):
            return 0
