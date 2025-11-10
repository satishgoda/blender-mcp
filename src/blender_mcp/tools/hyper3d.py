"""Hyper3D Rodin integration tools."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, cast

from urllib.parse import urlparse

from ..app import mcp as _mcp  # type: ignore[attr-defined]
from ..config import LOGGER
from ..connection import get_blender_connection
from .runtime import process_bbox

mcp = cast(Any, _mcp)


@mcp.tool()
def get_hyper3d_status(ctx: Any) -> str:
    """Check if Hyper3D Rodin integration is enabled."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command("get_hyper3d_status")
        enabled = result.get("enabled", False)
        message = result.get("message", "")
        if enabled:
            message += ""
        return message
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error checking Hyper3D status: %s", exc)
        return f"Error checking Hyper3D status: {exc}"


@mcp.tool()
def generate_hyper3d_model_via_text(
    ctx: Any,
    text_prompt: str,
    bbox_condition: Optional[Sequence[float]] = None,
) -> str:
    """Generate a Hyper3D asset using a text prompt."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command(
            "create_rodin_job",
            {
                "text_prompt": text_prompt,
                "images": None,
                "bbox_condition": process_bbox(bbox_condition),
            },
        )
        succeed = result.get("submit_time", False)
        if succeed:
            return json.dumps(
                {
                    "task_uuid": result["uuid"],
                    "subscription_key": result["jobs"]["subscription_key"],
                }
            )
        return json.dumps(result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error generating Hyper3D task: %s", exc)
        return f"Error generating Hyper3D task: {exc}"


@mcp.tool()
def generate_hyper3d_model_via_images(
    ctx: Any,
    input_image_paths: Optional[Sequence[str]] = None,
    input_image_urls: Optional[Sequence[str]] = None,
    bbox_condition: Optional[Sequence[float]] = None,
) -> str:
    """Generate a Hyper3D asset using image references."""
    del ctx
    if input_image_paths is not None and input_image_urls is not None:
        return "Error: Conflict parameters given!"
    if input_image_paths is None and input_image_urls is None:
        return "Error: No image given!"

    images: list[Any] = []

    if input_image_paths is not None:
        if not all(os.path.exists(path) for path in input_image_paths):
            return "Error: not all image paths are valid!"
        for path in input_image_paths:
            with open(path, "rb") as handle:
                images.append((Path(path).suffix, base64.b64encode(handle.read()).decode("ascii")))
    elif input_image_urls is not None:
        if not all(urlparse(url) for url in cast(Sequence[str], input_image_paths)):
            return "Error: not all image URLs are valid!"
        images = list(input_image_urls)

    try:
        blender = get_blender_connection()
        result = blender.send_command(
            "create_rodin_job",
            {
                "text_prompt": None,
                "images": images,
                "bbox_condition": process_bbox(bbox_condition),
            },
        )
        succeed = result.get("submit_time", False)
        if succeed:
            return json.dumps(
                {
                    "task_uuid": result["uuid"],
                    "subscription_key": result["jobs"]["subscription_key"],
                }
            )
        return json.dumps(result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error generating Hyper3D task: %s", exc)
        return f"Error generating Hyper3D task: {exc}"


@mcp.tool()
def poll_rodin_job_status(
    ctx: Any,
    subscription_key: Optional[str] = None,
    request_id: Optional[str] = None,
):
    """Poll the status of a Hyper3D generation task."""
    del ctx
    try:
        blender = get_blender_connection()
        kwargs: Dict[str, Optional[str]] = {}
        if subscription_key:
            kwargs = {"subscription_key": subscription_key}
        elif request_id:
            kwargs = {"request_id": request_id}
        result = blender.send_command("poll_rodin_job_status", kwargs)
        return result
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error generating Hyper3D task: %s", exc)
        return f"Error generating Hyper3D task: {exc}"


@mcp.tool()
def import_generated_asset(
    ctx: Any,
    name: str,
    task_uuid: Optional[str] = None,
    request_id: Optional[str] = None,
):
    """Import a generated Hyper3D asset after job completion."""
    del ctx
    try:
        blender = get_blender_connection()
        kwargs: Dict[str, Optional[str]] = {"name": name}
        if task_uuid:
            kwargs["task_uuid"] = task_uuid
        elif request_id:
            kwargs["request_id"] = request_id
        result = blender.send_command("import_generated_asset", kwargs)
        return result
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error generating Hyper3D task: %s", exc)
        return f"Error generating Hyper3D task: {exc}"
