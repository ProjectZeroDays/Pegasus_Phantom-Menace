"""Console stream guard.

Windows consoles - and any redirected/piped stdio - can hand colorama a dead
handle.  colorama's ``AnsiToWin32.write`` then raises
``OSError: [WinError 6] The handle is invalid`` *from inside* logging's emit
path, which produces a ``--- Logging error ---`` traceback for every single
record and can abort interactive commands.

Two independent write paths have to be neutralised:

1. ``colorama.ansitowin32.AnsiToWin32.write`` - the instance method colorama
   installs as ``sys.stdout`` when ``colorama.init()`` runs.
2. ``logging.StreamHandler.emit`` - the framework call that ultimately writes
   to that stream.

Both are patched defensively and idempotently; installing the guard can never
raise, and it never swallows anything other than ``OSError`` from a dead
handle.
"""
from __future__ import annotations

import logging

_INSTALLED = False


def install() -> bool:
    """Install the console guard. Returns True when the guard is active."""
    global _INSTALLED
    if _INSTALLED:
        return True

    # 1. colorama's ANSI writer (instance method on the class).
    try:
        import colorama.ansitowin32 as ansi_win32

        writer_cls = getattr(ansi_win32, "AnsiToWin32", None)
        if writer_cls is not None and hasattr(writer_cls, "write"):
            _orig_write = writer_cls.write

            def _safe_write(self, text, *a, **k):
                try:
                    return _orig_write(self, text, *a, **k)
                except OSError:
                    return len(text) if isinstance(text, str) else 0

            writer_cls.write = _safe_write
    except Exception:  # pragma: no cover - guard must never break import
        pass

    # 2. logging's stream handler emit.
    try:
        _orig_emit = logging.StreamHandler.emit

        def _safe_emit(self, record):
            try:
                return _orig_emit(self, record)
            except OSError:
                return None

        logging.StreamHandler.emit = _safe_emit
    except Exception:  # pragma: no cover
        pass

    _INSTALLED = True
    return True


def is_installed() -> bool:
    return _INSTALLED
