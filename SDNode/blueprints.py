import json
import re
import bpy
import random
from pathlib import Path
from copy import deepcopy
from ..SDNode.nodes import NodeBase
from .utils import gen_mask, get_tree
from .nodes import NodeBase
from ..SDNode.manager import Task
from ..timer import Timer
from ..kclogger import logger
from ..utils import _T
from ..translations import ctxt, get_reg_name, get_ori_name


def get_sync_rand_node():
    tree = get_tree()
    for node in tree.get_nodes():
        # node不是KSampler、KSamplerAdvanced 跳过
        if not hasattr(node, "seed") and node.class_type != "KSamplerAdvanced":
            continue
        if node.sync_rand:
            return node


def get_fixed_seed():
    return int(random.randrange(4294967294))


class BluePrintBase:
    comfyClass = ""

    def pre_filter(s, desc):
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
        tree = get_tree()
        all_links: bpy.types.NodeLinks = tree.links[:]

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
            md = self.get_meta(reg_name)
            inp_info = {"name": inp_name,
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
                inp_info["widget"] = {"name": reg_name,
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
            if (snode := get_sync_rand_node()) and snode != self:
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
            s.serialize_specific(self, cfg, execute)
        return cfg

    def pre_fn(s, self: NodeBase):
        # logger.debug(f"{self.class_type} {_T('Pre Function')}")
        ...

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")


class WD14Tagger(BluePrintBase):
    comfyClass = "WD14Tagger|pysssss"

    def pre_filter(s, desc):
        desc["input"]["required"]["tags"] = ["STRING", {"default": "", "multiline": True}]

    def dump_specific(s, self: NodeBase = None, cfg=None, selected_only=False, **kwargs):
        cfg["widgets_values"] = cfg["widgets_values"][:4]

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        text = result.get("output", {}).get("tags", [])
        if text and isinstance(text[0], str):
            self.tags = text[0]


class PreviewTextNode(BluePrintBase):
    comfyClass = "PreviewTextNode"

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        text = result.get("output", {}).get("string", [])
        if text and isinstance(text[0], str):
            self.text = text[0]


class CheckpointLoaderSimpleWithImages(BluePrintBase):
    comfyClass = "CheckpointLoader|pysssss"

    def pre_filter(s, desc):
        for k in ["required", "optional"]:
            for inp, inp_desc in desc["input"].get(k, {}).items():
                stype = inp_desc[0]
                if not isinstance(stype, list):
                    continue
                if not stype or not isinstance(stype[0], dict):
                    continue
                for idx, item in enumerate(stype):
                    if "content" not in item:
                        continue
                    stype[idx] = item["content"]
        return desc


class MultiAreaConditioning(BluePrintBase):
    comfyClass = "MultiAreaConditioning"

    def load_specific(s, self: NodeBase, data, with_id=True):
        config = json.loads(self.config)
        for i in range(2):
            d = data["properties"]["values"][i]
            config[i]["x"] = d[0]
            config[i]["y"] = d[1]
            config[i]["sdn_width"] = d[2]
            config[i]["sdn_height"] = d[3]
            config[i]["strength"] = d[4]
        self["config"] = json.dumps(config)
        d = data["properties"]["values"][self.index]
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
                               self.index,
                               *properties["values"][self.index]]


class KSamplerAdvanced(BluePrintBase):
    comfyClass = "KSamplerAdvanced"

    def serialize_pre_specific(s, self: NodeBase):
        if (snode := get_sync_rand_node()) and snode != self:
            return
        if not self.exe_rand and not bpy.context.scene.sdn.rand_all_seed:
            return
        self.noise_seed = str(get_fixed_seed())


class KSampler(BluePrintBase):
    comfyClass = "KSampler"

    def load_specific(s, self: NodeBase, data, with_id=True):
        v = data["widgets_values"][1]
        if isinstance(v, bool):
            data["widgets_values"][1] = ["fixed", "increment", "decrement", "randomize"][int(v)]


class KSamplerAdvanced(BluePrintBase):
    comfyClass = "KSamplerAdvanced"

    def serialize_specific(s, self: NodeBase, cfg, execute):
        cfg["inputs"]["noise_seed"] = int(cfg["inputs"]["noise_seed"])


class Mask(BluePrintBase):
    comfyClass = "Mask"

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


class 预览(BluePrintBase):
    comfyClass = "预览"

    def serialize_pre_specific(s, self: NodeBase):
        if self.inputs[0].is_linked:
            return
        self.prev.clear()

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        img_paths = result.get("output", {}).get("images", [])
        if not img_paths:
            return
        logger.warn(f"{_T('Load Preview Image')}: {img_paths}")

        def f(self, img_paths: list[str]):
            self.prev.clear()

            from .manager import TaskManager
            d = TaskManager.get_temp_directory()
            for img_path in img_paths:
                if isinstance(img_path, dict):
                    img_path = Path(d).joinpath(img_path.get("filename")).as_posix()
                if not Path(img_path).exists():
                    continue
                p = self.prev.add()
                p.image = bpy.data.images.load(img_path)
        Timer.put((f, self, img_paths))


class 存储(BluePrintBase):
    comfyClass = "存储"

    def post_fn(s, self: NodeBase, t: Task, result):
        logger.debug(f"{self.class_type}{_T('Post Function')}->{result}")
        img_paths = result.get("output", {}).get("images", [])
        for img in img_paths:
            if self.mode == "Save":
                def f(self, img):
                    return bpy.data.images.load(img)
            elif self.mode == "Import":
                def f(self, img):
                    self.image.filepath = img
                    self.image.filepath_raw = img
                    self.image.source = "FILE"
                    if self.image.packed_file:
                        self.image.unpack(method="REMOVE")
                    self.image.reload()
            Timer.put((f, self, img))


class 输入图像(BluePrintBase):
    comfyClass = "输入图像"

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


def get_blueprints(comfyClass, default=BluePrintBase) -> BluePrintBase:
    for cls in BluePrintBase.__subclasses__():
        if cls.comfyClass != comfyClass:
            continue
        return cls()
    return default()
