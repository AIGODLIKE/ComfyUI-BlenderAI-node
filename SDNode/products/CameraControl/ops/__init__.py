import bpy


class SwitchWH(bpy.types.Operator):
    bl_idname = "render.switch_wh"
    bl_label = "Switch WH"
    bl_description = "Switch WH"

    def execute(self, context):
        render = context.scene.render
        render.resolution_x, render.resolution_y = render.resolution_y, render.resolution_x
        return {'FINISHED'}


class PanCamera(bpy.types.Operator):
    bl_idname = "render.pan_camera"
    bl_label = "Pan Camera"
    bl_description = "Pan Camera"

    def invoke(self, context, event):
        from ..utils import get_active_camera
        camera = get_active_camera(context)
        with context.temp_override(selected_objects=[camera, ]):
            bpy.ops.transform.translate("INVOKE_DEFAULT", True)
        return {"PASS_THROUGH", "FINISHED"}


class DollyCamera(bpy.types.Operator):
    bl_idname = "render.dolly_camera"
    bl_label = "Dolly Camera"
    bl_description = "Dolly Camera"

    def invoke(self, context, event):
        from ..utils import get_active_camera
        camera = get_active_camera(context)
        with context.temp_override(selected_objects=[camera, ], active_object=camera, object=camera):
            bpy.ops.transform.translate("INVOKE_DEFAULT", True,
                                        orient_matrix_type='LOCAL',
                                        orient_type='LOCAL',
                                        constraint_axis=(False, False, True))
        return {"PASS_THROUGH", "FINISHED"}


clss = [
    SwitchWH,
    PanCamera,
    DollyCamera,
]

reg, unreg = bpy.utils.register_classes_factory(clss)

modules = ["camera_to_board", "board_to_camera", "texture_space"]

reg_submodule, unreg_submodule = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    reg()
    reg_submodule()


def unregister():
    unreg()
    unreg_submodule()
