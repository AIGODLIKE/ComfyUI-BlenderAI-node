import blf
import bpy
import gpu
from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import intersect_point_line

from .utils import line_factor_point, scale_to_matrix
import bmesh
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


def test_hover(context, a, b, mouse_pos):
    a, b = [location_3d_to_region_2d(context.region, context.space_data.region_3d, v) for v in
            (a, b)]  # 两个点转换为屏幕坐标
    factor = intersect_point_line(mouse_pos, a, b)[1]  # 获取鼠标和线段相交点系数
    p = line_factor_point(a, b, factor)  # 获取鼠标投到线段上的点
    mouse_distance = (p - Vector(mouse_pos)).length

    if (0 < factor < 1) and mouse_distance < 5:
        is_hover = 0
    else:
        is_hover = -1
    return is_hover


class TextureSpaceGizmo(bpy.types.Gizmo):
    bl_idname = "TEXTURE_SPACE_GT_gizmo"
    bl_options = {"PERSISTENT", "SHOW_MODAL_ALL", "UNDO", "GRAB_CURSOR"}
    # "SCALE",
    is_hover = False
    direction_index: int = 0
    start_mouse: Vector
    start_texture_space_control_offset = Vector

    bl_target_properties = (
        {"id": "texture_space_control_offset", "type": "FLOAT", "array_length": 4},
    )

    @property
    def line_width(self):
        return 5 if self.is_hover else 2

    @property
    def is_vertical(self):
        return self.direction in ("BOTTOM", "TOP")

    @property
    def is_corner(self) -> bool:
        return "_" in self.direction

    @property
    def is_negative_xis(self) -> bool:
        return self.direction in ("LEFT", "BOTTOM")

    @property
    def points(self) -> list[Vector]:
        """
        b----d
        |    |
        a----c
        """

        obj = bpy.context.object
        bound_box = obj.bound_box
        return [Vector(bound_box[i]) for i in (1, 2, 5, 6)]

    def offset(self) -> Vector:
        l, r, t, b = self.target_get_value("texture_space_control_offset")
        # print("offset", l, r, t, b)
        if of := {
            "RIGHT": (r, 0, 0),
            "BOTTOM": (0, b, 0),
            "LEFT": (l, 0, 0),
            "TOP": (0, t, 0),
            "LEFT_TOP": (l, t, 0),
            "RIGHT_TOP": (r, t, 0),
            "LEFT_BOTTOM": (l, b, 0),
            "RIGHT_BOTTOM": (r, b, 0),
        }.get(self.direction):
            return Vector(of)
        return Vector((0, 0, 0))

    def anchor_point(self, context, offset=True, direction=None):
        """定位点
        在角上就是一个点
        在边上就是两个点
        """
        if direction is None:
            direction = self.direction
        points = self.points
        a, b, c, d = points
        if v := {
            "RIGHT": (d, c),
            "BOTTOM": (a, c),
            "LEFT": (b, a),
            "TOP": (b, d),
            "LEFT_TOP": b,
            "RIGHT_TOP": d,
            "LEFT_BOTTOM": a,
            "RIGHT_BOTTOM": c,
        }.get(direction):
            if isinstance(v, tuple):
                aa, bb = v
                if offset:
                    l, r, t, bo = self.target_get_value("texture_space_control_offset")
                    if self.is_vertical:
                        oa = (l, 0, 0)
                        ob = (r, 0, 0)
                    else:
                        oa = (0, t, 0)
                        ob = (0, bo, 0)
                    aa = aa + Vector(oa)
                    bb = bb + Vector(ob)
                return aa, bb
            else:
                return v
        return Vector((0, 0, 0))

    def point(self, context, ap=None, offset=True, direction=None) -> Vector:
        if ap is None:
            ap = self.anchor_point(context, offset, direction)
        if isinstance(ap, tuple):
            aa, bb = ap
            value = (aa + bb) / 2
        else:
            value = ap

        if offset:
            po = value + self.offset()
        else:
            po = value
        return po

    def tow_2d_point(self, context, matrix=None):
        obj = context.object
        dim = max(obj.dimensions)
        a, b = self.anchor_point(context)
        dim = min((a - b).length, dim) * 0.1

        p = self.point(context)
        if self.is_vertical:
            a, b = Vector((dim, 0, 0)), Vector((-dim, 0, 0))
        else:
            a, b = Vector((0, dim, 0)), Vector((0, -dim, 0))

        mat = obj.matrix_world
        if matrix:
            mat = mat @ matrix
        return mat @ (p + a), mat @ (p + b)

    def corner_3d_points(self, context):
        l, r, t, bo = self.target_get_value("texture_space_control_offset")
        a, b, c, d = self.points
        e = ((b + Vector((l, 0, 0))) - (d + Vector((r, 0, 0)))).length
        f = ((b + Vector((0, t, 0))) - (a + Vector((0, bo, 0)))).length

        obj = context.object
        dim = max(obj.dimensions)
        dim = min(e, f, dim) * 0.1

        point = self.point(context)
        omv = 0  # offset margin value
        ov = dim  # offset margin
        corner_offset = {
            "LEFT_TOP": ((-omv, -ov, 0), (-omv, omv, 0), (ov, omv, 0)),
            "RIGHT_TOP": ((-ov, omv, 0), (omv, omv, 0), (omv, -ov, 0)),
            "LEFT_BOTTOM": ((-omv, ov, 0), (-omv, -omv, 0), (ov, -omv, 0)),
            "RIGHT_BOTTOM": ((-ov, -omv, 0), (omv, -omv, 0), (omv, ov, 0)),
        }
        points = corner_offset.get(self.direction)
        return list(obj.matrix_world @ (Vector(i) + point) for i in points)

    @property
    def direction(self) -> str:
        return DIRECTION_ITEMS[self.direction_index]

    def draw_corner(self, context):
        color = (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 1)
        with gpu.matrix.push_pop():
            shader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
            batch = batch_for_shader(
                shader,
                'LINES',
                {"pos": self.corner_3d_points(context), "color": [color, color, color]},
                indices=((0, 1), (1, 2)))
            shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
            shader.uniform_float("lineWidth", self.line_width)
            batch.draw(shader)

    def draw(self, context):
        gpu.state.line_width_set(self.line_width)
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_test_set("ALWAYS")
        #
        # text = f"{self.direction} {self.is_hover}"
        # blf.size(0, 20)
        # blf.draw(0, text)
        #
        # color = (1, 0, 1, 1) if self.is_hover else (1, 1, 0, 1)
        # shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        # batch = batch_for_shader(shader, 'POINTS',
        #                          {"pos": [context.object.matrix_world @ self.point(context, offset=False), ]})
        # shader.uniform_float("color", color)
        # batch.draw(shader)

        if self.is_corner:
            self.draw_corner(context)
            return

        color = (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 1)
        shader = gpu.shader.from_builtin('POLYLINE_SMOOTH_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": self.tow_2d_point(context), "color": [color, color]},
                                 indices=((0, 1),)
                                 )
        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", self.line_width)
        batch.draw(shader)

    def invoke(self, context, event):
        bpy.ops.ed.undo_push(message="Push Undo")
        self.start_mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.start_texture_space_control_offset = self.target_get_value("texture_space_control_offset")
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        if event.value == "RELEASE":  # event.type == "LEFTMOUSE" and
            self.exit(context, False)
            return {"FINISHED"}
        elif event.type == "MOUSEMOVE":
            self.move_event(context, event)
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        if cancel:
            context.object.texture_space_control_offset = self.start_texture_space_control_offset

    def test_select(self, context, mouse_pos):
        if self.is_corner:
            a, b, c = self.corner_3d_points(context)
            d = test_hover(context, a, b, mouse_pos)
            e = test_hover(context, b, c, mouse_pos)
            self.is_hover = d == 0 or e == 0
            is_hover = 0 if self.is_hover else -1
        else:
            a, b = self.tow_2d_point(context)
            is_hover = test_hover(context, a, b, mouse_pos)
            self.is_hover = is_hover == 0
        return is_hover

    def move_event(self, context, event):
        """
        1.通过两个3d点 -> 2d点
        2.计算两个3d点的距离
        3.计算两个2d点的距离
        4.获取2d点到3d点的比例(移动2d点的话对应的多少3d点)
        5.用intersect_point_line来获取两个点的偏移比例
        """
        obj = context.object

        texture_space_control_offset = Vector(self.target_get_value("texture_space_control_offset"))
        ofv = texture_space_control_offset
        region, region_3d = context.region, context.space_data.region_3d
        matrix = obj.matrix_world

        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        sm = scale_to_matrix(obj.matrix_world.to_scale()).inverted()
        dx, dy, dz = obj.dimensions
        if self.is_corner:
            lt = matrix @ self.point(context, offset=False, direction="LEFT_TOP")
            rt = matrix @ self.point(context, offset=False, direction="RIGHT_TOP")
            lb = matrix @ self.point(context, offset=False, direction="LEFT_BOTTOM")
            rb = matrix @ self.point(context, offset=False, direction="RIGHT_BOTTOM")
            lt2d = location_3d_to_region_2d(region, region_3d, lt)
            rt2d = location_3d_to_region_2d(region, region_3d, rt)
            lb2d = location_3d_to_region_2d(region, region_3d, lb)
            rb2d = location_3d_to_region_2d(region, region_3d, rb)
            (ax2d, bx2d), (cy2d, dy2d), (ix, iy), (ffx, ffy) = {
                "LEFT_TOP": [(lt2d, rt2d), (lt2d, lb2d), (0, 2), (1, -1)],  # x,y
                "RIGHT_TOP": [(rt2d, lt2d), (rt2d, rb2d), (1, 2), (-1, -1)],
                "LEFT_BOTTOM": [(lb2d, rb2d), (lb2d, lt2d), (0, 3), (1, 1)],
                "RIGHT_BOTTOM": [(rb2d, lb2d), (rb2d, rt2d), (1, 3), (-1, 1)],
            }.get(self.direction)
            _, ax = intersect_point_line(mouse, ax2d, bx2d)
            _, by = intersect_point_line(mouse, cy2d, dy2d)

            xx = dx * ax
            yy = dy * by
            fxx = (sm @ Vector((xx, xx, xx)))[0]
            fyy = (sm @ Vector((yy, yy, yy)))[0]
            ofv[ix] = fxx * ffx
            ofv[iy] = fyy * ffy
            self.target_set_value("texture_space_control_offset", ofv)
        else:
            l = matrix @ self.point(context, offset=False, direction="LEFT")
            r = matrix @ self.point(context, offset=False, direction="RIGHT")
            t = matrix @ self.point(context, offset=False, direction="TOP")
            b = matrix @ self.point(context, offset=False, direction="BOTTOM")
            l2d, r2d = location_3d_to_region_2d(region, region_3d, l), location_3d_to_region_2d(region, region_3d, r)
            t2d, b2d = location_3d_to_region_2d(region, region_3d, t), location_3d_to_region_2d(region, region_3d, b)
            (a2d, b2d), index = {
                "LEFT": [(l2d, r2d), 0],
                "RIGHT": [(r2d, l2d), 1],
                "TOP": [(t2d, b2d), 2],
                "BOTTOM": [(b2d, t2d), 3]
            }.get(self.direction)
            _, o = intersect_point_line(mouse, a2d, b2d)

            if self.is_vertical:
                v = dy * o
            else:
                v = dx * o
            fv = (sm @ Vector((v, v, v)))[0]
            if not self.is_negative_xis:
                fv = fv * -1
            ofv[index] = fv
            self.target_set_value("texture_space_control_offset", ofv)


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
            gz.use_draw_modal = True
            gz.use_draw_value = True
            gz.line_width = 1
            # gz.target_set_prop("texture_space_control_offset", context.object, "texture_space_control_offset")

        # gz = self.gizmos.new("GIZMO_GT_arrow_3d")
        # gz.draw_style = "NORMAL"
        # gz.aspect = (0, 0)

    def draw_prepare(self, context):
        self.refresh(context)

    def refresh(self, context):
        context.area.tag_redraw()
        for g in self.gizmos:
            g.target_set_prop("texture_space_control_offset", context.object, "texture_space_control_offset")


clss = [
    TextureSpaceGizmo,
    TextureSpaceControl,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
