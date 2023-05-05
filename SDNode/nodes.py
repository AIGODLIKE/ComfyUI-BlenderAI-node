from __future__ import annotations
import bpy
import random
import os
import re
import json
import textwrap
from math import ceil
from typing import Any
from pathlib import Path
from random import random as rand
from functools import partial
from .utils import gen_mask, SELECTED_COLLECTIONS
from ..utils import logger, update_screen, Icon, _T
from ..datas import ENUM_ITEMS_CACHE
from ..preference import get_pref
from ..timer import Timer
from ..translation import ctxt
from .manager import url, Task

NODES_POLL = {}
Icon.reg_none(Path(__file__).parent / "NONE.png")
PREVICONPATH = {}
PATH_CFG = Path(__file__).parent / "PATH_CFG.json"
PROP_NAME_HEAD = "sdn_"
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


def get_reg_name(inp_name):
    if inp_name in {"width", "height"}:
        return PROP_NAME_HEAD + inp_name
    return inp_name


def get_fixed_seed():
    return int(random.randrange(4294967294))


class NodeBase(bpy.types.Node):
    bl_width_min = 200.0
    bl_width_max = 2000.0
    order: bpy.props.IntProperty(default=-1)
    id: bpy.props.StringProperty(default="-1")
    pool = set()

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

    def apply_unique_id(self):
        self.id = self.unique_id()
        return self.id

    def draw_label(self):
        return self.name

    def update(self):
        self.remove_multi_link()
        self.remove_invalid_link()

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
                if fs.bl_idname == ts.bl_idname:
                    continue
                if not hasattr(bpy.context.space_data, "edit_tree"):
                    continue
                bpy.context.space_data.edit_tree.links.remove(l)

    def get_from_link(self, socket: bpy.types.NodeSocket):
        if not socket.is_linked:
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

    def serialize(self, execute=True):
        inputs = {}
        for inp_name in self.inp_types:
            # inp = self.inp_types[inp_name]
            reg_name = get_reg_name(inp_name)
            if inp := self.inputs.get(reg_name):
                link = self.get_from_link(inp)
                if not link:
                    continue
                inputs[inp_name] = [link.from_node.id, link.from_socket.slot_index]
            else:
                # 添加 非socket
                inputs[inp_name] = getattr(self, reg_name)
        cfg = {
            "inputs": inputs,
            "class_type": self.class_type
        }
        spec_serialize(self, cfg, execute)
        return cfg

    def load(self, data, with_id=True):
        self.pool.discard(self.id)
        self.location[:] = [data["pos"][0], -data["pos"][1]]
        self.width, self.height = [data["size"]["0"], -data["size"]["1"]]
        title = data.get("title", "")
        if self.class_type in {"KSampler", "KSamplerAdvanced"}:
            logger.info(_T("Saved Title Name -> ") + title)  # do not replace name
        elif title:
            self.name = title
        if with_id:
            try:
                self.id = str(data["id"])
                self.pool.add(self.id)
            except BaseException:
                self.apply_unique_id()
        if self.class_type == "KSamplerAdvanced":
            data["widgets_values"].pop(2)
        if self.class_type == "KSampler":
            data["widgets_values"].pop(1)
        for inp_name in self.inp_types:
            reg_name = get_reg_name(inp_name)
            if reg_name in self.inputs:
                continue
            try:
                v = data["widgets_values"].pop(0)
                setattr(self, reg_name, v)
            except TypeError as e:
                if inp_name in {"seed", "noise_seed"}:
                    setattr(self, reg_name, str(v))
                elif (enum := re.findall(' enum "(.*?)" not found', str(e), re.S)):
                    logger.warn(f"{_T('|IGNORED|')} {self.class_type} -> {inp_name} -> {_T('Not Found Item')}: {enum[0]}")
                else:
                    logger.error(f"|{e}|")
            except IndexError:
                logger.info(f"{_T('|IGNORED|')} -> {_T('Load')}<{self.class_type}>{_T('Params not matching with current node')}")
            except Exception as e:
                logger.error(f"{_T('Params Loading Error')} {self.class_type} -> {self.class_type}.{inp_name}")
                logger.error(f" -> {e}")

    def dump(self):
        tree = bpy.context.space_data.edit_tree
        all_links: bpy.types.NodeLinks = tree.links[:]

        inputs = []
        outputs = []
        widgets_values = []
        for inp_name in self.inp_types:
            # inp = self.inp_types[inp_name]
            reg_name = get_reg_name(inp_name)
            if inp := self.inputs.get(reg_name):
                link = self.get_from_link(inp)
                if not link:
                    continue

                inp_info = {"name": inp_name,
                            "type": link.from_socket.bl_idname,
                            "link": all_links.index(inp.links[0]),
                            "slot_index": inp.slot_index}
                inputs.append(inp_info)
            else:
                # 添加 非socket
                widgets_values.append(getattr(self, reg_name))
        if self.class_type == "KSamplerAdvanced":
            widgets_values.insert(2, False)
        if self.class_type == "KSampler":
            widgets_values.insert(1, False)
        for out in self.outputs:
            out_info = {"name": out.name,
                        "type": out.name,
                        "links": [all_links.index(link) for link in out.links],
                        "slot_index": out.index
                        }
            outputs.append(out_info)

        cfg = {
            "id": int(self.id),
            "type": self.class_type,
            "pos": [self.location.x, -self.location.y],
            "size": {"0": self.width, "1": self.height},
            "flags": {},
            "order": self.order,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "title": self.name,
            "properties": {},
            "widgets_values": widgets_values
        }
        return cfg

    def save(self):
        save = {
            "id": 11,
            "type": "SaveImage",
            "pos": [
                1451,
                189
            ],
            "size": {
                "0": 210,
                "1": 58
            },
            "flags": {},
            "order": 2,
            "mode": 0,
            "inputs": [
                {
                    "name": "images",
                    "type": "IMAGE",
                    "link": 11  # id号 或 None
                }
            ],
            "properties": {},
            "widgets_values": [
                "ComfyUI"
            ]
        }
        return save

    def post_fn(self, task):
        ...


class SocketBase(bpy.types.NodeSocket):
    allowLink = set()

    def linkLimitCheck(self, context):
        self.allowLink.add(self.bl_label)
        # 连接限制
        for link in list(self.links):
            if link.from_node.bl_label not in self.allowLink:
                logger.warn(f"{_T('Remove Link')}:{link.from_node.bl_label}",)
                context.space_data.edit_tree.links.remove(link)

    color: bpy.props.FloatVectorProperty(size=4, default=(1, 0, 0, 1))

    def draw_color(self, context, node):
        return self.color


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


def parse_node():
    logger.warn(_T("Parsing Node Start"))
    path = Path(__file__).parent / "object_info.json"
    try:
        import requests
        req = requests.get(f"{url}/object_info")
        if req.status_code != 200:
            return {"FINISHED"}
        object_info = req.json()
        path.write_text(json.dumps(object_info, ensure_ascii=False, indent=2))
    except requests.exceptions.ConnectionError:
        logger.warn(_T("Server Launch Failed"))
        object_info = json.load(path.open("r"))

    nodetree_desc = {}
    nodes_desc = {}
    sockets = set()  # Enum/Int/Float/String/Bool 不需要socket
    # node input type -> {'required', 'optional', 'hidden'}
    # node_inp_type = set()
    # for node in object_info.values():
    #     node_inp_type.update(set(node["input"].keys()))
    # logger.info(f"Node Input Type -> {node_inp_type}")

    for name, desc in object_info.items():
        cat = desc["category"]
        for inp, inp_desc in desc["input"].get("required", {}).items():
            stype = inp_desc[0]
            if isinstance(stype, list):
                sockets.add("ENUM")
            else:
                sockets.add(inp_desc[0])
        for inp, inp_desc in desc["input"].get("optional", {}).items():
            stype = inp_desc[0]
            if isinstance(stype, list):
                sockets.add("ENUM")
            else:
                sockets.add(inp_desc[0])
        for index, out_type in enumerate(desc.get("output", [])):
            desc["output"][index] = [out_type, out_type]
        for index, out_name in enumerate(desc.get("output_name", [])):
            desc["output"][index][1] = out_name
        cpath = cat.split("/")
        nodes_desc[name] = desc
        ncur = nodetree_desc

        while cpath:
            ccur = cpath.pop(0)
            if ccur not in ncur:
                ncur[ccur] = {"items": [], "menus": {}}
            if not cpath:
                ncur[ccur]["items"].append(name)
            else:
                ncur = ncur[ccur]["menus"]

    # input / output / name / category
    # logger.warn(nodes_desc)
    # logger.warn(nodetree_desc)
    nodes_desc_ = {
        'KSampler': {
            'input': {
                'required': {
                    'model': ['MODEL'],
                    'seed': ['INT', {'default': 0, 'min': 0, 'max': 18446744073709551615}],
                    'cfg': ['FLOAT', {'default': 8.0, 'min': 0.0, 'max': 100.0}],
                    'sampler_name': [['euler', 'euler_ancestral']],
                    'scheduler': [['karras', 'normal', 'simple', 'ddim_uniform']],
                    'positive': ['CONDITIONING'],
                    'latent_image': ['LATENT']}},
            'output': ['LATENT'],
            'output_name': ['LATENT'], # optional
            'name': 'KSampler',
            'display_name': "", # optional
            'description': '',
            'category': 'sampling'}
    }
    node_clss = []

    for nname, ndesc in nodes_desc.items():
        opt_types = ndesc["input"].get("optional", {})
        inp_types = ndesc["input"]["required"]
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
                    socket = "ENUM"
                    continue
                if socket in {"ENUM", "INT", "FLOAT", "STRING"}:
                    continue
                # logger.warn(inp)
                in1 = self.inputs.new(socket, inp_name)
                in1.display_shape = "DIAMOND_DOT"
                # in1.link_limit = 0
                in1.index = index
            for index, [out_type, out_name] in enumerate(self.out_types):
                if out_type in {"ENUM", "INT", "FLOAT"}:
                    continue
                out = self.outputs.new(out_type, out_name)
                out.display_shape = "DIAMOND_DOT"
                # out.link_limit = 0
                out.index = index
            self.calc_slot_index()

        def draw_buttons(self, context, layout: bpy.types.UILayout):
            for prop in self.__annotations__:
                if spec_draw(self, context, layout, prop):
                    continue
                layout.column().prop(self, prop, text=prop, text_ctxt=ctxt)

        def find_icon(nname, inp_name, item):
            prev_path_list = get_icon_path(nname).get(inp_name)
            if not prev_path_list:
                return 0
            file_list = []
            for prev_path in prev_path_list:
                if not Path(prev_path).exists():
                    continue
                for file in Path(prev_path).iterdir():
                    file_list.append(file)
            # file_list = [file for prev_path in prev_path_list for file in Path(prev_path).iterdir()]
            for file in file_list:
                if item not in file.stem:
                    continue
                if file.suffix not in {".png", ".jpg", ".jpeg"}:
                    continue
                # logger.info(f"🌟 Found Icon -> {file.name}")
                return Icon.reg_icon(file.absolute())
            # logger.info(f"🌚 No Icon <- {file.name}")
            return Icon["NONE"]

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
            if proptype not in {"ENUM", "INT", "FLOAT", "STRING"}:
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
                            items.append((item, item, "", icon_id, len(items)))
                        return items
                    return wrap

                prop = bpy.props.EnumProperty(items=get_items(nname, reg_name, inp))
            elif proptype == "INT":
                # {'default': 20, 'min': 1, 'max': 10000}
                inp[1]["max"] = min(int(inp[1].get("max", 9999999)), 2**31 - 1)
                inp[1]["min"] = max(int(inp[1].get("min", -999999)), -2**31)
                inp[1]["default"] = int(inp[1].get("default", 0))
                inp[1]["step"] = ceil(inp[1].get("step", 1))

                prop = bpy.props.IntProperty(**inp[1])

                if nname == "KSampler" and inp_name == "seed":
                    def setter(self, v):
                        try:
                            _ = int(v)
                            self["seed"] = v
                        except Exception:
                            ...

                    def getter(self):
                        if "seed" not in self:
                            self["seed"] = "0"
                        return str(self["seed"])
                    prop = bpy.props.StringProperty(default="0", set=setter, get=getter)
                if nname == "KSamplerAdvanced" and inp_name == "noise_seed":
                    def setter(self, v):
                        try:
                            _ = int(v)
                            self["noise_seed"] = v
                        except Exception:
                            ...

                    def getter(self):
                        if "noise_seed" not in self:
                            self["noise_seed"] = "0"
                        return str(self["noise_seed"])
                    prop = bpy.props.StringProperty(default="0", set=setter, get=getter)

            elif proptype == "FLOAT":
                {'default': 8.0, 'min': 0.0, 'max': 100.0}
                prop = bpy.props.FloatProperty(**inp[1])
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

            properties[reg_name] = prop
        spec_properties(properties, nname, ndesc)
        fields = {"init": init,
                  "inp_types": inp_types,
                  "out_types": out_types,
                  "class_type": nname,
                  "bl_label": nname,
                  "draw_buttons": draw_buttons,
                  "__annotations__": properties
                  }
        spec_functions(fields, nname, ndesc)
        NodeDesc = type(nname, (NodeBase,), fields)
        NodeDesc.dcolor = (rand() / 2, rand() / 2, rand() / 2)
        node_clss.append(NodeDesc)
    socket_clss = []
    for stype in sockets:
        {'STYLE_MODEL', 'VAE', 'CLIP_VISION', 'MASK', 'UPSCALE_MODEL', 'FLOAT', 'CLIP_VISION_OUTPUT', 'STRING', 'INT', 'IMAGE', 'MODEL', 'CONDITIONING', 'ENUM', 'CONTROL_NET', 'LATENT', 'CLIP'}
        if stype in {"ENUM", "INT", "FLOAT"}:
            continue

        def draw(self, context, layout, node, text):
            layout.label(text=self.name, text_ctxt=ctxt)
        color = bpy.props.FloatVectorProperty(size=4, default=(rand()**0.5, rand()**0.5, rand()**0.5, 1))
        fields = {"draw": draw, "bl_label": stype, "__annotations__": {"color": color,
                                                                       "index": bpy.props.IntProperty(default=-1),
                                                                       "slot_index": bpy.props.IntProperty(default=-1)}}
        SocketDesc = type(stype, (SocketBase,), fields)
        socket_clss.append(SocketDesc)

    nodes_ = {
        'sampling': {
            'items': ['KSampler', 'KSamplerAdvanced']},
        'conditioning': {
            'items': ['CLIPTextEncode', 'CLIPSetLastLayer', 'ConditioningCombine', 'ConditioningSetArea', 'ControlNetApply'],
            'menus': {'style_model': {'items': ['StyleModelApply']}}},
        '无限圣杯': {
            'items': ['存储', 'ToBlender', 'Mask', '蜡笔']}
    }
    logger.warn(_T("Parsing Node Finished!"))
    return nodetree_desc, node_clss, socket_clss


def spec_properties(properties, nname, ndesc):
    if nname == "输入图像":
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["prev"] = prop

    elif nname == "Mask":
        items = [("Grease Pencil", "Grease Pencil", "", "", 0),
                 ("Object", "Object", "", "", 1),
                 ("Collection", "Collection", "", "", 2),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop

        prop = bpy.props.PointerProperty(type=bpy.types.GreasePencil)
        prop = bpy.props.PointerProperty(type=bpy.types.Object)
        properties["gp"] = prop
        # prop = bpy.props.PointerProperty(type=bpy.types.Object)
        # properties["obj"] = prop
        # prop = bpy.props.PointerProperty(type=bpy.types.Collection)
        # properties["col"] = prop
    elif nname == "预览":
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["prev"] = prop
    elif nname in {"KSampler", "KSamplerAdvanced"}:
        prop = bpy.props.BoolProperty(default=False)
        properties["exe_rand"] = prop


def spec_serialize(self, cfg, execute):
    if not execute:
        return
    if self.class_type == "输入图像":
        if self.mode == "渲染":
            logger.warn(f"{_T('Render')}->{self.image}")
            bpy.context.scene.render.filepath = self.image
            bpy.ops.render.render(write_still=True)
        elif self.mode == "输入":
            ...
    elif self.class_type == "Mask":
        gen_mask(self)
    elif self.class_type == "KSampler":
        cfg["inputs"]["seed"] = int(cfg["inputs"]["seed"])
        if cfg["inputs"]["seed"] == -1:
            cfg["inputs"]["seed"] = get_fixed_seed()
            return
        if not self.exe_rand and not bpy.context.scene.sdn.rand_all_seed:
            return
        cfg["inputs"]["seed"] = get_fixed_seed()
        self.seed = str(cfg["inputs"]["seed"])
    elif self.class_type == "KSamplerAdvanced":
        cfg["inputs"]["noise_seed"] = int(cfg["inputs"]["noise_seed"])
        if cfg["inputs"]["noise_seed"] == "-1":
            cfg["inputs"]["noise_seed"] = get_fixed_seed()
            return
        if not self.exe_rand and not bpy.context.scene.sdn.rand_all_seed:
            return
        cfg["inputs"]["noise_seed"] = get_fixed_seed()
        self.noise_seed = str(cfg["inputs"]["noise_seed"])


def spec_functions(fields, nname, ndesc):
    if nname == "存储":
        def post_fn(self: NodeBase, t):
            logger.debug(f"{self.class_type} {_T('Post Function')}")
            logger.debug(t.res)
            img_paths = t.res.get("output", {}).get("images", [])
            for img in img_paths:
                def f(img): return bpy.data.images.load(img)
                Timer.put((f, img))

        fields["post_fn"] = post_fn
    if nname == "预览":
        def post_fn(self: NodeBase, t: Task):
            img_paths = t.res.get("output", {}).get("images", [])
            if not img_paths:
                return
            img = img_paths[0]
            logger.warn(f"{_T('Load Preview Image')}: {img}")
            def f(img): return setattr(self, "prev", bpy.data.images.load(img))
            Timer.put((f, img))

        fields["post_fn"] = post_fn


def spec_draw(self: NodeBase, context: bpy.types.Context, layout: bpy.types.UILayout, prop: str):
    def show_model_preview(self: NodeBase, context: bpy.types.Context, layout: bpy.types.UILayout, prop: str):
        if self.class_type not in name2path:
            return
        row = layout.row()
        if prop in get_icon_path(self.class_type):
            row.template_icon_view(self, prop, show_labels=True, scale_popup=popup_scale, scale=popup_scale)

    def setwidth(self: NodeBase, w):
        w = max(self.bl_width_min, w)
        w = min(self.bl_width_max, w)
        if self.width == w:
            return

        def delegate(self, w):
            self.width = w

        Timer.put((delegate, self, w))
    popup_scale = 5
    try:
        popup_scale = get_pref().popup_scale
    except BaseException:
        ...
    show_model_preview(self, context, layout, prop)
    if self.class_type == "KSampler":
        if prop == "seed":
            row = layout.row(align=True)
            row.prop(self, "seed", text_ctxt=ctxt)
            row.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=ctxt)
            row.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=ctxt)
            return True
        if prop == "exe_rand":
            return True
    elif self.class_type == "KSamplerAdvanced":
        if prop in {"add_noise", "return_with_leftover_noise"}:
            row = layout.row()
            row.label(text=prop, text_ctxt=ctxt)
            row.prop(self, prop, expand=True, text_ctxt=ctxt)
            return True
        if prop == "noise_seed":
            row = layout.row(align=True)
            row.prop(self, "noise_seed", text_ctxt=ctxt)
            row.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=ctxt)
            row.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=ctxt)
            return True
        if prop == "exe_rand":
            return True

    elif self.class_type == "输入图像":
        if prop == "mode":
            layout.prop(self, "image", text="", text_ctxt=ctxt)
            layout.prop(self, prop, expand=True, text_ctxt=ctxt)
            if self.mode == "渲染":
                layout.label(text="Set Image Path of Render Result(.png)", icon="ERROR")
            return True
        elif prop == "image":
            if os.path.exists(self.image):
                def f(self):
                    Icon.load_icon(self.image)
                    if not (img := Icon.find_image(self.image)):
                        return
                    self.prev = img
                    w = max(self.prev.size[0], self.prev.size[1])
                    setwidth(self, w)
                    update_screen()
                if Icon.try_mark_image(self.image) or not self.prev:
                    Timer.put((f, self))
            elif self.prev:
                def f(self):
                    self.prev = None
                    update_screen()
                Timer.put((f, self))
            return True
        elif prop == "prev":
            if self.prev:
                Icon.reg_icon_by_pixel(self.prev, self.prev.filepath)
                idon_id = Icon[self.prev.filepath]
                layout.template_icon(idon_id, scale=max(self.prev.size[0], self.prev.size[1]) // 20)
            return True

    elif self.class_type == "Mask":
        if prop == "mode":
            layout.prop(self, prop, expand=True, text_ctxt=ctxt)
            if self.mode == "Grease Pencil":
                layout.prop(self, "gp", text="", text_ctxt=ctxt)
            if self.mode == "Object":
                # layout.prop(self, "obj", text="")
                layout.label(text="  Select mask Objects", text_ctxt=ctxt)
            if self.mode == "Collection":
                # layout.prop(self, "col", text="")
                layout.label(text="  Select mask Collections", text_ctxt=ctxt)
            return True
        elif prop in {"gp", "obj", "col"}:
            return True
    elif self.class_type == "预览":
        if self.prev:
            if self.prev.name not in Icon:
                Icon.reg_icon_by_pixel(self.prev, self.prev.name)
                w = max(self.prev.size[0], self.prev.size[1])
                setwidth(self, w)
            idon_id = Icon[self.prev.name]
            layout.template_icon(idon_id, scale=max(self.prev.size[0], self.prev.size[1]) // 20)
        # else:
        #     setwidth(self, 200)
        if prop == "prev":
            return True
    elif self.class_type == "CLIPTextEncode":
        if prop == "text":
            width = int(self.width) // 7
            lines = textwrap.wrap(text=str(self.text), width=width)
            for line in lines:
                layout.label(text=line, text_ctxt=ctxt)
    return False


clss = [GetSelCol, ]
reg, unreg = bpy.utils.register_classes_factory(clss)


def nodes_reg():
    reg()


def nodes_unreg():
    try:
        unreg()
    except BaseException:
        ...
