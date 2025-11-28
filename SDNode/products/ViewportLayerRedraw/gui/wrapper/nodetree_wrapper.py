from __future__ import annotations
import bpy
import json
from uuid import uuid4
from copy import deepcopy
from pathlib import Path
from typing import Dict, Optional
from tempfile import gettempdir
from .common_wrappers import WidgetDescriptor, DescriptorFactory, BaseAdapter
from .....nodes import NodeParser
from .....tree import CFNodeTree, TREE_TYPE, NodeBase
from ......timer import Timer

WORKFLOW_DEFAULT = {}
default_wk_path = Path(__file__).parent.parent.parent.joinpath("workflow/default.json")
if default_wk_path.exists():
    WORKFLOW_DEFAULT = json.loads(default_wk_path.read_text())


def object_info() -> Dict[str, Dict]:
    return NodeParser.CACHED_OBJECT_INFO


def try_get_canvas_workflow(obj: bpy.types.Object, data: Dict) -> Optional[CFNodeTree]:
    nt_name = obj.get("Canvas_Workflow", "")
    nt_id = obj.get("Canvas_Workflow_Id", "")
    workflow: CFNodeTree = bpy.data.node_groups.get(nt_name, None)
    if not workflow or nt_id != workflow.sdn_time_code:
        workflow = set_canvas_workflow(obj, data)
    return workflow


def get_canvas_workflow(obj: bpy.types.Object) -> Optional[CFNodeTree]:
    nt_name = obj.get("Canvas_Workflow", "")
    nt_id = obj.get("Canvas_Workflow_Id", "")
    workflow: CFNodeTree = bpy.data.node_groups.get(nt_name, None)
    if not workflow or nt_id != workflow.sdn_time_code:
        return None
    return workflow


def set_canvas_workflow(obj: bpy.types.Object, workflow: Dict) -> CFNodeTree:
    nt_name = f"Canvas_Workflow_{obj.name}_{obj.as_pointer()}"
    node_tree: CFNodeTree = bpy.data.node_groups.new(name=nt_name, type=TREE_TYPE)
    node_tree.clear_nodes()
    node_tree.load_json_ex(deepcopy(workflow))
    node_tree.set_sdn_time_code()
    nt_id = node_tree.sdn_time_code
    obj["Canvas_Workflow"] = nt_name
    obj["Canvas_Workflow_Id"] = nt_id
    return node_tree


class NodeTreeWrapper:
    """
    用于包装工作流json数据，以便在GUI中显示及编辑
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, NodeDescriptor] = {}
        self.node_tree: CFNodeTree = None

    def load(self, obj: bpy.types.Object, data: Dict = None, filter=lambda _: True):
        if not data:
            data = WORKFLOW_DEFAULT
        self.node_tree = try_get_canvas_workflow(obj, data)
        for node in data.get("nodes", []):
            if not filter(node):
                continue
            node_ori = self.node_tree.nodes.get(node["title"])
            if not node_ori:
                continue
            n = self._create_node(node_ori)
            self.nodes[n.node_title] = n

    def _create_node(self, node: NodeBase) -> "NodeDescriptor":
        n = NodeDescriptor()
        n.load(node)
        return n


class NodeDescriptor:
    def __init__(self):
        self.node_ref: NodeBase = None
        self.display_name: str = ""
        self.widgets: Dict[str, WidgetDescriptor] = {}
        self.adapter: BaseAdapter = None

    @property
    def node_title(self):
        return self.node_ref.name if self.node_ref else ""

    @property
    def node_type(self):
        return self.node_ref.class_type if self.node_ref else ""

    def load(self, node: NodeBase):
        self.node_ref = node
        self.adapter = NodeAdapter(node)
        self.widgets.clear()
        if not self.node_title.startswith("#"):
            return
        lsquad = self.node_title.rfind("[")
        rsquad = self.node_title.rfind("]")
        if lsquad == -1 or rsquad == -1:
            return
        self.display_name = self.node_title[1:lsquad]
        node_def = object_info().get(self.node_type, {})
        if not node_def:
            return

        for arg in self.node_title[lsquad + 1 : rsquad].split(","):
            wname = arg.strip()
            widget = node.get_meta(wname)
            wtype = widget[0]
            if isinstance(wtype, list):
                wtype = "ENUM"
            # 特殊处理
            if self.node_type == "输入图像" and wname == "image":
                wtype = "IMAGE"
            self.widgets[wname] = DescriptorFactory.create(wname, wtype, self)

    def display(self, wrapper, app):
        for widget in self.widgets.values():
            widget.display_begin(wrapper, app)
            widget.display(wrapper, app)
            widget.display_end(wrapper, app)


class NodeAdapter(BaseAdapter):
    def __init__(self, node: NodeBase):
        super().__init__(name=node.name)
        self.node = node

    def get_ctxt(self) -> str:
        return self.node.get_ctxt()

    def get_meta(self, prop: str):
        return self.node.get_meta(prop)

    def get_value(self, prop: str):
        if bpy.app.version > (5, 0):
            try:
                props = self.node.bl_system_properties_get()
                return props[prop]
            except Exception:
                pass
        return self.node[prop]

    def set_value(self, prop: str, value):
        if bpy.app.version > (5, 0):
            try:
                props = self.node.bl_system_properties_get()
                props[prop] = value
                return
            except Exception:
                pass
        self.node[prop] = value

    def on_image_action(self, prop: str, action: str):
        obj = bpy.context.object
        if action == "image_from_mat":
            node_load_image_from_mat(self.node, prop, obj)
        elif action == "image_from_file":
            node_load_image_from_file(self.node, prop, obj)
        elif action == "image_from_canvas":
            node_load_image_from_canvas(self.node, prop, obj)
        elif action == "image_from_render":
            node_load_image_from_render(self.node, prop, obj)
        elif action == "delete_image":
            node_delete_image(self.node, prop, obj)


# ---------------------INT FLOAT BOOLEAN ENUM COMBO STRING IMAGE---------------------


def find_node_by_type(nt: bpy.types.NodeTree, node_type: str):
    for node in nt.nodes:
        if node.type == node_type:
            return node
        if node.type == "GROUP" and node.node_tree:
            n = find_node_by_type(node.node_tree, node_type)
            if n:
                return n
    return None


def node_load_image_from_mat(node: NodeBase, prop: str, obj: bpy.types.Object):
    mat = obj.active_material
    if not mat:
        return
    img_node: bpy.types.ShaderNodeTexImage = find_node_by_type(mat.node_tree, "TEX_IMAGE")
    if not img_node or not img_node.image:
        return
    image = img_node.image.copy()
    temp_file = Path(gettempdir()) / f"{uuid4().hex}.png"
    image.save(filepath=temp_file.as_posix())
    node[prop] = temp_file.as_posix()
    print("加载材质图片", node[prop], obj.name)


def node_load_image_from_file(node: NodeBase, prop: str, obj: bpy.types.Object):
    bpy.ops.sdn.cfnode_image_importer("INVOKE_DEFAULT", tree_name=node.get_tree().name, node_name=node.name, prop_name=prop)


def node_load_image_from_canvas(node: NodeBase, prop: str, obj: bpy.types.Object):
    bpy.ops.sdn.cfnode_canvas_picker("INVOKE_DEFAULT", tree_name=node.get_tree().name, node_name=node.name, prop_name=prop)
    print("加载画布图片", node[prop], obj.name)


def node_load_image_from_render(node: NodeBase, prop: str, obj: bpy.types.Object):
    print("渲染图片", node[prop], obj.name)

    def run(node: NodeBase, prop: str, obj: bpy.types.Object):
        old = bpy.context.scene.render.filepath
        old_fmt = bpy.context.scene.render.image_settings.file_format

        temp_file = Path(gettempdir()) / f"{uuid4().hex}.png"
        bpy.context.scene.render.filepath = temp_file.as_posix()
        bpy.context.scene.render.image_settings.file_format = "PNG"
        node[prop] = temp_file.as_posix()
        bpy.ops.render.render(write_still=True)

        bpy.context.scene.render.filepath = old
        bpy.context.scene.render.image_settings.file_format = old_fmt

    Timer.put((run, node, prop, obj))


def node_delete_image(node: NodeBase, prop: str, obj: bpy.types.Object):
    node[prop] = ""
    print("删除图片", node[prop], obj.name)


# ---------------------INT FLOAT BOOLEAN ENUM COMBO STRING IMAGE---------------------
