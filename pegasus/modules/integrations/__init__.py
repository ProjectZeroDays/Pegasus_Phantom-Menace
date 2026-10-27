"""
Pegasus Phantom Menace v2 - Integrations Module
External integrations and slash command framework.
"""
from pegasus.modules.integrations.slash_commands import (
    SlashCommandManager,
    SlashCommand,
    slash_command_manager,
    initialize_slash_commands,
)

__all__ = [
    "SlashCommandManager",
    "SlashCommand",
    "slash_command_manager",
    "initialize_slash_commands",
]