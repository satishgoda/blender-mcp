"""Application entry point for the Blender MCP server."""

from __future__ import annotations

import importlib
import sys
from typing import Any, cast

from mcp.server.fastmcp import FastMCP  # type: ignore[import]

from .lifespan import server_lifespan
from .config import LOGGER

__all__ = ["mcp", "main"]

mcp = cast(Any, FastMCP("BlenderMCP", lifespan=server_lifespan))
sys.modules.setdefault("blender_mcp.app", sys.modules[__name__])

_components_registered = False


def _register_components() -> None:
    """Import modules that register tools and prompts with the MCP server."""
    global _components_registered
    if _components_registered:
        return

    module_names = [
        "blender_mcp.tools.scene",
        "blender_mcp.tools.runtime",
        "blender_mcp.tools.polyhaven",
        "blender_mcp.tools.sketchfab",
        "blender_mcp.tools.hyper3d",
        "blender_mcp.prompts.asset_creation",
    ]
    for module_name in module_names:
        importlib.import_module(module_name)

    try:
        tool_names = [tool.name for tool in mcp._tool_manager.list_tools()]  # type: ignore[attr-defined]
        LOGGER.info("Registered MCP tools: %s", ", ".join(tool_names) or "none")
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Could not enumerate registered tools: %s", exc)

    _components_registered = True


_register_components()


def main() -> None:
    """Run the FastMCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
