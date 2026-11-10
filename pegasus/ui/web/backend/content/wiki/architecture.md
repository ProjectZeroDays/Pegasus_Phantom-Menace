# Architecture

Pegasus runs as three cooperating layers.

## Backend

A Flask application in `pegasus/ui/web/backend`. Every route module exposes
`register(app, ok, fail)` and is wired from `create_app()`. Module state that
must survive a reinstall lives under `~/.pegasus` as JSON.

## Plugin layer

`pegasus/core/plugin` loads built-in modules listed in `BUILTIN_MODULES`.
Each module lives in `pegasus/modules/<name>/` with a `module.py`, a
`plugin.py` carrying `PluginMetadata`, and a `create_plugin` factory.

## Frontend

A Vite + React console in `pegasus/ui/web/src`. Pages are routed by `wouter`,
navigation is declared once in `nav.ts`, and the shared primitives live in
`components/ui.tsx`.

## Desktop shell

`electron/` wraps the backend in a Chromium shell. `main.js` resolves the
Python interpreter and the launcher script inside the packaged `resources`
directory.
