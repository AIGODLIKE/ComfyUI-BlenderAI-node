import bpy

from ....kclogger import logger

modules = ["gizmo", "texture_space_tool", "ops"]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    bpy.types.Object.texture_space_control_offset = bpy.props.FloatVectorProperty(
        name="Texture Control Offset",
        description="左右上下",
        default=(0, 0, 0, 0),
        size=4,
        options={"TEXTEDIT_UPDATE"}
    )
    reg()
    logger.debug(f"{__package__} registered")


def unregister():
    unreg()
    logger.debug(f"{__package__} unregistered")

    del bpy.types.Object.texture_space_control_offset
