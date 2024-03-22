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
from .utils import gen_mask, THelper
from .plugins.animatedimageplayer import AnimatedImagePlayer as AIP
from .nodes import NodeBase, Ops_Add_SaveImage, Ops_Link_Mask, Ops_Active_Tex, Set_Render_Res, Ops_Switch_Socket_Widget
from .nodes import name2path, get_icon_path, Images
from ..SDNode.manager import Task
from ..timer import Timer
from ..preference import get_pref
from ..kclogger import logger
from ..utils import _T, Icon, update_screen, PrevMgr, rgb2hex, hex2rgb
from ..translations import get_reg_name, get_ori_name


def get_next_filename(save_path, max_len=4):
    save_path = Path(save_path)
    directory = save_path.parent
    basename = save_path.stem
    ext = save_path.suffix

    # 移除文件名末尾的数字序号（如果有的话）
    match = re.match(r"(.+)_(\d+)$", basename)
    if match:
        basename, _ = match.groups()

    pattern = f"{basename}_*{ext}"
    existing_files = list(directory.glob(pattern))

    # 初始化最大序号长度为默认值或已存在文件中的最大长度
    numbers = [0]
    for file in existing_files:
        match = re.search(rf"{re.escape(basename)}_(\d+){re.escape(ext)}$", file.name)
        if match:
            num = int(match.group(1))
            num_str = str(num)
            numbers.append(num)
            max_len = max(max_len, len(num_str))

    next_number = max(numbers) + 1

    # 使用检测到的最大序号长度来格式化新的文件名
    new_filename = f"{basename}_{next_number:0{max_len}d}{ext}"
    new_save_path = directory / new_filename

    return new_save_path


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


def draw_prop_with_link(layout, self, prop, swsock, swdisp=False, row=True, pre=None, post=None, **kwargs):
    layout = Ops_Switch_Socket_Widget.draw_prop(layout, self, prop, row, swsock, swdisp)
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

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
        def show_model_preview(self: NodeBase, context: bpy.types.Context, layout: bpy.types.UILayout, prop: str):
            if self.class_type not in name2path:
                return False
            if prop not in get_icon_path(self.class_type):
                return False
            col = draw_prop_with_link(layout, self, prop, swsock, swdisp, text="", row=False)
            col.template_icon_view(self, prop, show_labels=True, scale_popup=popup_scale, scale=popup_scale)
            return True

        # 多行文本处理
        md = self.get_meta(prop)
        if md and md[0] == "STRING" and len(md) > 1 and isinstance(md[1], dict) and md[1].get("multiline",):
            width = int(self.width) // 7
            lines = textwrap.wrap(text=str(s.getattr(self, prop)), width=width)
            for line in lines:
                layout.label(text=line, text_ctxt=self.get_ctxt())
            row = draw_prop_with_link(layout, self, prop, swsock, swdisp)
            row.operator("sdn.enable_mlt", text="", icon="TEXT")
            if not swdisp:
                return True
            stat = self.mlt_stats.get(prop)
            enable = bool(stat and stat.enable)
            op = row.operator("sdn.adv_text_edit", text="", icon="OPTIONS", depress=enable)
            op.prop = prop
            op.action = "SwitchAdvText"
            if enable:
                box = layout.box()
                col = box.column()
                mgr = bpy.context.window_manager
                col.prop(stat, "addtext", icon="ADD", text="")
                col.template_list("MLTWords_UL_UIList", prop, mgr, "mlt_words", mgr, "mlt_words_index")
                col.template_list("MLTText_UL_UIList", "", stat, "texts", stat, "tindex")
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
                row = draw_prop_with_link(layout, self, prop, swsock, swdisp, text=prop, text_ctxt=self.get_ctxt())
                row.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                row.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                row.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
                return True
            if prop in {"exe_rand", "sync_rand"}:
                return True
        elif hasattr(self, "noise_seed"):
            if prop in {"add_noise", "return_with_leftover_noise"}:
                def dpre(layout): layout.label(text=prop, text_ctxt=self.get_ctxt())
                draw_prop_with_link(layout, self, prop, swsock, swdisp, expand=True, pre=dpre, text_ctxt=self.get_ctxt())
                return True
            if prop == "noise_seed":
                def dpost(layout):
                    layout.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                    layout.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                    layout.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
                draw_prop_with_link(layout, self, prop, swsock, swdisp, post=dpost, text_ctxt=self.get_ctxt())
                return True
            if prop in {"exe_rand", "sync_rand"}:
                return True
        elif self.class_type in {"OpenPoseFull", "OpenPoseHand", "OpenPoseMediaPipeFace", "OpenPoseDepth", "OpenPose", "OpenPoseFace", "OpenPoseLineart", "OpenPoseFullExtraLimb", "OpenPoseKeyPose", "OpenPoseCanny", }:
            return True
        elif self.get_blueprints().spec_draw(self, context, layout, prop, swsock, swdisp):
            return True
        return False

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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
            logger.warning("%s: %s.%s -> %s", _T('Non-Standard Enum'), nname, inp, winfo)
        for k in ["required", "optional"]:
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
        data["title"] = self.name  # 反向同步到metadata
        if with_id:
            try:
                if "index" in data:
                    old_id = str(data["index"])
                else:
                    old_id = str(data["id"])
                self.id = old_id
                pool.add(self.id)
            except BaseException:
                self.apply_unique_id()
        # 处理 inputs
        for inp in data.get("inputs", []):
            name = inp.get("name", "")
            if not self.is_base_type(name):
                continue
            new_socket = self.switch_socket_widget(name, True)
            if si := inp.get("slot_index"):
                new_socket.slot_index = si
            md = self.get_meta(name)
            if isinstance(md, list):
                continue
            if not (default := inp.get("widget", {}).get("config", {}).get("default")):
                continue
            # reg_name = get_reg_name(name)
            # s.setattr(self, reg_name, default)
            s.try_set_widget(self, name, default)

        s.load_specific(self, data, with_id)
        for inp_name in self.inp_types:
            if not self.is_base_type(inp_name):
                continue
            reg_name = get_reg_name(inp_name)
            try:
                v = data["widgets_values"].pop(0)
            except IndexError:
                logger.info("%s -> %s<%s>%s " + reg_name, _T('|IGNORED|'), _T('Load'), self.class_type, _T('Params not matching with current node'))
                continue
            s.try_set_widget(self, inp_name, v)

    def try_set_widget(s, self: NodeBase, inp_name, v):
        if not self.is_base_type(inp_name):
            return
        reg_name = get_reg_name(inp_name)
        try:
            s.setattr(self, reg_name, v)
            return True
        except TypeError as e:
            if inp_name in {"seed", "noise_seed"}:
                setattr(self, reg_name, str(v))
            elif (enum := re.findall(' enum "(.*?)" not found', str(e), re.S)):
                logger.warning("%s %s -> %s -> %s: %s", _T('|IGNORED|'), self.class_type, inp_name, _T('Not Found Item'), enum[0])
            else:
                logger.error("|%s|", e)
        except Exception as e:
            logger.error("%s %s -> %s.%s", _T('Params Loading Error'), self.class_type, self.class_type, inp_name)
            logger.error(" -> %s", e)

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
        __locals_copy__ = dict(locals())
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
        logger.debug("BluePrintBase: %s %s->%s", self.class_type, _T('Post Function'), result)

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
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
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
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
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

    def spec_draw(s, self: NodeBase, context, layout, prop: str, swsock=True, swdisp=False) -> bool:
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

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
        if prop in {"add_noise", "return_with_leftover_noise"}:
            def dpre(layout): layout.label(text=prop, text_ctxt=self.get_ctxt())
            draw_prop_with_link(layout, self, prop, swsock, swdisp, expand=True, pre=dpre, text_ctxt=self.get_ctxt())
            return True
        if prop == "noise_seed":
            def dpost(layout):
                layout.prop(self, "exe_rand", text="", icon="FILE_REFRESH", text_ctxt=self.get_ctxt())
                layout.prop(bpy.context.scene.sdn, "rand_all_seed", text="", icon="HAND", text_ctxt=self.get_ctxt())
                layout.prop(self, "sync_rand", text="", icon="MOD_WAVE", text_ctxt=self.get_ctxt())
            draw_prop_with_link(layout, self, prop, swsock, swdisp, post=dpost, text_ctxt=self.get_ctxt())
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

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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

    def spec_draw(s, self: NodeBase, context, layout, prop: str, swsock=True, swdisp=False):
        if self.outputs[0].is_linked and self.outputs[0].links:
            node = self.outputs[0].links[0].to_node
            # 可能会导致prop在node中找不到的情况(断开连接的时候)
            if not hasattr(node, self.prop):
                return True
            if self.get_blueprints().draw_button(node, context, layout, self.prop, swsock=False, swdisp=swdisp):
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
            if self.prop not in {"seed", "noise_seed"}:
                widgets_values.pop()

    def serialize_pre_specific(s, self: NodeBase):
        if not self.outputs[0].is_linked:
            return
        prop = s.getattr(self.outputs[0].links[0].to_node, get_reg_name(self.prop))
        for link in self.outputs[0].links[1:]:
            setattr(link.to_node, get_reg_name(link.to_socket.name), prop)


def upload_image(img_path):
    from .manager import TaskManager

    url = f"{TaskManager.server.get_url()}/upload/image"
    img_path = Path(img_path)
    if img_path.is_dir() or not img_path.exists():
        return

    # 准备文件数据
    try:
        import requests
        from urllib3.util import Timeout
        data = {"overwrite": "true", "subfolder": "SDN"}
        img_type = f"image/{img_path.suffix.replace('.', '')}"
        files = {'image': (img_path.name, img_path.read_bytes(), img_type)}
        timeout = Timeout(connect=5, read=5)
        url = url.replace("0.0.0.0", "127.0.0.1")
        response = requests.post(url, data=data, files=files, timeout=timeout)
        # 检查响应
        if response.status_code == 200:
            logger.info("Upload Image Success")
            # {'name': 'icon.png', 'subfolder': 'SDN', 'type': 'input'}
            return response.json()
        else:
            logger.error(f"{_T('Upload Image Fail')}: {response.text}")
    except Exception as e:
        logger.error(f"{_T('Upload Image Fail')}: {e}")


def cache_to_local(data, suffix="png", save_path="") -> Path:
    '''data = {"filename": filename, "subfolder": subfolder, "type": folder_type}'''
    url_values = urllib.parse.urlencode(data)
    from .manager import TaskManager
    url = f"{TaskManager.server.get_url()}/view?{url_values}"
    # logger.debug(f'requesting {url} for image data')
    with urllib.request.urlopen(url) as response:
        img_data = response.read()
        if not save_path:
            save_path = Path(tempfile.gettempdir()) / data.get('filename', f'preview.{suffix}')
        with open(save_path, "wb") as f:
            f.write(img_data)
        return save_path


class 预览(BluePrintBase):
    comfyClass = "预览"

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.CollectionProperty(type=Images)
        properties["prev"] = prop
        properties["lnum"] = bpy.props.IntProperty(default=3, min=1, max=10, name="Image num per line")

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error('response is %s, cannot find images in it', result)
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

        def f(self, img_paths: list[dict]):
            self.prev.clear()
            for data in img_paths:
                img_path = cache_to_local(data)
                if not img_path:
                    continue
                img_path = Path(img_path).as_posix()
                # if isinstance(img_path, dict):
                #     img_path = Path(d).joinpath(img_path.get("filename")).as_posix()
                if not Path(img_path).exists():
                    continue
                try:
                    p = self.prev.add()
                    # p.image = bpy.data.images.load(img_path)
                    Icon.load_icon(img_path)
                    if not (img := Icon.find_image(img_path)):
                        return
                    p.image = img
                except TypeError:
                    ...
        Timer.put((f, self, img_paths))


class PreviewImage(BluePrintBase):
    comfyClass = "PreviewImage"

    def spec_extra_properties(s, properties, nname, ndesc):
        prop = bpy.props.CollectionProperty(type=Images)
        properties["prev"] = prop
        properties["lnum"] = bpy.props.IntProperty(default=3, min=1, max=10, name="Image num per line")

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error('response is %s, cannot find images in it', result)
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

        def f(self, img_paths: list[dict]):
            self.prev.clear()
            for data in img_paths:
                img_path = cache_to_local(data)
                if not img_path:
                    continue
                img_path = Path(img_path).as_posix()
                # if isinstance(img_path, dict):
                #     img_path = Path(d).joinpath(img_path.get("filename")).as_posix()
                if not Path(img_path).exists():
                    continue
                try:
                    p = self.prev.add()
                    # p.image = bpy.data.images.load(img_path)
                    Icon.load_icon(img_path)
                    if not (img := Icon.find_image(img_path)):
                        return
                    p.image = img
                except TypeError:
                    ...
        Timer.put((f, self, img_paths))


class 存储(BluePrintBase):
    comfyClass = "存储"

    def spec_extra_properties(s, properties, nname, ndesc):
        items = [("Save", "Save", "", "", 0),
                 ("Import", "Import", "", "", 1),
                 ("ToImage", "ToImage", "", "", 2),
                 ("ToSeq", "ToSeq", "", "", 3),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Object)
        properties["obj"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["image"] = prop

        properties["seq_mode"] = bpy.props.EnumProperty(items=[("SeqReplace", "SeqReplace", "", "", 0),
                                                               ("SeqAppend", "SeqAppend", "", "", 1),
                                                               ("SeqStack", "SeqStack", "", "", 2),
                                                               ])
        properties["channel"] = bpy.props.IntProperty(default=1, min=1, max=127)
        properties["frame_start"] = bpy.props.IntProperty()
        properties["frame_final_duration"] = bpy.props.IntProperty(default=25, min=1)

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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
            elif self.mode == "ToSeq":
                layout.prop(self, "seq_mode", expand=True)
                col = layout.box().column()
                row = col.row(align=True)
                row.prop(self, "channel")
                row.prop(self, "frame_start")
                col.prop(self, "frame_final_duration")
                return True
        return True

    def make_serialize(s, self: NodeBase, parent: NodeBase = None) -> dict:
        def __post_fn__(self: NodeBase, t: Task, result: dict, mode, image):
            logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
            img_paths = result.get("output", {}).get("images", [])
            for img in img_paths:
                if mode == "Save":
                    filename_prefix = img.get("filename", self.filename_prefix)
                    output_dir = self.output_dir
                    if not output_dir or not Path(output_dir).is_dir():
                        output_dir = tempfile.gettempdir()
                    save_path = Path(output_dir).joinpath(filename_prefix)
                    img = cache_to_local(img, save_path=save_path).as_posix()
                    if save_path.exists():
                        output_dir = save_path.parent.as_posix()

                        def save_out_dir(self, output_dir):
                            self.output_dir = output_dir
                        Timer.put((save_out_dir, self, output_dir))

                    def f(_, img):
                        return bpy.data.images.load(img)
                elif mode in {"Import", "ToImage"}:
                    img = cache_to_local(img).as_posix()

                    def f(img_src, img):
                        if not img_src:
                            return
                        img_src.filepath = img
                        img_src.filepath_raw = img
                        img_src.source = "FILE"
                        if img_src.packed_file:
                            img_src.unpack(method="REMOVE")
                        img_src.reload()
                elif mode == "ToSeq":
                    img = cache_to_local(img).as_posix()
                    def f(_, img):
                        name = Path(img).name
                        seqe = bpy.context.scene.sequence_editor
                        if self.seq_mode == "SeqReplace":
                            # 替换模式: 查找当前通道的 frame_start 到 frame_final_duration 之间的所有序列, 删除, 然后将新建序列
                            rm_seq = []
                            start = self.frame_start
                            end = self.frame_start + self.frame_final_duration
                            for seq in seqe.sequences:
                                if seq.channel != self.channel:
                                    continue
                                if seq.frame_final_start <= start < seq.frame_final_end or seq.frame_final_start < end <= seq.frame_final_end:
                                    rm_seq.append(seq)
                            for seq in rm_seq:
                                seqe.sequences.remove(seq)
                            seq = seqe.sequences.new_image(name, img, self.channel, self.frame_start)
                            seq.frame_final_duration = self.frame_final_duration

                        elif self.seq_mode == "SeqAppend":
                            # 追加模式: 查找当前通道的 最后一个序列的持续位置, 往后新增
                            max_final_start = -9999
                            for seq in seqe.sequences:
                                if seq.channel != self.channel:
                                    continue
                                if seq.frame_final_end > max_final_start:
                                    max_final_start = seq.frame_final_end
                            seq = seqe.sequences.new_image(name, img, self.channel, max_final_start)
                            seq.frame_final_duration = self.frame_final_duration
                        elif self.seq_mode == "SeqStack":
                            # 堆叠模式: 直接新建, blender会自己堆叠
                            seq = seqe.sequences.new_image(name, img, self.channel, self.frame_start)
                            seq.frame_final_duration = self.frame_final_duration

                Timer.put((f, image, img))
        post_fn = partial(__post_fn__, self, mode=self.mode, image=self.image)
        return {self.id: (self.serialize(parent=parent), self.pre_fn, post_fn)}

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if self.mode not in {"Import", "ToImage"}:
            return
        if "output_dir" in cfg.get("inputs", {}):
            cfg.get("inputs", {})["output_dir"] = tempfile.gettempdir()
        if "filename_prefix" in cfg.get("inputs", {}):
            cfg.get("inputs", {})["filename_prefix"] = "SDNode"


class SaveImage(BluePrintBase):
    comfyClass = "SaveImage"

    def spec_extra_properties(s, properties, nname, ndesc):
        desktop = Path.home().joinpath("Desktop").as_posix()
        prop = bpy.props.StringProperty(default=desktop, subtype="DIR_PATH")
        properties["output_dir"] = prop
        prop = bpy.props.PointerProperty(type=bpy.types.Image)
        properties["image"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
        if prop == "output_dir":
            layout.prop(self, prop, text="")
            return True
        if prop == "image":
            return True
        return False

    def make_serialize(s, self: NodeBase, parent: NodeBase = None) -> dict:
        def __post_fn__(self: NodeBase, t: Task, result: dict, image):
            logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
            img_paths = result.get("output", {}).get("images", [])
            for img in img_paths:
                filename_prefix = img.get("filename", self.filename_prefix)
                output_dir = self.output_dir
                if not output_dir or not Path(output_dir).is_dir():
                    output_dir = tempfile.gettempdir()
                save_path = Path(output_dir).joinpath(filename_prefix)
                img = cache_to_local(img, save_path=save_path).as_posix()
                if save_path.exists():
                    output_dir = save_path.parent.as_posix()

                    def save_out_dir(self, output_dir):
                        self.output_dir = output_dir
                    Timer.put((save_out_dir, self, output_dir))

                def f(_, img):
                    return bpy.data.images.load(img)
                Timer.put((f, image, img))
        post_fn = partial(__post_fn__, self, image=self.image)
        return {self.id: (self.serialize(parent=parent), self.pre_fn, post_fn)}


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

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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
        def render():
            if self.mode not in {"渲染", "视口"}:
                return
            if self.disable_render or bpy.context.scene.sdn.disable_render_all:
                return
            if self.mode == "视口":
                # 使用临时文件
                self.image = Path(tempfile.gettempdir()).joinpath("viewport.png").as_posix()
            logger.warning("%s->%s", _T('Render'), self.image)
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

        @Timer.wait_run
        def r():
            render()
            # 上传图片
            upload_image(self.image)
        r()

    def serialize_pre(s, self: NodeBase):
        if self.mode == "视口":
            if not self.image:
                self.image = Path(tempfile.gettempdir()).joinpath("viewport.png").as_posix()
            if Path(self.image).is_dir():
                self.image = Path(self.image).joinpath("viewport.png").as_posix()
            if Path(self.image).suffix not in {".png", ".jpg", ".jpeg"}:
                self.image = Path(self.image).with_suffix(".png").as_posix()
        super().serialize_pre(self)

    def serialize_specific(s, self: NodeBase, cfg, execute):
        if "image" in cfg.get("inputs", {}):
            cfg["inputs"]["image"] = cfg["inputs"]["image"].replace("\\\\", "/").replace("\\", "/")


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

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
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

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
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
        return super().draw_button(self, context, layout, prop, swsock, swdisp)

    def _capture(s, self: NodeBase):
        from ..External.mss import mss
        from ..External.mss.tools import to_png
        x1, y1, x2, y2 = self.x1, self.y1, self.x2, self.y2
        if x1 == x2 or y1 == y2:
            logger.error("%s: %s", _T('Error Capture Screen Region'), (x1, y1, x2, y2))
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
                logger.error("%s: %s", _T('Error Capture Screen Region'), (x1, y1, x2, y2))
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
            upload_image(self.image)
        f()


class AnimateDiffCombine(BluePrintBase):
    comfyClass = "AnimateDiffCombine"
    PREV = PrevMgr.new()
    PLAYERS: dict[str, AIP] = {}

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swsock, swdisp)

    def post_fn(s, self: NodeBase, t: Task, result):
        """
        result : {'node': '11', 'output': {'videos': [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}]}, 'prompt_id': ''}
        """
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("videos", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

        def f(self, img_paths: list[dict]):
            """
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                img_path = cache_to_local(data, suffix="gif").as_posix()
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

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swsock, swdisp)

    def post_fn(s, self: NodeBase, t: Task, result):
        """
        result :
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00001.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}]}, 'prompt_id': 'ad41d87b-384b-470c-9ebe-cde8801272c3'}
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00002.webp', 'subfolder': '', 'type': 'output', 'format': 'image/webp'}]}, 'prompt_id': '16091f8f-cbf2-4c90-8b6c-5b3823344ccc'}
            {'node': '9', 'output': {'gifs': [{'filename': 'AnimateDiff_00003.mov', 'subfolder': '', 'type': 'output', 'format': 'video/ProRes'}]}, 'prompt_id': '462c8f2d-7e1b-4003-9a12-36b43bec6743'}
        """
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("gifs", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

        def f(self, img_paths: list[dict]):
            """
            img_paths: [{'filename': 'img.gif', 'subfolder': '', 'type': 'output', 'format': 'image/gif'}, ...]
            """
            # self.prev.clear()
            for data in img_paths:
                file_type = data.get("format", None)
                if file_type not in {"image/gif", "image/webp"}:
                    continue
                img_path = cache_to_local(data, suffix=file_type.split("/")[1]).as_posix()
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

    def pre_filter(s, nname, desc):
        cmb_format = desc["input"]["required"].get("format", [])
        if not cmb_format:
            return
        cmb_format = cmb_format[0]
        if not cmb_format:
            return
        support_fmt = []
        if "image/gif" in cmb_format:
            support_fmt.append("image/gif")
        if "image/webp" in cmb_format:
            support_fmt.append("image/webp")
        desc["input"]["required"]["format"] = [support_fmt]

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

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swsock, swdisp)

    def post_fn(s, self: NodeBase, t: Task, result):

        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

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
                img_path = cache_to_local(data, suffix=file_type[1:]).as_posix()
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

    def draw_button(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False):
        if prop == "prev_name":
            prev = s.PREV.get(self.prev_name, None)
            if prev:
                scale = min(max(prev.image_size), self.width) // 20
                scale = min(scale, 100)
                layout.template_icon(icon_value=prev.icon_id, scale=scale)
            return True
        super().draw_button(self, context, layout, prop, swsock, swdisp)

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        # img_paths = link_get(result, "output.videos")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            logger.error(f'response is {result}, cannot find images in it')
            return
        logger.warning("%s: %s", _T('Load Preview Image'), img_paths)

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
                img_path = cache_to_local(data, suffix=file_type[1:]).as_posix()
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


class TripoSRViewer(BluePrintBase):
    comfyClass = "TripoSRViewer"

    def spec_extra_properties(s, properties, nname, ndesc):
        desktop = Path.home().joinpath("Desktop").as_posix()
        prop = bpy.props.StringProperty(name="Output Path", default=desktop, subtype="DIR_PATH")
        properties["output_dir"] = prop
        items = [("Import", "Import", "", "", 0),
                 ("Replace", "Replace", "", "", 1),
                 ("Export", "Export", "", "", 2),
                 ]
        prop = bpy.props.EnumProperty(items=items)
        properties["mode"] = prop
        prop = bpy.props.StringProperty(default="model.obj")
        properties["filename"] = prop

    def spec_draw(s, self: NodeBase, context: Context, layout: UILayout, prop: str, swsock=True, swdisp=False) -> bool:
        if prop == "mode":
            layout.prop(self, prop, expand=True, text_ctxt=self.get_ctxt())
            if self.mode == "Import":
                layout.prop(self, "output_dir", expand=True, text_ctxt=self.get_ctxt())
            elif self.mode == "Replace":
                o = bpy.context.object
                if o:
                    layout.label(text=_T('Current Object: %s') % o.name)
            elif self.mode == "Export":
                layout.prop(self, "filename", expand=True, text_ctxt=self.get_ctxt())
                layout.prop(self, "output_dir", expand=True, text_ctxt=self.get_ctxt())
        return True

    def create_mat(s) -> bpy.types.Material:
        name = "TripoSR Material"
        if name in bpy.data.materials:
            return bpy.data.materials[name]
        mat = bpy.data.materials.new(name="TripoSR Material")
        mat.use_nodes = True
        nodetree = mat.node_tree
        # 创建3个节点 ShaderNodeVertexColor ShaderNodeBsdfPrincipled 和 ShaderNodeOutputMaterial
        nodetree.nodes.clear()
        n1 = nodetree.nodes.new(type='ShaderNodeVertexColor')
        n1.location = -200, 300
        n2 = nodetree.nodes.new(type='ShaderNodeBsdfPrincipled')
        n2.location = 10, 300
        n3 = nodetree.nodes.new(type='ShaderNodeOutputMaterial')
        n3.location = 300, 300
        # 依次连接n1-n2-n3 均连接第一个接口
        nodetree.links.new(n1.outputs[0], n2.inputs[0])
        nodetree.links.new(n2.outputs[0], n3.inputs[0])
        return mat

    def set_origin(s, obj: bpy.types.Object):
        import numpy as np
        from mathutils import Vector
        # obj = bpy.context.active_object
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        mesh: bpy.types.Mesh = obj.data
        # 使用numpy加速获取所有顶点的Z坐标
        verts = np.zeros(len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", verts)
        verts = verts.reshape((-1, 3))
        # 计算中心点
        center = verts.sum(axis=0) / len(mesh.vertices)
        center[2] = verts[:, 2].min()
        lowest_point = Vector(center)
        # 将原点设置到底部中心点
        # 首先，将3D光标移动到底部中心点位置
        cursor_loc = bpy.context.scene.cursor.location
        bpy.context.scene.cursor.location = lowest_point
        # 然后，将原点设置到3D光标的位置
        bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        bpy.context.scene.cursor.location = cursor_loc

    def import_obj(s, filepath) -> list[bpy.types.Object]:
        rec_objs = set(bpy.context.scene.objects)
        bpy.ops.wm.obj_import(filepath=filepath)
        new_objs = set(bpy.context.scene.objects) - rec_objs
        for obj in new_objs:
            bpy.context.view_layer.objects.active = obj
            obj.active_material = s.create_mat()
            s.set_origin(obj)
            bpy.ops.object.shade_smooth()
        return list(new_objs)

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug("%s%s->%s", self.class_type, _T('Post Function'), result)
        # result = {'node': '4', 'output': {'mesh': [{'filename': 'meshsave_00002_.obj', 'type': 'output', 'subfolder': ''}]}}
        output = result.get("output", {})
        meshes = output.get("mesh", [])
        if not meshes:
            return

        def f(self, meshes):
            for data in meshes:
                filename = data.get("filename", "")
                if not filename.lower().endswith(".obj"):
                    logger.warning(f"Not process {filename}")
                    continue

                if self.mode in {"Import", "Replace"}:
                    active_object = bpy.context.object
                    save_path = Path(self.output_dir).joinpath(filename)
                    obj = cache_to_local(data, suffix=".obj", save_path=save_path).as_posix()
                    imp_objs = s.import_obj(obj)
                    if self.mode == "Replace" and active_object and imp_objs:
                        active_object.data, imp_objs[0].data = imp_objs[0].data, active_object.data
                        bpy.data.objects.remove(imp_objs[0])
                        bpy.context.view_layer.objects.active = active_object
                        active_object.select_set(True)
                elif self.mode == "Export":
                    save_path = Path(self.output_dir).joinpath(self.filename).with_suffix(".obj")
                    save_path = get_next_filename(save_path)
                    obj = cache_to_local(data, suffix=".obj", save_path=save_path).as_posix()
        Timer.put((f, self, meshes))


class SDNGroupBP(BluePrintBase):
    comfyClass = "SDNGroup"

    def load_delay(s, self: NodeBase, data, with_id=True):
        helper = THelper()
        # widgets_values分布: widgets ->  linked_widgets
        converted_widgets = [w for w in data.get("inputs", []) if "widget" in w]  # 可能为[]
        num_cw = len(converted_widgets)
        widgets: list = data["widgets_values"][:-num_cw] if num_cw else data["widgets_values"][:]
        # linked_widget: list = data["widgets_values"][-len(inputs):]
        # widgets_cache: dict[NodeBase, dict[str, str]] = {}
        # for index, inp in enumerate(inputs):
        #     name = inp["widget"].get("name", None)
        #     if not name or " " not in name:
        #         continue
        #     value = linked_widget[index]
        #     nname, vname = name.rpartition(" ")[::2]
        #     node = self.node_tree.nodes.get(nname)
        #     if not node:
        #         continue
        #     if node not in widgets_cache:
        #         widgets_cache[node] = {}
        #     widgets_cache[node][vname] = value
        # group中记录的 nodes的inputs代表 有连接 或者转成了接口的widget
        # 排除之后剩下的 widgets 存储在 widgets_values中
        mnodes = self.__metadata__.get("nodes", [])
        dumped_node_vname = []
        for mnode in mnodes:
            nname = mnode["title"]
            # node 必定存在, 如果不存在 则之前的步骤有问题
            node: NodeBase = self.node_tree.nodes.get(nname)
            if node.bl_idname == "PrimitiveNode" and mnode["outputs"]:
                out = mnode["outputs"][0]
                if "widget" in out:
                    inp = out["widget"]["name"]
                    dumped_node_vname.append((node, inp))
                continue
            dumped_widgets = node.widgets
            for inp in mnode["inputs"]:
                if "widget" not in inp:
                    continue
                if inp["name"] in {"seed", "noise_seed"} and "control_after_generate" in dumped_widgets:
                    dumped_widgets.remove("control_after_generate")
                dumped_widgets.remove(inp["name"])
            for inp in dumped_widgets:
                dumped_node_vname.append((node, inp))
        # logger.debug(widgets)
        for node, inp in dumped_node_vname:
            v = widgets.pop(0)
            if node.bl_idname == "PrimitiveNode":
                pnode = node
                node = helper.find_to_node(node.outputs[0].links[0])
                if inp in {"seed", "noise_seed"} or type(v) in {int, float}:
                    sv = widgets.pop(0)
                    logger.warning("%s : %s %s", pnode.name, sv, _T('|IGNORED|'))
                # continue
            if s.try_set_widget(node, inp, v):
                logger.debug("%s.%s = %s", node.name, inp, v)

    def load(s, self: NodeBase, data, with_id=True):
        super().load(self, data, with_id)
        from threading import Thread

        def f(self, data, with_id):
            import time
            time.sleep(0.1)
            Timer.put((s.load_delay, self, data, with_id))
        Thread(target=f, args=(self, data, with_id)).start()

    def dump(s, self: SDNGroup, selected_only=False):
        helper = THelper()
        tree = self.get_tree()
        outer_all_links: list[bpy.types.NodeLink] = tree.links[:]
        # all_links: list[bpy.types.NodeLink] = self.node_tree.links[:]
        ordered_nodes = self.node_tree.compute_execution_order()
        total_widgets = set()
        for sn in ordered_nodes:
            total_widgets.update(sn.get_widgets(exclude_converted=True))
        inputs = []
        outputs = []
        widgets_values = []
        # 组的 widgets_values 导出顺序非常重要 和 node.id及order有关
        for sn in ordered_nodes:
            if sn.bl_idname == "NodeReroute":
                continue
            # if sn.bl_idname == "NodeReroute" and sn.outputs[0].links:
            #     tsock = helper.find_to_sock(sn.outputs[0])
            #     sn: NodeBase = tsock.node
            #     if sn.bl_idname == "NodeGroupOutput":
            #         continue
            #     if sn.is_base_type(tsock.name):
            #         widgets_values.append(s.getattr(sn, get_reg_name(tsock.name)))
            #         continue

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
                    continue
                # 如果为 control_after_generate 则判断 seed 和 noise_seed 是否连接
                if inp_name == "control_after_generate":
                    if sn.query_stat("seed") and sn.inputs["seed"].links:
                        rm_index.append(i)
                        continue
                    if sn.query_stat("noise_seed") and sn.inputs["noise_seed"].links:
                        rm_index.append(i)
                        continue
            for i in rm_index[::-1]:
                nwidgets.pop(i)
            widgets_values += nwidgets
        # widgets_values 最后补上转换后的接口对应的widget值
        inode, onode = self.get_in_out_node()
        for outer_inp in self.inputs:
            sid = outer_inp[SOCK_TAG]
            slink = inode.get_output(sid).links[0]
            inp = slink.to_socket
            snode: NodeBase = slink.to_node
            inp_name = inp.name
            ori_name = get_ori_name(inp_name)
            if not snode.is_base_type(inp_name):
                continue
            md = snode.get_meta(ori_name)
            if not snode.query_stat(inp_name) or not md:
                continue
            out_inp_widget = s.getattr(snode, get_reg_name(inp_name))
            widgets_values.append(out_inp_widget)
            if inp_name in {"seed", "noise_seed"}:
                widgets_values.append("fixed")
        dumped_sockets = []
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
                full_name = f"{snode.name} {ori_name}"
                if ori_name in total_widgets:
                    ori_name = full_name
                else:
                    total_widgets.add(ori_name)
                inp_info["widget"] = {"name": ori_name}
                inp_info["name"] = full_name
                inp_info["type"] = ",".join(md[0]) if isinstance(md[0], list) else md[0]
            if snode.bl_idname == "NodeReroute":
                inp_info["name"] = inp_info["type"]
                tsock = helper.find_to_sock(inp)
                if tsock.node.is_base_type(tsock.name):
                    inp_info["widget"] = {"name": inp_info["type"]}
            if "widget" not in inp_info:
                if inp_info["name"] in dumped_sockets:
                    inp_info["name"] = f"{snode.name} {inp_info['name']}"
                else:
                    dumped_sockets.append(inp_info["name"])
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
        __locals_copy__ = dict(locals())
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


class SDParameterGenerator(BluePrintBase):
    comfyClass = "SDParameterGenerator"

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        widgets_values = cfg["widgets_values"]
        types = self.widgets
        if "control_after_generate" not in types:
            return
        rm = types.index("control_after_generate")
        if len(widgets_values) > rm:
            widgets_values.pop(rm)


@lru_cache(maxsize=1024)
def get_blueprints(comfyClass, default=BluePrintBase) -> BluePrintBase:
    for cls in BluePrintBase.__subclasses__():
        if cls.comfyClass != comfyClass:
            continue
        return cls()
    return default()
