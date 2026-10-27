"""
Forensics module plugin entry point.
"""
from pegasus_v2.modules.base import BaseModule
from pegasus_v2.core.plugin import PluginMetadata


class ForensicsModule(BaseModule):
    @property
    def module_name(self) -> str:
        return "Forensics"

    @property
    def module_description(self) -> str:
        return "Android forensics, artifact extraction, chain of custody"

    @property
    def module_category(self) -> str:
        return "forensics"

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> bool:
        self._initialized = False
        return True


metadata = PluginMetadata(
    name="forensics",
    version="2.0.0",
    description="Android forensics, artifact extraction, chain of custody",
    author="ProjectZeroDays",
    category="forensics",
    tags=["forensics", "extraction", "chain-of-custody", "browser", "sms", "contacts"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return ForensicsModule(context)


main = create_plugin