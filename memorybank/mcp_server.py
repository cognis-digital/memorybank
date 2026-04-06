"""MEMORYBANK MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from memorybank.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-memorybank[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-memorybank[mcp]'")
        return 1
    app = FastMCP("memorybank")

    @app.tool()
    def memorybank_scan(target: str) -> str:
        """Portable long-term memory store for agents, exposed over MCP. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
