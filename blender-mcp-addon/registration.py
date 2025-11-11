"""Registration entry points for the Blender MCP add-on."""

from __future__ import annotations

import bpy

from . import properties, ui


def register() -> None:
    """Register properties and UI classes with Blender."""
    properties.register_properties()

    for cls in ui.CLASSES:
        bpy.utils.register_class(cls)

    print("BlenderMCP addon registered")


def unregister() -> None:
    """Unregister Blender objects and stop the server if needed."""
    if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
        bpy.types.blendermcp_server.stop()
        del bpy.types.blendermcp_server

    for cls in reversed(ui.CLASSES):
        bpy.utils.unregister_class(cls)

    properties.unregister_properties()

    print("BlenderMCP addon unregistered")


__all__ = ["register", "unregister"]
