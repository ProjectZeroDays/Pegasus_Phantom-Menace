"""OSINT search engines module plugin entry point."""
from pegasus.modules.osint.module import OsintModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="osint",
    version="2.0.0",
    description="Code, attack-surface, threat-intelligence, server and WiFi OSINT "
                "search engines with configurable API keys, plus MimiKATS, IVRE and Maltego",
    author="ProjectZeroDays",
    category="intelligence",
    tags=["osint", "shodan", "censys", "greynoise", "maltego", "mimikats",
          "ivre", "search", "reconnaissance"],
    requires=[],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return OsintModule(context)


main = create_plugin
