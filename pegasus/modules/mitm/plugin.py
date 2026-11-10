"""MITM module plugin entry point."""
from pegasus.modules.mitm.module import MITMModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="mitm",
    version="2.0.0",
    description="SSL pinning bypass, Frida scripts, objection delegation, and proxy helpers",
    author="ProjectZeroDays",
    category="exploit",
    tags=["mitm", "ssl-pinning", "frida", "objection", "proxy", "interception"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return MITMModule(context)


main = create_plugin
