"""Scene inspection and screenshot tools."""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any, cast

from mcp.server.fastmcp import Context, Image  # type: ignore[import]

from ..app import mcp as _mcp  # type: ignore[attr-defined]
from ..config import LOGGER
from ..connection import get_blender_connection

mcp = _mcp


@mcp.tool()
def get_scene_info(ctx: Any) -> str:
    """Return detailed information about the current Blender scene."""
    del ctx  # unused MCP context parameter
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_scene_info")
        return json.dumps(result, indent=2)
    except Exception as exc:  # noqa: BLE001 - propagate precise error message
        LOGGER.error("Error getting scene info from Blender: %s", exc)
        return f"Error getting scene info: {exc}"


@mcp.tool()
def get_object_info(ctx: Any, object_name: str) -> str:
    """Return detailed information about a specific object."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_object_info", {"name": object_name})
        return json.dumps(result, indent=2)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error getting object info from Blender: %s", exc)
        return f"Error getting object info: {exc}"


@mcp.tool()
def get_viewport_screenshot(ctx: Any, max_size: int = 800) -> Any:
    """Capture a screenshot of the current Blender 3D viewport."""
    del ctx
    try:
        blender = get_blender_connection()
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"blender_screenshot_{os.getpid()}.png")

        result = blender.send_command(
            "get_viewport_screenshot",
            {"max_size": max_size, "filepath": temp_path, "format": "png"},
        )

        if "error" in result:
            raise Exception(result["error"])

        if not os.path.exists(temp_path):
            raise Exception("Screenshot file was not created")

        with open(temp_path, "rb") as handle:
            image_bytes = handle.read()

        os.remove(temp_path)
        return cast(Any, Image(data=image_bytes, format="png"))
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error capturing screenshot: %s", exc)
        raise Exception(f"Screenshot failed: {exc}") from exc
