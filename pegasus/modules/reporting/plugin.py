"""
Reporting module plugin entry point.
"""
from pegasus.modules.reporting.module import ReportingModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="reporting",
    version="2.0.0",
    description="Professional HTML/JSON pentest reports with findings and payload tracking",
    author="ProjectZeroDays",
    category="reporting",
    tags=["reporting", "html", "pdf", "findings", "payloads"],
    requires=["rich", "jinja2"],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return ReportingModule(context)


main = create_plugin