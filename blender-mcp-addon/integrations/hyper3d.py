"""Hyper3D Rodin integration helpers."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from typing import Any, Dict, cast

try:
    import bpy as _bpy  # type: ignore[import]
except ImportError:  # pragma: no cover - only happens during static analysis outside Blender
    _bpy = None
bpy = cast(Any, _bpy)

try:
    import requests as _requests  # type: ignore[import]
except ImportError:  # pragma: no cover - requests should be available at runtime
    _requests = None
requests = cast(Any, _requests)

from ..constants import RODIN_FREE_TRIAL_KEY


class Hyper3DMixin:
    """Provide Hyper3D related operations."""

    def get_hyper3d_status(self) -> Dict[str, Any]:
        """Return integration state for Hyper3D usage."""
        enabled = bpy.context.scene.blendermcp_use_hyper3d
        if enabled:
            if not bpy.context.scene.blendermcp_hyper3d_api_key:
                return {
                    "enabled": False,
                    "message": (
                        "Hyper3D Rodin integration is currently enabled, but API key is not given. To enable it:\n"
                        "1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)\n"
                        "2. Keep the 'Use Hyper3D Rodin 3D model generation' checkbox checked\n"
                        "3. Choose the right plaform and fill in the API Key\n"
                        "4. Restart the connection to Claude"
                    ),
                }

            mode = bpy.context.scene.blendermcp_hyper3d_mode
            message = (
                "Hyper3D Rodin integration is enabled and ready to use. Mode: "
                f"{mode}. Key type: "
                f"{'private' if bpy.context.scene.blendermcp_hyper3d_api_key != RODIN_FREE_TRIAL_KEY else 'free_trial'}"
            )
            return {"enabled": True, "message": message}

        return {
            "enabled": False,
            "message": (
                "Hyper3D Rodin integration is currently disabled. To enable it:\n"
                "1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)\n"
                "2. Check the 'Use Hyper3D Rodin 3D model generation' checkbox\n"
                "3. Restart the connection to Claude"
            ),
        }

    def create_rodin_job(self, *args: Any, **kwargs: Any) -> Dict[str, Any] | str:
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.create_rodin_job_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.create_rodin_job_fal_ai(*args, **kwargs)
            case _:
                return "Error: Unknown Hyper3D Rodin mode!"

    def create_rodin_job_main_site(
        self,
        text_prompt: str | None = None,
        images: list[tuple[str, str]] | None = None,
        bbox_condition: Any | None = None,
    ) -> Dict[str, Any]:
        try:
            if images is None:
                images = []

            files: list[tuple[str, tuple[str | None, str]]]
            files = [
                *[("images", (f"{index:04d}{suffix}", img)) for index, (suffix, img) in enumerate(images)],
                ("tier", (None, "Sketch")),
                ("mesh_mode", (None, "Raw")),
            ]

            if text_prompt:
                files.append(("prompt", (None, text_prompt)))
            if bbox_condition:
                files.append(("bbox_condition", (None, json.dumps(bbox_condition))))

            response = requests.post(
                "https://hyperhuman.deemos.com/api/v2/rodin",
                headers={
                    "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
                },
                files=files,
            )
            return cast(Dict[str, Any], response.json())
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": str(exc)}

    def create_rodin_job_fal_ai(
        self,
        text_prompt: str | None = None,
        images: list[tuple[str, str]] | None = None,
        bbox_condition: Any | None = None,
    ) -> Dict[str, Any]:
        try:
            payload: dict[str, object] = {"tier": "Sketch"}
            if images:
                payload["input_image_urls"] = images
            if text_prompt:
                payload["prompt"] = text_prompt
            if bbox_condition:
                payload["bbox_condition"] = bbox_condition

            response = requests.post(
                "https://queue.fal.run/fal-ai/hyper3d/rodin",
                headers={
                    "Authorization": f"Key {bpy.context.scene.blendermcp_hyper3d_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            return cast(Dict[str, Any], response.json())
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": str(exc)}

    def poll_rodin_job_status(self, *args: Any, **kwargs: Any) -> Dict[str, Any] | str:
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.poll_rodin_job_status_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.poll_rodin_job_status_fal_ai(*args, **kwargs)
            case _:
                return "Error: Unknown Hyper3D Rodin mode!"

    def poll_rodin_job_status_main_site(self, subscription_key: str) -> Dict[str, Any]:
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/status",
            headers={
                "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
            json={"subscription_key": subscription_key},
        )
        data = cast(Dict[str, Any], response.json())
        return {"status_list": [item["status"] for item in data["jobs"]]}

    def poll_rodin_job_status_fal_ai(self, request_id: str) -> Dict[str, Any]:
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}/status",
            headers={
                "Authorization": f"KEY {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
        )
        return cast(Dict[str, Any], response.json())

    @staticmethod
    def _clean_imported_glb(filepath: str, mesh_name: str | None = None) -> Any | None:
        existing_objects = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=filepath)
        bpy.context.view_layer.update()

        imported_objects = list(set(bpy.data.objects) - existing_objects)
        if not imported_objects:
            print("Error: No objects were imported.")
            return None

        mesh_obj = None

        if len(imported_objects) == 1 and imported_objects[0].type == "MESH":
            mesh_obj = imported_objects[0]
        else:
            if len(imported_objects) == 2:
                empty_objs = [obj for obj in imported_objects if obj.type == "EMPTY"]
                if len(empty_objs) != 1:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return None
                parent_obj = empty_objs.pop()
                if len(parent_obj.children) == 1:
                    potential_mesh = parent_obj.children[0]
                    if potential_mesh.type == "MESH":
                        potential_mesh.parent = None
                        bpy.data.objects.remove(parent_obj)
                        mesh_obj = potential_mesh
                    else:
                        print("Error: Child is not a mesh object.")
                        return None
                else:
                    print("Error: Expected an empty node with one mesh child or a single mesh object.")
                    return None
            else:
                print("Error: Expected an empty node with one mesh child or a single mesh object.")
                return None

        if mesh_obj and mesh_obj.name is not None and mesh_name:
            try:
                mesh_obj.name = mesh_name
                if mesh_obj.data and mesh_obj.data.name is not None:
                    mesh_obj.data.name = mesh_name
            except Exception:
                print("Having issue with renaming, give up renaming.")

        return mesh_obj

    def import_generated_asset(self, *args: Any, **kwargs: Any) -> Dict[str, Any] | str:
        match bpy.context.scene.blendermcp_hyper3d_mode:
            case "MAIN_SITE":
                return self.import_generated_asset_main_site(*args, **kwargs)
            case "FAL_AI":
                return self.import_generated_asset_fal_ai(*args, **kwargs)
            case _:
                return "Error: Unknown Hyper3D Rodin mode!"

    def import_generated_asset_main_site(self, task_uuid: str, name: str) -> Dict[str, Any]:
        response = requests.post(
            "https://hyperhuman.deemos.com/api/v2/download",
            headers={
                "Authorization": f"Bearer {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
            json={"task_uuid": task_uuid},
        )
        data = response.json()
        temp_file = None

        for item in data.get("list", []):
            if item["name"].endswith(".glb"):
                temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=task_uuid, suffix=".glb")
                try:
                    response = requests.get(item["url"], stream=True)
                    response.raise_for_status()
                    for chunk in response.iter_content(chunk_size=8192):
                        temp_file.write(chunk)
                    temp_file.close()
                except Exception as exc:
                    temp_file.close()
                    os.unlink(temp_file.name)
                    return {"succeed": False, "error": str(exc)}
                break
        else:
            return {
                "succeed": False,
                "error": "Generation failed. Please first make sure that all jobs of the task are done and then try again later.",
            }

        try:
            obj = self._clean_imported_glb(filepath=temp_file.name, mesh_name=name)
            if obj is None:
                return {"succeed": False, "error": "Failed to import object"}

            result: Dict[str, Any] = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                result["world_bounding_box"] = cast(Any, self)._get_aabb(obj)

            return {"succeed": True, **result}
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"succeed": False, "error": str(exc)}
        finally:
            with suppress(Exception):
                os.unlink(temp_file.name)

    def import_generated_asset_fal_ai(self, request_id: str, name: str) -> Dict[str, Any]:
        response = requests.get(
            f"https://queue.fal.run/fal-ai/hyper3d/requests/{request_id}",
            headers={
                "Authorization": f"Key {bpy.context.scene.blendermcp_hyper3d_api_key}",
            },
        )
        data = response.json()

        temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=request_id, suffix=".glb")

        try:
            response = requests.get(data["model_mesh"]["url"], stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file.close()
        except Exception as exc:
            temp_file.close()
            os.unlink(temp_file.name)
            return {"succeed": False, "error": str(exc)}

        try:
            obj = self._clean_imported_glb(filepath=temp_file.name, mesh_name=name)
            if obj is None:
                return {"succeed": False, "error": "Failed to import object"}

            result: Dict[str, Any] = {
                "name": obj.name,
                "type": obj.type,
                "location": [obj.location.x, obj.location.y, obj.location.z],
                "rotation": [obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z],
                "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            }

            if obj.type == "MESH":
                result["world_bounding_box"] = cast(Any, self)._get_aabb(obj)

            return {"succeed": True, **result}
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"succeed": False, "error": str(exc)}
        finally:
            with suppress(Exception):
                os.unlink(temp_file.name)


__all__ = ["Hyper3DMixin"]
