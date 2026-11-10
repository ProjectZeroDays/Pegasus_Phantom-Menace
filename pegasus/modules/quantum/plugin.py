"""Quantum Security module plugin entry point."""
from pegasus.modules.quantum.module import QuantumModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="quantum",
    version="2.0.0",
    description="Quantum cryptography, QKD simulation, post-quantum migration audit, quantum-resistant checks",
    author="ProjectZeroDays",
    category="security",
    tags=["quantum", "qkd", "bb84", "pqc", "ml-kem", "ml-dsa", "slh-dsa", "hybrid"],
    requires=[],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return QuantumModule(context)


main = create_plugin
