"""C2 server module plugin entry point."""
from pegasus.modules.c2_server.module import C2ServerModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="c2_server",
    version="2.0.0",
    description="Built-in C2 listener for session callbacks",
    author="ProjectZeroDays",
    category="exploit",
    tags=["c2", "callback", "listener", "session", "beacon"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return C2ServerModule(context)


main = create_plugin
