import bpy


class SDViewportLayerRedrawProperties(bpy.types.PropertyGroup):
    pass


def register():
    bpy.types.Object.is_sdn_canvas_layer = bpy.props.BoolProperty(name="SDN Canvas Layer", default=False)


def unregister():
    del bpy.types.Object.is_sdn_canvas_layer
