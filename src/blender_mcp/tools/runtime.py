"""Runtime execution helpers."""

from __future__ import annotations

from typing import Any, Sequence, cast

from ..app import mcp as _mcp  # type: ignore[attr-defined]
from ..config import LOGGER
from ..connection import get_blender_connection

__all__ = ["execute_blender_code", "process_bbox"]

mcp = cast(Any, _mcp)


@mcp.tool()
def execute_blender_code(ctx: Any, code: str) -> str:
    """Execute arbitrary Python code inside Blender."""
    del ctx
    try:
        blender = get_blender_connection()
        result = blender.send_command("execute_code", {"code": code})

        output = result.get("result", "")
        message = f"Code executed successfully: {output}"

        text_name = result.get("text_name")
        if text_name:
            message += f"\nSnippet stored in Blender Text block: {text_name}"

        return message
    except Exception as exc:  # noqa: BLE001
        LOGGER.error("Error executing code: %s", exc)
        return f"Error executing code: {exc}"


def process_bbox(original_bbox: Sequence[float] | Sequence[int] | None) -> list[int] | None:
    """Normalize bounding box ratios for Hyper3D requests."""
    if original_bbox is None:
        return None

    if all(isinstance(value, int) for value in original_bbox):
        return [int(value) for value in original_bbox]

    if any(float(value) <= 0 for value in original_bbox):
        raise ValueError("Incorrect number range: bbox must be bigger than zero!")

    largest = max(float(value) for value in original_bbox)
    return [int(float(value) / largest * 100) for value in original_bbox]
