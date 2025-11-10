"""PolyHaven integration tools."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from ..app import mcp as _mcp  # type: ignore[attr-defined]
from ..config import LOGGER
from ..connection import get_blender_connection, is_polyhaven_enabled


mcp = _mcp

@mcp.tool()
def get_polyhaven_categories(ctx: Any, asset_type: str = "hdris") -> str:
    """List PolyHaven categories for the requested asset type."""
    del ctx
    try:
        blender = get_blender_connection()
        if not is_polyhaven_enabled():
            return "PolyHaven integration is disabled. Select it in the sidebar in BlenderMCP, then run it again."

        result: Dict[str, Any] = blender.send_command("get_polyhaven_categories", {"asset_type": asset_type})
        if "error" in result:
            return f"Error: {result['error']}"

        categories = result.get("categories", {})
        formatted_output = f"Categories for {asset_type}:\n\n"
        sorted_categories = sorted(categories.items(), key=lambda item: item[1], reverse=True)
        for category, count in sorted_categories:
            formatted_output += f"- {category}: {count} assets\n"
        return formatted_output
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error getting Polyhaven categories: %s", exc)
        return f"Error getting Polyhaven categories: {exc}"


@mcp.tool()
def search_polyhaven_assets(
    ctx: Any,
    asset_type: str = "all",
    categories: Optional[str] = None,
) -> str:
    """Search PolyHaven assets with optional category filtering."""
    del ctx
    try:
        blender = get_blender_connection()
        result: Dict[str, Any] = blender.send_command(
            "search_polyhaven_assets",
            {"asset_type": asset_type, "categories": categories},
        )

        if "error" in result:
            return f"Error: {result['error']}"

        assets: Dict[str, Dict[str, Any]] = result.get("assets", {})
        total_count = result.get("total_count", 0)
        returned_count = result.get("returned_count", 0)

        formatted_output = f"Found {total_count} assets"
        if categories:
            formatted_output += f" in categories: {categories}"
        formatted_output += f"\nShowing {returned_count} assets:\n\n"

        sorted_assets = sorted(
            assets.items(),
            key=lambda item: item[1].get("download_count", 0),
            reverse=True,
        )

        type_labels: list[str] = ["HDRI", "Texture", "Model"]
        for asset_id, asset_data in sorted_assets:
            formatted_output += f"- {asset_data.get('name', asset_id)} (ID: {asset_id})\n"
            asset_type_index = asset_data.get("type", 0)
            index = cast(int, asset_type_index)
            type_label: str
            if 0 <= index < len(type_labels):
                type_label = type_labels[index]
            else:
                type_label = "Unknown"
            formatted_output += f"  Type: {type_label}\n"
            formatted_output += f"  Categories: {', '.join(asset_data.get('categories', []))}\n"
            formatted_output += f"  Downloads: {asset_data.get('download_count', 'Unknown')}\n\n"

        return formatted_output
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error searching Polyhaven assets: %s", exc)
        return f"Error searching Polyhaven assets: {exc}"


@mcp.tool()
def download_polyhaven_asset(
    ctx: Any,
    asset_id: str,
    asset_type: str,
    resolution: str = "1k",
    file_format: Optional[str] = None,
) -> str:
    """Download and import a PolyHaven asset into Blender."""
    del ctx
    try:
        blender = get_blender_connection()
        result: Dict[str, Any] = blender.send_command(
            "download_polyhaven_asset",
            {
                "asset_id": asset_id,
                "asset_type": asset_type,
                "resolution": resolution,
                "file_format": file_format,
            },
        )

        if "error" in result:
            return f"Error: {result['error']}"

        if result.get("success"):
            message = result.get("message", "Asset downloaded and imported successfully")
            if asset_type == "hdris":
                return f"{message}. The HDRI has been set as the world environment."
            if asset_type == "textures":
                material_name = result.get("material", "")
                maps = ", ".join(result.get("maps", []))
                return f"{message}. Created material '{material_name}' with maps: {maps}."
            if asset_type == "models":
                return f"{message}. The model has been imported into the current scene."
            return message
        return f"Failed to download asset: {result.get('message', 'Unknown error')}"
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error downloading Polyhaven asset: %s", exc)
        return f"Error downloading Polyhaven asset: {exc}"


@mcp.tool()
def set_texture(ctx: Any, object_name: str, texture_id: str) -> str:
    """Apply a previously downloaded PolyHaven texture to an object."""
    del ctx
    try:
        blender = get_blender_connection()
        result: Dict[str, Any] = blender.send_command(
            "set_texture",
            {"object_name": object_name, "texture_id": texture_id},
        )

        if "error" in result:
            return f"Error: {result['error']}"

        if result.get("success"):
            material_name = result.get("material", "")
            maps = ", ".join(result.get("maps", []))
            material_info = result.get("material_info", {})
            node_count = material_info.get("node_count", 0)
            has_nodes = material_info.get("has_nodes", False)
            texture_nodes = material_info.get("texture_nodes", [])

            output = f"Successfully applied texture '{texture_id}' to {object_name}.\n"
            output += f"Using material '{material_name}' with maps: {maps}.\n\n"
            output += f"Material has nodes: {has_nodes}\n"
            output += f"Total node count: {node_count}\n\n"

            if texture_nodes:
                output += "Texture nodes:\n"
                for node in texture_nodes:
                    output += f"- {node['name']} using image: {node['image']}\n"
                    if node.get("connections"):
                        output += "  Connections:\n"
                        for connection in node["connections"]:
                            output += f"    {connection}\n"
            else:
                output += "No texture nodes found in the material.\n"

            return output
        return f"Failed to apply texture: {result.get('message', 'Unknown error')}"
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error applying texture: %s", exc)
        return f"Error applying texture: {exc}"


@mcp.tool()
def get_polyhaven_status(ctx: Any) -> str:
    """Return the PolyHaven integration status message."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_polyhaven_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += "PolyHaven is good at Textures, and has a wider variety of textures than Sketchfab."
        return message
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error checking PolyHaven status: %s", exc)
        return f"Error checking PolyHaven status: {exc}"
