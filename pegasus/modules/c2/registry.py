"""DNA -> run binding. Orphans are kept, not dropped."""
import json
import pathlib
import threading
import time

ORPHANS = pathlib.Path.home() / ".pegasus" / "orphans"
_BY_DNA: dict[str, str] = {}
_BY_RUN: dict[str, str] = {}
_LOCK = threading.Lock()


def bind(dna: str, run_id: str) -> None:
    with _LOCK:
        _BY_DNA[dna] = run_id
        _BY_RUN[run_id] = dna


def unbind(run_id: str) -> None:
    with _LOCK:
        dna = _BY_RUN.pop(run_id, None)
        if dna:
            _BY_DNA.pop(dna, None)


def run_for(dna: str) -> str | None:
    return _BY_DNA.get(dna)


def append(dna: str, body: dict) -> None:
    run_id = run_for(dna)
    if not run_id:
        ORPHANS.mkdir(parents=True, exist_ok=True)
        with (ORPHANS / f"{dna}.jsonl").open("a") as fh:
            fh.write(json.dumps({"ts": time.time(), **body}) + "\n")
        return
    from ..autonomous import engine
    run = engine.get(run_id)
    if run:
        run.absorb(body)
