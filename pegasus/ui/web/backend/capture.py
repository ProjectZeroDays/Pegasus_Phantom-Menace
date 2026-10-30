"""Output capture utilities.

Pegasus modules write to a Rich ``Console`` and, in a few places, to raw
stdout/file-descriptor 1 (``subprocess.run`` without ``capture_output``).
To surface that output in the web GUI we capture all three layers:

* ``sys.stdout`` / ``sys.stderr`` replacements (Python-level writes),
* file descriptor 1/2 duplication into a temporary file (C-level writes),
* a Rich ``Console`` bound to the same buffer (styled markup stripped).

The context manager is thread-safe per instance; jobs each get their own.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from typing import Optional

from rich.console import Console


class StreamCapture:
    """Capture Python-level and file-descriptor-level output."""

    def __init__(self) -> None:
        self.buffer = io.StringIO()
        self._tmp = tempfile.TemporaryFile(mode="w+b")
        self._saved: list[tuple[int, int]] = []
        self._old_stdout = None
        self._old_stderr = None
        self._active = False
        self._rich_restore: list[tuple[Any, bool]] = []
        self._old_columns: Optional[str] = None

    # -- context manager -------------------------------------------------
    def __enter__(self) -> "StreamCapture":
        self._active = True
        self._disable_legacy_windows()
        # Module consoles are created at import time with a default width; Rich
        # honours COLUMNS for every console it renders, so tables are not
        # truncated (e.g. CVE identifiers) in captured output.
        self._old_columns = os.environ.get("COLUMNS")
        os.environ["COLUMNS"] = "180"
        sys.stdout.flush()
        sys.stderr.flush()
        self._old_stdout, self._old_stderr = sys.stdout, sys.stderr
        # Python-level writes go only into the string buffer; descriptor-level
        # writes (subprocess children, C extensions) land in the temp file.
        # Tee-ing to the original stream as well would duplicate every line,
        # because that stream's descriptor is redirected to the same temp file.
        sys.stdout = _Tee(self.buffer, None)
        sys.stderr = _Tee(self.buffer, None)
        try:
            for fd in (1, 2):
                saved = os.dup(fd)
                self._saved.append((fd, saved))
                os.dup2(self._tmp.fileno(), fd)
        except OSError:
            # Non-standard streams (some Windows services): python-level only.
            pass
        return self

    def _disable_legacy_windows(self) -> None:
        """Keep Unicode box-drawing glyphs instead of cp437 substitutions.

        Rich renders tables with ``┌─┐`` unless ``legacy_windows`` is on; on
        Windows that flag trips even with a captured stream and the emitted
        characters become unmappable mojibake in JSON.
        """
        try:
            import rich.console as rich_console

            self._rich_restore.append((rich_console, rich_console.WINDOWS))
            rich_console.WINDOWS = False
        except Exception:
            return
        # Consoles created at import time already latched the flag; flip them.
        for name, module in list(sys.modules.items()):
            if name is None or not name.startswith("pegasus"):
                continue
            try:
                values = list(vars(module).values())
            except TypeError:
                continue
            for value in values:
                if value.__class__.__name__ == "Console" and hasattr(
                    value, "legacy_windows"
                ):
                    self._rich_restore.append((value, value.legacy_windows))
                    try:
                        value.legacy_windows = False
                    except Exception:
                        pass

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        for fd, saved in reversed(self._saved):
            try:
                os.dup2(saved, fd)
                os.close(saved)
            except OSError:
                pass
        self._saved.clear()
        sys.stdout = self._old_stdout or sys.__stdout__
        sys.stderr = self._old_stderr or sys.__stderr__
        try:
            self._tmp.seek(0)
            data = self._tmp.read().decode("utf-8", errors="replace")
            if data:
                self.buffer.write(data)
        except Exception:
            pass
        for target, value in reversed(self._rich_restore):
            try:
                if hasattr(target, "legacy_windows"):
                    target.legacy_windows = value
                else:
                    setattr(target, "WINDOWS", value)
            except Exception:
                pass
        self._rich_restore.clear()
        if self._old_columns is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = self._old_columns
        self._active = False
        return False

    # -- accessors -------------------------------------------------------
    def getvalue(self) -> str:
        return self.buffer.getvalue()

    def console(self, **kwargs) -> Console:
        """A Rich console writing plain text into this capture.

        ``legacy_windows=False`` keeps Unicode box-drawing/icon glyphs intact —
        otherwise Rich substitutes cp437-era characters and the captured log
        renders as mojibake in the HTTP response.
        """
        return Console(
            file=self.buffer,
            force_terminal=False,
            color_system=None,
            legacy_windows=False,
            width=kwargs.pop("width", 180),
            highlight=False,
            markup=True,
            **kwargs,
        )

    def close(self) -> None:
        try:
            self._tmp.close()
        except Exception:
            pass


class _Tee(io.TextIOBase):
    def __init__(self, primary: io.StringIO, secondary: Optional[io.TextIOBase]) -> None:
        self._primary = primary
        self._secondary = secondary

    def write(self, s: str) -> int:  # type: ignore[override]
        self._primary.write(s)
        if self._secondary is not None:
            try:
                self._secondary.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        try:
            self._primary.flush()
        except Exception:
            pass
        if self._secondary is not None:
            try:
                self._secondary.flush()
            except Exception:
                pass

    @property
    def encoding(self) -> str:  # type: ignore[override]
        return "utf-8"

    def isatty(self) -> bool:  # type: ignore[override]
        return False


class TeeBuffer:
    """Thread-safe-ish append-only line buffer used by long-running jobs."""

    def __init__(self, limit: int = 400_000) -> None:
        self._parts: list[str] = []
        self._size = 0
        self._limit = limit

    def write(self, text: str) -> None:
        if not text:
            return
        self._parts.append(text)
        self._size += len(text)
        while self._size > self._limit and len(self._parts) > 1:
            dropped = self._parts.pop(0)
            self._size -= len(dropped)

    def getvalue(self) -> str:
        return "".join(self._parts)
