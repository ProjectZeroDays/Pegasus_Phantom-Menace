"""
Pegasus Phantom Menace v2 - Agent Factory Package

Autonomous agent factory plus the global command factory (28 commands across
agents, skills, custom commands, MCP servers, plugins, extensions and
workflows).

Source roots are bounded: ``C:/Projects/Quantum CLI``, ``C:/Projects/Quantum C2``,
``~/.config/opencode/skills``, ``~/.pegasus/skills`` and desktop skill/agent
folders.
"""

from .factory import (
    AgentConfig,
    AgentFactory,
    AgentType,
    FactoryCommand,
    FactoryError,
    GlobalCommandFactory,
    command_factory,
    create_agent,
    execute_agent,
    get_agent,
    get_agent_factory,
    get_command_factory,
    list_agents,
    run_factory_command,
)

__all__ = [
    "AgentConfig",
    "AgentFactory",
    "AgentType",
    "FactoryCommand",
    "FactoryError",
    "GlobalCommandFactory",
    "command_factory",
    "create_agent",
    "execute_agent",
    "get_agent",
    "get_agent_factory",
    "get_command_factory",
    "list_agents",
    "run_factory_command",
]
