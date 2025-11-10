"""Application lifespan management for the Blender MCP server."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from .config import LOGGER
from .connection import get_blender_connection, shutdown_connection


@asynccontextmanager
async def server_lifespan(server: Any) -> AsyncIterator[Dict[str, Any]]:
    """Manage startup and shutdown hooks for the FastMCP server."""
    try:
        server_path = os.path.abspath(__file__)
        LOGGER.info("BlenderMCP server starting up from local repository: %s", server_path)
        LOGGER.info("Repository location: %s", os.path.dirname(os.path.dirname(server_path)))
        LOGGER.info("BlenderMCP server starting up")

        try:
            get_blender_connection()
            LOGGER.info("Successfully connected to Blender on startup")
        except Exception as exc:  # noqa: BLE001 - warn but continue startup
            LOGGER.warning("Could not connect to Blender on startup: %s", exc)
            LOGGER.warning("Make sure the Blender addon is running before using Blender resources or tools")

        yield {}
    finally:
        shutdown_connection()
        LOGGER.info("BlenderMCP server shut down")
