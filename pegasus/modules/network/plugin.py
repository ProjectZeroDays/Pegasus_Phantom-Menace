"""
Network module plugin entry point.
"""
from pegasus.modules.base import BaseModule
from pegasus.core.plugin import PluginMetadata


class NetworkModule(BaseModule):
    @property
    def module_name(self) -> str:
        return "Network Tools"

    @property
    def module_description(self) -> str:
        return "Network scanning, port forwarding, ngrok tunnel management"

    @property
    def module_category(self) -> str:
        return "network"

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> bool:
        self._initialized = False
        return True


metadata = PluginMetadata(
    name="network",
    version="2.0.0",
    description="Network scanning, port forwarding, ngrok tunnel management",
    author="ProjectZeroDays",
    category="network",
    tags=["network", "nmap", "ngrok", "port-forwarding", "socat"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return NetworkModule(context)


main = create_plugin