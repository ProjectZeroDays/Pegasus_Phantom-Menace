"""
Payload module plugin entry point.
"""
from pegasus_v2.modules.payload.module import PayloadModule
from pegasus_v2.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="payload",
    version="2.0.0",
    description="msfvenom payload generation, APK binding, DNA tracking, and mutation",
    author="ProjectZeroDays",
    category="payload",
    tags=["payload", "msfvenom", "apk", "binding", "dna", "mutation"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return PayloadModule(context)


main = create_plugin