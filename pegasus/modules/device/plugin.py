"""
Device module plugin entry point.
"""
from pegasus_v2.modules.device.module import DeviceModule
from pegasus_v2.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="device",
    version="2.0.0",
    description="ADB device communication, fingerprinting, and inventory management",
    author="ProjectZeroDays",
    category="device",
    tags=["adb", "device", "inventory", "fingerprinting"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    """Factory function to create the device module plugin."""
    return DeviceModule(context)


# Also expose as main for backward compatibility
main = create_plugin