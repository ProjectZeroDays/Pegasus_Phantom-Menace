"""
Intelligence module plugin entry point.
"""
from pegasus.modules.base import BaseModule
from pegasus.core.plugin import PluginMetadata


class IntelligenceModule(BaseModule):
    @property
    def module_name(self) -> str:
        return "Threat Intelligence"

    @property
    def module_description(self) -> str:
        return "CVE, IOC, VirusTotal, OTX threat intelligence"

    @property
    def module_category(self) -> str:
        return "intelligence"

    async def initialize(self) -> bool:
        self._initialized = True
        return True

    async def shutdown(self) -> bool:
        self._initialized = False
        return True


metadata = PluginMetadata(
    name="intelligence",
    version="2.0.0",
    description="CVE, IOC, VirusTotal, OTX threat intelligence",
    author="ProjectZeroDays",
    category="intelligence",
    tags=["cve", "ioc", "virustotal", "otx", "threat-intel"],
    requires=["rich", "requests"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return IntelligenceModule(context)


main = create_plugin