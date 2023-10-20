import json
import re
import bpy
import random
import os
import textwrap
import urllib.request
import urllib.parse
import tempfile
from functools import partial, lru_cache
from pathlib import Path
from copy import deepcopy
from bpy.types import Context, UILayout
from .utils import gen_mask
from .nodes import NodeBase, Ops_Add_SaveImage, Ops_Link_Mask, Ops_Active_Tex, Set_Render_Res, Ops_Swith_Socket
from .nodes import name2path, get_icon_path, Images
from ..SDNode.manager import Task
from ..timer import Timer
from ..preference import get_pref
from ..kclogger import logger
from ..utils import _T, Icon, update_screen
from ..translations import ctxt, get_reg_name, get_ori_name


def get_sync_rand_node(tree):
    for node in tree.get_nodes():
        # node不是KSampler、KSamplerAdvanced 跳过
        if not hasattr(node, "seed") and node.class_type != "KSamplerAdvanced":
            continue
        if node.sync_rand:
            return node


def get_fixed_seed():
    return int(random.randrange(4294967294))


def is_bool_list(some_list: list):
    if not some_list:
        return False
    return isinstance(some_list[0], bool)


def draw_prop_with_link(layout, self, prop, swlink, row=True, pre=None, post=None, **kwargs):
    layout = Ops_Swith_Socket.draw_prop(layout, self, prop, row, swlink)
    if pre:
        pre(layout)
    layout.prop(self, prop, **kwargs)
    if post:
        post(layout)
    return layout


def setwidth(self: NodeBase, w, count=1):
    if not w:
        return 0
    oriw = w
    w = max(self.bl_width_min, w)
    fpis = get_pref().fixed_preview_image_size
    if fpis:
        pw = get_pref().preview_image_size
        w = min(oriw, pw)
    sw = w
    w *= count

    def delegate(self, w, fpis):
        """
        可能会因为 width 访问导致crash, 可以先清理Timer
        """
        if not fpis:
            self.bl_width_max = 8192
            self.bl_width_min = 32
        if self.width == w and not fpis:
            return
        self.width = w
        if self.bl_width_max < w or fpis:
            self.bl_width_max = w

    Timer.put((delegate, self, w, fpis))
    return sw


class BluePrintBase:
    comfyClass = ""

    def new_btn_enable(s, self, layout, context):
        return True

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        def show_model_preview(self: NodeBase, context: bpy.types.Context, layout: bpy.types.UILayout, prop: str):
            if self.class_type not in name2path:
                return False
            if prop not in get_icon_path(self.class_type):
                return False
            col = draw_prop_with_link(layout, self, prop, swlink, text="", row=False)
            col.template_icon_view(self, prop, show_labels=True, scale_popup=popup_scale, scale=popup_scale)
            return True

        # 多行文本处理
        md = self.get_meta(prop)
        if md and md[0] == "STRING" and len(md) > 1 and isinstance(md[1], dict) and md[1].get("multiline",):
            width = int(self.width) // 7
            lines = textwrap.wrap(text=str(getattr(self, prop)), width=width)
            for line in lines:
                layout.label(text=line, text_ctxt=self.get_ctxt())
            row = draw_prop_with_link(layout, self, prop, swlink)
            row.operator("sdn.enable_mlt", text="", icon="TEXT")
            return True

        popup_scale = 5
        try:
            popup_scale = get_pref().popup_scale
        except BaseException:
            ...
        if show_model_preview(self, context, layout, prop):
            return True
        if hasattr(self, "seed"):
            if prop == "seed":
                row = draw_prop_with_link(layout, self, prop, swlink, text=prop, text_ctxt=self.get_ctxt())
                row.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                row.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                row.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
                return True
            if prop in {"exe_rand", "sync_rand"}:
                return True
        elif hasattr(self, "noise_seed"):
            if prop in {"add_noise", "return_with_leftover_noise"}:
                def dpre(layout): layout.label(text=prop, text_ctxt=self.get_ctxt())
                draw_prop_with_link(layout, self, prop, swlink, expand=True, pre=dpre, text_ctxt=self.get_ctxt())
                return True
            if prop == "noise_seed":
                def dpost(layout):
                    layout.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                    layout.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                    layout.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
                draw_prop_with_link(layout, self, prop, swlink, post=dpost, text_ctxt=self.get_ctxt())
                return True
            if prop in {"exe_rand", "sync_rand"}:
                return True
        elif self.class_type in {"OpenPoseFull", "OpenPoseHand", "OpenPoseMediaPipeFace", "OpenPoseDepth", "OpenPose", "OpenPoseFace", "OpenPoseLineart", "OpenPoseFullExtraLimb", "OpenPoseKeyPose", "OpenPoseCanny", }:
            return True
        elif self.get_blueprints().spec_draw(self, context, layout, prop, swlink):
            return True
        return False

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        return False

    def extra_properties(s, properties, nname, ndesc):
        if "seed" in properties or "noise_seed" in properties:
            prop = bpy.props.BoolProperty(default=False)
            properties["exe_rand"] = prop

            def update_sync_rand(self: NodeBase, context):
                if not self.sync_rand:
                    return
                tree = self.get_tree()
                for node in tree.get_nodes():
                    # if (not hasattr(node, "seed") and node.class_type != "KSamplerAdvanced") or node == self:
                    #     continue
                    if node == self:
                        continue
                    if not (hasattr(node, "seed") or hasattr(node, "noise_seed")):
                        continue
                    node.sync_rand = False
            prop = bpy.props.BoolProperty(default=False, name="Sync Rand", description="Sync Rand", update=update_sync_rand)
            properties["sync_rand"] = prop
        bp = get_blueprints(nname)
        bp.spec_extra_properties(properties, nname, ndesc)

    def spec_extra_properties(s, properties, nname, ndesc):
        ...

    def pre_filter(s, nname, desc):
        for k in {"required", "optional"}:
            for inp, inp_desc in desc["input"].get(k, {}).items():
                stype = deepcopy(inp_desc[0])
                if not stype:
                    continue
                if isinstance(stype, list) and is_bool_list(stype):
                    # 处理 bool 列表
                    logger.warn(f"{_T('Non-Standard Enum Detected')}: {nname}[{inp}] -> {stype}")
                if not (isinstance(stype, list) and isinstance(stype[0], dict)):
                    continue
                rep = [sti["content"] for sti in stype if "content" in sti]
                inp_desc[0] = rep if rep else stype
                if rep:
                    logger.warn(f"{_T('Non-Standard Enum Detected')}: {nname}[{inp}] -> {stype}")

        return desc

    def load_specific(s, self: NodeBase, data, with_id=True):
        ...

    def load_pre(s, self: NodeBase, data, with_id=True):
        return data

    def load(s, self: NodeBase, data, with_id=True):
        data = s.load_pre(self, data, with_id)
        self.pool.discard(self.id)
        self.location[:] = [data["pos"][0], -data["pos"][1]]
        if isinstance(data["size"], list):
            self.width, self.height = [data["size"][0], -data["size"][1]]
        else:
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
        # 处理 inputs
        for inp in data.get("inputs", []):
            name = inp.get("name", "")
            if not self.is_base_type(name):
                continue
            new_socket = self.switch_socket(name, True)
            if si := inp.get("slot_index"):
                new_socket.slot_index = si
            md = self.get_meta(name)
            if isinstance(md, list):
                continue
            if not (default := inp.get("widget", {}).get("config", {}).get("default")):
                continue
            reg_name = get_reg_name(name)
            setattr(self, reg_name, default)

        s.load_specific(self, data, with_id)
        for inp_name in self.inp_types:
            if not self.is_base_type(inp_name):
                continue
            reg_name = get_reg_name(inp_name)
            try:
                v = data["widgets_values"].pop(0)
                v = type(getattr(self, reg_name))(v)
                setattr(self, reg_name, v)
            except TypeError as e:
                if inp_name in {"seed", "noise_seed"}:
                    setattr(self, reg_name, str(v))
                elif (enum := re.findall(' enum "(.*?)" not found', str(e), re.S)):
                    logger.warn(f"{_T('|IGNORED|')} {self.class_type} -> {inp_name} -> {_T('Not Found Item')}: {enum[0]}")
                else:
                    logger.error(f"|{e}|")
            except IndexError:
                logger.info(f"{_T('|IGNORED|')} -> {_T('Load')}<{self.class_type}>{_T('Params not matching with current node')} " + reg_name)
            except Exception as e:
                logger.error(f"{_T('Params Loading Error')} {self.class_type} -> {self.class_type}.{inp_name}")

                logger.error(f" -> {e}")

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        """
        ```python
           cfg = {
            "id": ...,
            "type": ...,
            "pos": ...,
            "size": ...,
            "flags": {},
            "order": ...,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "title": ...,
            "properties": {},
            "widgets_values": {}
        }
        ```
        """
        ...

    def dump(s, self: NodeBase, selected_only=False):
        tree = self.get_tree()
        all_links: list[bpy.types.NodeLink] = tree.links[:]

        inputs = []
        outputs = []
        widgets_values = []
        # 单独处理 widgets_values
        for inp_name in self.inp_types:
            if not self.is_base_type(inp_name):
                continue
            widgets_values.append(getattr(self, get_reg_name(inp_name)))
        for inp in self.inputs:
            inp_name = inp.name
            reg_name = get_reg_name(inp_name)
            ori_name = get_ori_name(inp_name)
            md = self.get_meta(reg_name)
            inp_info = {"name": ori_name,
                        "type": inp.bl_idname,
                        "link": None}
            link = self.get_from_link(inp)
            is_base_type = self.is_base_type(inp_name)
            if link:
                if not selected_only:
                    inp_info["link"] = all_links.index(inp.links[0])
                elif inp.links[0].from_node.select:
                    inp_info["link"] = all_links.index(inp.links[0])
            if is_base_type:
                if not self.query_stat(inp.name) or not md:
                    continue
                inp_info["widget"] = {"name": ori_name,
                                      "config": md
                                      }
                inp_info["type"] = ",".join(md[0]) if isinstance(md[0], list) else md[0]
            inputs.append(inp_info)
        for i, out in enumerate(self.outputs):
            out_info = {"name": out.name,
                        "type": out.name,
                        }
            if not selected_only:
                out_info["links"] = [all_links.index(link) for link in out.links]
            elif out.links:
                out_info["links"] = [all_links.index(link) for link in out.links if link.to_node.select]
            out_info["slot_index"] = i
            outputs.append(out_info)
        cfg = {
            "id": int(self.id),
            "type": self.class_type,
            "pos": [self.location.x, -self.location.y],
            "size": {"0": self.width, "1": self.height},
            "flags": {},
            "order": self.sdn_order,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "title": self.name,
            "properties": {},
            "widgets_values": widgets_values
        }
        __locals_copy__ = locals()
        __locals_copy__.pop("s")
        s.dump_specific(**__locals_copy__)
        return cfg

    def serialize_pre_specific(s, self: NodeBase):
        ...

    def serialize_pre(s, self: NodeBase):
        if hasattr(self, "seed"):
            tree = self.get_tree()
            if (snode := get_sync_rand_node(tree)) and snode != self:
                return
            if not self.exe_rand and not bpy.context.scene.sdn.rand_all_seed:
                return
            self.seed = str(get_fixed_seed())
        s.serialize_pre_specific(self)

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if self.class_type in {"OpenPoseFull", "OpenPoseHand", "OpenPoseMediaPipeFace", "OpenPoseDepth", "OpenPose", "OpenPoseFace", "OpenPoseLineart", "OpenPoseFullExtraLimb", "OpenPoseKeyPose", "OpenPoseCanny", }:
            rpath = Path(bpy.path.abspath(bpy.context.scene.render.filepath)) / "MultiControlnet"
            cfg["inputs"]["image"] = rpath.as_posix()
            cfg["inputs"]["frame"] = bpy.context.scene.frame_current

    def serialize(s, self: NodeBase, execute=False):
        inputs = {}
        for inp_name in self.inp_types:
            # inp = self.inp_types[inp_name]
            reg_name = get_reg_name(inp_name)
            if inp := self.inputs.get(reg_name):
                link = self.get_from_link(inp)
                if link:
                    from_node = link.from_node
                    if from_node.bl_idname == "PrimitiveNode":
                        # 添加 widget
                        inputs[inp_name] = getattr(self, reg_name)
                    else:
                        # 添加 socket
                        inputs[inp_name] = [link.from_node.id, link.from_node.outputs[:].index(link.from_socket)]
                elif self.get_meta(inp_name):
                    if hasattr(self, reg_name):
                        # 添加 widget
                        inputs[inp_name] = getattr(self, reg_name)
                    # else:
                    #     # 添加 socket
                    #     inputs[inp_name] = [None]
            else:
                # 添加 widget
                inputs[inp_name] = getattr(self, reg_name)
        cfg = {
            "inputs": inputs,
            "class_type": self.class_type
        }
        if execute:
            # 公共部分
            if hasattr(self, "seed"):
                cfg["inputs"]["seed"] = int(cfg["inputs"]["seed"])
            if hasattr(self, "noise_seed"):
                cfg["inputs"]["noise_seed"] = int(cfg["inputs"]["noise_seed"])
            s.serialize_specific(self, cfg, execute)
        return cfg

    def pre_fn(s, self: NodeBase):
        # logger.debug(f"{self.class_type} {_T('Pre Function')}")
        ...

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"BluePrintBase: {self.class_type} {_T('Post Function')}->{result}")

    def make_serialze(s, self: NodeBase):
        return (self.serialize(), self.pre_fn, self.post_fn)


class WD14Tagger(BluePrintBase):
    comfyClass = "WD14Tagger|pysssss"

    def pre_filter(s, nname, desc):
        desc["input"]["required"]["tags"] = ["STRING", {"default": "", "multiline": True}]

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        cfg["widgets_values"] = cfg["widgets_values"][:4]

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        text = result.get("output", {}).get("tags", [])
        text = "".join(text)

        def f(node, t):
            node.tags = t

        Timer.put((f, self, text))


class LoraLoaderPysssss(BluePrintBase):
    comfyClass = "LoraLoader|pysssss"

    def load_pre(s, self: NodeBase, data, with_id=True):
        if not data["widgets_values"]:
            return data
        lora_name = data["widgets_values"][0]
        if isinstance(lora_name, dict) and "content" in lora_name:
            lora_name = lora_name["content"]
        data["widgets_values"][0] = lora_name
        return data

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        content = cfg["widgets_values"][0]
        cfg["widgets_values"][0] = {"content": content, "image": None}


class CheckpointLoaderPysssss(BluePrintBase):
    comfyClass = "CheckpointLoader|pysssss"

    def load_pre(s, self: NodeBase, data, with_id=True):
        if not data["widgets_values"]:
            return data
        ckpt_name = data["widgets_values"][0]
        if isinstance(ckpt_name, dict) and "content" in ckpt_name:
            ckpt_name = ckpt_name["content"]
        data["widgets_values"][0] = ckpt_name
        return data

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        content = cfg["widgets_values"][0]
        cfg["widgets_values"][0] = {"content": content, "image": None}


class PreviewTextNode(BluePrintBase):
    comfyClass = "PreviewTextNode"

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        text = result.get("output", {}).get("string", [])
        if text and isinstance(text[0], str):
            self.text = text[0]

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        inputs = cfg["inputs"]
        for inp in inputs:
            if inp.get("name") == "text" and "widget" in inp:
                inp.pop("widget")


class TextToConsole(BluePrintBase):
    comfyClass = "Text to Console"

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        inputs = cfg["inputs"]
        for inp in inputs:
            if inp.get("name") == "text" and "widget" in inp:
                inp.pop("widget")


class MultiAreaConditioning(BluePrintBase):
    comfyClass = "MultiAreaConditioning"

    def spec_extra_properties(s, properties, nname, ndesc):
        config = [{"x": 0,
                   "y": 0,
                   "sdn_width": 0,
                   "sdn_height": 0,
                   "strength": 1.0,
                   "col": (1, 0, 1, 0.5)
                   },
                  {"x": 0,
                   "y": 0,
                   "sdn_width": 0,
                   "sdn_height": 0,
                   "strength": 1.0,
                   "col": (0, 1, 1, 0.5)
                   }]

        def config_set(self, value):
            self["config"] = value

        def config_get(self):
            if 'config' not in self:
                self['config'] = json.dumps(config)
            return self['config']

        prop = bpy.props.StringProperty(default=json.dumps(config), set=config_set, get=config_get)
        properties["config"] = prop

        def update(self):
            config = json.loads(self.config)
            c = config[self.index]
            for k in c:
                if k not in self:
                    continue
                c[k] = getattr(self, k)
            self.config = json.dumps(config)

        def resolutionX_set(self, value):
            self['resolutionX'] = (value // 64) * 64

        def resolutionX_get(self):
            if 'resolutionX' not in self:
                self['resolutionX'] = 0
            return self['resolutionX']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=resolutionX_set, get=resolutionX_get)
        properties["resolutionX"] = prop

        def resolutionY_set(self, value):
            self['resolutionY'] = (value // 64) * 64

        def resolutionY_get(self):
            if 'resolutionY' not in self:
                self['resolutionY'] = 0
            return self['resolutionY']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=resolutionY_set, get=resolutionY_get)
        properties["resolutionY"] = prop

        def update_index(self, context):
            config = json.loads(self.config)
            c = config[self.index]
            for k in c:
                if k not in self:
                    continue
                self[k] = c[k]

        prop = bpy.props.IntProperty(default=0, min=0, max=1, update=update_index)
        properties["index"] = prop

        def x_set(self, value):
            self['x'] = (value // 64) * 64
            update(self)

        def x_get(self):
            if 'x' not in self:
                self['x'] = 0
            return self['x']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=x_set, get=x_get)
        properties["x"] = prop

        def y_set(self, value):
            self['y'] = (value // 64) * 64
            update(self)

        def y_get(self):
            if 'y' not in self:
                self['y'] = 0
            return self['y']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=y_set, get=y_get)
        properties["y"] = prop

        def sdn_width_set(self, value):
            self['sdn_width'] = (value // 64) * 64
            update(self)

        def sdn_width_get(self):
            if 'sdn_width' not in self:
                self['sdn_width'] = 0
            return self['sdn_width']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=sdn_width_set, get=sdn_width_get)
        properties["sdn_width"] = prop

        def sdn_height_set(self, value):
            self['sdn_height'] = (value // 64) * 64
            update(self)

        def sdn_height_get(self):
            if 'sdn_height' not in self:
                self['sdn_height'] = 0
            return self['sdn_height']
        prop = bpy.props.IntProperty(default=0, min=0, max=4096, set=sdn_height_set, get=sdn_height_get)
        properties["sdn_height"] = prop

        def update_strength(self, context):
            update(self)
        prop = bpy.props.FloatProperty(default=1.0, min=0, max=10, update=update_strength)
        properties["strength"] = prop

    def spec_draw(s, self: NodeBase, context, layout, prop: str, swlink=True) -> bool:
        if prop == "config":
            return True
        return False

    def load_specific(s, self: NodeBase, data, with_id=True):
        config = json.loads(getattr(self, "config"))
        for i in range(2):
            d = data["properties"]["values"][i]
            config[i]["x"] = d[0]
            config[i]["y"] = d[1]
            config[i]["sdn_width"] = d[2]
            config[i]["sdn_height"] = d[3]
            config[i]["strength"] = d[4]
        self["config"] = json.dumps(config)
        d = data["properties"]["values"][getattr(self, "index")]
        self["x"] = d[0]
        self["y"] = d[1]
        self["sdn_width"] = d[2]
        self["sdn_height"] = d[3]
        self["strength"] = d[4]
        self["resolutionX"] = data["properties"]["width"]
        self["resolutionY"] = data["properties"]["height"]

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        properties = cfg["properties"]
        widgets_values = cfg["widgets_values"]
        if self.class_type == "MultiAreaConditioning":
            config = json.loads(self["config"])
            properties.clear()
            properties.update({'Node name for S&R': 'MultiAreaConditioning',
                               'width': self["resolutionX"],
                               'height': self["resolutionY"],
                               'values': [[64, 128, 384, 128, 10],
                                          [320, 64, 192, 128, 0.03]]})
            for i in range(2):
                properties["values"][i] = [
                    config[i]["x"],
                    config[i]["y"],
                    config[i]["sdn_width"],
                    config[i]["sdn_height"],
                    config[i]["strength"],
                ]
            widgets_values.clear()
            widgets_values += [self["resolutionX"],
                               self["resolutionY"],
                               None,
                               getattr(self, "index"),
                               *properties["values"][getattr(self, "index")]]


class KSampler(BluePrintBase):
    comfyClass = "KSampler"

    def load_specific(s, self: NodeBase, data, with_id=True):
        v = data["widgets_values"][1]
        if isinstance(v, bool):
            data["widgets_values"][1] = ["fixed", "increment", "decrement", "randomize"][int(v)]


class KSamplerAdvanced(BluePrintBase):
    comfyClass = "KSamplerAdvanced"

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop in {"add_noise", "return_with_leftover_noise"}:
            def dpre(layout): layout.label(text=prop, text_ctxt=self.get_ctxt())
            draw_prop_with_link(layout, self, prop, swlink, expand=True, pre=dpre, text_ctxt=self.get_ctxt())
            return True
        if prop == "noise_seed":
            def dpost(layout):
                layout.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                layout.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                layout.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
            draw_prop_with_link(layout, self, prop, swlink, post=dpost, text_ctxt=self.get_ctxt())
            return True
        if prop in {"exe_rand", "sync_rand"}:
            return True

    def serialize_pre_specific(s, self: NodeBase):
        tree = self.get_tree()
        if (snode := get_sync_rand_node(tree)) and snode != self:
            return
        if not getattr(self, "exe_rand") and not bpy.context.scene.sdn.rand_all_seed:
            return
        self.noise_seed = str(get_fixed_seed())


class Mask(BluePrintBase):
    comfyClass = "Mask"

    def spec_extra_properties(s, properties, nname, ndesc):
        items = [("Grease Pencil", "Grease Pencil", "", "", 0),
                 ("Object", "Object", "", "", 1),
                 ("Collection", "Collection", "", "", 2),
                 ("Focus", "Focus", "", "", 3),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda s, o: o.type == "GPENCIL")
        properties["gp"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Object, poll=lambda s, o: o.type == "CAMERA")
        properties["cam"] = prop
        prop = bpy.props.BoolProperty(default=False)
        properties["disable_render"] = prop
        # prop = bpy.props.PointerProperty(type=bpy.types.Object)
        # properties["obj"] = prop
        # prop = bpy.props.PointerProperty(type=bpy.types.Collection)
        # properties["col"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop == "mode":
            layout.prop(self, prop, expand=True, text_ctxt=self.get_ctxt())
            if self.mode == "Grease Pencil":
                row = layout.row(align=True)
                row.prop(self, "gp", text="", text_ctxt=self.get_ctxt())
                icon = "RESTRICT_RENDER_ON" if self.disable_render else "RESTRICT_RENDER_OFF"
                row.prop(self, "disable_render", text="", icon=icon)
                icon = "HIDE_ON" if bpy.context.scene.sdn.disable_render_all else "HIDE_OFF"
                row.prop(bpy.context.scene.sdn, "disable_render_all", text="", icon=icon)
                row.operator("sdn.mask", text="", icon="ADD").node_name = self.name
            if self.mode == "Object":
                row = layout.row(align=True)
                row.label(text="  Select mask Objects", text_ctxt=self.get_ctxt())
                icon = "RESTRICT_RENDER_ON" if self.disable_render else "RESTRICT_RENDER_OFF"
                row.prop(self, "disable_render", text="", icon=icon)
                icon = "HIDE_ON" if bpy.context.scene.sdn.disable_render_all else "HIDE_OFF"
                row.prop(bpy.context.scene.sdn, "disable_render_all", text="", icon=icon)
            if self.mode == "Collection":
                row = layout.row(align=True)
                row.label(text="  Select mask Collections", text_ctxt=self.get_ctxt())
                icon = "RESTRICT_RENDER_ON" if self.disable_render else "RESTRICT_RENDER_OFF"
                row.prop(self, "disable_render", text="", icon=icon)
                icon = "HIDE_ON" if bpy.context.scene.sdn.disable_render_all else "HIDE_OFF"
                row.prop(bpy.context.scene.sdn, "disable_render_all", text="", icon=icon)
            if self.mode == "Focus":
                row = layout.row(align=True)
                row.prop(self, "cam", text="")
                icon = "RESTRICT_RENDER_ON" if self.disable_render else "RESTRICT_RENDER_OFF"
                row.prop(self, "disable_render", text="", icon=icon)
                icon = "HIDE_ON" if bpy.context.scene.sdn.disable_render_all else "HIDE_OFF"
                row.prop(bpy.context.scene.sdn, "disable_render_all", text="", icon=icon)
                op = row.operator(Ops_Link_Mask.bl_idname, text="", icon="VIEW_CAMERA")
                op.action = "OnlyFocus"
                op.cam_name = self.cam.name if self.cam else ""
                op.node_name = self.name
            return True
        elif prop in {"gp", "obj", "col", "cam", "disable_render"}:
            return True

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if self.disable_render or bpy.context.scene.sdn.disable_render_all:
            return
        gen_mask(self)


class Reroute(BluePrintBase):
    comfyClass = "Reroute"

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        outputs = cfg["outputs"]
        inputs = cfg["inputs"]
        properties = cfg["properties"]
        out = kwargs.get("out")
        all_links = kwargs.get("all_links")
        inputs.clear()
        inputs.append({"name": "", "type": "*", "link": None, })
        if self.inputs[0].is_linked:
            if not selected_only:
                inputs[0]["link"] = all_links.index(self.inputs[0].links[0])
            elif self.inputs[0].links[0].from_node.select:
                inputs[0]["link"] = all_links.index(self.inputs[0].links[0])
        if not self.outputs[0].is_linked:
            outputs[0]["name"] = outputs[0]["type"] = "*"
        else:
            def find_out_node(node: bpy.types.Node):
                output = node.outputs[0]
                if not output.is_linked:
                    return None
                to = output.links[0].to_node
                to_socket = output.links[0].to_socket
                if to.class_type == "Reroute":
                    return find_out_node(to)
                return to_socket
            to_socket = find_out_node(self)
            if out and to_socket:
                outputs[0]["name"] = to_socket.bl_idname
                outputs[0]["type"] = to_socket.bl_idname
        properties.clear()
        properties.update({"showOutputText": True, "horizontal": False})


class PrimitiveNode(BluePrintBase):
    comfyClass = "PrimitiveNode"

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.StringProperty()
        properties["prop"] = prop

    def spec_draw(s, self: NodeBase, context, layout, prop: str, swlink=True):
        if self.outputs[0].is_linked and self.outputs[0].links:
            node = self.outputs[0].links[0].to_node
            # 可能会导致prop在node中找不到的情况(断开连接的时候)
            if not hasattr(node, self.prop):
                return True
            if self.get_blueprints().draw_button(node, context, layout, self.prop, swlink=False):
                return True
            layout.prop(node, get_reg_name(self.prop))
        return True

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        outputs = cfg["outputs"]
        widgets_values = cfg["widgets_values"]
        if self.outputs[0].is_linked and self.outputs[0].links:
            node = self.outputs[0].links[0].to_node
            meta_data = deepcopy(node.get_meta(self.prop))
            output = outputs[0]
            output["name"] = "COMBO" if isinstance(meta_data[0], list) else meta_data[0]
            output["type"] = ",".join(meta_data[0]) if isinstance(meta_data[0], list) else meta_data[0]
            if output["name"] != "COMBO":
                meta_data[1]["default"] = getattr(node, self.prop)
            output["widget"] = {"name": self.prop,
                                "config": meta_data
                                }
            widgets_values.clear()
            widgets_values += [getattr(node, self.prop), "fixed"]

    def serialize_pre_specific(s, self: NodeBase):
        if not self.outputs[0].is_linked:
            return
        prop = getattr(self.outputs[0].links[0].to_node, get_reg_name(self.prop))
        for link in self.outputs[0].links[1:]:
            setattr(link.to_node, get_reg_name(link.to_socket.name), prop)

def get_image_path(data):
    '''data = {"filename": filename, "subfolder": subfolder, "type": folder_type}'''
    url_values = urllib.parse.urlencode(data)
    from .manager import TaskManager
    url = "{}/view?{}".format(TaskManager.server.get_url(), url_values)
    # logger.debug(f'requesting {url} for image data')
    with urllib.request.urlopen(url) as response:
        img_data = response.read()
        img_path = Path(tempfile.gettempdir()) / data.get('filename', 'preview.png')
        with open(img_path, "wb") as f:
            f.write(img_data)
        return img_path


class 预览(BluePrintBase):
    comfyClass = "预览"

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.CollectionProperty(type=Images)
        properties["prev"] = prop
        properties["lnum"] = bpy.props.IntProperty(default=3, min=1, max=10, name="Image num per line")

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop == "lnum":
            return True
        if self.inputs[0].is_linked and self.inputs[0].links:
            for link in self.inputs[0].links[0].from_socket.links:
                if link.to_node.bl_idname == "存储":
                    break
            else:
                layout.operator(Ops_Add_SaveImage.bl_idname, text="", icon="FILE_TICK").node_name = self.name
        if prop == "prev":
            layout.prop(self, "lnum")
            pnum = len(self.prev)
            if pnum == 0:
                return True
            p0 = self.prev[0].image
            w = max(p0.size[0], p0.size[1])
            if w == 0:
                return True
            w = setwidth(self, w, count=min(self.lnum, pnum))
            layout.label(text=f"{p0.file_format} : [{p0.size[0]} x {p0.size[1]}]")
            col = layout.column(align=True)
            for i, p in enumerate(self.prev):
                if i % self.lnum == 0:
                    fcol = col.column_flow(columns=min(self.lnum, pnum), align=True)
                prev = p.image
                if prev.name not in Icon:
                    Icon.reg_icon_by_pixel(prev, prev.name)
                icon_id = Icon[prev.name]
                fcol.template_icon(icon_id, scale=w // 20)
            return True

    def serialize_pre_specific(s, self: NodeBase):
        if self.inputs[0].is_linked:
            return
        self.prev.clear()

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[dict]):
            self.prev.clear()
            for data in img_paths:
                img_path = get_image_path(data)
                if not img_path:
                    continue
                img_path = Path(img_path).as_posix()
                # if isinstance(img_path, dict):
                #     img_path = Path(d).joinpath(img_path.get("filename")).as_posix()
                if not Path(img_path).exists():
                    continue
                try:
                    p = self.prev.add()
                    p.image = bpy.data.images.load(img_path)
                except TypeError:
                    ...
        Timer.put((f, self, img_paths))

PreviewImage = 预览


class 存储(BluePrintBase):
    comfyClass = "存储"

    def spec_extra_properties(s, properties, nname, ndesc):
        items = [("Save", "Save", "", "", 0),
                 ("Import", "Import", "", "", 1),
                 ("ToImage", "ToImage", "", "", 2),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Object)
        properties["obj"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["image"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop == "mode":
            layout.prop(self, prop, expand=True, text_ctxt=self.get_ctxt())
            if self.mode == "Save":
                layout.prop(self, "filename_prefix", text_ctxt=self.get_ctxt())
                layout.prop(self, "output_dir", text_ctxt=self.get_ctxt())
                return True
            elif self.mode == "Import":
                layout.prop(self, "obj", text="")
                if obj := self.obj:
                    def find_tex(root, tex=None) -> list[bpy.types.Image]:
                        tex = tex if tex else []
                        for node in root.node_tree.nodes:
                            if node.type in {"TEX_IMAGE", "TEX_ENVIRONMENT"}:
                                if not node.image:
                                    continue
                                tex.append(node.image)
                            if node.type == "GROUP":
                                find_tex(node, tex)
                        return tex
                    if textures := find_tex(obj.active_material):
                        box = layout.box()
                        for t in textures:
                            row = box.row(align=True)
                            row.label(text=t.name)
                            col = row.column()
                            if t == self.image:
                                col.alert = True
                            op = col.operator(Ops_Active_Tex.bl_idname, text="", icon="REC")
                            op.node_name = self.name
                            op.img_name = t.name
                    if textures and self.image:
                        layout.label(text=f"当前纹理: {self.image.name}")
                return True
            elif self.mode == "ToImage":
                layout.prop(self, "image")
                return True
        return True

    def make_serialze(s, self: NodeBase):
        def __post_fn__(self: NodeBase, t: Task, result: dict, mode, image):
            logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
            img_paths = result.get("output", {}).get("images", [])
            for img in img_paths:
                if mode == "Save":
                    def f(_, img):
                        return bpy.data.images.load(img)
                elif mode in {"Import", "ToImage"}:
                    def f(img_src, img):
                        if not img_src:
                            return
                        img_src.filepath = img
                        img_src.filepath_raw = img
                        img_src.source = "FILE"
                        if img_src.packed_file:
                            img_src.unpack(method="REMOVE")
                        img_src.reload()
                Timer.put((f, image, img))
        post_fn = partial(__post_fn__, self, mode=self.mode, image=self.image)
        return self.serialize(), self.pre_fn, post_fn

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if self.mode not in {"Import", "ToImage"}:
            return
        if "output_dir" in cfg.get("inputs", {}):
            import tempfile
            cfg.get("inputs", {})["output_dir"] = tempfile.gettempdir()
        if "filename_prefix" in cfg.get("inputs", {}):
            cfg.get("inputs", {})["filename_prefix"] = "SDNode"


class 输入图像(BluePrintBase):
    comfyClass = "输入图像"

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["prev"] = prop
        prop = bpy.props.StringProperty(default="", name="Render Layer")
        properties["render_layer"] = prop

        def search_layers(self, context):
            items = []
            if not bpy.context.scene.use_nodes:
                return items
            nodes = bpy.context.scene.node_tree.nodes
            render_layer = nodes.get(self.render_layer, None)
            if not render_layer:
                return items
            for output in render_layer.outputs:
                if not output.enabled:
                    continue
                items.append((output.name, output.name, "", len(items)))
            return items
        prop = bpy.props.EnumProperty(items=search_layers, name="Output Layer")
        properties["out_layers"] = prop
        prop = bpy.props.StringProperty(name="Frames Directory",
                                        subtype="DIR_PATH",
                                        default=Path.home().joinpath("Desktop").as_posix())
        properties["frames_dir"] = prop
        prop = bpy.props.BoolProperty(default=False)
        properties["disable_render"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop == "mode":
            if self.mode == "序列图":
                layout.prop(self, "frames_dir", text="")
            else:
                layout.prop(self, "image", text="", text_ctxt=self.get_ctxt())
            layout.row().prop(self, prop, expand=True, text_ctxt=self.get_ctxt())
            if self.mode == "序列图":
                layout.label(text="Frames Directory", text_ctxt=self.get_ctxt())
            if self.mode == "渲染":
                layout.label(text="Set Image Path of Render Result(.png)", icon="ERROR")
                if bpy.context.scene.use_nodes:
                    row = layout.row(align=True)
                    row.prop_search(self, "render_layer", bpy.context.scene.sdn, "render_layer")
                    icon = "RESTRICT_RENDER_ON" if self.disable_render else "RESTRICT_RENDER_OFF"
                    row.prop(self, "disable_render", text="", icon=icon)
                    icon = "HIDE_ON" if bpy.context.scene.sdn.disable_render_all else "HIDE_OFF"
                    row.prop(bpy.context.scene.sdn, "disable_render_all", text="", icon=icon)
                    layout.prop(self, "out_layers")
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
                elif Icon.find_image(self.image) != self.prev:  # 修复加载A 后加载B图, 再加载A时 不更新
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
                icon_id = Icon[self.prev.filepath]
                row = layout.row(align=True)
                row.label(text=f"{self.prev.file_format} : [{self.prev.size[0]} x {self.prev.size[1]}]")
                row.operator(Set_Render_Res.bl_idname, text="", icon="LOOP_FORWARDS").node_name = self.name
                w = max(self.prev.size[0], self.prev.size[1])
                w = setwidth(self, w)
                layout.template_icon(icon_id, scale=w // 20)
            return True
        elif prop in {"render_layer", "out_layers", "frames_dir", "disable_render"}:
            return True

    def pre_fn(s, self: NodeBase):
        if self.mode != "渲染":
            return
        if self.disable_render or bpy.context.scene.sdn.disable_render_all:
            return

        @Timer.wait_run
        def r():
            logger.warn(f"{_T('Render')}->{self.image}")
            bpy.context.scene.render.filepath = self.image
            if (cam := bpy.context.scene.camera) and (gpos := cam.get("SD_Mask", [])):
                try:
                    for gpo in gpos:
                        gpo.hide_render = True
                except BaseException:
                    ...
            if bpy.context.scene.use_nodes:
                from .utils import set_composite
                nt = bpy.context.scene.node_tree

                with set_composite(nt) as cmp:
                    render_layer: bpy.types.CompositorNodeRLayers = nt.nodes.new("CompositorNodeRLayers")
                    if sel_render_layer := nt.nodes.get(self.render_layer, None):
                        render_layer.scene = sel_render_layer.scene
                        render_layer.layer = sel_render_layer.layer
                    if out := render_layer.outputs.get(self.out_layers):
                        nt.links.new(cmp.inputs["Image"], out)
                    bpy.ops.render.render(write_still=True)
                    nt.nodes.remove(render_layer)
            else:
                bpy.ops.render.render(write_still=True)
        r()


class 材质图(BluePrintBase):
    comfyClass = "材质图"

    def new_btn_enable(s, self, layout, context):
        if self.nodetype == s.comfyClass:
            tree = context.space_data.edit_tree
            mat_iamge_nodes = [n for n in tree.nodes if n.class_type == s.comfyClass]
            return len(mat_iamge_nodes) == 0
        return True

    def spec_extra_properties(s, properties, nname, ndesc):
        items = [("Object", "Object", "", "", 0),
                 ("Selected Objects", "Selected Objects", "", "", 1),
                 ("Collection", "Collection", "", "", 2),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Object)
        properties["obj"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Collection)
        properties["collection"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True) -> bool:
        if prop == "mode":
            layout.prop(self, prop, expand=True, text_ctxt=self.get_ctxt())
            if self.mode == "Object":
                layout.prop(self, "obj", text="")
            elif self.mode == "Selected Objects":
                for obj in bpy.context.selected_objects:
                    if obj.type != "MESH":
                        continue
                    layout.label(text=obj.name)
            elif self.mode == "Collection":
                layout.prop(self, "collection", text="")
        return True


@lru_cache(maxsize=1024)
def get_blueprints(comfyClass, default=BluePrintBase) -> BluePrintBase:
    for cls in BluePrintBase.__subclasses__():
        if cls.comfyClass != comfyClass:
            continue
        return cls()
    return default()
