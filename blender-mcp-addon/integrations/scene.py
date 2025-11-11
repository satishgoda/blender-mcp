"""Scene related helpers and generic operations."""

from __future__ import annotations

import io
import traceback
from contextlib import redirect_stdout
from typing import Any, Dict

import bpy
import mathutils


class SceneMixin:
    """Provide common Blender scene utilities for the MCP server."""

    def get_scene_info(self) -> Dict[str, Any]:
        """Return lightweight information about the current scene."""
        try:
            print("Getting scene info...")
            scene_info = {
                "name": bpy.context.scene.name,
                "object_count": len(bpy.context.scene.objects),
                "objects": [],
                "materials_count": len(bpy.data.materials),
            }

            for index, obj in enumerate(bpy.context.scene.objects):
                if index >= 10:
                    break

                obj_info = {
                    "name": obj.name,
                    "type": obj.type,
                    "location": [
                        round(float(obj.location.x), 2),
                        round(float(obj.location.y), 2),
                        round(float(obj.location.z), 2),
                    ],
                }
                scene_info["objects"].append(obj_info)

            print(f"Scene info collected: {len(scene_info['objects'])} objects")
            return scene_info
        except Exception as exc:  # pragma: no cover - Blender environment only
            print(f"Error in get_scene_info: {exc}")
            traceback.print_exc()
            return {"error": str(exc)}

    @staticmethod
    def _get_aabb(obj):  # noqa: D401 - Blender specific helper
        """Return the world-space AABB for a mesh object."""
        if obj.type != "MESH":
            raise TypeError("Object must be a mesh")

        local_bbox_corners = [mathutils.Vector(corner) for corner in obj.bound_box]
        world_bbox_corners = [obj.matrix_world @ corner for corner in local_bbox_corners]

        min_corner = mathutils.Vector(map(min, zip(*world_bbox_corners)))
        max_corner = mathutils.Vector(map(max, zip(*world_bbox_corners)))

        return [[*min_corner], [*max_corner]]

    def get_object_info(self, name: str) -> Dict[str, Any]:
        """Return detailed information about a specific object."""
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")

        obj_info = {
            "name": obj.name,
            "type": obj.type,
            "location": [obj.location.x, obj.location.y, obj.location.z],
            "rotation": [
                obj.rotation_euler.x,
                obj.rotation_euler.y,
                obj.rotation_euler.z,
            ],
            "scale": [obj.scale.x, obj.scale.y, obj.scale.z],
            "visible": obj.visible_get(),
            "materials": [],
        }

        if obj.type == "MESH":
            obj_info["world_bounding_box"] = self._get_aabb(obj)

        for slot in obj.material_slots:
            if slot.material:
                obj_info["materials"].append(slot.material.name)

        if obj.type == "MESH" and obj.data:
            mesh = obj.data
            obj_info["mesh"] = {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
            }

        return obj_info

    def get_viewport_screenshot(self, max_size: int = 800, filepath: str | None = None, format: str = "png") -> Dict[str, Any]:
        """Capture a screenshot for the current viewport."""
        try:
            if not filepath:
                return {"error": "No filepath provided"}

            area = None
            for area_candidate in bpy.context.screen.areas:
                if area_candidate.type == "VIEW_3D":
                    area = area_candidate
                    break

            if not area:
                return {"error": "No 3D viewport found"}

            with bpy.context.temp_override(area=area):
                bpy.ops.screen.screenshot_area(filepath=filepath)

            img = bpy.data.images.load(filepath)
            width, height = img.size

            if max(width, height) > max_size:
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img.scale(new_width, new_height)
                img.file_format = format.upper()
                img.save()
                width, height = new_width, new_height

            bpy.data.images.remove(img)

            return {
                "success": True,
                "width": width,
                "height": height,
                "filepath": filepath,
            }

        except Exception as exc:  # pragma: no cover - Blender environment only
            return {"error": str(exc)}

    def execute_code(self, code: str) -> Dict[str, Any]:
        """Execute arbitrary Blender Python code with stdout capture."""
        try:
            namespace = {"bpy": bpy}
            text_name = self._store_executed_code(code)
            capture_buffer = io.StringIO()

            with redirect_stdout(capture_buffer):
                exec(code, namespace)

            captured_output = capture_buffer.getvalue()
            return {"executed": True, "result": captured_output, "text_name": text_name}
        except Exception as exc:
            raise Exception(f"Code execution error: {exc}") from exc

    @staticmethod
    def _store_executed_code(code: str) -> str:
        """Persist executed code blocks for later auditing."""
        text_name = "MCP Delegated Code"
        text_block = bpy.data.texts.get(text_name)

        if text_block is None:
            text_block = bpy.data.texts.new(name=text_name)

        if text_block.lines:
            last_index = len(text_block.lines) - 1
            last_char = len(text_block.lines[-1].body)
            text_block.cursor_set(line=last_index, character=last_char)

        separator = "\n########\n"
        snippet = code if code.endswith("\n") else f"{code}\n"

        if text_block.lines and any(line.body.strip() for line in text_block.lines):
            text_block.write(separator)

        text_block.write(snippet)

        try:
            screen = bpy.context.screen
            if screen is not None:
                for area in screen.areas:
                    if area.type == "TEXT_EDITOR":
                        for space in area.spaces:
                            if space.type == "TEXT_EDITOR":
                                space.text = text_block
                                break
        except Exception:  # pragma: no cover - Blender environment only
            pass

        return text_block.name


__all__ = ["SceneMixin"]
