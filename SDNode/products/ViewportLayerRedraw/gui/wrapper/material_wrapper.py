from __future__ import annotations
import bpy
from slimgui import imgui
from typing import Any, Dict, List, Optional
from .common_wrappers import WidgetDescriptor, DescriptorFactory, BaseAdapter
from .common_wrappers import with_child


class ShaderNodeAdapter(BaseAdapter):
    """
    Blender 着色器节点属性访问适配器：通过统一接口控制材质节点的输入socket和RNA属性
    """

    def __init__(self, node: bpy.types.ShaderNode, prop_name: str):
        super().__init__(name=f"{node.name}.{prop_name}")
        self.node = node
        self.prop_name = prop_name
        self._prop_source = self._detect_property_source()

    def _detect_property_source(self) -> str:
        """检测属性来源：socket还是rna属性"""
        # 检查是否为input socket
        if self.prop_name in self.node.inputs:
            return "socket"
        # 检查是否为RNA属性
        elif hasattr(self.node, self.prop_name):
            return "rna"
        return "none"

    def get_ctxt(self) -> str:
        return "*"

    def get_meta(self, prop: str) -> Any:
        """返回属性元数据，用于推断控件类型"""
        if self._prop_source == "socket":
            socket: bpy.types.NodeSocket = self.node.inputs[self.prop_name]
            socket_type = socket.type
            try:
                socket = self.node.node_tree.interface.items_tree[self.prop_name]
            except Exception:
                pass
            # 根据socket类型推断元数据
            if socket_type == "VALUE":
                # 尝试获取范围属性
                min_val = getattr(socket, "min_value", 0.0)
                max_val = getattr(socket, "max_value", 1.0)
                return ["FLOAT", {"min": min_val, "max": max_val, "default": socket.default_value}]
            elif socket_type == "INT":
                min_val = getattr(socket, "min_value", 0)
                max_val = getattr(socket, "max_value", 100)
                return ["INT", {"min": min_val, "max": max_val, "default": socket.default_value}]
            elif socket_type == "RGBA":
                return ["RGBA", {}]
            elif socket_type == "BOOLEAN":
                return ["BOOLEAN", {}]
            elif socket_type == "STRING":
                return ["STRING", {}]
        elif self._prop_source == "rna":
            # 从RNA属性获取元数据
            try:
                prop_rna = self.node.bl_rna.properties.get(self.prop_name)
                if prop_rna:
                    if prop_rna.type == "FLOAT":
                        return ["FLOAT", {"min": prop_rna.hard_min, "max": prop_rna.hard_max, "default": prop_rna.default}]
                    elif prop_rna.type == "INT":
                        return ["INT", {"min": prop_rna.hard_min, "max": prop_rna.hard_max, "default": prop_rna.default}]
                    elif prop_rna.type == "BOOLEAN":
                        return ["BOOLEAN", {}]
                    elif prop_rna.type == "ENUM":
                        items = [item.identifier for item in prop_rna.enum_items]
                        return [items, {}]
                    elif prop_rna.type == "STRING":
                        return ["STRING", {}]
            except Exception:
                pass
        return ["NONE", {}]

    def get_value(self, prop: str) -> Any:
        if self._prop_source == "socket":
            socket: bpy.types.NodeSocket = self.node.inputs[self.prop_name]
            return socket.default_value
        elif self._prop_source == "rna":
            return getattr(self.node, self.prop_name, None)
        return None

    def set_value(self, prop: str, value: Any) -> None:
        if self._prop_source == "socket":
            socket = self.node.inputs[self.prop_name]
            socket.default_value = value
        elif self._prop_source == "rna":
            try:
                setattr(self.node, self.prop_name, value)
            except Exception:
                pass

    def on_image_action(self, prop: str, action: str) -> None:
        # 材质节点暂不支持图像操作
        pass


class MaterialNodeDescriptor:
    """
    材质节点描述器：封装材质节点及其可控属性
    """

    def __init__(self):
        self.node: Optional[bpy.types.ShaderNode] = None
        self.display_name: str = ""
        self.widgets: Dict[str, WidgetDescriptor] = {}
        self.adapter: BaseAdapter = None
        self.flags = 0
        self.flags |= imgui.ChildFlags.FRAME_STYLE
        self.flags |= imgui.ChildFlags.AUTO_RESIZE_Y
        self.flags |= imgui.ChildFlags.ALWAYS_AUTO_RESIZE

    @property
    def node_title(self):
        return self.node.name if self.node else ""

    @property
    def node_type(self):
        return self.node.type if self.node else ""

    def load(self, node: bpy.types.ShaderNode, prop_names: List[str]):
        """
        加载节点及其属性列表
        Args:
            node: Blender着色器节点
            prop_names: 要控制的属性名列表
        """
        self.node = node
        self.display_name = node.label or node.name
        self.widgets.clear()

        for prop_name in prop_names:
            adapter = ShaderNodeAdapter(node, prop_name)
            meta = adapter.get_meta(prop_name)
            wtype = meta[0]

            # 类型映射
            type_map = {
                "VALUE": "FLOAT",
                "FLOAT": "FLOAT",
                "INT": "INT",
                "BOOLEAN": "BOOLEAN",
                "STRING": "STRING",
                "COLOR": "COLOR",
                "RGB": "COLOR",
                "RGBA": "COLOR",  # 暂不支持颜色控件，可扩展
            }

            if isinstance(wtype, list):
                wtype = "ENUM"
            elif wtype in type_map:
                wtype = type_map[wtype]
            else:
                continue

            # 先设置临时adapter，避免DescriptorFactory创建时访问None
            self.adapter = adapter

            # 创建控件描述器
            widget = DescriptorFactory.create(prop_name, wtype, self)
            # 再次确保adapter正确设置
            widget.adapter = adapter
            widget.widget_def = meta
            self.widgets[prop_name] = widget

        # 清空临时adapter
        self.adapter = None

    def display(self, wrapper, app):
        with with_child(self.node_title, (0, 0), self.flags):
            for widget in self.widgets.values():
                widget.display_begin(wrapper, app)
                widget.display(wrapper, app)
                widget.display_end(wrapper, app)


class MaterialWrapper:
    """
    材质包装器：管理材质节点树，为GUI提供节点属性控制
    """

    def __init__(self):
        self.material: Optional[bpy.types.Material] = None
        self.node_descriptors: Dict[str, MaterialNodeDescriptor] = {}

    def load(self, material: bpy.types.Material, filter=lambda _: True):
        self.material = material
        self.node_descriptors.clear()

        if not material or not material.node_tree:
            return

        node_config: Dict[str, List[str]] = {}

        for node in material.node_tree.nodes:
            if not filter(node):
                continue
            node_config[node.name] = []
            for inp in node.inputs:
                if inp.is_linked:
                    continue
                node_config[node.name].append(inp.name)

        for node_name in sorted(node_config):
            prop_names = node_config[node_name]
            node = material.node_tree.nodes.get(node_name)
            descriptor = MaterialNodeDescriptor()
            descriptor.load(node, prop_names)
            self.node_descriptors[node_name] = descriptor
