"""
Pegasus Phantom Menace v2 - Base Module Class
Base class for all module plugins with common functionality.
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from pegasus_v2.core.plugin import (
    Plugin,
    PluginMetadata,
    CommandInfo,
    UIComponent,
    hook,
    command,
    ui_component,
)
from pegasus_v2.core.config import get_settings


class BaseModule(Plugin, ABC):
    """Base class for all Pegasus modules."""

    def __init__(self, context):
        super().__init__(context)
        self.logger = logging.getLogger(f"pegasus.modules.{self.metadata.name}")
        self._commands: Dict[str, CommandInfo] = {}
        self._ui_components: List[UIComponent] = []
        self._console = Console()

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Human-readable module name."""
        pass

    @property
    @abstractmethod
    def module_description(self) -> str:
        """Module description."""
        pass

    @property
    @abstractmethod
    def module_category(self) -> str:
        """Module category (device, payload, session, etc.)."""
        pass

    async def initialize(self) -> bool:
        """Initialize the module. Register commands and hooks."""
        try:
            self.logger.info(f"Initializing module: {self.metadata.name}")
            await self._register_commands()
            await self._register_ui_components()
            await self._register_hooks()
            self._initialized = True
            self.logger.info(f"Module initialized: {self.metadata.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize module {self.metadata.name}: {e}")
            return False

    async def shutdown(self) -> bool:
        """Shutdown the module."""
        try:
            self.logger.info(f"Shutting down module: {self.metadata.name}")
            self._commands.clear()
            self._ui_components.clear()
            self._initialized = False
            return True
        except Exception as e:
            self.logger.error(f"Failed to shutdown module {self.metadata.name}: {e}")
            return False

    async def _register_commands(self) -> None:
        """Register module commands. Override in subclasses."""
        pass

    async def _register_ui_components(self) -> None:
        """Register UI components. Override in subclasses."""
        pass

    async def _register_hooks(self) -> None:
        """Register hook callbacks. Override in subclasses."""
        pass

    def register_command(self, name: str, description: str, callback: Callable, **kwargs) -> CommandInfo:
        """Register a command with the module."""
        cmd_info = CommandInfo(
            name=name,
            description=description,
            callback=callback.__name__,
            **kwargs
        )
        self._commands[name] = cmd_info
        self.context.register_command(cmd_info)
        return cmd_info

    def register_ui_component(self, name: str, component_type: str, path: str,
                              title: str, **kwargs) -> UIComponent:
        """Register a UI component."""
        comp = UIComponent(
            name=name,
            component_type=component_type,
            path=path,
            title=title,
            **kwargs
        )
        self._ui_components.append(comp)
        self.context.register_ui_component(comp)
        return comp

    def register_hook(self, hook_type: HookType, callback: Callable, priority: int = 0) -> None:
        """Register a hook callback."""
        self.context.hooks.register(hook_type, callback, priority)

    def get_commands(self) -> Dict[str, CommandInfo]:
        return self._commands.copy()

    def get_ui_components(self) -> List[UIComponent]:
        return self._ui_components.copy()

    def print_table(self, title: str, headers: List[str], rows: List[list]) -> None:
        """Print a formatted table."""
        table = Table(title=title, show_lines=True, header_style="bold cyan")
        for h in headers:
            table.add_column(h)
        for row in rows:
            table.add_row(*[str(c) for c in row])
        self._console.print(table)

    def print_panel(self, content: str, title: str, border_style: str = "cyan") -> None:
        """Print a formatted panel."""
        self._console.print(Panel(content, title=title, border_style=border_style))

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self._console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self._console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self._console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self._console.print(f"[blue]ℹ[/blue] {message}")

    def prompt(self, message: str, default: Optional[str] = None,
               password: bool = False, choices: Optional[list] = None) -> str:
        """Prompt user for input."""
        if choices:
            return Prompt.ask(message, choices=choices, default=default, show_choices=False)
        if password:
            return Prompt.ask(message, password=True)
        return Prompt.ask(message, default=default)

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask for confirmation."""
        return Confirm.ask(message, default=default)

    def get_device_id(self) -> Optional[str]:
        """Get selected device ID from context or prompt."""
        # Check if device is selected in context
        if hasattr(self.context, 'selected_device'):
            return self.context.selected_device
        return None

    def set_device_id(self, device_id: str) -> None:
        """Set selected device in context."""
        self.context.selected_device = device_id