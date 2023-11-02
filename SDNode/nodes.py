from __future__ import annotations
import bpy
import random
import time
import os
import re
import json
import math
import textwrap
import pickle
import urllib.request
import urllib.parse
from numpy import clip
from copy import deepcopy
from hashlib import md5
from math import ceil
from typing import Any
from pathlib import Path
from random import random as rand
from functools import partial, lru_cache
from mathutils import Vector, Matrix
from bpy.types import Context, Event
from .utils import gen_mask, get_tree, SELECTED_COLLECTIONS
from ..utils import logger, update_screen, Icon, _T
from ..datas import ENUM_ITEMS_CACHE, IMG_SUFFIX
from ..preference import get_pref
from ..timer import Timer
from ..translations import ctxt, get_reg_name, get_ori_name
from .manager import get_url, Task, WITH_PROXY

try:
    from requests import get as ______
except BaseException:
    from ..utils import PkgInstaller
    PkgInstaller.try_install("requests")

NODES_POLL = {}
Icon.reg_none(Path(__file__).parent / "NONE.png")
PREVICONPATH = {}
PATH_CFG = Path(__file__).parent / "PATH_CFG.json"
SOCKET_HASH_MAP = {  # {HASH: METATYPE}
    "INT": "INT",
    "FLOAT": "FLOAT",
    "STRING": "STRING",
    "BOOLEAN": "BOOLEAN"
}


name2path = {
    "CheckpointLoader": {"ckpt_name": "checkpoints"},
    "CheckpointLoaderSimple": {"ckpt_name": "checkpoints"},
    "VAELoader": {"vae_name": "vae"},
    "LoraLoader": {"lora_name": "loras"},
    "CLIPLoader": {"clip_name": "clip"},
    "ControlNetLoader": {"control_net_name": "controlnet"},
    "DiffControlNetLoader": {"control_net_name": "controlnet"},
    "StyleModelLoader": {"style_model_name": "style_models"},
    "CLIPVisionLoader": {"clip_name": "clip_vision"},
    "unCLIPCheckpointLoader": {"ckpt_name": "checkpoints"},
    "UpscaleModelLoader": {"model_name": "upscale_models"},
    "GLIGENLoader": {"gligen_name": "gligen"}
}


def ui_scale():
    return bpy.context.preferences.system.ui_scale


def get_node_center(node: bpy.types.Node) -> Vector:
    node_size = node.dimensions / ui_scale()
    node_center = node.location + node_size / 2 * Vector((1, -1))
    return node_center


def get_nearest_nodes(nodes: list[bpy.types.Node], mouse_pos: Vector):
    find_nodes = []
    for nd in nodes:
        if nd.type in {"FRAME", "REROUTE"}:
            continue
        v = mouse_pos - get_node_center(nd)
        find_nodes.append((nd, v.length))
    find_nodes.sort(key=lambda a: a[1])
    return find_nodes


def loc_to_region2d(vec):
    vec = vec * ui_scale()
    return Vector(bpy.context.region.view2d.view_to_region(vec.x, vec.y, clip=False))


def try_get_path_cfg():
    if not PATH_CFG.exists():
        return
    try:
        d = json.loads(PATH_CFG.read_text())
        return d
    except Exception as e:
        logger.warn(_T("icon path load error") + str(e))

    try:
        d = json.loads(PATH_CFG.read_text(encoding="gbk"))
        return d
    except Exception as e:
        logger.warn(_T("icon path load error") + str(e))


def get_icon_path(nname):

    {'controlnet': [['D:\\BaiduNetdiskDownload\\AI\\ComfyUI\\models\\controlnet',
                     'D:\\BaiduNetdiskDownload\\AI\\ComfyUI\\models\\t2i_adapter'], ['.bin', '.safetensors', '.pth', '.pt', '.ckpt']],
     'upscale_models': [['D:\\BaiduNetdiskDownload\\AI\\ComfyUI\\models\\upscale_models'], ['.bin', '.safetensors', '.pth', '.pt', '.ckpt']]}

    if not PREVICONPATH:
        if not (d := try_get_path_cfg()):
            return {}
        # prev_dir = Path(get_pref().model_path) / "models"
        # {
        #     "ckpt_name": prev_dir / "checkpoints",
        # }
        for class_type in name2path:
            path_list = {}
            PREVICONPATH[class_type] = path_list
            for name in name2path[class_type]:
                reg_name = get_reg_name(name)
                path_list[reg_name] = d[name2path[class_type][name]][0]
    return PREVICONPATH.get(nname, {})


def calc_hash_type(stype):
    from .blueprints import is_bool_list, is_number_list, is_all_str_list
    if is_bool_list(stype):
        hash_type = md5(f"{{True, False}}".encode()).hexdigest()
    elif not is_all_str_list(stype):
        hash_type = md5(",".join([str(i) for i in stype]).encode()).hexdigest()
    else:
        try:
            hash_type = md5(",".join(stype).encode()).hexdigest()
        except TypeError:
            winfo = str(stype)
            if len(winfo) > 100:
                winfo = winfo[:40] + "......"
            raise TypeError(f"{_T('Non-Standard Enum')} -> {winfo}")
    return hash_type


class NodeBase(bpy.types.Node):
    bl_width_min = 200.0
    bl_width_max = 2000.0
    sdn_order: bpy.props.IntProperty(default=-1)
    id: bpy.props.StringProperty(default="-1")
    builtin__stat__: bpy.props.StringProperty(subtype="BYTE_STRING")  # ori name: True/False
    pool = set()
    class_type: str

    def get_tree(self):
        from .tree import CFNodeTree
        tree: CFNodeTree = self.id_data
        return tree

    def get_blueprints(self):
        from .blueprints import get_blueprints
        return get_blueprints(self.class_type)

    def get_ctxt(self) -> str:
        from ..translations.translation import get_ctxt
        return get_ctxt(self.class_type)

    def query_stat(self, name):
        if not self.builtin__stat__:
            return None
        stat = pickle.loads(self.builtin__stat__)
        name = get_ori_name(name)
        return stat.get(name, None)

    def is_base_type(self, name):
        """
        判断是不是基本类型, 目前通过 拥有注册属性名判断
        """
        reg_name = get_reg_name(name)
        return hasattr(self, reg_name)

    def set_stat(self, name, value):
        if not self.builtin__stat__:
            self.builtin__stat__ = pickle.dumps({})
        stat = pickle.loads(self.builtin__stat__)
        stat[name] = value
        self.builtin__stat__ = pickle.dumps(stat)

    def switch_socket(self, name, value):
        self.set_stat(name, value)
        if value:
            socket_type = NodeParser.SOCKET_TYPE[self.class_type].get(name, "NONE")
            inp = self.inputs.new(socket_type, name)
            inp.slot_index = len(self.inputs) - 1
            return inp
        elif inp := self.inputs.get(name):
            self.inputs.remove(inp)

    @lru_cache
    def get_meta(self, inp_name) -> list:
        """
        判断`属性名`是否存在于`元数据`中(可能是socket也可能是widgets)
        """
        if not hasattr(self, "__metadata__"):
            logger.warn(f"node {self.name} has no metadata")
            return []
        inputs = self.__metadata__.get("input", {})
        if inp_name in (r := inputs.get("required", {})):
            return r[inp_name]
        if inp_name in (o := inputs.get("optional", {})):
            return o[inp_name]
        return []

    def calc_slot_index(self):
        for i, inp in enumerate(self.inputs):
            inp.slot_index = i
        for i, out in enumerate(self.outputs):
            out.slot_index = i

    def unique_id(self):
        for i in range(3, 99999):
            i = str(i)
            if i not in self.pool:
                self.pool.add(i)
                return i

    def free(self):
        self.pool.discard(self.id)

    def copy(self, node):
        self.apply_unique_id()
        if hasattr(self, "sync_rand"):
            self.sync_rand = False
        if self.class_type == "材质图":
            name = node.name
            self.get_tree().safe_remove_nodes([node])

            def f(self, name):
                self.name = name
            Timer.put((f, self, name))

    def apply_unique_id(self):
        self.id = self.unique_id()
        return self.id

    def draw_label(self):
        ntype = _T(self.bl_idname)
        if self.bl_idname in self.name:
            return self.name.replace(self.bl_idname, ntype)
        if ntype in self.name:
            return self.name
        if self.name != ntype:
            return f"{self.name}[{ntype}]"
        return ntype

    def update(self):
        if not self.is_registered_node_type():
            return
        self.remove_multi_link()
        self.remove_invalid_link()
        self.primitive_check()

    def remove_multi_link(self):
        for inp in self.inputs:
            if len(inp.links) <= 1:
                continue
            for l in inp.links[1:]:
                if not hasattr(bpy.context.space_data, "edit_tree"):
                    continue
                bpy.context.space_data.edit_tree.links.remove(l)

    def remove_invalid_link(self):
        for inp in self.inputs:
            if not inp.is_linked:
                continue
            lfrom = self.get_from_link(inp)
            for l in inp.links:
                fs = l.from_socket
                if lfrom:
                    fs = lfrom.from_socket
                ts = l.to_socket
                if fs.bl_idname == "*" and SOCKET_HASH_MAP.get(ts.bl_idname) in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN"}:
                    continue
                if fs.bl_idname == ts.bl_idname:
                    continue
                # from端为转接点
                # if not lfrom and l.from_node.bl_idname == "NodeReroute":
                #     continue
                # if fs.bl_idname == "NodeReroute":
                #     continue
                if not hasattr(bpy.context.space_data, "edit_tree"):
                    continue

                bpy.context.space_data.edit_tree.links.remove(l)

    def primitive_check(self):
        if not bpy.context.space_data:
            return
        if bpy.context.space_data.type != "NODE_EDITOR":
            return
        tree = self.get_tree()
        if tree.bl_idname != "CFNodeTree":
            return
        # 对PrimitiveNode类型的输出进行限制
        if self.class_type != "PrimitiveNode":
            return
        if not self.outputs:
            return
        out = self.outputs[0]
        for l in out.links:
            if l.to_node.bl_idname != "NodeReroute":
                continue
            tree.links.remove(l)

        if not out.is_linked:
            return
        if not out.links:
            return
        self.prop = out.links[0].to_socket.name
        to_meta = [None]
        for link in out.links:
            if not link.to_node.is_registered_node_type():
                continue
            to_meta = link.to_node.get_meta(self.prop)
            break

        def meta_equal(meta1, meta2):
            if not meta1 or not meta2:
                return False
            if isinstance(meta1[0], list) or isinstance(meta2[0], list):
                return meta1[0] == meta2[0]
            if meta1[0] != meta2[0]:
                return False
            for k in meta1[1]:
                if k == "default":
                    continue
                if meta1[1][k] != meta2[1][k]:
                    return False
            return True
        for l in out.links:
            if l.to_node.is_registered_node_type() and meta_equal(to_meta, l.to_node.get_meta(l.to_socket.name)):
                continue
            tree.links.remove(l)

    def get_from_link(self, socket: bpy.types.NodeSocket):
        if not socket.is_linked:
            return
        if not socket.links:
            return
        link = socket.links[0]
        while True:
            node = link.from_node
            if node.bl_idname == "NodeReroute":
                if node.inputs[0].is_linked:
                    link = node.inputs[0].links[0]
                else:
                    return
            else:
                return link

    def serialize_pre(self):
        bp = self.get_blueprints()
        return bp.serialize_pre(self)

    def serialize(self, execute=True):
        """
        gen prompt
        """
        bp = self.get_blueprints()
        return bp.serialize(self, execute)

    def load(self, data, with_id=True):
        bp = self.get_blueprints()
        return bp.load(self, data, with_id)

    def dump(self, selected_only=False):
        bp = self.get_blueprints()
        return bp.dump(self, selected_only)

    def post_fn(self, task, result):
        bp = self.get_blueprints()
        bp.post_fn(self, task, result)

    def pre_fn(self):
        bp = self.get_blueprints()
        bp.pre_fn(self)

    def make_serialze(self):
        bp = self.get_blueprints()
        return bp.make_serialze(self)


class SocketBase(bpy.types.NodeSocket):
    allowLink = {"*", }

    def linkLimitCheck(self, context):
        self.allowLink.add(self.bl_label)
        # 连接限制
        for link in list(self.links):
            if link.from_node.bl_label in self.allowLink:
                continue
            logger.warn(f"{_T('Remove Link')}:{link.from_node.bl_label}",)
            context.space_data.edit_tree.links.remove(link)

    color: bpy.props.FloatVectorProperty(size=4, default=(1, 0, 0, 1))

    def draw_color(self, context, node):
        return self.color

    if bpy.app.version >= (4, 0):
        draw_color_simple_ = (1, 0, 0, 1)

        @classmethod
        def draw_color_simple(cls):
            return cls.draw_color_simple_


class Ops_Swith_Socket(bpy.types.Operator):
    bl_idname = "sdn.switch_socket"
    bl_label = "切换Socket/属性"
    socket_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()
    action: bpy.props.StringProperty(default="")

    def execute(self, context):
        tree = get_tree()
        node: NodeBase = None
        socket_name = get_ori_name(self.socket_name)
        if not (node := tree.nodes.get(self.node_name)):
            return {"FINISHED"}
        match self.action:
            case "ToSocket":
                node.switch_socket(socket_name, True)
            case "ToProp":
                node.switch_socket(socket_name, False)
        self.action = ""
        return {"FINISHED"}

    def draw_prop(layout, node, prop, row=True, swlink=True) -> bpy.types.UILayout:
        l = layout
        if swlink:
            l = layout.row(align=True)
            op = l.operator(Ops_Swith_Socket.bl_idname, text="", icon="LINKED")
            op.node_name = node.name
            op.socket_name = prop
            op.action = "ToSocket"
        if row:
            l = l.row(align=True)
        else:
            l = l.column(align=True)
        return l


class Ops_Add_SaveImage(bpy.types.Operator):
    bl_idname = "sdn.add_saveimage"
    bl_label = "添加保存图片节点"
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        tree = get_tree()
        node: NodeBase = None
        if not (node := tree.nodes.get(self.node_name)):
            return {"FINISHED"}
        inp = node.inputs[0]
        if not inp.is_linked:
            return {"FINISHED"}
        save_image_node = tree.nodes.new("存储")
        save_image_node.location = node.location
        save_image_node.location.y += 200
        tree.links.new(inp.links[0].from_socket, save_image_node.inputs[0])
        return {"FINISHED"}


class Ops_Active_Tex(bpy.types.Operator):
    bl_idname = "sdn.act_tex"
    bl_label = "选择纹理"
    img_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()

    def execute(self, context):
        if not (img := bpy.data.images.get(self.img_name)):
            return {"FINISHED"}
        tree = get_tree()
        if not (node := tree.nodes.get(self.node_name)):
            return {"FINISHED"}
        node.image = None if img == node.image else img
        return {"FINISHED"}


class Ops_Link_Mask(bpy.types.Operator):
    bl_idname = "sdn.link_mask"
    bl_label = "链接遮照"
    bl_options = {"REGISTER", "UNDO"}
    action: bpy.props.StringProperty(default="")
    cam_name: bpy.props.StringProperty(default="")
    node_name: bpy.props.StringProperty(default="")
    kmi: bpy.types.KeyMapItem = None
    kmis: list[tuple[bpy.types.KeyMap, bpy.types.KeyMapItem]] = []
    properties = {}
    shotcut = {
        "idname": bl_idname,
        "type": "F",
        "value": "PRESS",
        "shift": False,
        "ctrl": False,
        "alt": False,
    }

    def get_nearest_node(self, context: bpy.types.Context, filter=lambda _: True) -> bpy.types.Node:
        mouse_pos = context.space_data.cursor_location
        for node in get_nearest_nodes(context.space_data.edit_tree.nodes, mouse_pos):
            if not filter(node[0]):
                continue
            return node[0]
        return None

    @classmethod
    def poll(cls, context):
        from .tree import TREE_TYPE
        return context.space_data.tree_type == TREE_TYPE

    def invoke(self, context: Context, event: Event):
        if self.action == "OnlyFocus":
            tree = context.space_data.edit_tree
            to_node = tree.nodes.get(self.node_name)
            if cam := bpy.data.objects.get(self.cam_name):
                self.validate_cam_cache(cam, to_node)
            else:
                cam = self.create_cam()
                to_node.cam = cam
                bpy.ops.sdn.mask(action="add", node_name=to_node.name, cam_name=cam.name)
            self.focus_cam(cam)
            self.active_cam_gp(cam)
            self.action = ""
            self.node_name = ""
            return {"FINISHED"}

        self.from_node: bpy.types.Node = None
        self.to_node: bpy.types.Node = None

        def prev_filter(n):
            return hasattr(n, "prev")
        self.from_node = self.get_nearest_node(context, filter=prev_filter)
        if not self.from_node:
            self.report({"ERROR"}, "No ImageNode Found!")
            return {"FINISHED"}
        bpy.context.window_manager.modal_handler_add(self)
        import gpu
        import gpu_extras
        if bpy.app.version >= (4, 0):
            shader_color = gpu.shader.from_builtin("UNIFORM_COLOR")
        else:
            shader_color = gpu.shader.from_builtin("2D_UNIFORM_COLOR")
        shader_line = gpu.shader.from_builtin("POLYLINE_SMOOTH_COLOR")
        shader_line.uniform_float("viewportSize", gpu.state.viewport_get()[2:4])
        shader_line.uniform_float("lineSmooth", True)

        def draw_fill_circle(pos, r=15, col=(1.0, 1.0, 1.0, .75), resolution=32):
            fac = 2.0 * math.pi / resolution  # pre calc
            vpos = ((pos[0], pos[1]), *((r * math.cos(i * fac) + pos[0], r * math.sin(i * fac) + pos[1]) for i in range(resolution + 1)))
            gpu.state.blend_set("ALPHA")
            shader_color.bind()
            shader_color.uniform_float("color", col)
            gpu_extras.batch.batch_for_shader(shader_color, "TRI_FAN", {"pos": vpos}).draw(shader_color)

        def draw_line(pos1, pos2, width=10, col1=(1.0, 1.0, 1.0, .75), col2=(1.0, 1.0, 1.0, .75)):
            gpu.state.blend_set("ALPHA")
            shader_line.bind()
            shader_line.uniform_float("lineWidth", width)
            content = {"pos": (pos1, pos2), "color": (col1, col2)}
            gpu_extras.batch.batch_for_shader(shader_line, "LINE_STRIP", content).draw(shader_line)

        def draw(self, context):
            if not self.from_node:
                return
            endpos = get_node_center(self.to_node) if self.to_node else context.space_data.cursor_location
            p1 = loc_to_region2d(get_node_center(self.from_node))
            p2 = loc_to_region2d(endpos)
            draw_line(p1, p2)
            draw_fill_circle(p1)
            if self.to_node:
                draw_fill_circle(p2)

        self.handle = bpy.types.SpaceNodeEditor.draw_handler_add(draw, (self, context), 'WINDOW', 'POST_PIXEL')
        return {"RUNNING_MODAL"}

    def modal(self, context: Context, event: Event):
        context.area.tag_redraw()

        if not context.space_data.edit_tree:
            self.exit()
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            def mask_filter(n: bpy.types.Node):
                return n.bl_idname == "Mask"
            n = self.get_nearest_node(context, filter=mask_filter)
            if n != self.from_node:
                self.to_node = n
        elif event.type == Ops_Link_Mask.kmi.type and event.value == "RELEASE":
            self.exec()
            self.exit()
            return {"FINISHED"}
        else:
            return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def exec(self):
        if not self.from_node:
            self.report({"ERROR"}, "No ImageNode Found!")
            return
        if not self.to_node:
            self.report({"ERROR"}, "No MaskNode Found!")
            return
        print(f"{self.from_node.name} -> {self.to_node.name}")
        if not (img := self.from_node.prev):
            self.report({"ERROR"}, "No Image Found!")
            return
        self.to_node.mode = "Focus"
        if not (cam := self.to_node.cam):
            cam = self.create_cam()
            self.to_node.cam = cam
        camdata = cam.data
        if not camdata.background_images:
            bg = camdata.background_images.new()
        bg = camdata.background_images[0]
        bg.alpha = 1
        bg.image = img
        bg.show_background_image = True
        self.validate_cam_cache(cam, self.to_node)
        self.focus_cam(cam)
        self.active_cam_gp(cam)

    def exit(self):
        if not self.handle:
            return
        bpy.types.SpaceNodeEditor.draw_handler_remove(self.handle, "WINDOW")
        self.handle = None

    def create_cam(self) -> bpy.types.Object:
        camdata = bpy.data.cameras.new("SDN_Mask_Focus")
        cam = bpy.data.objects.new(name=camdata.name, object_data=camdata)
        cam.matrix_world = Matrix(((0.7071, -0.5, 0.5, 5.0),
                                   (0.7071, 0.5, -0.5, -5.0),
                                   (0, 0.7071, 0.7071, 5.0),
                                   (0.0, 0.0, 0.0, 1.0)))
        bpy.context.scene.collection.objects.link(cam)
        camdata.show_background_images = True
        return cam

    def validate_cam_cache(self, cam, node):
        gp = cam.get("SD_Mask", None)
        if isinstance(gp, list):
            gp = [o for o in gp if o is not None]
            cam["SD_Mask"] = gp
        if not gp:
            cam.pop("SD_Mask", None)
            bpy.ops.sdn.mask(action="add", node_name=node.name, cam_name=cam.name)

    def active_cam_gp(self, cam):
        gp = cam.get("SD_Mask")
        if isinstance(gp, list):
            gp = gp[0]
        if gp is None:
            return
        # toggle to draw mask
        bpy.context.view_layer.objects.active = gp
        bpy.ops.object.mode_set(mode="PAINT_GPENCIL")

    def focus_cam(self, cam):
        bpy.context.scene.camera = cam
        for node in bpy.context.space_data.edit_tree.nodes:
            if node.bl_idname != "Mask":
                continue
            if not node.cam:
                continue
            gp = node.cam.get("SD_Mask", [])

            if not isinstance(gp, list):
                gp.hide_set(cam != node.cam)
                continue
            for i in gp:
                if not i:
                    continue
                i.hide_set(cam != node.cam)
        for area in bpy.context.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.spaces[0].region_3d.view_perspective = "CAMERA"
            area.spaces[0].overlay.show_overlays = True

    @classmethod
    def reg(cls):
        # km = wm.keyconfigs.addon.keymaps.new(name = '3D View Generic', space_type = 'VIEW_3D')
        # kmi = km.keymap_items.new(isolate_select.bl_idname, 'Q', 'PRESS')
        # addon_keymaps.append((km, kmi))
        wm = bpy.context.window_manager
        km = wm.keyconfigs.addon.keymaps.new(name="Node Editor", space_type="NODE_EDITOR")
        cls.kmi = km.keymap_items.new(**cls.shotcut)
        for k, v in cls.properties.items():
            setattr(cls.kmi.properties, k, v)
        cls.kmis.append((km, cls.kmi))

    @classmethod
    def unreg(cls):
        for km, kmi in cls.kmis:
            km.keymap_items.remove(kmi)
        cls.kmis.clear()


class Set_Render_Res(bpy.types.Operator):
    bl_idname = "sdn.set_render_res"
    bl_label = ""
    bl_translation_context = ctxt
    node_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        node = bpy.context.space_data.edit_tree.nodes.get(self.node_name)
        if not node or not node.prev:
            return {"FINISHED"}
        bpy.context.scene.render.resolution_x = node.prev.size[0]
        bpy.context.scene.render.resolution_y = node.prev.size[1]
        bpy.context.scene.render.resolution_percentage = 100
        return {'FINISHED'}


class GetSelCol(bpy.types.Operator):
    bl_idname = "sdn.get_sel_col"
    bl_label = ""
    bl_translation_context = ctxt

    def execute(self, context):
        SELECTED_COLLECTIONS.clear()
        for item in context.selected_ids:
            if item.bl_rna.identifier == "Collection":
                SELECTED_COLLECTIONS.append(item.name)
        return {'FINISHED'}


class NodeParser:
    CACHED_OBJECT_INFO = {}
    SOCKET_TYPE = {}  # NodeType: {PropName: SocketType}
    OBJECT_INFO_REQ = None
    DIFF_PATH = Path(__file__).parent / "diff_object_info.json"
    PATH = Path(__file__).parent / "object_info.json"
    INTERNAL_PATH = Path(__file__).parent / "object_info_internal.json"

    def __init__(self) -> None:
        self.ori_object_info = {}
        self.object_info = {}
        self.diff_object_info = {}
        self.diff = False

    def load_internal(self):
        self.object_info["PrimitiveNode"] = {
            "input": {"required": {}},
            "output": ["*"],
            "output_is_list": [False],
            "output_name": [
                "Output"
            ],
            "name": "PrimitiveNode",
            "display_name": "Primitive",
            "description": "",
            "category": "utils",
            "output_node": False
        }
        self.object_info["Note"] = {
            "input": {"required": {
                "text": [
                    "STRING",
                    {
                        "multiline": True
                    }
                ],
            }},
            "output": ["*"],
            "output_is_list": [False],
            "output_name": [
                "Output"
            ],
            "name": "Note",
            "display_name": "Note",
            "description": "",
            "category": "utils",
            "output_node": False
        }

    def fetch_object(self):
        self.ori_object_info.clear()
        if self.INTERNAL_PATH.exists():
            self.ori_object_info.update(json.load(self.INTERNAL_PATH.open("r")))
        if self.PATH.exists():
            self.ori_object_info.update(json.load(self.PATH.open("r")))
        from .manager import TaskManager, FakeServer
        if TaskManager.server != FakeServer._instance:
            self._fetch_object_from_server()
        return self.ori_object_info

    def _fetch_object_from_server(self):
        try:
            import requests
            from urllib3.util import Timeout
            timeout = Timeout(connect=0.1, read=2)
            if WITH_PROXY:
                req = requests.get(f"{get_url()}/object_info", timeout=timeout)
            else:
                req = requests.get(f"{get_url()}/object_info", proxies={"http": None, "https": None}, timeout=timeout)
            if req.status_code == 200:
                cur_object_info = req.json()
                self.ori_object_info.update(cur_object_info)
                js = json.dumps(self.ori_object_info, ensure_ascii=False, indent=2)
                self.PATH.write_text(js)
                self.ori_object_info = cur_object_info
        except requests.exceptions.ConnectionError:
            logger.warn(_T("Server Launch Failed"))
        except ModuleNotFoundError:
            logger.error(f"Module: requests import error!")

    def find_diff(self):
        # 获取差异object_info
        if self.DIFF_PATH.exists():
            self.diff_object_info = json.load(self.DIFF_PATH.open("r"))
        for name in {"Note", "PrimitiveNode", "Cache Node"}:
            self.diff_object_info.pop(name, None)
        return self.diff_object_info

    def parse(self, diff=False):
        if diff:
            self.object_info = self.find_diff()
        else:
            logger.warn(_T("Parsing Node Start"))
            self.object_info = self.fetch_object()
            self.SOCKET_TYPE.clear()
            self.load_internal()
        # self.CACHED_OBJECT_INFO.update(deepcopy(self.ori_object_info))
        socket_clss = self._parse_sockets_clss()
        node_clss = self._parse_node_clss()
        nodetree_desc = self._get_nt_desc()
        if not diff:
            logger.warn(_T("Parsing Node Finished!"))
        return nodetree_desc, node_clss, socket_clss

    def _get_n_desc(self):
        from .blueprints import get_blueprints
        for name, desc in self.object_info.items():
            bp = get_blueprints(name)
            desc = bp.pre_filter(name, desc)
        _desc = {}

        def _parse(name, desc, _desc):
            for index, out_type in enumerate(desc.get("output", [])):
                desc["output"][index] = [out_type, out_type]
            output_name = desc.get("output_name", [])
            if isinstance(output_name, str):
                output_name = [output_name]
            for index, out_name in enumerate(output_name):
                if not out_name:
                    continue
                desc["output"][index][1] = out_name
            _desc[name] = desc
        for name in list(self.object_info.keys()):
            desc = self.object_info[name]
            try:
                _parse(name, desc, _desc)
            except Exception as e:
                logger.error(f"{_T('Parsing Failed')}: {name} -> {e}")
                self.object_info.pop(name)
        return _desc

    def _get_nt_desc(self):
        _desc = {}
        for name, desc in self.object_info.items():
            cpath = desc["category"].split("/")
            ncur = _desc
            while cpath:
                ccur = cpath.pop(0)
                if ccur not in ncur:
                    ncur[ccur] = {"items": [], "menus": {}}
                if not cpath:
                    ncur[ccur]["items"].append(name)
                else:
                    ncur = ncur[ccur]["menus"]
        return _desc

    def _get_socket_desc(self):
        _desc = {"*", }  # Enum/Int/Float/String/Bool 不需要socket

        def _parse(name, desc, _desc):
            for inp_channel in {"required", "optional"}:
                for inp, inp_desc in desc["input"].get(inp_channel, {}).items():
                    stype = inp_desc[0]
                    if isinstance(stype, list):
                        _desc.add("ENUM")
                        # 太长 不能注册为 socket type(<64)
                        hash_type = calc_hash_type(stype)
                        _desc.add(hash_type)
                        SOCKET_HASH_MAP[hash_type] = "ENUM"
                        self.SOCKET_TYPE[name][inp] = hash_type
                    else:
                        _desc.add(inp_desc[0])
                        self.SOCKET_TYPE[name][inp] = inp_desc[0]
            for out_type in desc["output"]:
                # _desc.add(out_type[0])
                stype = out_type[0]
                if isinstance(stype, list):
                    _desc.add("ENUM")
                    # 太长 不能注册为 socket type(<64)
                    hash_type = calc_hash_type(stype)
                    _desc.add(hash_type)
                    SOCKET_HASH_MAP[hash_type] = "ENUM"
                    # self.SOCKET_TYPE[name][inp] = hash_type
                else:
                    _desc.add(out_type[0])
                    # self.SOCKET_TYPE[name][inp] = inp_desc[0]
        for name in list(self.object_info.keys()):
            desc = self.object_info[name]
            self.SOCKET_TYPE[name] = {}
            try:
                _parse(name, desc, _desc)
            except Exception as e:
                logger.error(f"{_T('Parsing Failed')}: {name} -> {e}")
                self.object_info.pop(name)
        return _desc

    def _parse_sockets_clss(self):
        socket_clss = []
        sockets = self._get_socket_desc()
        for stype in sockets:
            if stype in {"ENUM", }:
                continue

            def draw(self, context, layout, node: NodeBase, text):
                if node.bl_idname == "NodeUndefined":
                    return
                prop = get_reg_name(self.name)
                if self.is_output or not hasattr(node, prop):
                    layout.label(text=self.name, text_ctxt=node.get_ctxt())
                    return
                row = layout.row(align=True)
                row.label(text=prop, text_ctxt=node.get_ctxt())
                op = row.operator(Ops_Swith_Socket.bl_idname, text="", icon="UNLINKED")
                op.node_name = node.name
                op.socket_name = self.name
                op.action = "ToProp"
                row.prop(node, prop, text="", text_ctxt=node.get_ctxt())
            rand_color = (rand()**0.5, rand()**0.5, rand()**0.5, 1)
            color = bpy.props.FloatVectorProperty(size=4, default=rand_color)
            __annotations__ = {"color": color,
                               "index": bpy.props.IntProperty(default=-1),
                               "slot_index": bpy.props.IntProperty(default=-1)}
            fields = {"draw": draw,
                      "bl_label": stype,
                      "__annotations__": __annotations__,
                      "draw_color_simple_": rand_color
                      }
            SocketDesc = type(stype, (SocketBase,), fields)
            socket_clss.append(SocketDesc)
        return socket_clss

    def _parse_node_clss(self):
        nodes_desc = self._get_n_desc()
        node_clss = []
        for nname, ndesc in nodes_desc.items():
            opt_types = ndesc["input"].get("optional", {})
            inp_types = {}
            for key, value in ndesc["input"].get("required", {}).items():
                inp_types[key] = value
                if key in {"seed", "noise_seed"}:
                    inp_types["control_after_generate"] = [["fixed", "increment", "decrement", "randomize"]]

            inp_types.update(opt_types)
            out_types = ndesc["output"]
            # 节点初始化

            def init(self: NodeBase, context):
                # logger.error("INIT")
                self.inputs.clear()
                self.outputs.clear()

                self.apply_unique_id()
                # self.use_custom_color = True
                # self.color = self.dcolor
                for index, inp_name in enumerate(self.inp_types):
                    inp = self.inp_types[inp_name]
                    if not inp:
                        logger.error(f"{_T('None Input')}: %s", inp_name)
                        continue
                    socket = inp[0]
                    if isinstance(inp[0], list):
                        # socket = "ENUM"
                        socket = calc_hash_type(inp[0])
                        continue
                    if socket in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN"}:
                        continue
                    # logger.warn(inp)
                    in1 = self.inputs.new(socket, get_reg_name(inp_name))
                    in1.display_shape = "DIAMOND_DOT"
                    # in1.link_limit = 0
                    in1.index = index
                for index, [out_type, out_name] in enumerate(self.out_types):
                    if out_type in {"ENUM", }:
                        continue
                    out = self.outputs.new(out_type, out_name)
                    out.display_shape = "DIAMOND_DOT"
                    # out.link_limit = 0
                    out.index = index
                self.calc_slot_index()

            def draw_buttons(self: NodeBase, context, layout: bpy.types.UILayout):
                for prop in self.__annotations__:
                    if self.query_stat(prop):
                        continue
                    if prop == "control_after_generate":
                        continue
                    l = layout
                    # 返回True 则不绘制
                    if self.get_blueprints().draw_button(self, context, l, prop):
                        continue
                    if self.is_base_type(prop) and get_ori_name(prop) in self.inp_types:
                        l = Ops_Swith_Socket.draw_prop(l, self, prop)
                    l.prop(self, prop, text=prop, text_ctxt=self.get_ctxt())

            def find_icon(nname, inp_name, item):
                prev_path_list = get_icon_path(nname).get(inp_name)
                if not prev_path_list:
                    return 0

                file_list = []
                for prev_path in prev_path_list:
                    pp = Path(prev_path)
                    if not pp.exists():
                        continue
                    # 直接搜索 prev_path_list + item文件名 + jpg/png后缀
                    for suffix in IMG_SUFFIX:
                        pimg = pp / Path(item).with_suffix(suffix).as_posix()
                        if not pimg.exists():
                            continue
                        return Icon.reg_icon(pimg.absolute())
                    for file in pp.iterdir():
                        file_list.append(file)
                item_prefix = Path(item).stem
                # file_list = [file for prev_path in prev_path_list for file in Path(prev_path).iterdir()]
                for file in file_list:
                    if (item not in file.stem) and (item_prefix not in file.stem):
                        continue
                    if file.suffix.lower() not in IMG_SUFFIX:
                        continue
                    # logger.info(f"🌟 Found Icon -> {file.name}")
                    return Icon.reg_icon(file.absolute())
                # logger.info(f"🌚 No Icon <- {file.name}")
                return Icon["NONE"]

            def validate_inp(inp):
                if not isinstance(inp, list):
                    return
                if len(inp) <= 1:
                    return
                if not isinstance(inp[1], dict):
                    return
                PARAMS = {"default", "min", "max", "step", "soft_min", "soft_max", "description", "subtype", "update", "options", "multiline"}
                # 排除掉不需要的属性
                for key in list(inp[1].keys()):
                    if key in PARAMS:
                        continue
                    inp[1].pop(key)

            properties = {}
            for inp_name in inp_types:
                reg_name = get_reg_name(inp_name)
                inp = inp_types[inp_name]
                if not inp:
                    logger.error(f"{_T('None Input')}: %s", inp)
                    continue
                proptype = inp[0]
                if isinstance(inp[0], list):
                    proptype = "ENUM"
                validate_inp(inp)
                if proptype not in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN"}:
                    continue
                if proptype == "ENUM":

                    def get_items(nname, inp_name, inp):
                        def wrap(self, context):
                            if nname not in ENUM_ITEMS_CACHE:
                                ENUM_ITEMS_CACHE[nname] = {}
                            if inp_name in ENUM_ITEMS_CACHE[nname]:
                                return ENUM_ITEMS_CACHE[nname][inp_name]
                            items = []
                            for item in inp[0]:
                                icon_id = find_icon(nname, inp_name, item)
                                if icon_id:
                                    ENUM_ITEMS_CACHE[nname][inp_name] = items
                                items.append((str(item), str(item), "", icon_id, len(items)))
                            return items
                        return wrap
                    prop = bpy.props.EnumProperty(items=get_items(nname, reg_name, inp))
                    # 判断可哈希

                    def is_all_hashable(some_list):
                        return all(hasattr(item, "__hash__") for item in some_list)
                    if is_all_hashable(inp[0]) and set(inp[0]) == {True, False}:
                        prop = bpy.props.BoolProperty()
                elif proptype == "INT":
                    # {'default': 20, 'min': 1, 'max': 10000}
                    inp[1]["max"] = min(int(inp[1].get("max", 9999999)), 2**31 - 1)
                    inp[1]["min"] = max(int(inp[1].get("min", -999999)), -2**31)
                    default = inp[1].get("default", 0)
                    if not default:
                        default = 0
                    inp[1]["default"] = int(default)
                    inp[1]["step"] = ceil(inp[1].get("step", 1))
                    prop = bpy.props.IntProperty(**inp[1])

                elif proptype == "FLOAT":
                    {'default': 8.0, 'min': 0.0, 'max': 100.0}
                    if len(inp) > 1:
                        if "step" in inp[1]:
                            inp[1]["step"] *= 100
                        prop = bpy.props.FloatProperty(**inp[1])
                elif proptype == "BOOLEAN":
                    prop = bpy.props.BoolProperty(**inp[1])
                elif proptype == "STRING":
                    {'default': 'ComfyUI', 'multiline': True}
                    subtype = "NONE"

                    def update_wrap(n=""):
                        i_name = n

                        def wrap(self, context):
                            if not self[i_name]:
                                return
                            if not self[i_name].startswith("//"):
                                return
                            self[i_name] = bpy.path.abspath(self[i_name])
                        return wrap
                    update = update_wrap(inp_name)
                    if inp_name == "image":
                        subtype = "FILE_PATH"
                    elif inp_name == "output_dir":
                        subtype = "DIR_PATH"
                    else:
                        def update(_, __): return
                    prop = bpy.props.StringProperty(default=str(inp[1].get("default", "")),
                                                    subtype=subtype,
                                                    update=update)
                prop = spec_gen_properties(nname, inp_name, prop)
                properties[reg_name] = prop
            from .blueprints import get_blueprints
            bp = get_blueprints(nname)
            bp.extra_properties(properties, nname, ndesc)
            # spec_extra_properties(properties, nname, ndesc)
            fields = {"init": init,
                      "inp_types": inp_types,
                      "out_types": out_types,
                      "class_type": nname,
                      "bl_label": nname,
                      "draw_buttons": draw_buttons,
                      "__annotations__": properties,
                      "__metadata__": ndesc
                      }
            NodeDesc = type(nname, (NodeBase,), fields)
            NodeDesc.dcolor = (rand() / 2, rand() / 2, rand() / 2)
            node_clss.append(NodeDesc)
        return node_clss


def spec_gen_properties(nname, inp_name, prop):

    def set_sync_rand(self: NodeBase, seed):
        if not getattr(self, "sync_rand", False):
            return
        tree = self.get_tree()
        for node in tree.get_nodes():
            if node == self:
                continue
            if hasattr(node, "seed"):
                node["seed"] = seed
            elif hasattr(node, "noise_seed"):
                node["noise_seed"] = seed

    if inp_name == "noise_seed":
        def setter(self, v):
            try:
                _ = int(v)
                self["noise_seed"] = v
            except Exception:
                ...
            set_sync_rand(self, self["noise_seed"])

        def getter(self):
            if "noise_seed" not in self:
                self["noise_seed"] = "0"
            return str(self["noise_seed"])
        prop = bpy.props.StringProperty(default="0", set=setter, get=getter)
    elif inp_name == "seed":
        def setter(self, v):
            try:
                _ = int(v)
                self["seed"] = v
            except Exception:
                ...
            set_sync_rand(self, self["seed"])

        def getter(self):
            if "seed" not in self:
                self["seed"] = "0"
            return str(self["seed"])
        prop = bpy.props.StringProperty(default="0", set=setter, get=getter)
    return prop


class Images(bpy.types.PropertyGroup):
    image: bpy.props.PointerProperty(type=bpy.types.Image)


clss = [Ops_Swith_Socket, Ops_Add_SaveImage, Set_Render_Res, GetSelCol, Ops_Active_Tex, Ops_Link_Mask, Images]

reg, unreg = bpy.utils.register_classes_factory(clss)


def nodes_reg():
    reg()
    Ops_Link_Mask.reg()


def nodes_unreg():
    clear_nodes_data_cache()
    try:
        unreg()
    except BaseException:
        ...
    Ops_Link_Mask.unreg()


def clear_nodes_data_cache():
    ENUM_ITEMS_CACHE.clear()
    PREVICONPATH.clear()
