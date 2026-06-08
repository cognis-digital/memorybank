"""MEMORYBANK — portable long-term memory store for AI agents.

A zero-dependency, stdlib-only engine for storing, retrieving, and ranking
agent memories with recency + relevance + importance scoring. Designed to be
exposed over MCP or driven from the CLI.
"""
from .core import (
    MemoryBank,
    Memory,
    MemoryBankError,
)

TOOL_NAME = "memorybank"
TOOL_VERSION = "1.0.0"

__all__ = [
    "MemoryBank",
    "Memory",
    "MemoryBankError",
    "TOOL_NAME",
    "TOOL_VERSION",
]
