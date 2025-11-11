"""Sketchfab integration helpers."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile
from contextlib import suppress
from typing import Any, Dict, cast

try:
    import bpy as _bpy  # type: ignore[import]
except ImportError:  # pragma: no cover - only happens during static analysis outside Blender
    _bpy = None
bpy: Any = cast(Any, _bpy)

try:
    import requests as _requests  # type: ignore[import]
except ImportError:  # pragma: no cover - requests should be available at runtime
    _requests = None
requests: Any = cast(Any, _requests)


class SketchfabMixin:
    """Provide Sketchfab related operations."""

    def _get_scene(self) -> Any:
        return bpy.context.scene

    def get_sketchfab_status(self) -> Dict[str, Any]:
        """Return integration state for Sketchfab usage."""
        scene = self._get_scene()
        enabled = scene.blendermcp_use_sketchfab
        api_key = scene.blendermcp_sketchfab_api_key

        if api_key:
            try:
                headers = {"Authorization": f"Token {api_key}"}
                response = requests.get(
                    "https://api.sketchfab.com/v3/me",
                    headers=headers,
                    timeout=30,
                )

                if response.status_code == 200:
                    user_data = cast(Dict[str, Any], response.json())
                    username = user_data.get("username", "Unknown user")
                    return {
                        "enabled": True,
                        "message": (
                            "Sketchfab integration is enabled and ready to use. "
                            f"Logged in as: {username}"
                        ),
                    }
                return {
                    "enabled": False,
                    "message": f"Sketchfab API key seems invalid. Status code: {response.status_code}",
                }
            except requests.exceptions.Timeout:
                return {
                    "enabled": False,
                    "message": "Timeout connecting to Sketchfab API. Check your internet connection.",
                }
            except Exception as exc:  # pragma: no cover - Blender environment only
                return {"enabled": False, "message": f"Error testing Sketchfab API key: {exc}"}

        if enabled and api_key:
            return {"enabled": True, "message": "Sketchfab integration is enabled and ready to use."}

        if enabled and not api_key:
            return {
                "enabled": False,
                "message": (
                    "Sketchfab integration is currently enabled, but API key is not given. To enable it:\n"
                    "1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)\n"
                    "2. Keep the 'Use Sketchfab' checkbox checked\n"
                    "3. Enter your Sketchfab API Key\n"
                    "4. Restart the connection to Claude"
                ),
            }

        return {
            "enabled": False,
            "message": (
                "Sketchfab integration is currently disabled. To enable it:\n"
                "1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)\n"
                "2. Check the 'Use assets from Sketchfab' checkbox\n"
                "3. Enter your Sketchfab API Key\n"
                "4. Restart the connection to Claude"
            ),
        }

    def search_sketchfab_models(
        self,
        query: str,
        categories: str | None = None,
        count: int = 20,
        downloadable: bool = True,
    ) -> Dict[str, Any]:
        """Search for Sketchfab models."""
        try:
            scene = self._get_scene()
            api_key = scene.blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            params: Dict[str, Any] = {
                "type": "models",
                "q": query,
                "count": count,
                "downloadable": downloadable,
                "archives_flavours": False,
            }

            if categories:
                params["categories"] = categories

            headers = {"Authorization": f"Token {api_key}"}
            response = requests.get(
                "https://api.sketchfab.com/v3/search",
                headers=headers,
                params=params,
                timeout=30,
            )

            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}
            if response.status_code != 200:
                return {"error": f"API request failed with status code {response.status_code}"}

            response_data_raw = response.json()
            if response_data_raw is None:
                return {"error": "Received empty response from Sketchfab API"}

            response_data = cast(Dict[str, Any], response_data_raw)
            results = response_data.get("results", [])
            if not isinstance(results, list):
                return {"error": f"Unexpected response format from Sketchfab API: {response_data}"}

            return response_data
        except requests.exceptions.Timeout:
            return {"error": "Request timed out. Check your internet connection."}
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON response from Sketchfab API: {exc}"}
        except Exception as exc:  # pragma: no cover - Blender environment only
            import traceback

            traceback.print_exc()
            return {"error": str(exc)}

    def download_sketchfab_model(self, uid: str) -> Dict[str, Any]:
        """Download and import a Sketchfab model by UID."""
        try:
            scene = self._get_scene()
            api_key = scene.blendermcp_sketchfab_api_key
            if not api_key:
                return {"error": "Sketchfab API key is not configured"}

            headers = {"Authorization": f"Token {api_key}"}
            download_endpoint = f"https://api.sketchfab.com/v3/models/{uid}/download"

            response = requests.get(download_endpoint, headers=headers, timeout=30)
            if response.status_code == 401:
                return {"error": "Authentication failed (401). Check your API key."}
            if response.status_code != 200:
                return {"error": f"Download request failed with status code {response.status_code}"}

            data_raw = response.json()
            if data_raw is None:
                return {"error": "Received empty response from Sketchfab API for download request"}
            data = cast(Dict[str, Any], data_raw)

            gltf_data = data.get("gltf")
            if not gltf_data:
                return {"error": "No gltf download URL available for this model. Response: " + str(data)}

            download_url = gltf_data.get("url")
            if not download_url:
                return {
                    "error": "No download URL available for this model. Make sure the model is downloadable and you have access.",
                }

            model_response = requests.get(download_url, timeout=60)
            if model_response.status_code != 200:
                return {"error": f"Model download failed with status code {model_response.status_code}"}

            temp_dir = tempfile.mkdtemp()
            zip_file_path = os.path.join(temp_dir, f"{uid}.zip")

            with open(zip_file_path, "wb") as file_handle:
                file_handle.write(model_response.content)

            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                for file_info in zip_ref.infolist():
                    file_path = file_info.filename
                    target_path = os.path.join(temp_dir, os.path.normpath(file_path))
                    abs_temp_dir = os.path.abspath(temp_dir)
                    abs_target_path = os.path.abspath(target_path)

                    if not abs_target_path.startswith(abs_temp_dir):
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with path traversal attempt"}

                    if ".." in file_path:
                        with suppress(Exception):
                            shutil.rmtree(temp_dir)
                        return {"error": "Security issue: Zip contains files with directory traversal sequence"}

                zip_ref.extractall(temp_dir)

            gltf_files = [file for file in os.listdir(temp_dir) if file.endswith((".gltf", ".glb"))]
            if not gltf_files:
                with suppress(Exception):
                    shutil.rmtree(temp_dir)
                return {"error": "No glTF file found in the downloaded model"}

            main_file = os.path.join(temp_dir, gltf_files[0])
            bpy.ops.import_scene.gltf(filepath=main_file)

            imported_objects = [obj.name for obj in bpy.context.selected_objects]

            with suppress(Exception):
                shutil.rmtree(temp_dir)

            return {
                "success": True,
                "message": "Model imported successfully",
                "imported_objects": imported_objects,
            }
        except requests.exceptions.Timeout:
            return {
                "error": "Request timed out. Check your internet connection and try again with a simpler model.",
            }
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON response from Sketchfab API: {exc}"}
        except Exception as exc:  # pragma: no cover - Blender environment only
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to download model: {exc}"}


__all__ = ["SketchfabMixin"]
