"""Socket connection management for the Blender MCP server."""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT, LOGGER


@dataclass
class BlenderConnection:
    """Handle low-level socket communication with the Blender add-on."""

    host: str
    port: int
    sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Establish the socket connection to Blender."""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            LOGGER.info("Connected to Blender at %s:%s", self.host, self.port)
            return True
        except Exception as exc:  # noqa: BLE001 - surface original error message
            LOGGER.error("Failed to connect to Blender: %s", exc)
            self.sock = None
            return False

    def disconnect(self) -> None:
        """Close the socket connection."""
        if self.sock is None:
            return

        try:
            self.sock.close()
        except Exception as exc:  # noqa: BLE001 - best effort close
            LOGGER.error("Error disconnecting from Blender: %s", exc)
        finally:
            self.sock = None

    def receive_full_response(self, sock: socket.socket, buffer_size: int = 8192) -> bytes:
        """Receive all chunks for the pending response."""
        chunks: list[bytes] = []
        sock.settimeout(DEFAULT_TIMEOUT)

        try:
            while True:
                try:
                    chunk = sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise Exception("Connection closed before receiving any data")
                        break

                    chunks.append(chunk)

                    try:
                        data = b"".join(chunks)
                        json.loads(data.decode("utf-8"))
                        LOGGER.info("Received complete response (%s bytes)", len(data))
                        return data
                    except json.JSONDecodeError:
                        continue
                except socket.timeout:
                    LOGGER.warning("Socket timeout during chunked receive")
                    break
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as exc:
                    LOGGER.error("Socket connection error during receive: %s", exc)
                    raise
        except socket.timeout:
            LOGGER.warning("Socket timeout during chunked receive")
        except Exception as exc:  # noqa: BLE001 - propagate to caller
            LOGGER.error("Error during receive: %s", exc)
            raise

        if chunks:
            data = b"".join(chunks)
            LOGGER.info("Returning data after receive completion (%s bytes)", len(data))
            try:
                json.loads(data.decode("utf-8"))
                return data
            except json.JSONDecodeError as exc:  # noqa: F841 - message used below
                raise Exception("Incomplete JSON response received") from exc
        raise Exception("No data received")

    def send_command(self, command_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a command to Blender and parse the JSON response."""
        if not self.sock and not self.connect():
            raise ConnectionError("Not connected to Blender")

        command: Dict[str, Any] = {"type": command_type, "params": params or {}}

        try:
            LOGGER.info("Sending command: %s with params: %s", command_type, params)
            assert self.sock is not None  # narrow type for mypy/static checkers
            self.sock.sendall(json.dumps(command).encode("utf-8"))
            LOGGER.info("Command sent, waiting for response...")

            self.sock.settimeout(DEFAULT_TIMEOUT)
            response_data = self.receive_full_response(self.sock)
            LOGGER.info("Received %s bytes of data", len(response_data))

            response = json.loads(response_data.decode("utf-8"))
            LOGGER.info("Response parsed, status: %s", response.get("status", "unknown"))

            if response.get("status") == "error":
                message = response.get("message", "Unknown error from Blender")
                LOGGER.error("Blender error: %s", message)
                raise Exception(message)

            return response.get("result", {})
        except socket.timeout as exc:
            LOGGER.error("Socket timeout while waiting for response from Blender")
            self.sock = None
            raise Exception("Timeout waiting for Blender response - try simplifying your request") from exc
        except (ConnectionError, BrokenPipeError, ConnectionResetError) as exc:
            LOGGER.error("Socket connection error: %s", exc)
            self.sock = None
            raise Exception(f"Connection to Blender lost: {exc}") from exc
        except json.JSONDecodeError as exc:
            LOGGER.error("Invalid JSON response from Blender: %s", exc)
            if "response_data" in locals() and response_data:  # type: ignore[name-defined]
                LOGGER.error("Raw response (first 200 bytes): %s", response_data[:200])  # type: ignore[index]
            raise Exception(f"Invalid response from Blender: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - bubble up precise error
            LOGGER.error("Error communicating with Blender: %s", exc)
            self.sock = None
            raise Exception(f"Communication error with Blender: {exc}") from exc


_blender_connection: Optional[BlenderConnection] = None
_polyhaven_enabled = False


def is_polyhaven_enabled() -> bool:
    """Return the cached PolyHaven status."""
    return _polyhaven_enabled


def get_blender_connection() -> BlenderConnection:
    """Return a persistent connection, creating a new one if necessary."""
    global _blender_connection, _polyhaven_enabled

    if _blender_connection is not None:
        try:
            result = _blender_connection.send_command("get_polyhaven_status")
            _polyhaven_enabled = result.get("enabled", False)
            return _blender_connection
        except Exception as exc:  # noqa: BLE001 - refresh connection below
            LOGGER.warning("Existing connection is no longer valid: %s", exc)
            try:
                _blender_connection.disconnect()
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass
            _blender_connection = None

    host = os.getenv("BLENDER_HOST", DEFAULT_HOST)
    port = int(os.getenv("BLENDER_PORT", DEFAULT_PORT))
    connection = BlenderConnection(host=host, port=port)

    if not connection.connect():
        LOGGER.error("Failed to connect to Blender")
        raise Exception("Could not connect to Blender. Make sure the Blender addon is running.")

    LOGGER.info("Created new persistent connection to Blender")
    _blender_connection = connection
    return connection


def shutdown_connection() -> None:
    """Dispose of the persistent connection on shutdown."""
    global _blender_connection

    if _blender_connection is None:
        return

    LOGGER.info("Disconnecting from Blender on shutdown")
    _blender_connection.disconnect()
    _blender_connection = None
