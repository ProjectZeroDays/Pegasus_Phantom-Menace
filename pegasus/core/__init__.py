"""Core primitives."""

from pegasus.core.console_guard import install as _install_console_guard

# Neutralise dead-console handle errors (OSError [WinError 6]) on Windows and
# under redirected stdio, for every entry point: CLI, TUI, Flask backend and
# background jobs.
_install_console_guard()
