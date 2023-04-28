import bpy
from pathlib import Path
from ..utils import logger

SELECTED_COLLECTIONS = []

def gen_mask(self):
    mode = self.mode
    mask_path = self.image
    if not Path(mask_path).parent.exists():
        return
    logger.debug("Gen Mask")
    r = bpy.context.scene.render
    oldsetting = (r.filepath, r.image_settings.color_mode, r.image_settings.compression,
                    bpy.context.scene.view_settings.view_transform)
    
    if mode in {"Collection", "Object"}:
        bpy.context.view_layer.use_pass_cryptomatte_object = True
        if mode == "Collection":
            # 集合遮罩
            area = [area for area in bpy.context.screen.areas if area.type == "OUTLINER"][0]
            with bpy.context.temp_override(area=area, region=area.regions[-1]):
                bpy.ops.sdn.get_sel_col()

            selected_objects = []
            for colname in SELECTED_COLLECTIONS:
                selected_objects += bpy.data.collections[colname].all_objects[:]
            selected_objects = set(selected_objects)
        else:
            # 多选物体遮罩
            selected_objects = bpy.context.selected_objects
        # 设置节点
        bpy.context.scene.use_nodes = True
        nt = bpy.context.scene.node_tree
        crypt = nt.nodes.new("CompositorNodeCryptomatteV2")
        crypt.matte_id = ",".join([o.name for o in selected_objects])

        inv = nt.nodes.new("CompositorNodeInvert")
        inv.invert_rgb = True
        inv.inputs["Fac"].default_value = 0
        nt.links.new(crypt.outputs['Matte'], inv.inputs['Color'])

        cmp = None
        for node in nt.nodes:
            if node.type != 'COMPOSITE':
                continue
            cmp = node

        if not cmp:
            logger.error("未找到合成节点")
            return
        # 后续恢复
        old_socket = cmp.inputs['Image'].links[0].from_socket
        nt.links.new(inv.outputs['Color'], cmp.inputs['Image'])
        # 渲染遮罩
        r.filepath = mask_path
        bpy.ops.render.render(write_still=True)
        # 移除新建节点
        nt.nodes.remove(crypt)
        nt.nodes.remove(inv)
        # 恢复链接
        if old_socket:
            nt.links.new(old_socket, cmp.inputs['Image'])
            
    elif mode == "Grease Pencil":
        hide_map = {}
        for o in bpy.context.scene.objects:
            hide_map[o.name] = o.hide_render
            o.hide_render = True
        # 开启透明
        bpy.context.scene.render.film_transparent = True


        r.filepath = mask_path
        r.image_settings.color_mode = "RGB"
        r.image_settings.compression = 100
        try:
            bpy.context.scene.view_settings.view_transform = 'Standard'
        except BaseException:
            pass

        for gpo in [self.gp]:
            gpo.hide_render = hide_map[gpo.name]
            for l in gpo.data.layers:
                l.use_lights = False
                l.opacity = 1
        bpy.ops.render.render(write_still=True)

        for o in bpy.context.scene.objects:
            o.hide_render = hide_map.get(o.name, o.hide_render)
            
    r.filepath, r.image_settings.color_mode, r.image_settings.compression, bpy.context.scene.view_settings.view_transform = oldsetting