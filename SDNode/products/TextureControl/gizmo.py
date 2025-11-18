import bpy
import gpu
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

DIRECTION_ITEMS = [
    "RIGHT",
    "BOTTOM",
    "LEFT",
    "TOP",
    "LEFT_TOP",
    "RIGHT_TOP",
    "LEFT_BOTTOM",
    "RIGHT_BOTTOM",
]


class TextureSpaceGizmo(bpy.types.Gizmo):
    bl_idname = "TEXTURE_SPACE_GT_gizmo"
    bl_options = {"PERSISTENT", "SCALE", "SHOW_MODAL_ALL", "UNDO", "GRAB_CURSOR"}

    is_hover = False
    direction_index: int = 0

    @property
    def color(self):
        return (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 1)

    @property
    def line_width(self):
        return 5 if self.is_hover else 2

    @property
    def is_corner(self) -> bool:
        return "_" in self.direction

    @property
    def points(self) -> list[Vector]:
        obj = bpy.context.object
        bound_box = obj.bound_box
        return [Vector(bound_box[i]) for i in (1, 2, 5, 6)]

    @property
    def point(self) -> Vector:
        """
        a----b
        |    |
        c----d
        """
        points = self.points
        a, b, c, d = points
        if v := {
            "RIGHT": (b, d),
            "BOTTOM": (c, d),
            "LEFT": (a, c),
            "TOP": (a, b),
            "LEFT_TOP": a,
            "RIGHT_TOP": b,
            "LEFT_BOTTOM": c,
            "RIGHT_BOTTOM": d,
        }.get(self.direction):
            if isinstance(v, tuple):
                aa, bb = v
                return (aa + bb) / 2
            else:
                return v
        return Vector((0, 0, 0))

    @property
    def is_vertical(self):
        return self.direction in ("BOTTOM", "TOP")

    def tow_2d_point(self, context, matrix=None):
        obj = context.object
        dim = max(obj.dimensions) * 0.1

        p = self.point
        if self.is_vertical:
            a, b = Vector((0, dim, 0)), Vector((0, -dim, 0))
        else:
            a, b = Vector((dim, 0, 0)), Vector((-dim, 0, 0))

        mat = obj.matrix_world
        if matrix:
            mat = mat @ matrix
        return mat @ (p + a), mat @ (p + b)

    @property
    def direction(self) -> str:
        return DIRECTION_ITEMS[self.direction_index]

    def draw_corner(self, context):
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'POINTS', {"pos": [self.point, ]})
        # shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        # shader.uniform_float("lineWidth", 3 if self.is_hover else 0)
        shader.uniform_float("color", (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 0))
        batch.draw(shader)

        with gpu.matrix.push_pop():
            # x, y = self.camera_border_2d[self.corner_index]
            # gpu.matrix.translate((x, y))
            # text = f"{self.corner_index} {self.camera_border_2d[self.corner_index]} {self.direction} {self.is_hover}"
            # blf.position(0, 0, 0, 0)
            # blf.size(0, 10)
            # blf.draw(0, text)
            # gpu_extras.presets.draw_circle_2d((0, 0, 0), (1, 1, 1, 1), 10)

            dim = max(context.object.dimensions) * 0.1
            omv = dim  # offset margin value
            ov = dim  # offset margin
            corner_offset = {
                "LEFT_TOP": ((-omv, -ov, 0), (-omv, omv, 0), (ov, omv, 0)),
                "RIGHT_TOP": ((-ov, omv, 0), (omv, omv, 0), (omv, -ov, 0)),
                "LEFT_BOTTOM": ((-omv, ov, 0), (-omv, -omv, 0), (ov, -omv, 0)),
                "RIGHT_BOTTOM": ((-ov, -omv, 0), (omv, -omv, 0), (omv, ov, 0)),
            }

            color = self.color
            points = corner_offset.get(self.direction)
            shader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
            batch = batch_for_shader(shader, 'LINES', {
                "pos": list(context.object.matrix_world @ (Vector(i) + self.point) for i in points),
                "color": [color, color, color]
            },
                                     indices=((0, 1), (1, 2)))
            shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
            shader.uniform_float("lineWidth", self.line_width)
            batch.draw(shader)

            return
            # points = self.corner_offset.get(self.direction)
            shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
            batch = batch_for_shader(shader, 'LINES', {"pos": self.tow_2d_point(context)}, indices=((0, 1), (1, 2)))
            shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
            shader.uniform_float("lineWidth", 3 if self.is_hover else 0)
            shader.uniform_float("color", (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 0))
            batch.draw(shader)

    def draw(self, context):
        gpu.state.line_width_set(self.line_width)
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("ALWAYS")
        if self.is_corner:
            self.draw_corner(context)
            return

        color = self.color
        shader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": self.tow_2d_point(context), "color": [color, color]},
                                 indices=((0, 1),)
                                 )
        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", self.line_width)
        batch.draw(shader)
        # with gpu.matrix.push_pop():
        # obj = context.object
        # gpu.matrix.translate(obj.matrix_world.translation)

        # space_type, mode = ToolSelectPanelHelper._tool_key_from_context(context)
        # cls = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
        # item, tool, icon_value = cls._tool_get_active(context, space_type, mode, with_icon=True)
        # print("draw", self.bl_idname, tool)
        # blf.size(0, 20)
        # blf.position(0, *self.point)
        # blf.draw(0, self.direction)
        # gpu_extras.presets.draw_circle_2d((0, 0, 0), (1, 1, 1, 1), 1)

    def invoke(self, context, event):
        bpy.ops.ed.undo_push(message="Push Undo")
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        ...

    def test_select(self, context, mouse_pos):
        # mathutils.geometry.intersect_point_line_segment
        return True


class TextureSpaceControl(bpy.types.GizmoGroup):
    bl_idname = "TEXTURE_SPACE_3D_control_gizmos"
    bl_label = "Texture Space"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {"3D", 'PERSISTENT', 'SHOW_MODAL_ALL'}  # 'SCALE',

    @classmethod
    def poll(cls, context):
        obj = context.object
        space_type, mode = ToolSelectPanelHelper._tool_key_from_context(context)
        cla = ToolSelectPanelHelper._tool_class_from_space_type(space_type)
        item, tool, icon_value = cla._tool_get_active(context, space_type, mode, with_icon=True)

        return obj and obj.type == "MESH" and obj.mode == "OBJECT" and tool and tool.idname == "object.texture_space_tool"

    def setup(self, context):
        for i in range(len(DIRECTION_ITEMS)):
            gz = self.gizmos.new(TextureSpaceGizmo.bl_idname)
            gz.direction_index = i
            gz.base_scale = 0.01
            gz.use_draw_scale = True
            gz.line_width = 1

        # gz = self.gizmos.new("GIZMO_GT_arrow_3d")
        # gz.draw_style = "NORMAL"
        # gz.aspect = (0, 0)

    def draw_prepare(self, context):
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
