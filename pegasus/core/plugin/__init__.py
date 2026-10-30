"""
Pegasus Phantom Menace - Plugin System
Extensible plugin architecture with hooks, commands, and UI components.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache

from pydantic import BaseModel, Field

from pegasus.core.config import get_settings


class PluginStatus(Enum):
    """Plugin lifecycle status."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ERROR = "error"
    DISABLED = "disabled"


class HookType(Enum):
    """Available hook points in the application lifecycle."""
    APP_STARTUP = "app_startup"
    APP_SHUTDOWN = "app_shutdown"
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    SESSION_CREATED = "session_created"
    SESSION_CLOSED = "session_closed"
    PAYLOAD_GENERATED = "payload_generated"
    PAYLOAD_DELIVERED = "payload_delivered"
    VULN_FOUND = "vuln_found"
    REPORT_GENERATED = "report_generated"
    EXPLOIT_EXECUTED = "exploit_executed"
    AI_QUERY = "ai_query"
    PRE_EXPLOIT = "pre_exploit"
    POST_EXPLOIT = "post_exploit"
    PRE_PAYLOAD_GEN = "pre_payload_gen"
    POST_PAYLOAD_GEN = "post_payload_gen"
    DEVICE_FINGERPRINT = "device_fingerprint"
    VULN_SCAN_START = "vuln_scan_start"
    VULN_SCAN_COMPLETE = "vuln_scan_complete"
    REPORT_START = "report_start"
    REPORT_COMPLETE = "report_complete"


@dataclass
class HookContext:
    """Context passed to hook callbacks."""
    hook_type: HookType
    data: dict
    timestamp: float
    plugin_name: str
    metadata: dict = field(default_factory=dict)


class HookManager:
    """Manages hook registration and execution."""
    
    def __init__(self):
        self._hooks: Dict[HookType, List[Callable]] = {h: [] for h in HookType}
    
    def register(self, hook_type: HookType, callback: Callable, priority: int = 0) -> None:
        """Register a hook callback with optional priority."""
        self._hooks[hook_type].append((priority, callback))
        # Sort by priority (higher first)
        self._hooks[hook_type].sort(key=lambda x: x[0], reverse=True)
    
    def unregister(self, hook_type: HookType, callback: Callable) -> bool:
        """Unregister a hook callback."""
        for i, (_, cb) in enumerate(self._hooks[hook_type]):
            if cb == callback:
                self._hooks[hook_type].pop(i)
                return True
        return False
    
    async def execute(self, hook_type: HookType, data: dict, plugin_name: str = "") -> List[Any]:
        """Execute all hooks for a given type."""
        results = []
        context = HookContext(
            hook_type=hook_type,
            data=data,
            timestamp=__import__("time").time(),
            plugin_name=plugin_name,
        )
        for _, callback in self._hooks.get(hook_type, []):
            try:
                if inspect.iscoroutinefunction(callback):
                    result = await callback(context)
                else:
                    result = callback(context)
                results.append(result)
            except Exception as e:
                # Log error but continue executing other hooks
                import logging
                logging.getLogger(__name__).error(f"Hook {hook_type} failed: {e}")
        return results
    
    def execute_sync(self, hook_type: HookType, data: dict, plugin_name: str = "") -> List[Any]:
        """Execute all hooks synchronously."""
        results = []
        context = HookContext(
            hook_type=hook_type,
            data=data,
            timestamp=__import__("time").time(),
            plugin_name=plugin_name,
        )
        for _, callback in self._hooks.get(hook_type, []):
            try:
                if inspect.iscoroutinefunction(callback):
                    # Skip async callbacks in sync execution
                    continue
                result = callback(context)
                results.append(result)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Hook {hook_type} failed: {e}")
        return results


class CommandInfo(BaseModel):
    """Information about a CLI command."""
    name: str
    description: str
    callback: str  # method name
    aliases: list[str] = Field(default_factory=list)
    arguments: dict = Field(default_factory=dict)  # arg_name -> {type, help, required, default}
    options: dict = Field(default_factory=dict)    # opt_name -> {type, help, default}
    examples: list[str] = Field(default_factory=list)
    hidden: bool = False


class UIComponent(BaseModel):
    """UI component definition for web/TUI."""
    name: str
    component_type: str  # page, panel, widget, dialog, menu
    path: str  # route path for web, or component ID for TUI
    title: str
    description: str = ""
    icon: str = ""
    order: int = 0
    permissions: list[str] = Field(default_factory=list)
    props: dict = Field(default_factory=dict)


class PluginMetadata(BaseModel):
    """Plugin metadata and configuration."""
    name: str
    version: str
    description: str
    author: str = ""
    author_email: str = ""
    license: str = "MIT"
    homepage: str = ""
    repository: str = ""
    license_file: str = ""
    requires: list[str] = Field(default_factory=list)  # Python package dependencies
    requires_python: str = ">=3.11"
    conflicts: list[str] = Field(default_factory=list)  # Conflicting plugin names
    provides: list[str] = Field(default_factory=list)   # Features this plugin provides
    tags: list[str] = Field(default_factory=list)
    category: str = "general"  # core, analysis, exploit, network, forensics, ai, etc.
    min_app_version: str = "2.0.0"
    max_app_version: str = ""
    entry_point: str = "main"  # Module attribute to call for initialization
    config_schema: dict = Field(default_factory=dict)  # JSON schema for plugin config
    default_config: dict = Field(default_factory=dict)
    hidden: bool = False
    internal: bool = False  # Internal plugins not shown in UI


class Plugin(ABC):
    """Base class for all plugins."""
    
    metadata: PluginMetadata
    
    def __init__(self, context: "AppContext"):
        self.context = context
        self.logger = context.logger
        self.settings = context.settings
        self.hooks = context.hooks
        self.db = context.db
        self._commands: Dict[str, CommandInfo] = {}
        self._ui_components: List[UIComponent] = []
        self._initialized = False
    
    @property
    def name(self) -> str:
        return self.metadata.name
    
    @property
    def version(self) -> str:
        return self.metadata.version
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the plugin. Return True on success."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Cleanup on shutdown. Return True on success."""
        pass
    
    def register_command(self, command: CommandInfo) -> None:
        """Register a CLI command."""
        self._commands[command.name] = command
        for alias in command.aliases:
            self.context.commands[alias] = command
    
    def register_ui_component(self, component: UIComponent) -> None:
        """Register a UI component."""
        self._ui_components.append(component)
    
    def register_hook(self, hook_type: "HookType", callback: Callable, priority: int = 0) -> None:
        """Register a hook callback."""
        self.hooks.register(hook_type, callback, priority)
    
    def get_commands(self) -> Dict[str, CommandInfo]:
        return self._commands.copy()
    
    def get_ui_components(self) -> List[UIComponent]:
        return self._ui_components.copy()
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get plugin-specific configuration."""
        plugin_config = self.settings.plugins.get(self.name, {})
        return plugin_config.get(key, self.metadata.default_config.get(key))
    
    def set_config(self, key: str, value: Any) -> None:
        """Set plugin-specific configuration (runtime only)."""
        if not hasattr(self, '_runtime_config'):
            self._runtime_config = {}
        self._runtime_config[key] = value


class AppContext:
    """Application context passed to all plugins."""
    
    def __init__(self, settings: "Settings"):
        self.settings = settings
        self.hooks = HookManager()
        self.commands: Dict[str, "CommandInfo"] = {}
        self.plugins: Dict[str, "Plugin"] = {}
        self.ui_components: List[UIComponent] = []
        self.logger = self._setup_logger()
        self.db = None  # Will be set after DB initialization
        self._running = False
    
    def _setup_logger(self):
        import logging
        logger = logging.getLogger("pegasus")
        logger.setLevel(logging.INFO)
        return logger
    
    def register_plugin(self, plugin: "Plugin") -> None:
        self.plugins[plugin.name] = plugin
        # Register commands
        for cmd in plugin.get_commands().values():
            self.commands[cmd.name] = cmd
            for alias in cmd.aliases:
                self.commands[alias] = cmd
        # Register UI components
        for comp in plugin.get_ui_components():
            self.ui_components.append(comp)

    def register_command(self, command: "CommandInfo") -> None:
        """Register a command with the context."""
        self.commands[command.name] = command
        for alias in command.aliases:
            self.commands[alias] = command

    def register_ui_component(self, component: "UIComponent") -> None:
        """Register a UI component with the context."""
        self.ui_components.append(component)
    
    def get_plugin(self, name: str) -> Optional["Plugin"]:
        return self.plugins.get(name)
    
    def get_all_plugins(self) -> List["Plugin"]:
        return list(self.plugins.values())


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle."""
    
    def __init__(self, context: AppContext):
        self.context = context
        self._loaded_modules: Dict[str, Any] = {}
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
    
    def discover_plugins(self, plugin_dirs: List[Path]) -> List[str]:
        """Discover available plugins in the given directories (recursive)."""
        plugins: List[str] = []
        seen = set()
        for plugin_dir in self.context.settings.plugins.plugin_dirs:
            if not plugin_dir.exists():
                continue
            for item in plugin_dir.rglob("*"):
                candidate = None
                if item.is_dir() and (item / "plugin.py").exists():
                    candidate = item / "plugin.py"
                elif item.suffix == ".py" and item.name == "plugin.py":
                    candidate = item
                if candidate is None:
                    continue
                resolved = str(candidate.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                plugins.append(resolved)
        return plugins
    
    def _apply_metadata(self, plugin: Plugin, metadata: PluginMetadata) -> None:
        """Attach module-level metadata to a plugin instance and its class."""
        try:
            plugin.metadata = metadata
        except Exception:
            pass
        plugin_class = plugin.__class__
        if getattr(plugin_class, "metadata", None) is None:
            try:
                plugin_class.metadata = metadata
            except Exception:
                pass

    def _bind_metadata(self, module, factory, metadata: PluginMetadata) -> None:
        """Bind module-level metadata onto the plugin class the factory returns.

        Module layout is `plugin.py` (metadata + factory) importing the real
        class from `module.py`, so the class object lives in another module and
        has no `metadata` of its own. Resolve the factory's return annotation /
        closure cell to find it, then set `Class.metadata`.
        """
        candidates = []

        # 1. Factory return annotation: `def create_plugin(context) -> Foo:`
        try:
            hints = getattr(factory, "__annotations__", {}) or {}
            hint = hints.get("return")
            if isinstance(hint, type) and issubclass(hint, Plugin):
                candidates.append(hint)
            elif isinstance(hint, str):
                resolved = getattr(module, hint, None)
                if isinstance(resolved, type) and issubclass(resolved, Plugin):
                    candidates.append(resolved)
        except Exception:
            pass

        # 2. Factory globals (module namespace of the defining module)
        for value in (getattr(factory, "__globals__", {}) or {}).values():
            if (
                isinstance(value, type)
                and issubclass(value, Plugin)
                and value is not Plugin
                and value not in candidates
            ):
                candidates.append(value)

        # 3. Closure cells
        try:
            for cell in getattr(factory, "__closure__", None) or ():
                value = cell.cell_contents
                if (
                    isinstance(value, type)
                    and issubclass(value, Plugin)
                    and value is not Plugin
                    and value not in candidates
                ):
                    candidates.append(value)
        except Exception:
            pass

        for cls in candidates:
            if getattr(cls, "metadata", None) is None:
                try:
                    cls.metadata = metadata
                except Exception:
                    pass

    @staticmethod
    def _run_async(coro) -> Any:
        """Run a coroutine from synchronous (possibly already-running) context."""
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)

        # Called from inside a running loop (e.g. the web server thread):
        # execute in a private loop on this thread.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def load_plugin(self, plugin_path: str) -> Optional[Plugin]:
        """Load a plugin from a Python file."""
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules["plugin_module"] = module
            spec.loader.exec_module(module)

            # Resolve metadata + factory declared at module level (the documented
            # plugin contract). Fall back to class discovery for legacy plugins.
            module_metadata = getattr(module, "metadata", None)
            if isinstance(module_metadata, PluginMetadata):
                if module_metadata.name in self.context.plugins:
                    self.context.logger.warning(
                        f"Plugin {module_metadata.name} already loaded"
                    )
                    return self.context.plugins[module_metadata.name]

                factory = getattr(module, "create_plugin", None) or getattr(
                    module, "main", None
                )
                if callable(factory):
                    # Bind metadata to plugin classes declared in this module or in
                    # the module that defines the factory's target class: module
                    # classes read self.metadata during __init__ (logger naming).
                    self._bind_metadata(module, factory, module_metadata)

                    plugin = factory(self.context)
                    if not isinstance(plugin, Plugin):
                        self.context.logger.error(
                            f"Factory in {plugin_path} did not return a Plugin"
                        )
                        return None
                    if getattr(plugin.__class__, "metadata", None) is None:
                        plugin.__class__.metadata = module_metadata
                    if getattr(plugin, "metadata", None) is None:
                        plugin.metadata = module_metadata
                    self._apply_metadata(plugin, module_metadata)

                    for dep in module_metadata.requires:
                        try:
                            importlib.import_module(dep)
                        except ImportError:
                            self.context.logger.error(
                                f"Plugin {module_metadata.name} missing dependency: {dep}"
                            )
                            return None

                    for conflict in module_metadata.conflicts:
                        if conflict in self.context.plugins:
                            self.context.logger.error(
                                f"Plugin {module_metadata.name} conflicts with {conflict}"
                            )
                            return None

                    success = self._run_async(plugin.initialize())
                    if not success:
                        self.context.logger.error(
                            f"Plugin {module_metadata.name} initialization failed"
                        )
                        return None

                    self.context.register_plugin(plugin)
                    self._loaded_modules[module_metadata.name] = module
                    self._plugin_classes[module_metadata.name] = plugin.__class__
                    self.context.logger.info(
                        f"Loaded plugin: {module_metadata.name} v{module_metadata.version}"
                    )
                    return plugin

            # Find plugin class, preferring classes defined in this module.
            plugin_class = None
            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Plugin)
                    and obj is not Plugin
                    and obj.__module__ == module.__name__
                ):
                    plugin_class = obj
                    break
            if plugin_class is None:
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                        plugin_class = obj
                        break

            if plugin_class is not None and isinstance(module_metadata, PluginMetadata):
                if getattr(plugin_class, "metadata", None) is None:
                    plugin_class.metadata = module_metadata
            
            if plugin_class is None:
                self.context.logger.warning(f"No Plugin class found in {plugin_path}")
                return None
            
            # Check if already loaded
            metadata = plugin_class.metadata
            if metadata.name in self.context.plugins:
                self.context.logger.warning(f"Plugin {metadata.name} already loaded")
                return self.context.plugins[metadata.name]
            
            # Check dependencies
            for dep in metadata.requires:
                try:
                    importlib.import_module(dep)
                except ImportError:
                    self.context.logger.error(f"Plugin {metadata.name} missing dependency: {dep}")
                    return None
            
            # Check conflicts
            for conflict in metadata.conflicts:
                if conflict in self.context.plugins:
                    self.context.logger.error(f"Plugin {metadata.name} conflicts with {conflict}")
                    return None
            
            # Instantiate plugin
            plugin = plugin_class(self.context)
            
            # Initialize
            success = self._run_async(plugin.initialize())
            if not success:
                self.context.logger.error(f"Plugin {metadata.name} initialization failed")
                return None
            
            # Register with context
            self.context.register_plugin(plugin)
            self._loaded_modules[metadata.name] = module
            self._plugin_classes[metadata.name] = plugin_class
            
            self.context.logger.info(f"Loaded plugin: {metadata.name} v{metadata.version}")
            return plugin
            
        except Exception as e:
            self.context.logger.error(f"Failed to load plugin {plugin_path}: {e}")
            return None
    
    def load_all_plugins(self, plugin_dirs: Optional[List[Path]] = None) -> List[Plugin]:
        """Load all plugins from the given directories.

        Falls back to importing built-in modules directly when file discovery
        yields nothing — the case in a PyInstaller bundle, where ``plugin.py``
        sources exist only inside the archive.
        """
        dirs = plugin_dirs or self.context.settings.plugins.plugin_dirs
        plugins = []

        for plugin_path in self.discover_plugins(dirs):
            plugin = self.load_plugin(plugin_path)
            if plugin:
                plugins.append(plugin)

        if not plugins:
            plugins = self.load_builtin_plugins()

        return plugins

    #: Built-in module plugins, in load order.
    BUILTIN_MODULES: tuple[str, ...] = (
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
        "access_workflow.post_exploitation",
    )

    def load_builtin_plugins(self) -> List[Plugin]:
        """Import built-in module plugins without touching the filesystem."""
        loaded: List[Plugin] = []
        for dotted in self.BUILTIN_MODULES:
            module_name = f"pegasus.modules.{dotted}.plugin"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001
                self.context.logger.error(f"Cannot import {module_name}: {exc}")
                continue

            metadata = getattr(module, "metadata", None)
            if not isinstance(metadata, PluginMetadata):
                self.context.logger.error(f"{module_name} has no module metadata")
                continue
            if metadata.name in self.context.plugins:
                continue

            factory = getattr(module, "create_plugin", None) or getattr(module, "main", None)
            if not callable(factory):
                self.context.logger.error(f"{module_name} has no factory")
                continue

            self._bind_metadata(module, factory, metadata)
            try:
                plugin = factory(self.context)
            except Exception as exc:  # noqa: BLE001
                self.context.logger.error(f"{metadata.name} instantiation failed: {exc}")
                continue
            if not isinstance(plugin, Plugin):
                continue
            self._apply_metadata(plugin, metadata)

            missing = []
            for dep in metadata.requires:
                try:
                    importlib.import_module(dep)
                except ImportError:
                    missing.append(dep)
            if missing:
                self.context.logger.error(
                    f"Plugin {metadata.name} missing dependencies: {', '.join(missing)}"
                )
                continue

            if not self._run_async(plugin.initialize()):
                self.context.logger.error(f"Plugin {metadata.name} initialization failed")
                continue

            self.context.register_plugin(plugin)
            self._plugin_classes[metadata.name] = plugin.__class__
            self.context.logger.info(
                f"Loaded builtin plugin: {metadata.name} v{metadata.version}"
            )
            loaded.append(plugin)
        return loaded
    
    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name."""
        if name not in self.context.plugins:
            return False
        
        plugin = self.context.plugins[name]
        
        # Shutdown
        success = self._run_async(plugin.shutdown())
        
        # Remove from context
        for cmd_name in list(self.context.commands.keys()):
            cmd = self.context.commands[cmd_name]
            if hasattr(cmd, '_plugin_name') and cmd._plugin_name == name:
                del self.context.commands[cmd_name]
        
        # Remove UI components
        self.context.ui_components = [
            c for c in self.context.ui_components 
            if not hasattr(c, '_plugin_name') or c._plugin_name != name
        ]
        
        del self.context.plugins[name]
        
        if name in self._loaded_modules:
            del self._loaded_modules[name]
        if name in self._plugin_classes:
            del self._plugin_classes[name]
        
        return success
    
    def reload_plugin(self, name: str) -> bool:
        """Reload a plugin by name."""
        if name not in self.context.plugins:
            return False
        
        plugin = self.context.plugins[name]
        plugin_class = plugin.__class__
        
        # Shutdown old
        self.unload_plugin(name)
        
        # Reload module
        module = self._loaded_modules.get(name)
        if module:
            importlib.reload(module)
            # Find new plugin class
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                    return self.load_plugin_from_class(obj)
        
        return False
    
    def load_plugin_from_class(self, plugin_class: Type[Plugin]) -> Optional[Plugin]:
        """Load a plugin directly from a class."""
        # Similar to load_plugin but from class
        metadata = plugin_class.metadata
        if metadata.name in self.context.plugins:
            self.context.logger.warning(f"Plugin {metadata.name} already loaded")
            return self.context.plugins[metadata.name]
        
        # Check dependencies
        for dep in metadata.requires:
            try:
                importlib.import_module(dep)
            except ImportError:
                self.context.logger.error(f"Plugin {metadata.name} missing dependency: {dep}")
                return None
        
        # Check conflicts
        for conflict in metadata.conflicts:
            if conflict in self.context.plugins:
                self.context.logger.error(f"Plugin {metadata.name} conflicts with {conflict}")
                return None
        
        # Instantiate and initialize
        plugin = plugin_class(self.context)

        success = self._run_async(plugin.initialize())
        if not success:
            self.context.logger.error(f"Plugin {metadata.name} initialization failed")
            return None
        
        self.context.register_plugin(plugin)
        self._loaded_modules[metadata.name] = sys.modules.get(plugin_class.__module__)
        self._plugin_classes[metadata.name] = plugin_class
        
        self.context.logger.info(f"Loaded plugin: {metadata.name} v{metadata.version}")
        return plugin
    
    def get_plugin(self, name: str) -> Optional[Plugin]:
        return self.context.plugins.get(name)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins with their metadata."""
        result = []
        for name, plugin in self.context.plugins.items():
            meta = plugin.metadata
            result.append({
                "name": meta.name,
                "version": meta.version,
                "description": meta.description,
                "author": meta.author,
                "category": meta.category,
                "tags": meta.tags,
                "enabled": not meta.hidden,
            })
        return result
    
    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a plugin."""
        if name not in self.context.plugins:
            return None
        
        plugin = self.context.plugins[name]
        meta = plugin.metadata
        
        return {
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "author": meta.author,
            "author_email": meta.author_email,
            "license": meta.license,
            "homepage": meta.homepage,
            "repository": meta.repository,
            "requires": meta.requires,
            "conflicts": meta.conflicts,
            "provides": meta.provides,
            "tags": meta.tags,
            "category": meta.category,
            "min_app_version": meta.min_app_version,
            "max_app_version": meta.max_app_version,
            "commands": [c.dict() for c in plugin.get_commands().values()],
            "ui_components": [c.dict() for c in plugin.get_ui_components()],
            "config_schema": meta.config_schema,
            "default_config": meta.default_config,
        }


# Global plugin manager instance (initialized in main)
plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    global plugin_manager
    if plugin_manager is None:
        from pegasus.core.config import get_settings
        settings = get_settings()
        context = AppContext(settings)
        plugin_manager = PluginManager(context)
    return plugin_manager


def initialize_plugin_system() -> PluginManager:
    """Initialize the plugin system and load all plugins."""
    global plugin_manager
    from pegasus.core.config import get_settings
    settings = get_settings()
    context = AppContext(settings)
    plugin_manager = PluginManager(context)
    
    # Load all plugins
    plugin_manager.load_all_plugins()
    
    return plugin_manager


# Decorator for easy command registration
def command(
    name: str,
    description: str,
    aliases: list[str] = None,
    arguments: dict = None,
    options: dict = None,
    examples: list[str] = None,
    hidden: bool = False,
):
    """Decorator to register a command on a plugin class."""
    def decorator(func):
        func._command_info = CommandInfo(
            name=name,
            description=description,
            callback=func.__name__,
            aliases=aliases or [],
            arguments=arguments or {},
            options=options or {},
            examples=examples or [],
            hidden=hidden,
        )
        return func
    return decorator


# Decorator for hook registration
def hook(hook_type: HookType, priority: int = 0):
    """Decorator to register a hook callback."""
    def decorator(func):
        func._hook_info = (hook_type, priority)
        return func
    return decorator


# Decorator for UI component registration
def ui_component(
    name: str,
    component_type: str,
    path: str,
    title: str,
    description: str = "",
    icon: str = "",
    order: int = 0,
    permissions: list[str] = None,
    props: dict = None,
):
    """Decorator to register a UI component."""
    def decorator(func):
        func._ui_component = UIComponent(
            name=name,
            component_type=component_type,
            path=path,
            title=title,
            description=description,
            icon=icon,
            order=order,
            permissions=permissions or [],
            props=props or {},
        )
        return func
    return decorator