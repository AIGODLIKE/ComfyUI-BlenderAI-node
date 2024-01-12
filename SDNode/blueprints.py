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

from .nodegroup import LABEL_TAG, SOCK_TAG, SDNGroup
from .nodes import NodeBase
from .utils import gen_mask, THelper, Interface
from .plugins.animatedimageplayer import AnimatedImagePlayer as AIP
from .nodes import NodeBase, Ops_Add_SaveImage, Ops_Link_Mask, Ops_Active_Tex, Set_Render_Res, Ops_Swith_Socket
from .nodes import name2path, get_icon_path, Images
from ..SDNode.manager import Task
from ..timer import Timer
from ..preference import get_pref
from ..kclogger import logger
from ..utils import _T, Icon, update_screen, PrevMgr, rgb2hex, hex2rgb
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


def is_number_list(some_list: list):
    if not some_list:
        return False
    return type(some_list[0]) in (int, float)


def is_all_str_list(some_list: list):
    if not some_list:
        return False
    return set(type(i) for i in some_list) == {str}


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


def link_get(d: dict, path: str):
    if not path:
        return d
    for p in path.split("."):
        d = d.get(p, {})
    return d


class BluePrintBase:
    comfyClass = ""

    def getattr(s, self, prop_name):
        meta = self.get_meta(prop_name)
        v = getattr(self, prop_name)
        if meta and meta[0] and isinstance(meta[0], list):
            t = type(meta[0][0])
            if t == bool and isinstance(v, str):
                return v == "True"
            if isinstance(v, str):
                for i in meta[0]:
                    if str(i) == v:
                        return i
            return type(meta[0][0])(v)
        return v

    def setattr(s, self: NodeBase, prop_name, v):
        v = type(getattr(self, prop_name))(v)
        setattr(self, prop_name, v)

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
            lines = textwrap.wrap(text=str(s.getattr(self, prop)), width=width)
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
        def log_non_standard(stype, nname, inp):
            winfo = str(stype)
            if len(winfo) > 40:
                winfo = winfo[:40] + "...]"
            logger.warn(f"{_T('Non-Standard Enum')}: {nname}.{inp} -> {winfo}")
        for k in {"required", "optional"}:
            for inp, inp_desc in desc["input"].get(k, {}).items():
                stype = deepcopy(inp_desc[0])
                if not stype:
                    continue
                if not is_all_str_list(stype):
                    log_non_standard(stype, nname, inp)
                # if isinstance(stype, list) and is_bool_list(stype):
                #     # 处理 bool 列表
                #     log_non_standard(stype, nname, inp)
                if not (isinstance(stype, list) and isinstance(stype[0], dict)):
                    continue
                rep = [sti["content"] for sti in stype if "content" in sti]
                inp_desc[0] = rep if rep else stype

        return desc

    def load_specific(s, self: NodeBase, data, with_id=True):
        ...

    def load_pre(s, self: NodeBase, data, with_id=True):
        return data

    def load(s, self: NodeBase, data, with_id=True):
        data = s.load_pre(self, data, with_id)
        pool = self.pool_get()
        pool.discard(self.id)
        self.location[:] = [data["pos"][0], -data["pos"][1]]
        size = data.get("size", [200, 200])
        properties = data.get("properties", {})
        self.sdn_hide = properties.get("sdn_hide", False)
        color = data.get("bgcolor", None)
        if color:
            self.color = hex2rgb(color)
            self.use_custom_color = True
        if isinstance(size, list):
            self.width, self.height = [size[0], -size[1]]
        else:
            self.width, self.height = [size["0"], -size["1"]]
        title = data.get("title", "")
        if self.class_type in {"KSampler", "KSamplerAdvanced"}:
            logger.info(_T("Saved Title Name -> ") + title)  # do not replace name
        elif title:
            self.name = title
        if with_id:
            try:
                self.id = str(data["id"])
                pool.add(self.id)
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
            s.setattr(self, reg_name, default)

        s.load_specific(self, data, with_id)
        for inp_name in self.inp_types:
            if not self.is_base_type(inp_name):
                continue
            reg_name = get_reg_name(inp_name)
            try:
                v = data["widgets_values"].pop(0)
                s.setattr(self, reg_name, v)
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
            widgets_values.append(s.getattr(self, get_reg_name(inp_name)))
        for inp in self.inputs:
            inp_name = inp.name
            ori_name = get_ori_name(inp_name)
            md = self.get_meta(ori_name)
            inp_info = {"name": ori_name,
                        "type": inp.bl_idname,
                        "link": None}
            inp_info["label"] = inp.name
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
            "pos": [int(self.location.x), -int(self.location.y)],
            "size": {"0": int(self.width), "1": int(self.height)},
            "flags": {},
            "order": self.sdn_order,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "title": self.name,
            "properties": {"sdn_hide": self.sdn_hide, },
            "widgets_values": widgets_values
        }
        if self.use_custom_color:
            color = rgb2hex(*self.color)
            cfg["bgcolor"] = color
        __locals_copy__ = locals()
        __locals_copy__.pop("s")
        s.dump_specific(**__locals_copy__)
        return cfg

    def serialize_pre_specific(s, self: NodeBase):
        ...

    def serialize_pre(s, self: NodeBase):
        nseed = ""
        if hasattr(self, "seed"):
            nseed = "seed"
        elif hasattr(self, "noise_seed"):
            nseed = "noise_seed"
        if nseed:
            tree = self.get_tree()
            if (snode := get_sync_rand_node(tree)) and snode != self:
                return
            if not s.getattr(self, "exe_rand") and not bpy.context.scene.sdn.rand_all_seed:
                return
            s.setattr(self, nseed, str(get_fixed_seed()))
        s.serialize_pre_specific(self)

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if self.class_type in {"OpenPoseFull", "OpenPoseHand", "OpenPoseMediaPipeFace", "OpenPoseDepth", "OpenPose", "OpenPoseFace", "OpenPoseLineart", "OpenPoseFullExtraLimb", "OpenPoseKeyPose", "OpenPoseCanny", }:
            rpath = Path(bpy.path.abspath(bpy.context.scene.render.filepath)) / "MultiControlnet"
            cfg["inputs"]["image"] = rpath.as_posix()
            cfg["inputs"]["frame"] = bpy.context.scene.frame_current

    def _serialize_input(s, self: NodeBase, inp_name, inputs, parent: NodeBase = None):
        """
        根据 inp_name 计算输入接口或widget值
        1. 当为接口时返回连接情况
        2. 当为widget时返回widget值
        """
        reg_name = get_reg_name(inp_name)
        inp = self.get_input(inp_name)
        # ---------------- widget ----------------
        # 1. 未在输入接口中
        if not inp:
            inputs[inp_name] = s.getattr(self, reg_name)
            return

        link = self.get_from_link(inp)
        # 2. 在输入接口中, 但未连接
        if not link:
            if self.get_meta(inp_name) and hasattr(self, reg_name):
                inputs[inp_name] = s.getattr(self, reg_name)
            return
        # 3. 在输入接口中, 且已连接, 但连接的是 PrimitiveNode
        if link.from_node.bl_idname == "PrimitiveNode":
            inputs[inp_name] = s.getattr(self, reg_name)
            return

        fnode: NodeBase = link.from_node
        fid = fnode.id
        sock_index = fnode.outputs[:].index(link.from_socket)
        # ---------------- socket ----------------
        # 1. 连接起始于组输入
        if fnode.bl_idname == "NodeGroupInput":
            # parent(组节点) { fnode <- self(在组内) }
            sid = link.from_socket.identifier
            pinp = parent.get_input(sid)
            plink = self.get_from_link(pinp)
            # plink为空(outer没连接)
            if not plink:
                if self.get_meta(inp_name) and hasattr(self, reg_name):
                    inputs[inp_name] = s.getattr(self, reg_name)
                return
            pfnode = plink.from_node
            sock_index = pfnode.outputs[:].index(plink.from_socket)
            fid = pfnode.id
        # 2. 连接起始于组节点
        elif fnode.is_group():
            # gonode(真实连接的节点) <- onode(组输出) <- fnode(组) <- self
            fnode: SDNGroup = fnode
            gout_id = link.from_socket[SOCK_TAG]
            inode, onode = fnode.get_in_out_node()
            oinp = onode.get_input(gout_id)
            golink = self.get_from_link(oinp)
            gonode = golink.from_node
            sock_index = gonode.outputs[:].index(golink.from_socket)
            fid = f"{fnode.id}:{gonode.id}"
            # 当gonode 为组输入时: gonode <- fnode:NodeReroute <- self
            if gonode.bl_idname == "NodeGroupInput":
                sid = golink.from_socket.identifier
                pinp = fnode.get_input(sid)
                plink = self.get_from_link(pinp)
                # plink可能为空(outer没连接)
                if not plink:
                    if self.get_meta(inp_name) and hasattr(self, reg_name):
                        inputs[inp_name] = s.getattr(self, reg_name)
                    return
                pfnode = plink.from_node
                sock_index = pfnode.outputs[:].index(plink.from_socket)
                fid = pfnode.id
        # 3. 由外部tree调用
        elif parent:
            fid = f"{parent.id}:{fnode.id}"
        # fnode 可能是 NodeGroupInput 需要转换
        inputs[inp_name] = [fid, sock_index]

    def serialize(s, self: NodeBase, execute=False, parent: NodeBase = None):
        inputs = {}
        for inp_name in self.inp_types:
            # inp = self.inp_types[inp_name]
            s._serialize_input(self, inp_name, inputs, parent)
            continue
            reg_name = get_reg_name(inp_name)
            if inp := self.inputs.get(reg_name):
                link = self.get_from_link(inp)
                if link:
                    from_node = link.from_node
                    if from_node.bl_idname == "PrimitiveNode":
                        # 添加 widget
                        inputs[inp_name] = s.getattr(self, reg_name)
                    else:
                        # 添加 socket
                        fnode: NodeBase = link.from_node
                        fid = fnode.id
                        sock_index = fnode.outputs[:].index(link.from_socket)
                        if fnode.bl_idname == "NodeGroupInput":
                            # 需要拿到 NodeGroup 的 id
                            sid = link.from_socket.identifier
                            pinp = parent.get_input(sid)
                            plink = self.get_from_link(pinp)
                            # plink可能为空(outer没连接)
                            if not plink:
                                if self.get_meta(inp_name) and hasattr(self, reg_name):
                                    inputs[inp_name] = s.getattr(self, reg_name)
                                continue
                            pfnode = plink.from_node
                            sock_index = pfnode.outputs[:].index(plink.from_socket)
                            fid = pfnode.id
                        elif fnode.is_group():
                            fnode: SDNGroup = fnode
                            # 需要拿到 NodeGroup 的 id
                            gout_id = link.from_socket[SOCK_TAG]
                            inode, onode = fnode.get_in_out_node()
                            oinp = onode.get_input(gout_id)
                            golink = self.get_from_link(oinp)
                            gonode = golink.from_node
                            # 有可能 outer_inp <- node_reroute <- outer_out
                            if gonode.bl_idname == "NodeGroupInput":
                                logger.critical(gonode)
                                sid = golink.from_socket.identifier
                                pinp = fnode.get_input(sid)
                                plink = self.get_from_link(pinp)
                                # plink可能为空(outer没连接)
                                if not plink:
                                    if self.get_meta(inp_name) and hasattr(self, reg_name):
                                        inputs[inp_name] = s.getattr(self, reg_name)
                                    continue
                                pfnode = plink.from_node
                                sock_index = pfnode.outputs[:].index(plink.from_socket)
                                fid = pfnode.id
                            else:
                                sock_index = gonode.outputs[:].index(golink.from_socket)
                                fid = f"{fnode.id}:{gonode.id}"
                        elif parent:
                            fid = f"{parent.id}:{fnode.id}"
                        # fnode 可能是 NodeGroupInput 需要转换
                        inputs[inp_name] = [fid, sock_index]
                elif self.get_meta(inp_name):
                    if hasattr(self, reg_name):
                        # 添加 widget
                        inputs[inp_name] = s.getattr(self, reg_name)
                    # else:
                    #     # 添加 socket
                    #     inputs[inp_name] = [None]
            else:
                # 添加 widget
                inputs[inp_name] = s.getattr(self, reg_name)
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

    def make_serialize(s, self: NodeBase, parent: NodeBase = None) -> dict:
        return {self.id: (self.serialize(parent=parent), self.pre_fn, self.post_fn)}

    def free(s, self: NodeBase):
        ...

    def copy(s, self: NodeBase, node):
        ...


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
        config = json.loads(s.getattr(self, "config"))
        for i in range(2):
            d = data["properties"]["values"][i]
            config[i]["x"] = d[0]
            config[i]["y"] = d[1]
            config[i]["sdn_width"] = d[2]
            config[i]["sdn_height"] = d[3]
            config[i]["strength"] = d[4]
        self["config"] = json.dumps(config)
        d = data["properties"]["values"][s.getattr(self, "index")]
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
                               s.getattr(self, "index"),
                               *properties["values"][s.getattr(self, "index")]]


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
        helper = THelper()
        if self.inputs[0].is_linked:
            if not selected_only:
                inputs[0]["link"] = all_links.index(self.inputs[0].links[0])
            elif self.inputs[0].links[0].from_node.select:
                inputs[0]["link"] = all_links.index(self.inputs[0].links[0])
            from_socket = self.inputs[0].links[0].from_socket
            if helper.is_reroute_socket(from_socket):
                inputs[0]["name"] = ""
                inputs[0]["type"] = "*"
        if not self.outputs[0].is_linked:
            outputs[0]["name"] = outputs[0]["type"] = "*"
        else:
            to_socket = helper.find_to_sock(self.outputs[0])
            if out and to_socket:
                outputs[0]["name"] = to_socket.bl_idname
                outputs[0]["type"] = to_socket.bl_idname
            if helper.is_reroute_socket(to_socket):
                outputs[0]["name"] = ""
                outputs[0]["type"] = "*"
            olink = self.outputs[0].links[0]
            ilink = self.inputs[0].links[0]
            if olink.to_node.bl_idname == "NodeGroupOutput" and ilink.from_node.bl_idname != "NodeGroupInput":
                outputs[0]["name"] = ""
                outputs[0]["type"] = "*"
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
                meta_data[1]["default"] = s.getattr(node, self.prop)
            output["widget"] = {"name": self.prop,
                                "config": meta_data
                                }
            widgets_values.clear()
            widgets_values += [s.getattr(node, self.prop), "fixed"]

    def serialize_pre_specific(s, self: NodeBase):
        if not self.outputs[0].is_linked:
            return
        prop = s.getattr(self.outputs[0].links[0].to_node, get_reg_name(self.prop))
        for link in self.outputs[0].links[1:]:
            setattr(link.to_node, get_reg_name(link.to_socket.name), prop)


def get_image_path(data, suffix="png") -> Path:
    '''data = {"filename": filename, "subfolder": subfolder, "type": folder_type}'''
    url_values = urllib.parse.urlencode(data)
    from .manager import TaskManager
    url = "{}/view?{}".format(TaskManager.server.get_url(), url_values)
    # logger.debug(f'requesting {url} for image data')
    with urllib.request.urlopen(url) as response:
        img_data = response.read()
        img_path = Path(tempfile.gettempdir()) / data.get('filename', f'preview.{suffix}')
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

    def make_serialize(s, self: NodeBase, parent: NodeBase = None) -> dict:
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
        return {self.id: (self.serialize(parent=parent), self.pre_fn, post_fn)}

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
        if self.mode not in {"渲染", "视口"}:
            return
        if self.disable_render or bpy.context.scene.sdn.disable_render_all:
            return

        @Timer.wait_run
        def r():
            if self.mode == "视口":
                # 使用临时文件
                self.image = Path(tempfile.gettempdir()).joinpath("viewport.png").as_posix()
            logger.warn(f"{_T('Render')}->{self.image}")
            old = bpy.context.scene.render.filepath
            bpy.context.scene.render.filepath = self.image
            if self.mode == "视口":
                # 场景相机可能为空
                if not bpy.context.scene.camera:
                    err_info = _T("No Camera in Scene") + " -> " + bpy.context.scene.name
                    raise Exception(err_info)
                bpy.ops.render.opengl(write_still=True, view_context=get_pref().view_context)
                bpy.context.scene.render.filepath = old
                return
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
            bpy.context.scene.render.filepath = old
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


class 截图(BluePrintBase):
    comfyClass = "截图"

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        if prop in {"x1", "y1", "x2", "y2"}:
            return True
        if prop == "capture":
            layout.prop(self, prop, text="", icon="CLIPUV_DEHLT", toggle=True, text_ctxt=self.get_ctxt())
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
        return super().draw_button(self, context, layout, prop, swlink)

    def _capture(s, self: NodeBase):
        from ..External.mss import mss
        from ..External.mss.tools import to_png
        x1, y1, x2, y2 = self.x1, self.y1, self.x2, self.y2
        if x1 == x2 or y1 == y2:
            logger.error(f"{_T('Error Capture Screen Region')}: {x1, y1, x2, y2}")
            return
        # print("GET REGION:", x1, y1, x2, y2)
        with mss() as sct:
            monitor = {"top": y1, "left": x1, "width": x2 - x1, "height": y2 - y1}
            output = "sct-{top}x{left}_{width}x{height}.png".format(**monitor)
            output = Path(tempfile.gettempdir()).joinpath(output).as_posix()
            # Grab the data
            from ..utils import CtxTimer
            with CtxTimer(f"{_T(('Capture Screen'))}: {output}"):
                sct_img = sct.grab(monitor)
            # Save to the picture file
            with CtxTimer(f"{_T('Save Screenshot')}: {output}"):
                to_png(sct_img.rgb, sct_img.size, output=output, level=0)
            self.image = output

    def spec_extra_properties(s, properties, nname, ndesc):
        def update_capture(self, context):
            if not self.capture:
                return
            self.capture = False
            from ..External.lupawrapper import get_lua_runtime
            rt = get_lua_runtime()
            hk = rt.load_dll("luahook")
            x1, y1, x2, y2 = hk.scrcap()
            if x1 == x2 or y1 == y2:
                logger.error(f"{_T('Error Capture Screen Region')}: {x1, y1, x2, y2}")
                return
            self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
            s._capture(self)
        prop = bpy.props.BoolProperty(default=False, update=update_capture, name="Capture Screen", description="Capture Screen Region")
        properties["capture"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["prev"] = prop
        prop = bpy.props.IntProperty(default=512)
        properties["x1"] = prop
        properties["y1"] = prop
        properties["x2"] = prop
        properties["y2"] = prop

    def pre_fn(s, self: NodeBase):
        @Timer.wait_run
        def f():
            s._capture(self)
        f()


class AnimateDiffCombine(BluePrintBase):
    comfyClass = "AnimateDiffCombine"
    PREV = PrevMgr.new()
    PLAYERS: dict[str, AIP] = {}

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swlink)

    def post_fn(s, self: NodeBase, t: Task, result):
        """
        result : {'node': '11', 'output': {'videos': [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}]}, 'prompt_id': ''}
        """
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("videos", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[dict]):
            """
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                img_path = get_image_path(data, suffix="gif").as_posix()
                # 和上次的相同则不管
                if img_path == self.prev_name:
                    return
                # 和上次不同, 先清理上次的结果
                if img_path in s.PLAYERS:
                    player = s.PLAYERS.pop(img_path)
                    player.free()
                    del player
                    prev = s.PREV[img_path]
                else:
                    prev = s.PREV.new(img_path)
                self.prev_name = img_path
                player = AIP(prev, img_path)
                s.PLAYERS[img_path] = player
                player.auto_play()
                break
        Timer.put((f, self, img_paths))

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.StringProperty()
        properties["prev_name"] = prop

    def free(s, self: NodeBase):
        if self.prev_name in s.PLAYERS:
            player = s.PLAYERS.pop(self.prev_name)
            player.free()
            del player

    def copy(s, self: NodeBase, node):
        self.prev_name = ""


class VHS_VideoCombine(BluePrintBase):
    comfyClass = "VHS_VideoCombine"
    PREV = PrevMgr.new()
    PLAYERS: dict[str, AIP] = {}

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swlink)

    def post_fn(s, self: NodeBase, t: Task, result):
        """
        result :
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00001.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}]}, 'prompt_id': 'ad41d87b-384b-470c-9ebe-cde8801272c3'}
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00002.webp', 'subfolder': '', 'type': 'output', 'format': 'image/webp'}]}, 'prompt_id': '16091f8f-cbf2-4c90-8b6c-5b3823344ccc'}
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00003.mov', 'subfolder': '', 'type': 'output', 'format': 'video/ProRes'}]}, 'prompt_id': '462c8f2d-7e1b-4003-9a12-36b43bec6743'}
        """
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("gifs", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[dict]):
            """
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                file_type = data.get("format", None)
                if file_type not in {"image/gif", "image/webp"}:
                    continue
                img_path = get_image_path(data, suffix=file_type.split("/")[1]).as_posix()
                # 和上次的相同则不管
                if img_path == self.prev_name:
                    return
                # 和上次不同, 先清理上次的结果
                if img_path in s.PLAYERS:
                    player = s.PLAYERS.pop(img_path)
                    player.free()
                    del player
                    prev = s.PREV[img_path]
                else:
                    prev = s.PREV.new(img_path)
                self.prev_name = img_path
                player = AIP(prev, img_path)
                s.PLAYERS[img_path] = player
                player.auto_play()
                break
        Timer.put((f, self, img_paths))

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.StringProperty()
        properties["prev_name"] = prop

    def free(s, self: NodeBase):
        if self.prev_name in s.PLAYERS:
            player = s.PLAYERS.pop(self.prev_name)
            player.free()
            del player

    def copy(s, self: NodeBase, node):
        self.prev_name = ""


class SaveAnimatedPNG(BluePrintBase):
    comfyClass = "SaveAnimatedPNG"
    PREV = PrevMgr.new()
    PLAYERS: dict[str, AIP] = {}

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swlink)

    def post_fn(s, self: NodeBase, t: Task, result):

        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[dict]):
            """
                        {'filename': 'img.png', 'subfolder': '', 'type': 'output'}
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                file_type = Path(data.get("filename", "None")).suffix
                if file_type != ".png":
                    continue
                img_path = get_image_path(data, suffix=file_type[1:]).as_posix()
                # 和上次的相同则不管
                if img_path == self.prev_name:
                    return
                # 和上次不同, 先清理上次的结果
                if img_path in s.PLAYERS:
                    player = s.PLAYERS.pop(img_path)
                    player.free()
                    del player
                    prev = s.PREV[img_path]
                else:
                    prev = s.PREV.new(img_path)
                self.prev_name = img_path
                player = AIP(prev, img_path)
                s.PLAYERS[img_path] = player
                player.auto_play()
                break
        Timer.put((f, self, img_paths))

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.StringProperty()
        properties["prev_name"] = prop

    def free(s, self: NodeBase):
        if self.prev_name in s.PLAYERS:
            player = s.PLAYERS.pop(self.prev_name)
            player.free()
            del player

    def copy(s, self: NodeBase, node):
        self.prev_name = ""


class SaveAnimatedWEBP(BluePrintBase):
    comfyClass = "SaveAnimatedWEBP"
    PREV = PrevMgr.new()
    PLAYERS: dict[str, AIP] = {}

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swlink=True):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swlink)

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[dict]):
            """
                        {'filename': 'img.webp', 'subfolder': '', 'type': 'output'}
                        {'filename': 'img.png', 'subfolder': '', 'type': 'output'}
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                file_type = Path(data.get("filename", "None")).suffix
                if file_type != ".webp":
                    continue
                img_path = get_image_path(data, suffix=file_type[1:]).as_posix()
                # 和上次的相同则不管
                if img_path == self.prev_name:
                    return
                # 和上次不同, 先清理上次的结果
                if img_path in s.PLAYERS:
                    player = s.PLAYERS.pop(img_path)
                    player.free()
                    del player
                    prev = s.PREV[img_path]
                else:
                    prev = s.PREV.new(img_path)
                self.prev_name = img_path
                player = AIP(prev, img_path)
                s.PLAYERS[img_path] = player
                player.auto_play()
                break
        Timer.put((f, self, img_paths))

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.StringProperty()
        properties["prev_name"] = prop

    def free(s, self: NodeBase):
        if self.prev_name in s.PLAYERS:
            player = s.PLAYERS.pop(self.prev_name)
            player.free()
            del player

    def copy(s, self: NodeBase, node):
        self.prev_name = ""


class SDNGroupBP(BluePrintBase):
    comfyClass = "SDNGroup"

    def dump(s, self: SDNGroup, selected_only=False):
        helper = THelper()
        tree = self.get_tree()
        outer_all_links: list[bpy.types.NodeLink] = tree.links[:]
        all_links: list[bpy.types.NodeLink] = self.node_tree.links[:]

        inputs = []
        outputs = []
        widgets_values = []
        # 组的 widgets_values 导出顺序非常重要 和 node.id有关
        for sn in self.get_sort_inner_nodes():
            if sn.bl_idname == "NodeReroute" and sn.outputs[0].links:
                tsock = helper.find_to_sock(sn.outputs[0])
                sn: NodeBase = tsock.node
                if sn.bl_idname == "NodeGroupOutput":
                    continue
                if sn.is_base_type(tsock.name):
                    widgets_values.append(s.getattr(sn, get_reg_name(tsock.name)))
                    continue

            if sn.bl_idname in {"NodeGroupInput", "NodeGroupOutput", "NodeUndefined"}:
                continue
            nwidgets = sn.dump(selected_only=selected_only).get("widgets_values")

            # # 单独处理 widgets_values
            # for inp_name in self.inp_types:
            #     if not self.is_base_type(inp_name):
            #         continue
            #     widgets_values.append(s.getattr(self, get_reg_name(inp_name)))
            # 需要将已经转为socket的widgets移除
            rm_index = []
            for i, inp_name in enumerate([it for it in sn.inp_types if sn.is_base_type(it)]):
                # 转为接口且已经连接
                if sn.query_stat(inp_name) and sn.inputs[inp_name].links:
                    rm_index.append(i)
            for i in rm_index[::-1]:
                nwidgets.pop(i)
            widgets_values += nwidgets
        inode, onode = self.get_in_out_node()
        for outer_inp in self.inputs:
            sid = outer_inp[SOCK_TAG]
            slink = inode.get_output(sid).links[0]
            inp = slink.to_socket
            snode: NodeBase = slink.to_node
            inp_name = inp.name
            ori_name = get_ori_name(inp_name)
            inp_info = {"name": ori_name,
                        "type": inp.bl_idname,
                        "link": None}
            if LABEL_TAG in outer_inp:
                inp_info["label"] = outer_inp[LABEL_TAG]
            link = self.get_from_link(outer_inp)
            is_base_type = snode.is_base_type(inp_name)
            if link:
                if not selected_only:
                    inp_info["link"] = outer_all_links.index(outer_inp.links[0])
                elif inp.links[0].from_node.select:
                    inp_info["link"] = outer_all_links.index(outer_inp.links[0])
                from_socket = link.from_socket
                if helper.is_reroute_socket(from_socket):
                    inp_info["name"] = "*"
                    inp_info["type"] = "*"
                    inp_info["label"] = "*"
                else:
                    slink = helper.find_to_link(slink)
                    tsocket = slink.to_socket
                    inp_info["name"] = from_socket.bl_idname
                    if not helper.is_reroute_socket(tsocket):
                        inp_info["name"] = tsocket.name
                    inp_info["type"] = from_socket.bl_idname
                    inp_info["label"] = from_socket.bl_idname
                if "slot_index" in outer_inp:
                    inp_info["slot_index"] = outer_inp["slot_index"]
            elif helper.is_reroute_socket(inp):
                tinp = helper.find_to_sock(inp)
                if tinp.bl_idname not in {"NodeGroupInput", "NodeGroupOutput"}:
                    inp_info["name"] = tinp.name  # f"{tinp.to_node.name} {tinp.name}"
                    inp_info["type"] = tinp.bl_idname
                    inp_info["label"] = tinp.name
                if helper.is_reroute_socket(tinp):
                    inp_info["name"] = "*"
                    inp_info["type"] = "*"
                    inp_info["label"] = "*"
            if is_base_type:
                md = snode.get_meta(ori_name)
                if not snode.query_stat(inp.name) or not md:
                    continue
                # inp_info["widget"] = {"name": ori_name, "config": md}
                inp_info["widget"] = {"name": ori_name}
                inp_info["type"] = ",".join(md[0]) if isinstance(md[0], list) else md[0]
            if snode.bl_idname == "NodeReroute":
                inp_info["name"] = inp_info["type"]
                tsock = helper.find_to_sock(inp)
                if tsock.node.is_base_type(tsock.name):
                    inp_info["widget"] = {"name": inp_info["type"]}
            inp_info["label"] = inp_info["name"]
            inputs.append(inp_info)
        for i, out in enumerate(self.outputs):
            out_info = {"name": out.name, "type": out.name}
            if LABEL_TAG in out:
                out_info["label"] = out[LABEL_TAG]
                out_info["type"] = out[LABEL_TAG]
            if not selected_only:
                out_info["links"] = [outer_all_links.index(link) for link in out.links]
            elif out.links:
                out_info["links"] = [outer_all_links.index(link) for link in out.links if link.to_node.select]
            if out_info["type"] == "*":
                # 当输出节点是reroute时, 需要找到真正的输出节点
                _, onode = self.get_in_out_node()
                if onode and SOCK_TAG in out:
                    inp = onode.inputs[out[SOCK_TAG]]
                    fsock = helper.find_from_sock(inp)
                    out_info["name"] = fsock.bl_idname
                    out_info["label"] = fsock.bl_idname
                    out_info["type"] = fsock.bl_idname
                    if helper.is_reroute_socket(fsock):
                        out_info["name"] = fsock.name + "*"
                        out_info["label"] = "*"
                        out_info["type"] = "*"
            out_info["slot_index"] = i
            outputs.append(out_info)
        cfg = {
            "id": int(self.id),
            "type": f"workflow/{self.node_tree.name}",
            "pos": [int(self.location.x), -int(self.location.y)],
            "size": {"0": int(self.width), "1": int(self.height)},
            "flags": {},
            "order": self.sdn_order,
            "mode": 0,
            "inputs": inputs,
            "outputs": outputs,
            "title": self.name,
            "properties": {"sdn_hide": self.sdn_hide, },
            "widgets_values": widgets_values
        }
        if self.use_custom_color:
            color = rgb2hex(*self.color)
            cfg["bgcolor"] = color
        __locals_copy__ = locals()
        __locals_copy__.pop("s")
        s.dump_specific(**__locals_copy__)
        return cfg

    def make_serialize(s, self: NodeBase, parent: NodeBase = None) -> dict:
        from .tree import CFNodeTree
        tree: CFNodeTree = self.node_tree
        if not tree:
            return {}
        sub_prompt = tree.serialize(parent=self)
        prompt = {}
        for k, v in sub_prompt.items():
            prompt[f"{self.id}:{k}"] = v
        return prompt
        return {self.id: (self.serialize(), )}


@lru_cache(maxsize=1024)
def get_blueprints(comfyClass, default=BluePrintBase) -> BluePrintBase:
    for cls in BluePrintBase.__subclasses__():
        if cls.comfyClass != comfyClass:
            continue
        return cls()
    return default()
