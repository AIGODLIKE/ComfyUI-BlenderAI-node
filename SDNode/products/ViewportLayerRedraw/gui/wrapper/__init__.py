"""GUI Wrapper模块：提供节点树和材质节点的通用imgui控制封装"""

from .common_wrappers import (
    BaseAdapter,
    WidgetDescriptor,
    PropertyType,
    IntDescriptor,
    FloatDescriptor,
    BoolDescriptor,
    EnumDescriptor,
    ComboDescriptor,
    StringDescriptor,
    ImageDescriptor,
    DescriptorFactory,
    with_child,
)

from .nodetree_wrapper import (
    NodeTreeWrapper,
    NodeDescriptor,
    NodeAdapter,
)

from .material_wrapper import (
    MaterialWrapper,
    MaterialNodeDescriptor,
    ShaderNodeAdapter,
)

__all__ = [
    # 公共抽象
    "BaseAdapter",
    "WidgetDescriptor",
    "PropertyType",
    "IntDescriptor",
    "FloatDescriptor",
    "BoolDescriptor",
    "EnumDescriptor",
    "ComboDescriptor",
    "StringDescriptor",
    "ImageDescriptor",
    "DescriptorFactory",
    "with_child",
    # NodeTree封装
    "NodeTreeWrapper",
    "NodeDescriptor",
    "NodeAdapter",
    # Material封装
    "MaterialWrapper",
    "MaterialNodeDescriptor",
    "ShaderNodeAdapter",
]
