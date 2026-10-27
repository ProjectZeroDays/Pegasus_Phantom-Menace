"""
AI module plugin entry point.
"""
from pegasus_v2.modules.base import BaseModule
from pegasus_v2.core.plugin import PluginMetadata


class AIModule(BaseModule):
    @property
    def module_name(self) -> str:
        return "AI Assistant"

    @property
    def module_description(self) -> str:
        return "Claude-powered pentest guidance with prompt caching"

    @property
    def module_category(self) -> str:
        return "ai"

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> bool:
        self._initialized = False
        return True


metadata = PluginMetadata(
    name="ai",
    version="2.0.0",
    description="Claude-powered pentest guidance with prompt caching",
    author="ProjectZeroDays",
    category="ai",
    tags=["ai", "claude", "llm", "guidance"],
    requires=["anthropic", "rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return AIModule(context)


main = create_plugin