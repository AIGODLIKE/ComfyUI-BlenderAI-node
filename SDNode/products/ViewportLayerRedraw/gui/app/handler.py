import bpy
import OpenImageIO as oiio
from copy import deepcopy
from typing import Any, Dict
from pathlib import Path


class LayerPanelHandler:
    @staticmethod
    def create_layer(config: Dict[str, Any]):
        ori_config = config
        config = deepcopy(config)
        me = bpy.data.meshes.new("CanvasLayer")
        pixel_size = config["pixel_size"]
        physical_size = config["physical_size"]
        physical_size[:] = [physical_size[0] / 100, physical_size[1] / 100]
        dpi = config["dpi"]
        # 创建mesh顶点
        vertices = [
            [0, 0, 0],
            [physical_size[0], 0, 0],
            [0, 0, physical_size[1]],
            [physical_size[0], 0, physical_size[1]],
        ]
        faces = [[0, 1, 3, 2]]
        me.from_pydata(vertices, [], faces)
        me.uv_layers.new()
        ob = bpy.data.objects.new("CanvasLayer", me)
        bpy.context.scene.collection.objects.link(ob)
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        ob.is_sdn_canvas_layer = True
        ob["SDN_LAYER_CONFIG"] = ori_config

    @staticmethod
    def create_layer_from_image(image_path: str):
        if not Path(image_path).exists():
            return


def register():
    pass


def unregister():
    pass
