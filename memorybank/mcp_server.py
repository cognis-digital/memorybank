"""MEMORYBANK MCP server — exposes MemoryBank operations as MCP tools."""
from __future__ import annotations

import json
import os

from memorybank.core import MemoryBank, MemoryBankError

_DEFAULT_PATH = os.environ.get("MEMORYBANK_PATH", "memorybank.jsonl")


def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-memorybank[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print("Install the MCP extra: pip install 'cognis-memorybank[mcp]'")
        return 1

    bank_path = _DEFAULT_PATH
    app = FastMCP("memorybank")

    @app.tool()
    def memorybank_remember(text: str, tags: str = "", importance: float = 1.0) -> str:
        """Store a new memory. tags is a comma-separated list. Returns JSON."""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        try:
            bank = MemoryBank(bank_path)
            m = bank.add(text, tags=tag_list, importance=importance)
            return json.dumps(m.to_dict(), sort_keys=True)
        except MemoryBankError as exc:
            return json.dumps({"error": str(exc)})

    @app.tool()
    def memorybank_recall(query: str, limit: int = 5, tag: str = "") -> str:
        """Retrieve memories ranked by query. Returns JSON list."""
        try:
            bank = MemoryBank(bank_path)
            results = bank.search(query, limit=limit, tag=tag or None)
            return json.dumps(results, sort_keys=True)
        except MemoryBankError as exc:
            return json.dumps({"error": str(exc)})

    @app.tool()
    def memorybank_stats() -> str:
        """Return bank statistics as JSON."""
        try:
            bank = MemoryBank(bank_path)
            return json.dumps(bank.stats(), sort_keys=True)
        except MemoryBankError as exc:
            return json.dumps({"error": str(exc)})

    app.run()
    return 0
