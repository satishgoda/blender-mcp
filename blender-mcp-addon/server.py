"""MCP socket server implementation."""

from __future__ import annotations

import json
import socket
import threading
import time
import traceback
from typing import Any, Callable

import bpy

from .constants import DEFAULT_HOST, DEFAULT_PORT
from .integrations.hyper3d import Hyper3DMixin
from .integrations.polyhaven import PolyhavenMixin
from .integrations.scene import SceneMixin
from .integrations.sketchfab import SketchfabMixin


Handler = Callable[..., Any]


class BlenderMCPServer(SceneMixin, PolyhavenMixin, Hyper3DMixin, SketchfabMixin):
    """Socket server that routes MCP commands into Blender API calls."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.running = False
        self.socket: socket.socket | None = None
        self.server_thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running:
            print("Server is already running")
            return

        self.running = True

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)

            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()

            print(f"BlenderMCP server started on {self.host}:{self.port}")
        except Exception as exc:
            print(f"Failed to start server: {exc}")
            self.stop()

    def stop(self) -> None:
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except Exception:
                pass
            self.server_thread = None

        print("BlenderMCP server stopped")

    def _server_loop(self) -> None:
        print("Server thread started")
        assert self.socket is not None
        self.socket.settimeout(1.0)

        while self.running:
            try:
                try:
                    client, address = self.socket.accept()
                    print(f"Connected to client: {address}")

                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client,),
                        daemon=True,
                    )
                    client_thread.start()
                except socket.timeout:
                    continue
                except Exception as exc:
                    print(f"Error accepting connection: {exc}")
                    time.sleep(0.5)
            except Exception as exc:
                print(f"Error in server loop: {exc}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("Server thread stopped")

    def _handle_client(self, client: socket.socket) -> None:
        print("Client handler started")
        client.settimeout(None)
        buffer = b""

        try:
            while self.running:
                try:
                    data = client.recv(8192)
                    if not data:
                        print("Client disconnected")
                        break

                    buffer += data
                    try:
                        command = json.loads(buffer.decode("utf-8"))
                        buffer = b""

                        def execute_wrapper() -> None:
                            try:
                                response = self.execute_command(command)
                                response_json = json.dumps(response)
                                client.sendall(response_json.encode("utf-8"))
                            except Exception as exc:
                                print(f"Error executing command: {exc}")
                                traceback.print_exc()
                                try:
                                    error_response = {
                                        "status": "error",
                                        "message": str(exc),
                                    }
                                    client.sendall(json.dumps(error_response).encode("utf-8"))
                                except Exception:
                                    pass

                        bpy.app.timers.register(execute_wrapper, first_interval=0.0)
                    except json.JSONDecodeError:
                        pass
                except Exception as exc:
                    print(f"Error receiving data: {exc}")
                    break
        except Exception as exc:
            print(f"Error in client handler: {exc}")
        finally:
            try:
                client.close()
            except Exception:
                pass
            print("Client handler stopped")

    def execute_command(self, command: dict) -> dict:
        try:
            return self._execute_command_internal(command)
        except Exception as exc:
            print(f"Error executing command: {exc}")
            traceback.print_exc()
            return {"status": "error", "message": str(exc)}

    def _execute_command_internal(self, command: dict) -> dict:
        cmd_type = command.get("type")
        params = command.get("params", {})

        if cmd_type == "get_polyhaven_status":
            return {"status": "success", "result": self.get_polyhaven_status()}

        handlers: dict[str, Handler] = {
            "get_scene_info": self.get_scene_info,
            "get_object_info": self.get_object_info,
            "get_viewport_screenshot": self.get_viewport_screenshot,
            "execute_code": self.execute_code,
            "get_polyhaven_status": self.get_polyhaven_status,
            "get_hyper3d_status": self.get_hyper3d_status,
            "get_sketchfab_status": self.get_sketchfab_status,
        }

        scene = bpy.context.scene
        if scene.blendermcp_use_polyhaven:
            handlers.update(
                {
                    "get_polyhaven_categories": self.get_polyhaven_categories,
                    "search_polyhaven_assets": self.search_polyhaven_assets,
                    "download_polyhaven_asset": self.download_polyhaven_asset,
                    "set_texture": self.set_texture,
                }
            )

        if scene.blendermcp_use_hyper3d:
            handlers.update(
                {
                    "create_rodin_job": self.create_rodin_job,
                    "poll_rodin_job_status": self.poll_rodin_job_status,
                    "import_generated_asset": self.import_generated_asset,
                }
            )

        if scene.blendermcp_use_sketchfab:
            handlers.update(
                {
                    "search_sketchfab_models": self.search_sketchfab_models,
                    "download_sketchfab_model": self.download_sketchfab_model,
                }
            )

        handler = handlers.get(cmd_type)
        if not handler:
            return {"status": "error", "message": f"Unknown command type: {cmd_type}"}

        try:
            print(f"Executing handler for {cmd_type}")
            result = handler(**params)
            print("Handler execution complete")
            return {"status": "success", "result": result}
        except Exception as exc:
            print(f"Error in handler: {exc}")
            traceback.print_exc()
            return {"status": "error", "message": str(exc)}


__all__ = ["BlenderMCPServer"]
