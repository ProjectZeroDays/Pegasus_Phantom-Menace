"""CVE framework module plugin entry point."""
from pegasus.modules.cve.module import CveModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="cve",
    version="2.0.0",
    description="CVE catalogue, asset fingerprinting and passive host validators",
    author="ProjectZeroDays",
    category="security",
    tags=["cve", "vulnerability", "fingerprint", "catalogue", "remediation"],
    requires=[],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return CveModule(context)


main = create_plugin
