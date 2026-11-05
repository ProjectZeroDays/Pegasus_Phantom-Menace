"""MCP plugin — bridges agent workflows to external MCP servers."""
# Example: exposes /mcp/tools for agent execution
from quantum.core.plugins import PluginCommand

def mcp_server_url():
    return "http://localhost:3000/mcp"
