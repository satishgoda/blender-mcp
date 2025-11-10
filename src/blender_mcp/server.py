"""Backward-compatible entry point for the Blender MCP server."""

from __future__ import annotations

from .app import main, mcp  # type: ignore[attr-defined]

__all__ = ["mcp", "main"]


if __name__ == "__main__":
    main()