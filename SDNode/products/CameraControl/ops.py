import bpy


class SwitchWH(bpy.types.Operator):
    bl_idname = "render.switch_wh"
    bl_label = "Switch WH"

    def execute(self, context):
        render = context.scene.render
        render.resolution_x, render.resolution_y = render.resolution_y, render.resolution_x
        return {'FINISHED'}


clss = [
    SwitchWH,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
