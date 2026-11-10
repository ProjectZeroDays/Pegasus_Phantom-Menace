"""Blockchain Integration module plugin entry point."""
from pegasus.modules.blockchain.module import BlockchainModule
from pegasus.core.plugin import PluginMetadata

metadata = PluginMetadata(
    name="blockchain",
    version="2.0.0",
    description="Smart contract interaction, decentralized storage, cryptographic proof, token economy",
    author="ProjectZeroDays",
    category="intelligence",
    tags=["blockchain", "erc20", "merkle", "ipfs", "storage", "token", "ledger"],
    requires=[],
    requires_python=">=3.11",
    entry_point="main",
)


def create_plugin(context):
    return BlockchainModule(context)


main = create_plugin
