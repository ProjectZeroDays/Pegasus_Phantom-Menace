"""Export module plugin entry point."""
from pegasus.modules.export.module import ExportModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="export",
    version="2.0.0",
    description="HTML assessment report generation",
    author="ProjectZeroDays",
    category="exploit",
    tags=["export", "report", "html", "assessment", "documentation"],
    requires=["rich"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return ExportModule(context)


main = create_plugin
