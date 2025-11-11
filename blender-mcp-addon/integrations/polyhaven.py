"""Poly Haven integration helpers."""

from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from contextlib import suppress
from typing import Any, Dict, List, Set, cast

try:
    import bpy as _bpy  # type: ignore[import]
except ImportError:  # pragma: no cover - only happens during static analysis outside Blender
    _bpy = None
bpy: Any = cast(Any, _bpy)

try:
    import requests as _requests  # type: ignore[import]
except ImportError:  # pragma: no cover - requests may be missing in Blender by default
    _requests = None
requests: Any = cast(Any, _requests)

from ..constants import REQ_HEADERS


class PolyhavenMixin:
    """Provide Polyhaven integration entry points."""

    def _require_requests(self) -> Any:
        if requests is None:
            raise RuntimeError(
                "The 'requests' library is required for PolyHaven integration. Install it in Blender's Python environment."
            )
        return requests

    def get_polyhaven_status(self) -> Dict[str, Any]:
        """Return integration state for Polyhaven usage."""
        enabled = bpy.context.scene.blendermcp_use_polyhaven
        if enabled:
            return {
                "enabled": True,
                "message": "PolyHaven integration is enabled and ready to use.",
            }
        return {
            "enabled": False,
            "message": (
                "PolyHaven integration is currently disabled. To enable it:\n"
                "1. In the 3D Viewport, find the BlenderMCP panel in the sidebar (press N if hidden)\n"
                "2. Check the 'Use assets from Poly Haven' checkbox\n"
                "3. Restart the connection to Claude"
            ),
        }

    def get_polyhaven_categories(self, asset_type: str) -> Dict[str, Any]:
        """Fetch Polyhaven categories for a given asset type."""
        try:
            req = self._require_requests()
            if asset_type not in ["hdris", "textures", "models", "all"]:
                return {
                    "error": (
                        f"Invalid asset type: {asset_type}. "
                        "Must be one of: hdris, textures, models, all"
                    )
                }

            response = req.get(
                f"https://api.polyhaven.com/categories/{asset_type}",
                headers=REQ_HEADERS,
            )
            if response.status_code == 200:
                return {"categories": response.json()}
            return {"error": f"API request failed with status code {response.status_code}"}
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": str(exc)}

    def search_polyhaven_assets(self, asset_type: str | None = None, categories: str | None = None) -> Dict[str, Any]:
        """Search Polyhaven assets with optional filters."""
        try:
            req = self._require_requests()
            url = "https://api.polyhaven.com/assets"
            params: dict[str, str] = {}

            if asset_type and asset_type != "all":
                if asset_type not in ["hdris", "textures", "models"]:
                    return {
                        "error": (
                            f"Invalid asset type: {asset_type}. "
                            "Must be one of: hdris, textures, models, all"
                        )
                    }
                params["type"] = asset_type

            if categories:
                params["categories"] = categories

            response = req.get(url, params=params, headers=REQ_HEADERS)
            if response.status_code != 200:
                return {"error": f"API request failed with status code {response.status_code}"}

            assets = response.json()
            limited_assets: Dict[str, Any] = {}
            for index, (key, value) in enumerate(assets.items()):
                if index >= 20:
                    break
                limited_assets[key] = value

            return {
                "assets": limited_assets,
                "total_count": len(assets),
                "returned_count": len(limited_assets),
            }
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": str(exc)}

    def download_polyhaven_asset(self, asset_id: str, asset_type: str, resolution: str = "1k", file_format: str | None = None) -> Dict[str, Any]:
        """Download and import an asset from Polyhaven."""
        try:
            req = self._require_requests()
            files_response = req.get(
                f"https://api.polyhaven.com/files/{asset_id}",
                headers=REQ_HEADERS,
            )
            if files_response.status_code != 200:
                return {"error": f"Failed to get asset files: {files_response.status_code}"}

            files_data = files_response.json()

            if asset_type == "hdris":
                return self._download_polyhaven_hdri(files_data, asset_id, resolution, file_format)

            if asset_type == "textures":
                return self._download_polyhaven_textures(files_data, asset_id, resolution, file_format)

            if asset_type == "models":
                return self._download_polyhaven_models(files_data, asset_id, resolution, file_format)

            return {"error": f"Unsupported asset type: {asset_type}"}
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": f"Failed to download asset: {exc}"}

    def set_texture(self, object_name: str, texture_id: str) -> Dict[str, Any]:
        """Assign a PolyHaven material previously created via download to an object."""
        obj = bpy.data.objects.get(object_name)
        if obj is None:
            return {"error": f"Object '{object_name}' not found"}

        material = bpy.data.materials.get(texture_id)
        if material is None:
            alt_material = next((mat for mat in bpy.data.materials if mat.name.startswith(texture_id)), None)
            if alt_material is None:
                return {
                    "error": (
                        f"Material '{texture_id}' not found. Download the texture first "
                        "or verify the material name in Blender."
                    )
                }
            material = alt_material

        data = getattr(obj, "data", None)
        if data is None or not hasattr(data, "materials"):
            return {"error": f"Object '{object_name}' does not support materials"}

        materials = data.materials

        if len(materials):
            index = obj.active_material_index if obj.active_material_index < len(materials) else 0
            materials[index] = material
        else:
            materials.append(material)

        has_nodes = bool(material.use_nodes and material.node_tree)
        node_count = len(material.node_tree.nodes) if has_nodes else 0

        maps: Set[str] = set()
        texture_nodes: List[Dict[str, Any]] = []

        if has_nodes:
            node_tree = material.node_tree
            for node in node_tree.nodes:
                if node.bl_idname == "ShaderNodeTexImage" and getattr(node, "image", None):
                    image = node.image
                    image_name = image.name
                    map_name = image_name
                    prefix = f"{texture_id}_"
                    if image_name.startswith(prefix):
                        map_name = image_name[len(prefix) :].split(".", 1)[0]
                    else:
                        map_name = image_name.split(".", 1)[0]
                    maps.add(map_name)

                    connections: List[str] = []
                    for output in node.outputs:
                        for link in getattr(output, "links", []):
                            to_socket = getattr(link.to_socket, "name", "")
                            to_node = getattr(link.to_node, "name", "")
                            connections.append(f"{node.name}.{output.name} -> {to_node}.{to_socket}")

                    texture_nodes.append(
                        {
                            "name": node.name,
                            "image": image_name,
                            "connections": connections,
                        }
                    )

        return {
            "success": True,
            "message": f"Applied texture '{texture_id}' to {object_name}",
            "material": material.name,
            "maps": sorted(maps) if maps else [],
            "material_info": {
                "has_nodes": has_nodes,
                "node_count": node_count,
                "texture_nodes": texture_nodes,
            },
        }

    # The next three helpers stay private to keep the public API surface compact.
    def _download_polyhaven_hdri(self, files_data: Dict[str, Any], asset_id: str, resolution: str, file_format: str | None) -> Dict[str, Any]:
        if not file_format:
            file_format = "hdr"

        req = self._require_requests()

        hdri_data = files_data.get("hdri")
        if not hdri_data or resolution not in hdri_data:
            return {"error": f"Requested resolution or format not available for this HDRI"}

        resolution_block = hdri_data[resolution]
        if file_format not in resolution_block:
            return {"error": f"Requested resolution or format not available for this HDRI"}

        file_info = resolution_block[file_format]
        file_url = file_info["url"]

        with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
            response = req.get(file_url, headers=REQ_HEADERS)
            if response.status_code != 200:
                return {"error": f"Failed to download HDRI: {response.status_code}"}
            tmp_file.write(response.content)
            tmp_path = tmp_file.name

        try:
            if not bpy.data.worlds:
                bpy.data.worlds.new("World")

            world = bpy.data.worlds[0]
            world.use_nodes = True
            node_tree = world.node_tree

            for node in node_tree.nodes:
                node_tree.nodes.remove(node)

            tex_coord = node_tree.nodes.new(type="ShaderNodeTexCoord")
            tex_coord.location = (-800, 0)

            mapping = node_tree.nodes.new(type="ShaderNodeMapping")
            mapping.location = (-600, 0)

            env_tex = node_tree.nodes.new(type="ShaderNodeTexEnvironment")
            env_tex.location = (-400, 0)
            env_tex.image = bpy.data.images.load(tmp_path)

            if file_format.lower() == "exr":
                for color_space in ["Linear", "Non-Color"]:
                    try:
                        env_tex.image.colorspace_settings.name = color_space
                        break
                    except Exception:
                        continue
            else:
                for color_space in ["Linear", "Linear Rec.709", "Non-Color"]:
                    try:
                        env_tex.image.colorspace_settings.name = color_space
                        break
                    except Exception:
                        continue

            background = node_tree.nodes.new(type="ShaderNodeBackground")
            background.location = (-200, 0)

            output = node_tree.nodes.new(type="ShaderNodeOutputWorld")
            output.location = (0, 0)

            node_tree.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
            node_tree.links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
            node_tree.links.new(env_tex.outputs["Color"], background.inputs["Color"])
            node_tree.links.new(background.outputs["Background"], output.inputs["Surface"])

            bpy.context.scene.world = world

            with suppress(Exception):
                os.unlink(tmp_path)

            return {
                "success": True,
                "message": f"HDRI {asset_id} imported successfully",
                "image_name": env_tex.image.name,
            }
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": f"Failed to set up HDRI in Blender: {exc}"}

    def _download_polyhaven_textures(self, files_data: Dict[str, Any], asset_id: str, resolution: str, file_format: str | None) -> Dict[str, Any]:
        if not file_format:
            file_format = "jpg"
        downloaded_maps: Dict[str, Any] = {}

        try:
            req = self._require_requests()
            for map_type, map_payload in files_data.items():
                if map_type in ["blend", "gltf"]:
                    continue

                resolution_block = map_payload.get(resolution)
                if not resolution_block:
                    continue

                format_block = resolution_block.get(file_format)
                if not format_block:
                    continue

                file_url = format_block["url"]

                with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as tmp_file:
                    response = req.get(file_url, headers=REQ_HEADERS)
                    if response.status_code != 200:
                        continue
                    tmp_file.write(response.content)
                    tmp_path = tmp_file.name

                image = bpy.data.images.load(tmp_path)
                image.name = f"{asset_id}_{map_type}.{file_format}"
                image.pack()

                if map_type.lower() in ["color", "diffuse", "albedo"]:
                    with suppress(Exception):
                        image.colorspace_settings.name = "sRGB"
                else:
                    with suppress(Exception):
                        image.colorspace_settings.name = "Non-Color"

                downloaded_maps[map_type] = image

                with suppress(Exception):
                    os.unlink(tmp_path)

            if not downloaded_maps:
                return {"error": "No texture maps found for the requested resolution and format"}

            material = bpy.data.materials.new(name=asset_id)
            material.use_nodes = True
            nodes = material.node_tree.nodes
            links = material.node_tree.links

            nodes.clear()

            output = nodes.new(type="ShaderNodeOutputMaterial")
            output.location = (300, 0)

            principled = nodes.new(type="ShaderNodeBsdfPrincipled")
            principled.location = (0, 0)
            links.new(principled.outputs[0], output.inputs[0])

            tex_coord = nodes.new(type="ShaderNodeTexCoord")
            tex_coord.location = (-800, 0)

            mapping = nodes.new(type="ShaderNodeMapping")
            mapping.location = (-600, 0)
            mapping.vector_type = "TEXTURE"
            links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

            x_pos = -400
            y_pos = 300

            for map_type, image in downloaded_maps.items():
                tex_node = nodes.new(type="ShaderNodeTexImage")
                tex_node.location = (x_pos, y_pos)
                tex_node.image = image

                if map_type.lower() in ["color", "diffuse", "albedo"]:
                    with suppress(Exception):
                        tex_node.image.colorspace_settings.name = "sRGB"
                else:
                    with suppress(Exception):
                        tex_node.image.colorspace_settings.name = "Non-Color"

                links.new(mapping.outputs["Vector"], tex_node.inputs["Vector"])

                lowered = map_type.lower()
                if lowered in ["color", "diffuse", "albedo"]:
                    links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])
                elif lowered in ["roughness", "rough"]:
                    links.new(tex_node.outputs["Color"], principled.inputs["Roughness"])
                elif lowered in ["metallic", "metalness", "metal"]:
                    links.new(tex_node.outputs["Color"], principled.inputs["Metallic"])
                elif lowered in ["normal", "nor"]:
                    normal_map = nodes.new(type="ShaderNodeNormalMap")
                    normal_map.location = (x_pos + 200, y_pos)
                    links.new(tex_node.outputs["Color"], normal_map.inputs["Color"])
                    links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])
                elif lowered in ["displacement", "disp", "height"]:
                    disp_node = nodes.new(type="ShaderNodeDisplacement")
                    disp_node.location = (x_pos + 200, y_pos - 200)
                    links.new(tex_node.outputs["Color"], disp_node.inputs["Height"])
                    links.new(disp_node.outputs["Displacement"], output.inputs["Displacement"])

                y_pos -= 250

            return {
                "success": True,
                "message": f"Texture {asset_id} imported as material",
                "material": material.name,
                "maps": list(downloaded_maps.keys()),
            }
        except Exception as exc:  # pragma: no cover - Blender environment only
            traceback.print_exc()
            return {"error": f"Failed to process textures: {exc}"}

    def _download_polyhaven_models(self, files_data: Dict[str, Any], asset_id: str, resolution: str, file_format: str | None) -> Dict[str, Any]:
        if not file_format:
            file_format = "gltf"

        req = self._require_requests()
        format_block = files_data.get(file_format)
        if not format_block:
            return {"error": "Requested format or resolution not available for this model"}

        resolution_block = format_block.get(resolution)
        if not resolution_block:
            return {"error": "Requested format or resolution not available for this model"}

        file_info = resolution_block.get(file_format)
        if not file_info:
            return {"error": "Requested format or resolution not available for this model"}

        file_url = file_info["url"]
        temp_dir = tempfile.mkdtemp()
        main_file_path = ""

        try:
            main_file_name = file_url.split("/")[-1]
            main_file_path = os.path.join(temp_dir, main_file_name)

            response = req.get(file_url, headers=REQ_HEADERS)
            if response.status_code != 200:
                return {"error": f"Failed to download model: {response.status_code}"}

            with open(main_file_path, "wb") as file_handle:
                file_handle.write(response.content)

            include_data = file_info.get("include", {})
            for include_path, include_info in include_data.items():
                include_url = include_info["url"]
                include_file_path = os.path.join(temp_dir, include_path)
                os.makedirs(os.path.dirname(include_file_path), exist_ok=True)
                include_response = req.get(include_url, headers=REQ_HEADERS)
                if include_response.status_code == 200:
                    with open(include_file_path, "wb") as include_file:
                        include_file.write(include_response.content)
                else:
                    print(f"Failed to download included file: {include_path}")

            if file_format in ["gltf", "glb"]:
                bpy.ops.import_scene.gltf(filepath=main_file_path)
            elif file_format == "fbx":
                bpy.ops.import_scene.fbx(filepath=main_file_path)
            elif file_format == "obj":
                bpy.ops.import_scene.obj(filepath=main_file_path)
            elif file_format == "blend":
                with bpy.data.libraries.load(main_file_path, link=False) as (data_from, data_to):
                    data_to.objects = data_from.objects

                for obj in data_to.objects:
                    if obj is not None:
                        bpy.context.collection.objects.link(obj)
            else:
                return {"error": f"Unsupported model format: {file_format}"}

            imported_objects = [obj.name for obj in bpy.context.selected_objects]

            return {
                "success": True,
                "message": f"Model {asset_id} imported successfully",
                "imported_objects": imported_objects,
            }
        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": f"Failed to import model: {exc}"}
        finally:
            with suppress(Exception):
                shutil.rmtree(temp_dir)


__all__ = ["PolyhavenMixin"]
