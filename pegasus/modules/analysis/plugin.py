"""
CVE Scanner module plugin entry point.
"""
from pegasus_v2.modules.analysis.module import CVEScannerModule
from pegasus_v2.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="cve_scanner",
    version="2.0.0",
    description="Android CVE fingerprinting via ADB + NVD API lookup",
    author="ProjectZeroDays",
    category="analysis",
    tags=["cve", "vulnerability", "scanner", "android", "nvd"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return CVEScannerModule(context)


main = create_plugin