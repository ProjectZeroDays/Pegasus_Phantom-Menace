"""
BrutDroid module plugin entry point.
Android emulator automation: rooting, Frida server, Burp cert, custom scripts.
"""
from pegasus.modules.brutdroid.module import BrutDroidModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="brutdroid",
    version="2.0.0",
    description="Android Studio pentest automator - emulator creation, rooting, Frida, Burp cert, custom scripts",
    author="Brut Security",
    category="device",
    tags=["android", "emulator", "root", "frida", "burp", "certificate", "frida-scripts"],
    requires=["rich", "requests"],
    requires_python=">=3.9",
    entry_point="main",
)


def create_plugin(context):
    return BrutDroidModule(context)


main = create_plugin
