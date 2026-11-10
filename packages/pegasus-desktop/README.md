# @ProjectZeroDays/pegasus-desktop

Pegasus Phantom Menace — desktop shell for Windows.

This package contains the Electron wrapper (`main.js`, `preload.js`, `renderer/`) plus the
Inno Setup installer scripts (`installer.nsh`, `pegasus.iss`) used to build the signed
Windows installer published on GitHub Releases.

## Install

```bash
npm install @ProjectZeroDays/pegasus-desktop --registry=https://npm.pkg.github.com
```

GitHub Packages requires an authenticated token:

```bash
# .npmrc
registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NODE_AUTH_TOKEN}
```

> The token needs the `write:packages` scope for the `ProjectZeroDays` account.

## Run

```bash
npx pegasus-desktop
```

The Electron main process resolves the Python backend in this order:

1. `PEGASUS_PYTHON` (explicit interpreter override)
2. `python` / `python3` on `PATH`
3. `<install>/resources/pegasus/venv/Scripts/python.exe` (packaged venv)

and then locates the launcher script (`start_server.py`, falling back to `run_server.py`) next to
the packaged `pegasus` package.

## Windows installer

The full desktop build (setup + portable) is published on the GitHub release for each tag:

https://github.com/ProjectZeroDays/Pegasus_Phantom-Menace/releases

## Notes

- Authorized security testing and auditing only.
- The package is the desktop shell only; the Python backend (`pegasus/`) and the web console
  (`pegasus/ui/web/dist`) are bundled into the installer by electron-builder's `extraResources`.

## License

MIT — see the repository `LICENSE`.
