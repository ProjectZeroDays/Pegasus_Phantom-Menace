"""
Session module plugin entry point.
"""
from pegasus_v2.modules.session.module import SessionModule
from pegasus_v2.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="session",
    version="2.0.0",
    description="Metasploit RPC integration, session keepalive, and device operations",
    author="ProjectZeroDays",
    category="session",
    tags=["metasploit", "session", "rpc", "meterpreter", "keepalive"],
    requires=["pymetasploit3"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return SessionModule(context)


main = create_plugin