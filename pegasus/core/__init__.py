"""
Pegasus Phantom Menace v2 - Core Package
"""
from pegasus_v2.core.config import get_settings, Settings
from pegasus_v2.core.plugin import (
    Plugin,
    PluginMetadata,
    PluginManager,
    HookManager,
    HookType,
    CommandInfo,
    UIComponent,
    initialize_plugin_system,
    get_plugin_manager,
)
from pegasus_v2.core.db.session import (
    init_db,
    close_db,
    get_session,
    get_sync_session,
    get_db_session,
    create_all_tables_sync,
    drop_all_tables_sync,
)

__all__ = [
    "get_settings",
    "Settings",
    "Plugin",
    "PluginMetadata",
    "PluginManager",
    "HookManager",
    "HookType",
    "CommandInfo",
    "UIComponent",
    "initialize_plugin_system",
    "get_plugin_manager",
    "init_db",
    "close_db",
    "get_session",
    "get_sync_session",
    "get_db_session",
    "create_all_tables_sync",
    "drop_all_tables_sync",
]