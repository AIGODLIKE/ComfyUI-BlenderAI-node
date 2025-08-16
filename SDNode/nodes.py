from __future__ import annotations
import bpy
import os
import json
import math
import re
from collections.abc import Iterable
from hashlib import md5
from math import ceil
from typing import Set, Any
from pathlib import Path
from random import random as rand
from functools import lru_cache
from mathutils import Vector, Matrix
from bpy.types import Context, Event
from .utils import SELECTED_COLLECTIONS, get_default_tree
from ..utils import logger, Icon, _T, read_json, hex2rgb
from ..datas import ENUM_ITEMS_CACHE, IMG_SUFFIX
from ..timer import Timer
from ..translations.translation import ctxt
from .manager import get_url, WITH_PROXY

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
    "BOOLEAN": "BOOLEAN",
    "COMBO": "COMBO",
}

NODE_SLOTS = {
    "CLIP": "#FFD500",
    "CLIP_VISION": "#A8DADC",
    "CLIP_VISION_OUTPUT": "#AD7452",
    "CONDITIONING": "#FFA931",
    "CONTROL_NET": "#6EE7B7",
    "IMAGE": "#64B5F6",
    "LATENT": "#FF9CF9",
    "MASK": "#81C784",
    "MODEL": "#B39DDB",
    "STYLE_MODEL": "#C2FFAE",
    "VAE": "#FF6E6E",
    "TAESD": "#DCC274",
    "PIPE_LINE": "#7737AA",
    "PIPE_LINE_SDXL": "#7737AA",
    "INT": "#29699C",
    "X_Y": "#38291F",
    "XYPLOT": "#74DA5D",
    "LORA_STACK": "#94DCCD",
    "CONTROL_NET_STACK": "#94DCCD",
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

name2type = {
    "ckpt_name": "checkpoints",
    "vae_name": "vae",
    "clip_name": "clip",
    "gligen_name": "gligen",
    "control_net_name": "controlnet",
    "lora_name": "loras",
    "style_model_name": "style_models",
    "hypernetwork_name": "hypernetworks",
    "unet_name": "unets",
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
        logger.warning(_T("icon path load error") + str(e))

    try:
        d = json.loads(PATH_CFG.read_text(encoding="gbk"))
        return d
    except Exception as e:
        logger.warning(_T("icon path load error") + str(e))


def get_icon_path(nname):
    from .blueprints import get_blueprints
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
        for class_type, pathmap in name2path.items():
            path_list = {}
            PREVICONPATH[class_type] = path_list
            for name, mpath in pathmap.items():
                reg_name = get_blueprints().get_prop_reg_name(name)
                if mpath not in d:
                    continue
                path_list[reg_name] = d[mpath][0]
    return PREVICONPATH.get(nname, {})


def calc_hash_type(stype):
    from .blueprints import is_bool_list, is_all_str_list
    if is_bool_list(stype):
        hash_type = md5("{True, False}".encode()).hexdigest()
    elif not is_all_str_list(stype):
        hash_type = md5(",".join([str(i) for i in stype]).encode()).hexdigest()
    else:
        try:
            hash_type = md5(",".join(stype).encode()).hexdigest()
        except TypeError as e:
            winfo = str(stype)
            if len(winfo) > 100:
                winfo = winfo[:40] + "......"
            raise TypeError(f"{_T('Non-Standard Enum')} -> {winfo}") from e
    return hash_type


class PropGen:
    @staticmethod
    def _find_icon_local(nname, inp_name, item):
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
                ipath = pp.joinpath(item)
                pimg = ipath.with_suffix(suffix)
                pimg = pimg if pimg.exists() else Path(ipath.as_posix() + suffix)
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

    @staticmethod
    def _find_icon_remote(nname, inp_name, item):
        from .manager import TaskManager, RemoteServer
        server: RemoteServer = TaskManager.server
        mtype = name2type.get(inp_name, "")
        path: Path = server.cache_model_icon(mtype, item)
        if not path:
            return
        return Icon.reg_icon(path.absolute(), reload=True)

    @staticmethod
    def _find_icon(nname, inp_name, item):
        from .manager import TaskManager
        server = TaskManager.server
        if server and server.server_type == "Remote":
            icon = PropGen._find_icon_remote(nname, inp_name, item)
        else:
            icon = PropGen._find_icon_local(nname, inp_name, item)
        if not icon:
            icon = Icon["NONE"]
        return icon

    @staticmethod
    def Gen(proptype, nname, inp_name, inp):
        from .blueprints import get_blueprints
        reg_name = get_blueprints(nname).get_prop_reg_name(inp_name)
        prop = getattr(PropGen, proptype)(nname, inp_name, reg_name, inp)
        prop = PropGen._spec_gen_properties(nname, inp_name, prop)
        return prop

    @staticmethod
    def ENUM(nname, inp_name, reg_name, inp):
        def get_items(nname, inp_name, inp):
            def wrap(self, context):
                if nname not in ENUM_ITEMS_CACHE:
                    ENUM_ITEMS_CACHE[nname] = {}
                if inp_name in ENUM_ITEMS_CACHE[nname]:
                    return ENUM_ITEMS_CACHE[nname][inp_name]
                items = []
                # 专门用于 老版本的 翻译
                spec_trans = {
                    "输入": "Image Path/Name",
                    "渲染": "Render",
                    "序列图": "Sequence",
                    "视口": "Viewport",
                }
                for item in inp[0]:
                    icon_id = PropGen._find_icon(nname, inp_name, item)
                    if icon_id:
                        ENUM_ITEMS_CACHE[nname][inp_name] = items
                    si = str(item)
                    if si in spec_trans:
                        items.append((si, spec_trans.get(si, si), ""))
                        continue
                    items.append((si, spec_trans.get(si, si), "", icon_id, len(items)))
                return items

            return wrap

        prop = bpy.props.EnumProperty(items=get_items(nname, reg_name, inp))

        # 判断可哈希
        def is_all_hashable(some_list):
            return all(hasattr(item, "__hash__") for item in some_list)

        if is_all_hashable(inp[0]) and set(inp[0]) == {True, False}:
            prop = bpy.props.BoolProperty()
        return prop

    @staticmethod
    def COMBO(nname, inp_name, reg_name, inp):
        def get_items(nname, inp_name, inp_params):
            def wrap(self, context):
                if nname not in ENUM_ITEMS_CACHE:
                    ENUM_ITEMS_CACHE[nname] = {}
                if inp_name in ENUM_ITEMS_CACHE[nname]:
                    return ENUM_ITEMS_CACHE[nname][inp_name]
                items = []
                # 专门用于 老版本的 翻译
                spec_trans = {
                    "输入": "Image Path/Name",
                    "渲染": "Render",
                    "序列图": "Sequence",
                    "视口": "Viewport",
                }
                for item in inp_params.get("options", []):
                    icon_id = PropGen._find_icon(nname, inp_name, item)
                    if icon_id:
                        ENUM_ITEMS_CACHE[nname][inp_name] = items
                    si = str(item)
                    if si in spec_trans:
                        items.append((si, spec_trans.get(si, si), ""))
                        continue
                    items.append((si, spec_trans.get(si, si), "", icon_id, len(items)))
                return items

            return wrap

        inp_params: dict = inp[1] if len(inp) > 1 else {}
        items_ori: list = inp_params.get("options", [])
        kwargs = {}
        if default := inp_params.get("default"):
            kwargs["default"] = items_ori.index(default)
        if tooltip := inp_params.get("tooltip"):
            kwargs["description"] = tooltip
        prop = bpy.props.EnumProperty(items=get_items(nname, reg_name, inp_params), **kwargs)

        # 判断可哈希
        def is_all_hashable(some_list):
            return all(hasattr(item, "__hash__") for item in some_list)

        if is_all_hashable(items_ori) and set(items_ori) == {True, False}:
            prop = bpy.props.BoolProperty()
        return prop

    @staticmethod
    def INT(nname, inp_name, reg_name, inp):
        # {'default': 20, 'min': 1, 'max': 10000}
        if len(inp) == 1:
            return bpy.props.IntProperty()
        inp[1]["max"] = min(int(inp[1].get("max", 9999999)), 2**31 - 1)
        inp[1]["min"] = max(int(inp[1].get("min", -999999)), -2**31)
        default = inp[1].get("default", 0)
        if not default:
            default = 0
        inp[1]["default"] = int(default)
        if inp[1]["default"] > 2**31 - 1:
            logger.warning("Default value is too large: %s.%s -> %s", nname, inp_name, inp[1]["default"])
            inp[1]["default"] = min(inp[1]["default"], 2**31 - 1)
        elif inp[1]["default"] < -2**31:
            logger.warning("Default value is too small: %s.%s -> %s", nname, inp_name, inp[1]["default"])
            inp[1]["default"] = max(inp[1]["default"], -2**31)
        inp[1]["step"] = ceil(inp[1].get("step", 1))
        if inp[1].pop("display", False):
            inp[1]["subtype"] = "FACTOR"
        params = {}
        for k in ["name", "description", "translation_context", "default", "min", "max", "soft_min", "soft_max", "step", "options", "override", "tags", "subtype", "update", "get", "set",]:
            if k in inp[1]:
                params[k] = inp[1][k]
        prop = bpy.props.IntProperty(**params)
        return prop

    @staticmethod
    def FLOAT(nname, inp_name, reg_name, inp):
        {'default': 8.0, 'min': 0.0, 'max': 100.0}
        if len(inp) > 1:
            if "step" in inp[1]:
                inp[1]["step"] = min(inp[1]["step"] * 100, 100)
            if inp[1].pop("display", False):
                inp[1]["subtype"] = "FACTOR"
            default = inp[1].pop("default", 0)
            if isinstance(default, Iterable):
                default = list(default)[0]
            if isinstance(default, (float, int)):
                inp[1]["default"] = default
            else:
                logger.warning("Default value is not a number: %s.%s -> %s", nname, inp_name, default)
            params = {}
            for k in ["name", "description", "translation_context", "default", "min", "max", "soft_min", "soft_max", "step", "precision", "options", "override", "tags", "subtype", "unit", "update", "get", "set"]:
                if k in inp[1]:
                    params[k] = inp[1][k]
            prop = bpy.props.FloatProperty(**params)
            return prop
        return bpy.props.FloatProperty()

    @staticmethod
    def BOOLEAN(nname, inp_name, reg_name, inp):
        if len(inp) <= 1:
            return bpy.props.BoolProperty()
        params = {}
        for k in ["name", "description", "translation_context", "default", "options", "override", "tags", "subtype", "update", "get", "set"]:
            if k not in inp[1]:
                continue
            params[k] = inp[1][k]
        if "default" in params:
            default_value = params["default"]
            if isinstance(default_value, str):
                try:
                    from ast import literal_eval
                    default_value = literal_eval(default_value)
                except Exception:
                    pass
            params["default"] = bool(default_value)
        return bpy.props.BoolProperty(**params)

    @staticmethod
    def STRING(nname, inp_name, reg_name, inp):
        {'default': 'ComfyUI', 'multiline': True}
        subtype = "NONE"

        def update_default_wrap(n):
            inp_name = n

            def wrap(self: NodeBase, context):
                stat = self.mlt_stats.get(inp_name)
                if not stat or not stat.enable:
                    return
                stat.freeze = True
                rm = False
                try:
                    stat.texts.clear()
                    for text in self[inp_name].split(","):
                        t = text.strip()
                        if t in stat.texts:
                            rm = True
                            continue
                        i = stat.texts.add()
                        i.name = t
                except Exception:
                    import traceback
                    traceback.print_exc()
                stat.freeze = False
                # if rm:
                #     ct = ",".join([t.name for t in stat.texts])
                #     if ct == self[inp_name]:
                #         return
                #     self[inp_name] = ct
            return wrap
        update_default = update_default_wrap(inp_name)

        def update_wrap(n=""):
            i_name = n
            update_default = update_default_wrap(n)

            def wrap(self, context):
                update_default(self, context)
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
            update = update_default
        prop = bpy.props.StringProperty(default=str(inp[1].get("default", "")),
                                        subtype=subtype,
                                        update=update)
        return prop

    @staticmethod
    def _spec_gen_properties(nname, inp_name, prop):

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
                    return "0"
                return str(self["seed"])
            prop = bpy.props.StringProperty(default="0", set=setter, get=getter)
        return prop


class SDNConfig(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    visible: bpy.props.BoolProperty(default=False)
    in_out: bpy.props.EnumProperty(items=[("INPUT", "INPUT", ""), ("OUTPUT", "OUTPUT", "")], default="INPUT")
    converted: bpy.props.BoolProperty(default=False)


class MLTText(bpy.types.PropertyGroup):
    def find_stat(self, node: NodeBase):
        if not node:
            return
        for stat in node.mlt_stats:
            if not stat.enable or stat.freeze:
                continue
            if not hasattr(node, stat.name):
                continue
            for t in stat.texts:
                if t != self:
                    continue
                return stat

    def set_content(self, v):
        # v format: '[xxx]key'
        # 如果v已经存在则弹出报错
        if "]" in v:
            v = v.split("]")[1].strip()
        node: NodeBase = bpy.context.active_node
        stat = self.find_stat(node)
        if stat and v in stat.texts:
            def pop_error(self, context):
                self.layout.label(text="Text already exists", icon="ERROR")
            bpy.context.window_manager.popup_menu(pop_error, title="ERROR", icon="ERROR")
            return
        self["name"] = v

    def get_content(self):
        if "name" not in self:
            self["name"] = ""
        return self["name"]

    def update_content(self, context):
        node: NodeBase = get_ctx_node()
        # 合并text
        stat = self.find_stat(node)
        if not stat:
            return
        ct = ",".join([t.name for t in stat.texts])
        if ct == getattr(node, stat.name):
            return
        setattr(node, stat.name, ct)

    name: bpy.props.StringProperty(update=update_content, set=set_content, get=get_content)


class MLTRec(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    enable: bpy.props.BoolProperty(default=False)
    texts: bpy.props.CollectionProperty(type=MLTText)
    tindex: bpy.props.IntProperty(default=0)
    freeze: bpy.props.BoolProperty(default=False)

    def add_text_update(self, context):
        if not self.addtext:
            return
        t = self.addtext.strip()
        self.addtext = ""
        if t not in self.texts:
            i = self.texts.add()
            i.name = t
        else:
            def pop_error(self, context):
                self.layout.label(text="Text already exists", icon="ERROR")
            bpy.context.window_manager.popup_menu(pop_error, title="ERROR", icon="ERROR")
    addtext: bpy.props.StringProperty(name="Add Tag By Input", update=add_text_update)


class MLTWords_UL_UIList(bpy.types.UIList):

    def draw_item(self,
                  context: bpy.types.Context,
                  layout: bpy.types.UILayout,
                  data, item, icon, active_data, active_property, index=0, flt_flag=0):
        row = layout.row()
        # row.label(text=str(item.freq), icon="SOLO_ON")
        row.label(text=item.name)
        op = row.operator(AdvTextEdit.bl_idname, text="", icon="ADD")
        op.text_name = item.value
        op.prop = self.list_id
        op.action = "AddTag"


class MLTText_UL_UIList(bpy.types.UIList):
    def draw_item(self,
                  context: bpy.types.Context,
                  layout: bpy.types.UILayout,
                  data, item, icon, active_data, active_property, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.label(text="", icon="KEYTYPE_KEYFRAME_VEC")
        if getattr(data, active_property) == index:
            row.prop_search(item, "name", bpy.context.window_manager, "mlt_words", text="", results_are_suggestions=True)
        else:
            row.label(text=item.name)

        op = row.operator(AdvTextEdit.bl_idname, text="", icon="ADD")
        op.text_name = item.name
        op.prop = data.name
        op.action = "UpTagWeight"

        op = row.operator(AdvTextEdit.bl_idname, text="", icon="REMOVE")
        op.text_name = item.name
        op.prop = data.name
        op.action = "DownTagWeight"

        op = row.operator(AdvTextEdit.bl_idname, text="", icon="RADIOBUT_OFF")
        op.text_name = item.name
        op.prop = data.name
        op.action = "RemoveTagWeight"

        op = row.operator(AdvTextEdit.bl_idname, text="", icon="X")
        op.text_name = item.name
        op.prop = data.name
        op.action = "RemoveTag"


class NodeBase(bpy.types.Node):
    bl_width_min = 200.0
    bl_width_max = 2000.0
    sdn_order: bpy.props.IntProperty(default=-1)
    sdn_level: bpy.props.IntProperty(default=0)
    sdn_dirty: bpy.props.BoolProperty(default=False)
    sdn_hide: bpy.props.BoolProperty(default=False)
    sdn_socket_visible_in: bpy.props.CollectionProperty(type=SDNConfig)
    sdn_socket_visible_out: bpy.props.CollectionProperty(type=SDNConfig)
    id: bpy.props.StringProperty(default="-1")
    mlt_stats: bpy.props.CollectionProperty(type=MLTRec)
    class_type: str
    # for pylint
    inp_types: list[str]
    __metadata__: dict
    __annotations__: dict
    prop: str
    sync_rand: bool

    def get_visible_cfg(self, in_out="INPUT"):
        return self.sdn_socket_visible_in if in_out == "INPUT" else self.sdn_socket_visible_out

    def set_sock_visible(self, name, in_out="INPUT", value=True):
        cfg: dict[str, SDNConfig] = self.get_visible_cfg(in_out)
        name = self.get_blueprints().get_prop_ori_name(name)
        if name not in cfg:
            cfg.add().name = name
        cfg[name].visible = bool(value)

    def get_sock_visible(self, name, in_out="INPUT"):
        cfg: dict[str, SDNConfig] = self.get_visible_cfg(in_out)
        name = self.get_blueprints().get_prop_ori_name(name)
        if name not in cfg:
            return True
        return cfg[name].visible

    def get_widgets(self, exclude_converted=False) -> list[str]:
        """
        # 获取当前节点的widgets
        """
        widgets = self.widgets
        if exclude_converted:
            widgets = [w for w in widgets if not self.query_stat(w)]
        return widgets

    def get_widgets_num(self):
        """
        # 计算当前节点的widgets数量(已转sock不记入)
        """
        if self.bl_idname == "PrimitiveNode":
            return 1
        num = 0
        for inp in self.inp_types:
            if inp == "control_after_generate":
                continue
            if inp in self.inputs:
                continue
            num += 1
        return num

    def get_input(self, identifier):
        if bpy.app.version >= (4, 0):
            return self.inputs.get(identifier)
        else:
            for s in self.inputs:
                if s.identifier == identifier:
                    return s
            return None

    def get_output(self, identifier):
        if bpy.app.version >= (4, 0):
            return self.outputs.get(identifier)
        else:
            for s in self.outputs:
                if s.identifier == identifier:
                    return s
            return None

    def store_appearance(self):
        if self.label.endswith(("-EXEC", "-ERROR")):
            return
        self["OLD_APPEARANCE"] = {
            "label": self.label,
            "color": self.color[:],
            "use_custom_color": self.use_custom_color
        }

    def restore_appearance(self):
        if not self.label.endswith(("-EXEC", "-ERROR")):
            return
        if "OLD_APPEARANCE" not in self:
            return
        appearance = self.get("OLD_APPEARANCE", {})
        for k in appearance:
            setattr(self, k, appearance[k])

    def is_dirty(self):
        return self.sdn_dirty

    def set_dirty(self, value=True):
        self.sdn_dirty = value

    def is_group(self) -> bool:
        return False

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

    def query_stats(self) -> dict:
        if "BUILTIN_STAT" not in self:
            return {}
        return self["BUILTIN_STAT"]

    def query_stat(self, name):
        stat = self.query_stats()
        name = self.get_blueprints().get_prop_ori_name(name)
        return stat.get(name, None)

    def set_stat(self, name, value):
        if "BUILTIN_STAT" not in self:
            self["BUILTIN_STAT"] = {}
        stat = self.query_stats()
        stat[name] = value

    def query_mlt_stats(self) -> dict:
        if "BUILTIN_MLT_STAT" not in self:
            return {}
        return self["BUILTIN_MLT_STAT"]

    def query_mlt_stat(self, name):
        return self.query_mlt_stats().get(name, False)

    def set_mlt_stat(self, name, stat):
        if "BUILTIN_MLT_STAT" not in self:
            self["BUILTIN_MLT_STAT"] = {}
        stat = self.query_mlt_stats()
        if name not in stat:
            stat[name] = {}
        stat[name]["stat"]

    def is_output_node(self):
        return self.__metadata__.get("output_node", False)

    def reaches_output(self):
        """
            判断当前节点是否最终连接到ouput_node
        """
        if self.is_output_node():
            return True
        reached = False
        for out in self.outputs:
            if not out.is_linked:
                continue
            for link in out.links:
                reached |= link.to_node.reaches_output()
        return reached

    def is_base_type(self, name):
        """
        是基本类型?
        目前通过 拥有注册属性名判断
        """
        reg_name = self.get_blueprints().get_prop_reg_name(name)
        return hasattr(self, reg_name)

    @property
    def widgets(self) -> list[str]:
        return [inp for inp in self.inp_types if self.is_base_type(inp)]

    def is_ori_sock(self, name, in_out="INPUT"):
        """
        是原始socket?
        """
        reg_name = self.get_blueprints().get_prop_reg_name(name)
        if in_out == "INPUT":
            return not hasattr(self, reg_name) and self.inputs.get(name)
        return not hasattr(self, reg_name) and self.outputs.get(name)

    def switch_socket_widget(self, name, value):
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
            logger.warning(f"node {self.name} has no metadata")
            return []
        inputs = self.__metadata__.get("input", {})
        if inp_name in (r := inputs.get("required", {})):
            return r[inp_name]
        if inp_name in (o := inputs.get("optional", {})):
            return o[inp_name]
        return []

    def is_optional(self, inp_name):
        return inp_name in self.__metadata__.get("input", {}).get("optional", {})

    def is_required(self, inp_name):
        return inp_name in self.__metadata__.get("input", {}).get("required", {})

    def calc_slot_index(self):
        for i, inp in enumerate(self.inputs):
            inp.slot_index = i
        for i, out in enumerate(self.outputs):
            out.slot_index = i

    def pool_get(self) -> set:
        return self.get_tree().get_id_pool()

    def unique_id(self):
        pool = self.pool_get()
        for i in range(3, 99999):
            i = str(i)
            if i not in pool:
                pool.add(i)
                return i

    def free(self):
        self.pool_get().discard(self.id)
        bp = self.get_blueprints()
        bp.free(self)

    def copy(self, node):
        bp = self.get_blueprints()
        bp.copy(self, node)
        self.apply_unique_id()
        if hasattr(self, "sync_rand"):
            self.sync_rand = False
        if self.class_type == "材质图":
            name = node.name
            self.get_tree().safe_remove_nodes([node])

            def f(self: NodeBase, name):
                self.name = name
            Timer.put((f, self, name))

    def apply_unique_id(self):
        self.id = self.unique_id()
        return self.id

    def _draw_(self, context, layout, ext=False):
        for prop in self.__annotations__:
            if not ext and not self.get_sock_visible(prop, "INPUT"):
                continue
            if self.query_stat(prop):
                continue
            if prop == "control_after_generate":
                continue
            l = layout
            # 返回True 则不绘制
            if self.get_blueprints().draw_button(self, context, l, prop, swdisp=ext):
                continue
            if self.is_base_type(prop) and self.get_blueprints().get_prop_ori_name(prop) in self.inp_types:
                l = Ops_Switch_Socket_Widget.draw_prop(l, self, prop, swdisp=ext)
            l.prop(self, prop, text=prop, text_ctxt=self.get_ctxt())

    def draw_buttons(self: NodeBase, context, layout: bpy.types.UILayout):
        if self.sdn_hide:
            return
        self._draw_(context, layout)

    def draw_buttons_ext(self, context, layout):
        row = layout.row(align=True)
        row.label(text=self.name, icon="NODE")
        row.prop(self, "sdn_hide", text="", icon="HIDE_ON" if self.sdn_hide else "HIDE_OFF")
        self._draw_(context, layout, ext=True)

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
        tree = self.get_tree()
        if tree.freeze:
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
                if ts.bl_idname == "*" or fs.bl_idname == "*":
                    continue
                if fs.bl_idname == "*" and SOCKET_HASH_MAP.get(ts.bl_idname) in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}:
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
                # 组中的 NodeReroute的output 不删除, 但要检查是否连接的相同接口
                if any(self.get_tree().get_in_out_node()) and l.from_node.bl_idname == "NodeReroute":
                    reroute = l.from_node
                    for l2 in reroute.outputs[0].links[:]:
                        if l2.to_node == self:
                            continue
                        if l2.to_socket.bl_idname == ts.bl_idname:
                            continue
                        bpy.context.space_data.edit_tree.links.remove(l2)
                    continue
                bpy.context.space_data.edit_tree.links.remove(l)

    def primitive_check(self):
        # 在timer里会失败 导致prop为空
        # if not bpy.context.space_data:
        #     return
        # if bpy.context.space_data.type != "NODE_EDITOR":
        #     return
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
                inp = node.inputs[0]
                if inp.is_linked and inp.links:
                    link = inp.links[0]
                else:
                    return
            else:
                return link

    def serialize_pre(self):
        bp = self.get_blueprints()
        return bp.serialize_pre(self)

    def serialize(self, execute=True, parent: NodeBase = None):
        """
        gen prompt
        """
        bp = self.get_blueprints()
        return bp.serialize(self, execute, parent=parent)

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

    def make_serialize(self, parent: NodeBase = None) -> dict:
        bp = self.get_blueprints()
        return bp.make_serialize(self, parent=parent)

    def draw_socket_io_box(self, context, layout: bpy.types.UILayout, node: NodeBase, text=""):
        if not max(len(self.inputs), len(self.outputs)):
            return
        box = layout.box()
        box.label(text="Socket管理")
        row = box.row()
        if self.inputs:
            lbox = row.box()
            lbox.label(text="Input")
        for inp in self.inputs:
            lrow = lbox.row(align=True)
            visible = node.get_sock_visible(inp.name, in_out="INPUT")
            icon = "HIDE_OFF" if visible else "HIDE_ON"
            lrow.label(text=inp.name)
            op = lrow.operator(Ops_Switch_Socket_Disp.bl_idname, text="", icon=icon)
            op.action = "Hide" if visible else "Show"
            op.socket_name = inp.name
            op.node_name = node.name
            op.in_out = "INPUT"
        if self.outputs:
            rbox = row.box()
            rbox.label(text="Output")
        for out in self.outputs:
            rrow = rbox.row(align=True)
            visible = node.get_sock_visible(out.name, in_out="OUTPUT")
            icon = "HIDE_OFF" if visible else "HIDE_ON"
            rrow.label(text=out.name)
            op = rrow.operator(Ops_Switch_Socket_Disp.bl_idname, text="", icon=icon)
            op.action = "Hide" if visible else "Show"
            op.socket_name = out.name
            op.node_name = node.name
            op.in_out = "OUTPUT"

    def draw_socket(_self, self: bpy.types.NodeSocket, context, layout, node: NodeBase, text):
        if not node.is_registered_node_type():
            return
        rinfo = ""
        linfo = ""
        if text == "SDN_OUTER_INPUT":
            rinfo = f" [{_T(node.name)}]"
        if text == "SDN_OUTER_OUTPUT":
            linfo = f"[{_T(node.name)}] "
        prop = _self.get_blueprints().get_prop_reg_name(self.name)
        if self.is_output or not hasattr(node, prop):
            layout.label(text=linfo + _T(self.name) + rinfo, text_ctxt=node.get_ctxt())
            return
        row = layout.row(align=True)
        row.label(text=linfo + _T(prop) + rinfo, text_ctxt=node.get_ctxt())
        op = row.operator(Ops_Switch_Socket_Widget.bl_idname, text="", icon="UNLINKED")
        op.node_name = node.name
        op.socket_name = self.name
        op.action = "ToProp"
        row.prop(node, prop, text="", text_ctxt=node.get_ctxt())


class SocketBase(bpy.types.NodeSocket):
    color: bpy.props.FloatVectorProperty(size=4, default=(1, 0, 0, 1))

    def draw_color(self, context, node):
        return self.color

    if bpy.app.version >= (4, 0):
        draw_color_simple_ = (1, 0, 0, 1)

        @classmethod
        def draw_color_simple(cls):
            return cls.draw_color_simple_


class Ops_Switch_Socket_Disp(bpy.types.Operator):
    bl_idname = "sdn.switch_socket_disp"
    bl_label = "Toggle socket visibility"
    bl_translation_context = ctxt
    socket_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()
    action: bpy.props.StringProperty(default="")
    in_out: bpy.props.EnumProperty(items=[("INPUT", "INPUT", ""), ("OUTPUT", "OUTPUT", "")], default="INPUT")

    def switch_disp(self, node: NodeBase):
        if self.action == "Show":
            node.set_sock_visible(self.socket_name, self.in_out, True)
        elif self.action == "Hide":
            node.set_sock_visible(self.socket_name, self.in_out, False)

    def execute(self, context: Context) -> Set[int] | Set[str]:
        from .tree import CFNodeTree
        from .nodegroup import SDNGroup
        node: SDNGroup = get_ctx_node()
        if not node:
            return {"FINISHED"}
        if not node.is_group():
            self.switch_disp(node)
            return {"FINISHED"}
        if not node.node_tree:
            return {"FINISHED"}
        otree: CFNodeTree = node.get_tree()
        tree: CFNodeTree = node.node_tree
        otree.store_toggle_links()
        sel_node: NodeBase = tree.nodes.get(self.node_name)
        self.switch_disp(sel_node)

        node.clear_interface(tree)
        node.clear_sockets()
        tree.interface_update(context)
        tree.update()
        # 通知更新所有节点
        bpy.msgbus.publish_rna(key=(bpy.types.SpaceNodeEditor, "node_tree"))
        tree.switch_tree_update()
        otree.active = node
        otree.restore_toggle_links()
        return {"FINISHED"}


def get_ctx_node():
    node = getattr(bpy.context, "node", None)
    if node:
        return node
    node = getattr(bpy.context, "active_node", None)
    if node:
        return node


class Ops_Switch_Socket_Widget(bpy.types.Operator):
    bl_idname = "sdn.switch_socket_widget"
    bl_label = "Toggle socket"
    bl_description = "Toggle whether a socket is or isn't used for input"
    socket_name: bpy.props.StringProperty()
    node_name: bpy.props.StringProperty()
    action: bpy.props.StringProperty(default="")
    bl_translation_context = ctxt

    def set_active_node(self, tree):
        if not tree:
            return
        node = get_ctx_node()
        if not node:
            return
        if tree.nodes.active:
            tree.nodes.active.select = False
        tree.nodes.active = node
        node.select = True

    def execute(self, context):
        from .tree import CFNodeTree
        tree: CFNodeTree = get_default_tree()
        otree = tree
        node: NodeBase = None
        if get_ctx_node() and get_ctx_node().is_group():
            self.set_active_node(otree)
            otree.store_toggle_links()
            tree = get_ctx_node().node_tree
        if not (node := tree.nodes.get(self.node_name)):
            return {"FINISHED"}
        socket_name = node.get_blueprints().get_prop_ori_name(self.socket_name)
        match self.action:
            case "ToSocket":
                node.switch_socket_widget(socket_name, True)
            case "ToProp":
                node.switch_socket_widget(socket_name, False)
        if get_ctx_node() and get_ctx_node().is_group():
            tree.interface_update(context)
            tree.update()
            # 通知更新所有节点
            bpy.msgbus.publish_rna(key=(bpy.types.SpaceNodeEditor, "node_tree"))
            otree.switch_tree_update()
            otree.restore_toggle_links()
        self.action = ""
        return {"FINISHED"}

    @staticmethod
    def draw_prop(layout, node: NodeBase, prop, row=True, swsock=True, swdisp=False) -> bpy.types.UILayout:
        l = layout
        if swsock:
            l = layout.row(align=True)
            op = l.operator(Ops_Switch_Socket_Widget.bl_idname, text="", icon="LINKED")
            op.node_name = node.name
            op.socket_name = prop
            op.action = "ToSocket"
        if swdisp and not node.get_tree().root:
            visible = node.get_sock_visible(prop, in_out="INPUT")
            icon = "HIDE_OFF" if visible else "HIDE_ON"
            op = l.operator(Ops_Switch_Socket_Disp.bl_idname, text="", icon=icon)
            op.action = "Hide" if visible else "Show"
            op.socket_name = prop
            op.node_name = node.name
            op.in_out = "INPUT"
        if row:
            l = l.row(align=True)
        else:
            l = l.column(align=True)
        return l


class Ops_Add_SaveImage(bpy.types.Operator):
    bl_idname = "sdn.add_saveimage"
    bl_label = "Add SaveImage node"
    bl_description = "Add a SaveImage node and connect it to the image"
    node_name: bpy.props.StringProperty()
    bl_translation_context = ctxt

    def execute(self, context):
        tree = get_default_tree()
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
    bl_translation_context = ctxt

    def execute(self, context):
        if not (img := bpy.data.images.get(self.img_name)):
            return {"FINISHED"}
        tree = get_default_tree()
        if not (node := tree.nodes.get(self.node_name)):
            return {"FINISHED"}
        node.image = None if img == node.image else img
        return {"FINISHED"}


class Ops_Link_Mask(bpy.types.Operator):
    bl_idname = "sdn.link_mask"
    bl_label = "链接遮照"
    bl_options = {"REGISTER", "UNDO"}
    bl_translation_context = ctxt
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
    from_node: bpy.types.Node = None
    to_node: bpy.types.Node = None
    handle: Any = None

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
        return context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE

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
    bl_label = "Set Render Resolution"
    bl_description = "Set the render resolution to be the same as this node's image"
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


class AdvTextEdit(bpy.types.Operator):
    bl_idname = "sdn.adv_text_edit"
    bl_label = ""
    bl_translation_context = ctxt
    prop: bpy.props.StringProperty(default="")
    text_name: bpy.props.StringProperty(default="")
    action: bpy.props.EnumProperty(items=[("SwitchAdvText", "SwitchAdvText", "", 0),
                                          ("RemoveTag", "RemoveTag", "", 1),
                                          ("AddTag", "AddTag", "", 2),
                                          ("UpTagWeight", "UpTagWeight", "", 3),
                                          ("DownTagWeight", "DownTagWeight", "", 4),
                                          ("RemoveTagWeight", "RemoveTagWeight", "", 5),
                                          ],
                                   default="SwitchAdvText")

    @classmethod
    def description(cls, context: bpy.types.Context,
                    properties: bpy.types.OperatorProperties) -> str:
        desc = "Adv Text Action"
        if action := getattr(properties, "action", ""):
            desc = action
        return _T(desc)

    @classmethod
    def poll(cls, context):
        from .tree import TREE_TYPE
        return context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE

    def execute(self, context):
        node: NodeBase = get_ctx_node()
        if not node:
            return {"FINISHED"}
        stat: MLTRec = node.mlt_stats.get(self.prop)
        if self.action == "SwitchAdvText":
            if not stat:
                stat = node.mlt_stats.add()
                stat.name = self.prop
                stat.enable = True
            else:
                stat.enable ^= True
            self.update_list(node, stat)
        elif self.action == "RemoveTag":
            if stat:
                tindex = stat.texts.find(self.text_name)
                stat.texts.remove(tindex)
                self.dump_list(node, stat)
        elif self.action == "AddTag":
            if stat:
                if self.text_name not in stat.texts:
                    stat.texts.add().name = self.text_name
                    self.update_list(node, stat)
                else:
                    self.report({"ERROR"}, "Text already exists")
        elif self.action == "UpTagWeight":
            if stat and self.text_name in stat.texts:
                t = self.text_name.strip()
                # 权重格式 tag -> (tag:xxx), 其中xxx为权重值
                match = re.match(r"\((.*?):(.*?)\)", t)
                if match:
                    ot, weight = match.group(1, 2)
                    weight = float(weight)
                else:
                    ot, weight = t, 1
                weight += 0.1
                t = f"({ot}:{weight:.1f})"
                stat.texts[self.text_name].name = t
        elif self.action == "DownTagWeight":
            if stat and self.text_name in stat.texts:
                t = self.text_name.strip()
                # 权重格式 tag -> (tag:xxx), 其中xxx为权重值
                match = re.match(r"\((.*?):(.*?)\)", t)
                if match:
                    ot, weight = match.group(1, 2)
                    weight = float(weight)
                else:
                    ot, weight = t, 1
                weight -= 0.1
                t = f"({ot}:{weight:.1f})"
                stat.texts[self.text_name].name = t
        elif self.action == "RemoveTagWeight":
            if stat and self.text_name in stat.texts:
                t = self.text_name.strip()
                # 权重格式 tag -> (tag:xxx), 其中xxx为权重值
                match = re.match(r"\((.*?):(.*?)\)", t)
                ot = t if not match else match.group(1)
                stat.texts[self.text_name].name = ot
        return {'FINISHED'}

    def dump_list(self, node, stat):
        if not stat.enable:
            return
        if not hasattr(node, stat.name):
            return
        ct = ",".join([t.name for t in stat.texts])
        if ct == getattr(node, stat.name):
            return
        setattr(node, stat.name, ct)
        self.update_list(node, stat)

    def update_list(self, node, stat):
        if not stat or not node:
            return
        stat.texts.clear()
        rm = False
        for text in getattr(node, self.prop).split(","):
            text = text.strip()
            if not text:
                rm = True
                continue
            i = stat.texts.add()
            i.name = text.strip()
        if rm:
            self.dump_list(node, stat)


class NodeParser:
    CACHED_OBJECT_INFO = {}
    SOCKET_TYPE = {}  # NodeType: {PropName: SocketType}
    DIFF_IGNORE = {
        "Note",
        "PrimitiveNode",
        "Cache Node",
        "LayerUtility: TextImage",
        "MoonvalleyImg2VideoNode",
        "MoonvalleyTxt2VideoNode",
        "MoonvalleyVideo2VideoNode",
    }
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
            self.ori_object_info.update(read_json(self.INTERNAL_PATH))
        if self.PATH.exists():
            self.ori_object_info.update(read_json(self.PATH))
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
            logger.warning("Server Launch Failed")
        except ModuleNotFoundError:
            logger.error("Module: requests import error!")

    def find_diff(self):
        # 获取差异object_info
        if self.DIFF_PATH.exists():
            self.diff_object_info = read_json(self.DIFF_PATH)
        for name in self.DIFF_IGNORE:
            self.diff_object_info.pop(name, None)
        return self.diff_object_info

    def parse(self, diff=False):
        if diff:
            self.object_info = self.find_diff()
        else:
            logger.warning("Parsing Node Start")
            self.object_info = self.fetch_object()
            self.SOCKET_TYPE.clear()
            self.load_internal()
        # self.CACHED_OBJECT_INFO.update(deepcopy(self.ori_object_info))
        try:
            socket_clss = self._parse_sockets_clss()
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error("socket模板解析失败, 请联系开发者")
            raise Exception("socket模板解析失败") from e
        try:
            node_clss = self._parse_node_clss()
        except Exception as e:
            logger.error("节点模板解析失败, 可能由不标准的第三方节点导致, 请联系开发者")
            raise Exception("节点模板解析失败") from e
        try:
            nodetree_desc = self._get_nt_desc()
        except Exception as e:
            logger.error("节点树解析失败, 可能由不标准的第三方节点导致, 请联系开发者")
            raise Exception("节点树解析失败") from e
        if not diff:
            logger.warning("Parsing Node Finished!")
        return nodetree_desc, node_clss, socket_clss

    def _get_n_desc(self):
        from .blueprints import get_blueprints
        for name, desc in self.object_info.items():
            bp = get_blueprints(name)
            desc = bp.pre_filter(name, desc)
        _desc = {}

        def _parse(name, desc, _desc):
            # 有些书包节点定义的 output居然不是列表 而是单字符串
            if isinstance(desc.get("output", []), str):
                desc["output"] = [desc["output"]]
            if isinstance(desc.get("output_name", []), str):
                desc["output_name"] = [desc["output_name"]]
            for index, out_type in enumerate(desc.get("output", [])):
                desc["output"][index] = [out_type, out_type]
            output_name = desc.get("output_name", [])
            if isinstance(output_name, str):
                output_name = [output_name]
            for index, out_name in enumerate(output_name):
                if not out_name:
                    continue
                # 有些书包节点定义的 output_name 居然比 output多一个
                if index >= len(desc["output"]):
                    continue
                # 有些书包节点定义的 output为不标准的格式 如 列表 字符串嵌套什么的
                if not isinstance(desc["output"][index][0], str):
                    desc["output"][index][0] = out_name
                desc["output"][index][1] = out_name
            _desc[name] = desc
        for name in list(self.object_info.keys()):
            desc = self.object_info[name]
            try:
                _parse(name, desc, _desc)
            except Exception as e:
                import traceback
                stack = "\n" + traceback.format_exc()
                logger.debug(stack)
                logger.error(f"{_T('Parsing Failed')}: {name} -> {e}")
                self.object_info.pop(name)
        return _desc

    def _get_nt_desc(self):
        _desc = {}
        for name, desc in self.object_info.items():
            cpath = desc.get("category", "").split("/")
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
            for inp_channel in ["required", "optional"]:
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
                        if not isinstance(inp_desc[0], str):
                            logger.warning("socket type not str[IGNORE]: %s.%s -> %s", name, inp, inp_desc[0])
                            inp_desc[0] = str(inp_desc[0])
                        # 如果到这里仍然是空 则使用默认字符串
                        if inp_desc[0] == "":
                            inp_desc[0] = f"{name}_{inp}"
                        _desc.add(inp_desc[0])
                        self.SOCKET_TYPE[name][inp] = inp_desc[0]
            for index, out_type in enumerate(desc["output"]):
                if isinstance(out_type, list) and desc.get("output_name", []):
                    out_type = desc["output_name"][index]
                if isinstance(out_type, str):
                    _desc.add(out_type)
                else:
                    _desc.add(out_type[0])
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
            # 过滤不安全socket
            if stype == "":
                continue

            def draw(self, context, layout, node: NodeBase, text):
                if not node.is_registered_node_type():
                    return
                node.draw_socket(self, context, layout, node, text)
            rand_color = (rand()**0.5, rand()**0.5, rand()**0.5, 1)
            if stype in NODE_SLOTS:
                rand_color = Vector(hex2rgb(NODE_SLOTS[stype])).to_4d()
            color = bpy.props.FloatVectorProperty(size=4, default=rand_color)
            fields = {
                "draw": draw,
                "bl_label": stype,
                "__annotations__": {
                    "color": color,
                    "index": bpy.props.IntProperty(default=-1),
                    "slot_index": bpy.props.IntProperty(default=-1)
                },
                "draw_color_simple_": rand_color
            }
            SocketDesc = type(stype, (SocketBase,), fields)
            socket_clss.append(SocketDesc)
            fields = {
                "bl_idname": f"{stype}Interface",
                "bl_socket_idname": stype,
                "bl_label": stype,
                "draw_color": lambda s, c: s.color,
                "draw": lambda s, c, l: l.label(text=s.bl_label),
                "__annotations__": {
                    "color": color,
                    "sid": bpy.props.StringProperty(default=""),
                    "io_type": bpy.props.StringProperty(default=""),
                },
            }
            base = getattr(bpy.types, "NodeSocketInterface",
                           getattr(bpy.types, "NodeTreeInterfaceSocket", None))
            InterfaceDesc = type(f"{stype}Interface", (base,), fields)
            socket_clss.append(InterfaceDesc)
        return socket_clss

    def _parse_node_clss(self):
        nodes_desc = self._get_n_desc()
        node_clss = []
        for nname, ndesc in nodes_desc.items():
            # TODO: 暂时删除两个变更key, 由IPAdapter 导致
            ndesc.pop("input_order", None)
            ndesc.pop("python_module", None)
            ndesc.pop("description", None)  # 删除description
            opt_types: dict = ndesc["input"].get("optional", {})
            rqr_types: dict = ndesc["input"].get("required", {})
            inp_types = {}
            for key, value in list(rqr_types.items()) + list(opt_types.items()):
                inp_types[key] = value
                if key in {"seed", "noise_seed"}:
                    inp_types["control_after_generate"] = [["fixed", "increment", "decrement", "randomize"]]

            # inp_types.update(opt_types)
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
                        logger.error("None Input: %s", inp_name)
                        continue
                    socket = inp[0]
                    if isinstance(inp[0], list):
                        # socket = "ENUM"
                        socket = calc_hash_type(inp[0])
                        continue
                    if socket in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}:
                        continue
                    # logger.warning(inp)
                    in1 = self.inputs.new(socket, self.get_blueprints().get_prop_reg_name(inp_name))
                    in1.display_shape = "CIRCLE" if self.is_required(inp_name) else "CIRCLE_DOT"
                    # in1.link_limit = 0
                    in1.index = index
                for index, [out_type, out_name] in enumerate(self.out_types):
                    if out_type in {"ENUM", }:
                        continue
                    out = self.outputs.new(out_type, out_name)
                    out.display_shape = "CIRCLE"
                    # out.link_limit = 0
                    out.index = index
                self.calc_slot_index()

            def validate_inp(inp):
                if not isinstance(inp, list):
                    return
                if len(inp) <= 1:
                    return
                if not isinstance(inp[1], dict):
                    return
                PARAMS = {"default", "min", "max", "step", "soft_min", "soft_max", "description", "subtype", "update", "options", "multiline", "display"}
                # 排除掉不需要的属性
                for key in list(inp[1].keys()):
                    if key in PARAMS:
                        continue
                    inp[1].pop(key)
            properties = {}
            skip = False
            from .blueprints import get_blueprints
            bp = get_blueprints(nname)
            for inp_name, inp in inp_types.items():
                if not inp:
                    logger.error("None Input: %s", inp)
                    continue
                proptype = inp[0]
                if isinstance(inp[0], list):
                    proptype = "ENUM"
                validate_inp(inp)
                if proptype not in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}:
                    continue
                try:
                    prop = PropGen.Gen(proptype, nname, inp_name, inp)
                    reg_name = bp.get_prop_reg_name(inp_name)
                    properties[reg_name] = prop
                except Exception as e:
                    # 打印头部虚线
                    width = 80
                    try:
                        width = os.get_terminal_size().columns - 11  # len("[SDN-ERR]: ")
                    except OSError:
                        ...
                    logger.error("-" * width)
                    logger.error("Enum Hashable Error: %s", e)
                    logger.error("Node Name: %s", nname)
                    logger.error("Input Name: %s", inp_name)
                    logger.error("Input Type: %s", proptype)
                    logger.error("Input Value: %s", inp[0])
                    logger.error("-" * width)
                    skip = True
                    continue

            bp.extra_properties(properties, nname, ndesc)
            # spec_extra_properties(properties, nname, ndesc)
            fields = {
                "init": init,
                "inp_types": inp_types,
                "out_types": out_types,
                "class_type": nname,
                "bl_label": nname,
                "__annotations__": properties,
                "__metadata__": ndesc
            }
            if skip:
                logger.warning("Skip Reg Node: %s", nname)
                continue
            NodeDesc = type(nname, (NodeBase,), fields)
            NodeDesc.dcolor = (rand() / 2, rand() / 2, rand() / 2)
            node_clss.append(NodeDesc)
        return node_clss


class NodeRegister:
    CLSS_MAP: dict[str, NodeBase] = {}

    @classmethod
    def is_new(cls, node_cls: NodeBase) -> bool:
        if node_cls.bl_label not in cls.CLSS_MAP:
            return True
        old = cls.CLSS_MAP[node_cls.bl_label]
        if issubclass(node_cls, NodeBase):
            # 节点描述信息发生变化时重新注册
            if old.__metadata__ == node_cls.__metadata__:
                return False
            # 调试节点描述信息变更
            # a = old.__metadata__
            # b = node_cls.__metadata__
            # import sys
            # p = Path(__file__).parent.parent.joinpath("TestLib").as_posix()
            # if sys.path[-1] != p:
            #     sys.path.append(p)
            # from deepdiff import DeepDiff
            # diff = DeepDiff(a, b)
            # logger.debug(f"Diff: {node_cls.bl_label}")
            # for k, v in diff.items():
            #     logger.debug(f"{k}: {v}")
            return True
        # 不是节点时不更新
        return False

    @classmethod
    def reg_cls(cls, clss: NodeBase):
        if not cls.is_new(clss):
            return
        is_in = clss.bl_label in cls.CLSS_MAP
        cls.unreg_cls(clss)
        bpy.utils.register_class(clss)
        cls.CLSS_MAP[clss.bl_label] = clss
        if is_in:
            logger.warning(f"{clss.bl_label} is updated")
        return clss

    @classmethod
    def reg_clss(cls, clss):
        diff_clss = [c for c in clss if cls.reg_cls(c)]
        return diff_clss

    @classmethod
    def unreg_cls(cls, _cls: NodeBase):
        if _cls.bl_label not in cls.CLSS_MAP:
            return
        bpy.utils.unregister_class(cls.CLSS_MAP.pop(_cls.bl_label))

    @classmethod
    def unreg_unused(cls, clss):
        label_map = {_c.bl_label: _c for _c in clss}
        for label in list(cls.CLSS_MAP):
            if label in label_map:
                continue
            bpy.utils.unregister_class(cls.CLSS_MAP.pop(label))
            logger.warning(f"Unused {label} is unregistered")

    @classmethod
    def unreg_clss(cls, clss):
        for _cls in clss:
            cls.unreg_cls(_cls)

    @classmethod
    def unreg_all(cls):
        for _cls in cls.CLSS_MAP.values():
            bpy.utils.unregister_class(_cls)
        cls.CLSS_MAP.clear()


class Images(bpy.types.PropertyGroup):
    image: bpy.props.PointerProperty(type=bpy.types.Image)


clss = [SDNConfig, MLTText, MLTRec, MLTWords_UL_UIList, MLTText_UL_UIList, Ops_Switch_Socket_Disp, Ops_Switch_Socket_Widget, Ops_Add_SaveImage, Set_Render_Res, GetSelCol, AdvTextEdit, Ops_Active_Tex, Ops_Link_Mask, Images]

reg, unreg = bpy.utils.register_classes_factory(clss)


def notify_draw():
    from .tree import CFNodeTree, TREE_TYPE
    from .node_process import display_text
    tree: CFNodeTree = get_default_tree()
    if not tree:
        return
    if tree.bl_idname != TREE_TYPE:
        return
    i, o = tree.get_in_out_node()
    if not i or not o:
        return
    # 绘制警告信息
    view2d = bpy.context.region.view2d
    if not view2d:
        return
    size = 20 * ui_scale()
    x = y = 50
    us = ui_scale()
    display_text(_T("Warning:"), (x * us, (y + 60) * us), size, (0, 1, 0.0, 1.0))
    display_text(_T("Don't link to GroupIn/Out node"), ((x + 40) * us, (y + 30) * us), size, (0, 1, 0.0, 1.0))
    display_text(_T("Corresponding link will auto connect after exiting the group editing"), ((x + 40) * us, y * us), size, (0, 1, 0.0, 1.0))
    # size = calc_size(view2d, vsize)
    # for n in [i, o]:
    #     loc = n.location.copy()
    #     loc.y += 10
    #     pos = VecWorldToRegScale(loc)
    #     display_text("禁止手动连接到此节点", pos, size, (0, 1, 0.0, 1.0))

    # head = f"[{n.name}] {_T('Executing')}"
    # blf.size(FONT_ID, size)
    # loc.x += blf.dimensions(FONT_ID, head)[0] / size * vsize
    # pos = VecWorldToRegScale(loc)
    # display_text(" --2-- ", pos, size * 1.5, (1, 1, 0.0, 1.0))


handle = bpy.types.SpaceNodeEditor.draw_handler_add(notify_draw, (), 'WINDOW', 'POST_PIXEL')


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
