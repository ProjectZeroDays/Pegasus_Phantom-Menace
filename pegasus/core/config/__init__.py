import os
from pathlib import Path


def port() -> int:
    return int(os.environ.get("PEGASUS_PORT", "5001"))


def host() -> str:
    return os.environ.get("PEGASUS_HOST", "127.0.0.1")


def base_url() -> str:
    h = "127.0.0.1" if host() in ("0.0.0.0", "::") else host()
    return f"http://{h}:{port()}"


# ---------------------------------------------------------------------------
# Settings object — attribute + method surface used across the codebase
# ---------------------------------------------------------------------------

_HOME = Path.home() / ".pegasus"


class _PluginDirs(dict):
    """Mapping of plugin name -> config, plus the plugin_dirs list."""

    plugin_dirs: list[Path] = [Path("pegasus/modules")]

    def get(self, key, default=None):  # noqa: A001 — dict API
        return dict.get(self, key, default)


class Settings:
    version: str = "2.1.0"

    class ai:
        api_key = None
        model = "claude-sonnet-4-6"

    class database:
        path = str(_HOME / "pegasus.db")
        type = "sqlite"
        url = f"sqlite:///{_HOME / 'pegasus.db'}"
        echo = False
        pool_size = 5
        max_overflow = 10


class _Config:
    def __init__(self):
        self.app = type("App", (), {"version": "2.1.0", "name": "Pegasus Phantom Menace"})()
        self.ai = Settings.ai()
        self.database = Settings.database()
        self.plugins = _PluginDirs()
        self.workspace = type(
            "Workspace",
            (),
            {
                "workspace": str(_HOME),
                "databasePath": str(_HOME / "pegasus.db"),
                "reportsDir": str(_HOME / "reports"),
                "payloadsDir": str(_HOME / "payloads"),
                "logsDir": str(_HOME / "logs"),
                "aiConfigured": True,
                "version": "2.1.0",
            },
        )()
        self.environment = type(
            "Env",
            (),
            {
                "hostname": os.environ.get("COMPUTERNAME", "host"),
                "localIp": "127.0.0.1",
                "python": ".".join(map(str, __import__("sys").version_info[:3])),
                "platform": os.environ.get("OS", "win32").lower().split(" ")[0],
                "pid": os.getpid(),
                "cwd": os.getcwd(),
            },
        )()

    # -- workspace helpers used by the web backend ------------------------
    def get_workspace_path(self) -> Path:
        p = _HOME
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_logs_dir(self) -> Path:
        p = _HOME / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_reports_dir(self) -> Path:
        p = _HOME / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_payloads_dir(self) -> Path:
        p = _HOME / "payloads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_database_path(self) -> Path:
        return _HOME / "pegasus.db"


_settings = _Config()


def get_settings() -> _Config:
    return _settings


# ---------------------------------------------------------------------------
# Module-level workspace helpers (legacy interface used across the codebase)
# ---------------------------------------------------------------------------

def get_workspace() -> Path:
    return _settings.get_workspace_path()


def get_workspace_path() -> Path:
    return _settings.get_workspace_path()


def get_payloads_dir() -> Path:
    return _settings.get_payloads_dir()


def get_reports_dir() -> Path:
    return _settings.get_reports_dir()


def get_logs_dir() -> Path:
    return _settings.get_logs_dir()


def get_database_path() -> Path:
    return _settings.get_database_path()
