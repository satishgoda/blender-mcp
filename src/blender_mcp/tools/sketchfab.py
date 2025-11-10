"""Sketchfab integration tools."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from ..app import mcp as _mcp  # type: ignore[attr-defined]
from ..config import LOGGER
from ..connection import get_blender_connection


mcp = _mcp

@mcp.tool()
def get_sketchfab_status(ctx: Any) -> str:
    """Return Sketchfab integration status details."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_sketchfab_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += "Sketchfab is good at Realistic models, and has a wider variety of models than PolyHaven."
        return message
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error checking Sketchfab status: %s", exc)
        return f"Error checking Sketchfab status: {exc}"


@mcp.tool()
def search_sketchfab_models(
    ctx: Any,
    query: str,
    categories: Optional[str] = None,
    count: int = 20,
    downloadable: bool = True,
) -> str:
    """Search Sketchfab for downloadable models."""
    del ctx
    try:
        blender = get_blender_connection()
        LOGGER.info(
            "Searching Sketchfab models with query: %s, categories: %s, count: %s, downloadable: %s",
            query,
            categories,
            count,
            downloadable,
        )
        result = cast(
            Optional[Dict[str, Any]],
            blender.send_command(
                "search_sketchfab_models",
                {
                    "query": query,
                    "categories": categories,
                    "count": count,
                    "downloadable": downloadable,
                },
            ),
        )

        if result is None:
            LOGGER.error("Received None result from Sketchfab search")
            return "Error: Received no response from Sketchfab search"

        if "error" in result:
            LOGGER.error("Error from Sketchfab search: %s", result["error"])
            return f"Error: {result['error']}"

        models_raw: list[Any] = result.get("results", []) or []
        models = cast(list[Dict[str, Any]], models_raw)
        if not models:
            return f"No models found matching '{query}'"

        formatted_output = f"Found {len(models)} models matching '{query}':\n\n"
        for model in models:
            model_name = model.get("name", "Unnamed model")
            model_uid = model.get("uid", "Unknown ID")
            formatted_output += f"- {model_name} (UID: {model_uid})\n"

            user_raw = model.get("user")
            user_data = cast(Dict[str, Any], user_raw) if isinstance(user_raw, dict) else {}
            username = user_data.get("username", "Unknown author")
            formatted_output += f"  Author: {username}\n"

            license_raw = model.get("license")
            license_data = cast(Dict[str, Any], license_raw) if isinstance(license_raw, dict) else {}
            license_label = license_data.get("label", "Unknown")
            formatted_output += f"  License: {license_label}\n"

            face_count = model.get("faceCount", "Unknown")
            is_downloadable = "Yes" if model.get("isDownloadable") else "No"
            formatted_output += f"  Face count: {face_count}\n"
            formatted_output += f"  Downloadable: {is_downloadable}\n\n"

        return formatted_output
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error searching Sketchfab models: %s", exc)
        return f"Error searching Sketchfab models: {exc}"


@mcp.tool()
def download_sketchfab_model(ctx: Any, uid: str) -> str:
    """Download and import a Sketchfab model by UID."""
    del ctx
    try:
        blender = get_blender_connection()
        LOGGER.info("Attempting to download Sketchfab model with UID: %s", uid)
        result = cast(Optional[Dict[str, Any]], blender.send_command("download_sketchfab_model", {"uid": uid}))

        if result is None:
            LOGGER.error("Received None result from Sketchfab download")
            return "Error: Received no response from Sketchfab download request"

        if "error" in result:
            LOGGER.error("Error from Sketchfab download: %s", result["error"])
            return f"Error: {result['error']}"

        if result.get("success"):
            imported_objects = result.get("imported_objects", [])
            object_names = ", ".join(imported_objects) if imported_objects else "none"
            return f"Successfully imported model. Created objects: {object_names}"
        return f"Failed to download model: {result.get('message', 'Unknown error')}"
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error downloading Sketchfab model: %s", exc)
        return f"Error downloading Sketchfab model: {exc}"
