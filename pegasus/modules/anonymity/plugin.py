"""Anonymity module plugin entry point."""
from pegasus.modules.anonymity.module import AnonymityModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="anonymity",
    version="2.0.0",
    description="Proxy/Tor helpers for operator traffic",
    author="ProjectZeroDays",
    category="exploit",
    tags=["anonymity", "proxy", "tor", "opsec", "traffic", "tunnel"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return AnonymityModule(context)


main = create_plugin
