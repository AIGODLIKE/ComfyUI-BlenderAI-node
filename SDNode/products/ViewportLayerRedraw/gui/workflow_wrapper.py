from __future__ import annotations
from enum import Enum
from slimgui import imgui
from contextlib import contextmanager
from typing import Dict, List, Optional, Type
from .app.style import Const
from .app.app import App
from .texture import TexturePool
from ....nodes import NodeParser

"""
# 工作流相关(主要是节点)
WorkflowWrapper:
    - nodes: Dict[str, NodeDescriptor]

# 节点相关(主要是节点属性)
NodeDescriptor:
    - name: str
    - widgets: Dict[str, WidgetDescriptor]

# 与imgui对接 显示及编辑
WidgetDescriptor:
    - value: Any
    - display: function

"""


@contextmanager
def with_child(str_id: str, size: tuple[float, float] = (0.0, 0.0), child_flags: imgui.ChildFlags = imgui.ChildFlags.NONE, window_flags: imgui.WindowFlags = imgui.WindowFlags.NONE):
    imgui.begin_child(str_id, size, child_flags, window_flags)
    try:
        yield
    except Exception:
        pass
    imgui.end_child()


def object_info() -> Dict[str, Dict]:
    return NodeParser.CACHED_OBJECT_INFO


class WorkflowWrapper:
    """
    用于包装工作流json数据，以便在GUI中显示及编辑
    """

    def __init__(self) -> None:
        self.nodes: Dict[str, NodeDescriptor] = {}
        self.workflow = {}

    def load(self, data: Dict, filter=lambda _: True):
        self.workflow = data
        for node in self.workflow.get("nodes", []):
            if not filter(node):
                continue
            node = self._create_node(node)
            self.nodes[node.title] = node

    def _create_node(self, node_data) -> "NodeDescriptor":
        node = NodeDescriptor(self)
        node.load(node_data)
        return node

    def dump(self) -> Dict:
        for node in self.nodes.values():
            node.dump()
        return self.workflow


class NodeDescriptor:
    def __init__(self, node_data: Dict):
        self.metadata: Dict = node_data
        self.title: str = ""
        self.type: str = ""

        self.name: str = ""
        self.widgets: Dict[str, WidgetDescriptor] = {}
        self.widgets_values: List = []
        self.widgets_order: Dict[str, int] = {}

    def load(self, node_data: Dict):
        self.metadata = node_data
        self.title = node_data["title"]
        self.type = node_data["type"]
        self.widgets_values = node_data.get("widgets_values", [])
        self.widgets.clear()

        lsquad = self.title.rfind("[")
        rsquad = self.title.rfind("]")
        if lsquad == -1 or rsquad == -1:
            return
        self.name = self.title[1:lsquad]
        node_def = object_info().get(self.type, {})
        if not node_def:
            return

        widgets = {}
        widgets_order = []
        for inp_channel in ["required", "optional", "hidden"]:
            widgets_order += node_def["input_order"].get(inp_channel, [])
            for inp, inp_desc in node_def["input"].get(inp_channel, {}).items():
                wtype = inp_desc[0]
                if isinstance(wtype, List):
                    wtype = "ENUM"
                if wtype not in {"ENUM", "INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"}:
                    continue
                widgets[inp] = inp_desc
                if inp in {"seed", "noise_seed"}:
                    widgets["control_after_generate"] = []
        widgets_order = [w for w in widgets_order if w in widgets]
        self.widgets_order = {w: i for i, w in enumerate(widgets)}
        # print(self.widgets_order)

        for arg in self.title[lsquad + 1 : rsquad].split(","):
            wname = arg.strip()
            if wname not in widgets:
                continue
            widget = widgets[wname]
            wtype = widget[0]
            if isinstance(wtype, List):
                wtype = "ENUM"
            # 特殊处理
            if self.type == "输入图像" and wtype == "STRING":
                wtype = "IMAGE"
            self.widgets[wname] = DescriptorFactory.create(wname, wtype, self.title, widget)

    def dump(self):
        for widget in self.widgets.values():
            widget.dump()


# ---------------------INT FLOAT BOOLEAN ENUM COMBO STRING IMAGE---------------------


class PropertyType(Enum):
    NONE = "NONE"
    INT = "INT"
    FLOAT = "FLOAT"
    BOOLEAN = "BOOLEAN"
    ENUM = "ENUM"
    COMBO = "COMBO"
    STRING = "STRING"
    IMAGE = "IMAGE"


class WidgetDescriptor:
    ptype: PropertyType = PropertyType.NONE

    def __init__(self, widget_name: str, node_title: str = "", widget_def: Dict = None):
        self.widget_name = widget_name
        self.node_title = node_title
        self.widget_def = widget_def
        self.prop_index: int = -1
        self.widgets_values: List = []
        self.flags = 0
        self.flags |= imgui.ChildFlags.FRAME_STYLE
        self.flags |= imgui.ChildFlags.AUTO_RESIZE_Y
        self.flags |= imgui.ChildFlags.ALWAYS_AUTO_RESIZE

    @property
    def value(self):
        return self.widgets_values[self.prop_index]

    @value.setter
    def value(self, value):
        self.widgets_values[self.prop_index] = value

    def get_node_context(self, workflow: WorkflowWrapper) -> Optional[NodeDescriptor]:
        return workflow.nodes.get(self.node_title) if workflow else None

    def get_node_def(self, workflow: WorkflowWrapper) -> Optional[Dict]:
        node = self.get_node_context(workflow)
        if not node:
            return {}
        return object_info().get(node.type) if workflow else {}

    def dump(self):
        pass

    def display_begin(self, wrapper: WorkflowWrapper, app: App):
        imgui.push_id(f"{self.node_title}_{self.widget_name}")

    def display(self, wrapper: WorkflowWrapper, app: App):
        pass

    def display_end(self, wrapper: WorkflowWrapper, app: App):
        imgui.pop_id()


class IntDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.INT

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    # 实现imgui显示Int编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if self.prop_index == -1:
            self.widgets_values = node.widgets_values
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
        if self.prop_index == -1:
            return
        cfg = {
            "default": 0,
            "min": -65535,
            "max": +65535,
            "step": 1,
        }
        if len(self.widget_def) >= 2 and isinstance(self.widget_def[1], Dict):
            cfg.update(self.widget_def[1])
        imgui.push_style_var(imgui.StyleVar.GRAB_ROUNDING, Const.GRAB_R)
        imgui.push_style_color(imgui.Col.TEXT, (1, 1, 1, 0.7))
        imgui.push_style_color(imgui.Col.FRAME_BG_HOVERED, Const.RP_R_FRAME_BG_HOVERED)
        imgui.push_style_color(imgui.Col.FRAME_BG_ACTIVE, Const.RP_R_FRAME_BG_ACTIVE)
        imgui.push_style_color(imgui.Col.SLIDER_GRAB, Const.SLIDER_NORMAL)
        with with_child(f"##Workflow_{self.node_title}_{self.widget_name}", (0, 0), child_flags=self.flags):
            imgui.push_id(f"##Prop_{self.node_title}_{self.widget_name}")
            imgui.push_item_width(-1)
            vmin = max(-(2**30), cfg["min"])
            vmax = min(2**30 - 1, cfg["max"])
            _, self.value = imgui.slider_int("", self.value, vmin, vmax, f"{self.widget_name} [%d]")
            imgui.pop_item_width()
            imgui.pop_id()

        imgui.pop_style_var(1)
        imgui.pop_style_color(4)


class FloatDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.FLOAT

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    # 实现imgui显示Float编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if self.prop_index == -1:
            self.widgets_values = node.widgets_values
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
        if self.prop_index == -1:
            return
        cfg = {
            "min": 0.0,
            "max": 100.0,
            "step": 10.0,
            "default": 8.0,
        }
        if len(self.widget_def) >= 2 and isinstance(self.widget_def[1], Dict):
            cfg.update(self.widget_def[1])
        imgui.push_style_var(imgui.StyleVar.GRAB_ROUNDING, Const.GRAB_R)
        imgui.push_style_color(imgui.Col.TEXT, (1, 1, 1, 0.7))
        imgui.push_style_color(imgui.Col.FRAME_BG_HOVERED, Const.RP_R_FRAME_BG_HOVERED)
        imgui.push_style_color(imgui.Col.FRAME_BG_ACTIVE, Const.RP_R_FRAME_BG_ACTIVE)
        imgui.push_style_color(imgui.Col.SLIDER_GRAB, Const.SLIDER_NORMAL)
        with with_child(f"##Workflow_{self.node_title}_{self.widget_name}", (0, 0), child_flags=self.flags):
            imgui.push_id(f"##Prop_{self.node_title}_{self.widget_name}")
            imgui.push_item_width(-1)
            _, self.value = imgui.slider_float("", self.value, cfg["min"], cfg["max"], f"{self.widget_name} [%.4f]")
            imgui.pop_item_width()
            imgui.pop_id()

        imgui.pop_style_var(1)
        imgui.pop_style_color(4)


class BoolDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.BOOLEAN

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    # 实现imgui显示Bool编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if self.prop_index == -1:
            self.widgets_values = node.widgets_values
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
        if self.prop_index == -1:
            return
        imgui.text("Bool: " + str(self.value))


class EnumDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.ENUM

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self._index: int = 0
        self._cached_items: List[str] = []

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, value: int):
        self._index = value
        self.value = self._cached_items[self._index]

    # 实现imgui显示Enum编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if not self._cached_items:
            self.widgets_values = node.widgets_values
            if not isinstance(self.widget_def[0], List):
                return
            self._cached_items = self.widget_def[0]
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
            if self.prop_index == -1:
                return
            value = self.widgets_values[self.prop_index]
            try:
                self.index = self._cached_items.index(value)
            except ValueError:
                print()

        with with_child(f"##Workflow_{self.node_title}_{self.widget_name}", (0, 0), child_flags=self.flags):
            imgui.push_id(f"##Prop_{self.node_title}_{self.widget_name}")
            imgui.push_item_width(-1)
            changed, self.index = imgui.combo("", self.index, self._cached_items)
            imgui.pop_item_width()
            imgui.pop_id()


class ComboDescriptor(EnumDescriptor):
    ptype: PropertyType = PropertyType.COMBO


class StringDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.STRING

    # 实现imgui显示String编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if self.prop_index == -1:
            self.widgets_values = node.widgets_values
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
        if self.prop_index == -1:
            return

        with with_child(f"##Workflow_{self.node_title}_{self.widget_name}", (0, 240), child_flags=self.flags):
            imgui.text(f"{node.name}: {self.widget_name}")
            imgui.dummy((1, 4))
            imgui.push_style_var(imgui.StyleVar.SCROLLBAR_ROUNDING, Const.CHILD_SB_R)
            imgui.push_style_var(imgui.StyleVar.SCROLLBAR_SIZE, Const.CHILD_SB_S)
            imgui.push_style_var(imgui.StyleVar.SCROLLBAR_PADDING, Const.CHILD_SB_P)
            imgui.push_style_color(imgui.Col.FRAME_BG, Const.FRAME_BG)
            imgui.push_style_color(imgui.Col.SCROLLBAR_BG, Const.CHILD_SB_BG)
            imgui.push_style_color(imgui.Col.SCROLLBAR_GRAB, Const.CHILD_SB_GRAB)
            imgui.push_style_color(imgui.Col.SCROLLBAR_GRAB_ACTIVE, Const.CHILD_SB_GRAB_ACTIVE)
            imgui.push_style_color(imgui.Col.SCROLLBAR_GRAB_HOVERED, Const.CHILD_SB_GRAB_HOVERED)
            app.font_manager.push_content_font()
            mlt_flags = imgui.InputTextFlags.WORD_WRAP
            imgui.push_id(f"##Prop_{self.node_title}_{self.widget_name}")
            changed, self.value = imgui.input_text_multiline("", self.value, (-1, -1), mlt_flags)
            imgui.pop_id()
            app.font_manager.pop_font()
            imgui.pop_style_var(3)
            imgui.pop_style_color(5)


class ImageDescriptor(WidgetDescriptor):
    ptype: PropertyType = PropertyType.IMAGE

    def __init__(self, *arg, **kwargs):
        super().__init__(*arg, **kwargs)

    def show_input_image_widget(self, image, w, h, rw, rh):
        icon = TexturePool.get_tex_id(image)
        imgui.image_button(f"{self.node_title}_{self.widget_name}1", icon, (w, h))

    def dump(self):
        pass

    # 实现imgui显示Image编辑
    def display(self, wrapper: WorkflowWrapper, app: App):
        node = self.get_node_context(wrapper)
        if not node:
            return
        if self.prop_index == -1:
            self.widgets_values = node.widgets_values
            self.prop_index = node.widgets_order.get(self.widget_name, -1)
        if self.prop_index == -1:
            return
        with with_child(f"##Workflow_{self.node_title}_{self.widget_name}", (0, 0), child_flags=self.flags):
            imgui.push_id(f"##Prop_{self.node_title}_{self.widget_name}")
            imgui.text(f"输入图像: {self.widget_name}")

            imgui.push_style_color(imgui.Col.FRAME_BG, (56 / 255, 56 / 255, 56 / 255, 1))
            with with_child(f"##Workflow_{self.node_title}_{self.widget_name}_Innder", (0, 0), child_flags=self.flags):
                imgui.begin_table(f"##Prop_{self.node_title}_{self.widget_name}_List", 3, imgui.TableFlags.BORDERS)
                bw, bh = 102, 102
                imgui.table_next_column()
                icon = TexturePool.get_tex_id("camera")
                imgui.image_button(f"{self.node_title}_{self.widget_name}1", icon, (bw, bh))
                icon = TexturePool.get_tex_id("new")
                imgui.table_next_column()
                imgui.image_button(f"{self.node_title}_{self.widget_name}2", icon, (bw, bh))
                imgui.end_table()

            imgui.pop_style_color()
            imgui.pop_id()


# ---------------------INT FLOAT BOOLEAN ENUM COMBO STRING IMAGE---------------------


class DescriptorFactory:
    _registry: Dict[str, Type[WidgetDescriptor]] = {}

    @classmethod
    def register(cls, wtype: str, descriptor_class: Type[WidgetDescriptor]):
        cls._registry[wtype] = descriptor_class

    @classmethod
    def create(cls, wname: str, wtype: str, node_title: str, data: Dict) -> WidgetDescriptor:
        desctype = cls._registry.get(wtype, WidgetDescriptor)
        descriptor = desctype(wname, node_title, data)
        return descriptor


DescriptorFactory.register(PropertyType.INT.name, IntDescriptor)
DescriptorFactory.register(PropertyType.FLOAT.name, FloatDescriptor)
DescriptorFactory.register(PropertyType.BOOLEAN.name, BoolDescriptor)
DescriptorFactory.register(PropertyType.ENUM.name, EnumDescriptor)
DescriptorFactory.register(PropertyType.COMBO.name, ComboDescriptor)
DescriptorFactory.register(PropertyType.STRING.name, StringDescriptor)
DescriptorFactory.register(PropertyType.IMAGE.name, ImageDescriptor)
