import bpy
import gpu
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


class TextureSpaceGizmo(bpy.types.Gizmo):
    bl_idname = "TEXTURE_SPACE_GT_gizmo"
    bl_options = {"PERSISTENT", "SCALE", "SHOW_MODAL_ALL", "UNDO", "GRAB_CURSOR"}

    is_hover = False

    def draw(self, context):
        shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": [
            Vector((1, 1, 1)),
            Vector((1, 0, 1)),
            Vector((0, 1, 1)),
        ]}, indices=((0, 1), (1, 2)))
        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", 3 if self.is_hover else 0)
        shader.uniform_float("color", (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 0))
        batch.draw(shader)
        space_type, mode = ToolSelectPanelHelper._tool_key_from_context(context)
        cls = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
        item, tool, icon_value = cls._tool_get_active(context, space_type, mode, with_icon=True)

        # print("draw", self.bl_idname, tool)

    def invoke(self, context, event):
        bpy.ops.ed.undo_push(message="Push Undo")
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        ...

    def test_select(self, context, mouse_pos):
        return True


class TextureSpaceControl(bpy.types.GizmoGroup):
    bl_idname = "TEXTURE_SPACE_3D_control_gizmos"
    bl_label = "Texture Space"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        obj = context.object

        space_type, mode = ToolSelectPanelHelper._tool_key_from_context(context)
        cls = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
        item, tool, icon_value = cls._tool_get_active(context, space_type, mode, with_icon=True)

        return obj and obj.type == "MESH" and obj.mode == "OBJECT" and tool and tool.idname == "object.texture_space_tool"

    def setup(self, context):
        self.gizmos.new(TextureSpaceGizmo.bl_idname)

    def draw_prepare(self, context):
        context.area.tag_redraw()
        self.refresh(context)

    def refresh(self, context):
        context.area.tag_redraw()


clss = [
    TextureSpaceGizmo,
    TextureSpaceControl,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
