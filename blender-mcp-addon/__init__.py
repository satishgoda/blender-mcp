"""Public API surface for the Blender MCP add-on package."""

from __future__ import annotations

# from .constants import BL_INFO
from .constants import DEFAULT_HOST, DEFAULT_PORT, REQ_HEADERS, RODIN_FREE_TRIAL_KEY
from .registration import register as register_all
from .registration import unregister as unregister_all
from .server import BlenderMCPServer

# bl_info = BL_INFO

bl_info = {
    "name": "Blender MCP",
    "author": "BlenderMCP",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to Claude via MCP",
    "category": "Interface",
}

__all__ = [
    "register_all",
    "unregister_all",
    "BlenderMCPServer",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "RODIN_FREE_TRIAL_KEY",
    "REQ_HEADERS",
]


def register() -> None:
    """Register the Blender MCP add-on."""
    register_all()


def unregister() -> None:
    """Unregister the Blender MCP add-on."""
    unregister_all()


if __name__ == "__main__":
    register()
