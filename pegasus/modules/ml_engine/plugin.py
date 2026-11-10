"""ML Engine module plugin entry point."""
from pegasus.modules.ml_engine.module import MLEngineModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="ml_engine",
    version="2.0.0",
    description="Anomaly detection, behavior prediction, automated response, continuous learning",
    author="ProjectZeroDays",
    category="intelligence",
    tags=["ml", "anomaly", "behavior", "response", "telemetry", "detection"],
    requires=[],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return MLEngineModule(context)


main = create_plugin
