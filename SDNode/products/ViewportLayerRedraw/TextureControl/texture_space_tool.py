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

    is_running = False

    last_active_tool = None  # 开始
    origin_tools = None

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj and obj.type == "MESH" and cls.is_running

    def draw_settings(self, layout, tool):
        ...

    @classmethod
    def start(cls):
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper, activate_by_id
        view_3d = ToolSelectPanelHelper._tool_class_from_space_type("VIEW_3D")
        object_tools = view_3d._tools['OBJECT']
        if cls.origin_tools is None:
            cls.origin_tools = object_tools.copy()
        if cls.last_active_tool is None:
            cls.last_active_tool = view_3d._tool_get_active(context, "VIEW_3D", "OBJECT")
        tt = [i for i in object_tools if i.idname == "object.texture_space_tool"][0]
        view_3d._tools['OBJECT'] = [tt, ]
        activate_by_id(context, "VIEW_3D", "object.texture_space_tool")
        cls.is_running = True

    @classmethod
    def stop(cls):
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper, activate_by_id
        view_3d = ToolSelectPanelHelper._tool_class_from_space_type("VIEW_3D")
        view_3d._tools['OBJECT'] = cls.origin_tools
        activate_by_id(context, "VIEW_3D", cls.last_active_tool)

        cls.last_active_tool = None
        cls.origin_tools = None
        cls.is_running = False

    @classmethod
    def check(cls):
        return cls.is_running


def register():
    bpy.utils.register_tool(TextureSpaceTool, after=["builtin.measure"])


def unregister():
    bpy.utils.unregister_tool(TextureSpaceTool)
