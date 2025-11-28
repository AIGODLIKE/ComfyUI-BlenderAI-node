import bpy

modules = ["gizmo", "texture_space_tool", "ops"]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)
import numpy as np

def get_wh(self):
    ofl, ofr, oft, ofb = self.texture_space_control_offset[:]
    ll = np.multiply(ofl, np.divide(iw, dx))
    rr = np.multiply(ofr, np.divide(iw, dx))
    tt = np.multiply(oft, np.divide(ih, dy))
    bb = np.multiply(ofb, np.divide(ih, dy))
    return Vector((rr + ll, tt + bb))

def set_wh(self, value):
    ...


def register():
    bpy.types.Object.texture_space_control_offset = bpy.props.FloatVectorProperty(
        name="Texture Control Offset",
        description="左右上下",
        default=(0, 0, 0, 0),
        size=4,
        options={"TEXTEDIT_UPDATE"}
    )
    bpy.types.Object.texture_wh = bpy.props.IntVectorProperty(
        name="Texture Width Height", default=(0, 0), size=2,
        get=get_wh,
        set=set_wh,
    )
    reg()


def unregister():
    unreg()
    del bpy.types.Object.texture_space_control_offset
