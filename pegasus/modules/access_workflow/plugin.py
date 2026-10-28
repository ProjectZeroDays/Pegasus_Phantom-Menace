"""
Access Workflow module plugin entry point.
Autonomous vs manual access vector exploitation: ADB, Fastboot, QR pairing, USB.
"""
from pegasus.modules.access_workflow.module import AccessWorkflowModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="access_workflow",
    version="2.0.0",
    description="Access vector exploitation workflows - ADB/Fastboot/QR/USB, zero-click exploits, post-exploitation handoff",
    author="ProjectZeroDays",
    category="exploit",
    tags=["access", "workflow", "adb", "fastboot", "qr-pairing", "usb", "zero-click", "pixel-8", "post-exploitation"],
    requires=["rich", "requests"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return AccessWorkflowModule(context)


main = create_plugin
