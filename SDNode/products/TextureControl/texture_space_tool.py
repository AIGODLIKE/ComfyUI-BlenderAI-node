import bpy


class TextureSpaceTool(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'

    bl_idname = "object.texture_space_tool"
    bl_label = "Texture Space Tool"
    bl_description = "Texture Space Tool"
    bl_icon = "ops.transform.shrink_fatten"
    bl_widget = "TEXTURE_SPACE_3D_control_gizmos"
    bl_keymap = (
        ("transform.translate", {"type": 'G', "value": 'PRESS'}, {"properties": [
            ("texture_space", True),
            ("constraint_axis", (True, True, False)),
            ("orient_matrix_type", 'LOCAL'),
            ("orient_type", 'LOCAL'),
        ]}),
        ("transform.resize", {"type": 'S', "value": 'PRESS'}, {"properties": [("texture_space", True)]}),
        ("object.texture_space_location_restore", {"type": 'G', "value": 'PRESS', "alt": True}, {}),
        ("object.texture_space_scale_restore", {"type": 'S', "value": 'PRESS', "alt": True}, {}),
    )

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH"

    def draw_settings(self, layout, tool):
        ...


def register():
    bpy.utils.register_tool(TextureSpaceTool, after=["builtin.measure"])


def unregister():
    bpy.utils.unregister_tool(TextureSpaceTool)
