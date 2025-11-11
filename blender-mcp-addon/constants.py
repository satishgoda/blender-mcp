"""Shared constants for the Blender MCP add-on."""

from __future__ import annotations

from typing import Any, Dict, Optional

try:  # Blender's bundled Python may not include requests by default
    import requests as _requests  # type: ignore[import]
except ImportError:  # pragma: no cover - gracefully degrade when requests is absent
    _requests = None

requests: Optional[Any] = _requests

BL_INFO: Dict[str, Any] = {
    "name": "Blender MCP",
    "author": "BlenderMCP",
    "version": (1, 2),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > BlenderMCP",
    "description": "Connect Blender to Claude via MCP",
    "category": "Interface",
}

RODIN_FREE_TRIAL_KEY = "k9TcfFoEhNd9cCPP2guHAHHHkctZHIRhZDywZ1euGUXwihbYLpOjQhofby80NJez"

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876

def _build_default_headers(requests_module: Optional[Any]) -> Dict[str, str]:
    if requests_module is None:
        return {"User-Agent": "blender-mcp"}
    headers = requests_module.utils.default_headers()
    headers.update({"User-Agent": "blender-mcp"})
    return headers


REQ_HEADERS = _build_default_headers(requests)

__all__ = [
    "BL_INFO",
    "RODIN_FREE_TRIAL_KEY",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "REQ_HEADERS",
]
