# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Pegasus Phantom Menace v2 Web GUI.

Build:  python -m PyInstaller Pegasus-Web.spec --noconfirm
Output: dist/Pegasus-Web.exe
"""
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 - injected by PyInstaller
PKG = ROOT / "pegasus"
MODULES = PKG / "modules"

#: Built-in module plugins shipped in the executable.
MODULE_NAMES = [
    "device",
    "payload",
    "session",
    "reporting",
    "analysis",
    "exploit",
    "forensics",
    "intelligence",
    "network",
    "ai",
    "passgen",
    "brutdroid",
    "access_workflow",
    "access_workflow",
    "access_workflow/post_exploitation",
]

# --- data files -----------------------------------------------------------
datas = [
    (str(PKG / "ui" / "web" / "dist"), "pegasus/ui/web/dist"),
    (str(MODULES / "access_workflow" / "templates"), "pegasus/modules/access_workflow/templates"),
    (str(MODULES / "access_workflow" / "static"), "pegasus/modules/access_workflow/static"),
    (str(ROOT / "assets" / "icons" / "web" / "pegasus_icon.png"), "assets/icons/web"),
    (str(MODULES / "access_workflow" / "catalog_payloads"), "pegasus/modules/access_workflow/catalog_payloads"),
]

# Ship plugin sources as data so file-based discovery also works when frozen.
for _name in MODULE_NAMES:
    for _file in ("plugin.py", "module.py"):
        _path = MODULES / _name.replace("/", "\\") / _file
        if _path.exists():
            datas.append((str(_path), f"pegasus/modules/{_name}"))

# --- hidden imports -------------------------------------------------------
hiddenimports = [
    "flask",
    "flask_cors",
    "jinja2",
    "werkzeug",
    "rich",
    "click",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.ext.asyncio",
    "aiosqlite",
    "qrcode",
    "PIL",
    "PIL.Image",
    "requests",
    "jinja2.ext",
    "anthropic",
    # Pegasus packages loaded lazily at runtime.
    "pegasus.ui.web.backend.app",
    "pegasus.ui.web.backend.capture",
    "pegasus.ui.web.backend.jobs",
    "pegasus.ui.web.backend.tools",
    "pegasus.ui.web.backend.telemetry",
    "pegasus.modules.access_workflow.workflow_engine",
    "pegasus.modules.access_workflow.campaign_manager",
    "pegasus.modules.access_workflow.rat_module",
    "pegasus.modules.analysis.module",
    "pegasus.modules.integrations.slash_commands",
    "pegasus.modules.access_workflow.auth",
    "pegasus.modules.access_workflow.delivery",
    "pegasus.modules.access_workflow.catalog",
    "pegasus.modules.access_workflow.capabilities",
    "pegasus.modules.access_workflow.nso_ops",
    "pegasus.modules.access_workflow.nso_capabilities",
    "pegasus.modules.access_workflow.dna",
    "pegasus.modules.access_workflow.ai_mutation",
    "pegasus.modules.access_workflow.steganography",
    "pegasus.modules.access_workflow.telegram_control",
    "pegasus.modules.access_workflow.frp_unlock",
    "pegasus.modules.access_workflow.zero_click.registry",
]

# Every module plugin package + submodule, so builtin loading works when frozen.
for _name in MODULE_NAMES:
    _dotted = _name.replace("/", ".")
    hiddenimports.extend(
        [
            f"pegasus.modules.{_dotted}",
            f"pegasus.modules.{_dotted}.plugin",
            f"pegasus.modules.{_dotted}.module",
        ]
    )

a = Analysis(  # noqa: F821
    ["pegasus_web.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PyQt5",
        "PySide6",
        "IPython",
        "notebook",
        "pytest",
        "_pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Pegasus-Web",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / "version-web.txt"),
    icon=[str(ROOT / "assets" / "icons" / "windows" / "pegasus_icon.ico")],
)
