import blf
import bpy
import gpu.matrix
import gpu_extras
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix

from .utils import get_active_camera, get_3d_camera_border, get_2d_camera_border

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


class CornerControl:
    @property
    def is_corner(self) -> bool:
        return "_" in self.direction

    @property
    def corner_index(self) -> int:
        return {
            "LEFT_TOP": 3,
            "RIGHT_TOP": 0,
            "LEFT_BOTTOM": 2,
            "RIGHT_BOTTOM": 1,
        }.get(self.direction, -1)

    def draw_corner(self, context):
        text = f"{self.corner_index} {self.camera_border_2d[self.corner_index]} {self.direction} {self.is_hover}"
        with gpu.matrix.push_pop():
            x, y = self.camera_border_2d[self.corner_index]
            gpu.matrix.translate((x, y))
            blf.position(0, 0, 0, 0)
            blf.size(0, 10)
            blf.draw(0, text)
            gpu_extras.presets.draw_circle_2d((0, 0, 0), (1, 1, 1, 1), 10)

    def test_corner_select(self, context, mouse_pos):
        return -1


class ControlGizmo(bpy.types.Gizmo, CornerControl):
    bl_idname = "CAMERA_GT_gizmo"
    bl_options = {"PERSISTENT", "SCALE", "SHOW_MODAL_ALL", "UNDO", "GRAB_CURSOR"}

    camera_border_2d: list[Vector] | None = []
    camera_border_3d: list[Vector] | None = []
    camera_border_index: int = 0
    is_hover: bool = False
    margin = 5

    mouse: Vector = Vector((0.0, 0.0))
    start_mouse: Vector
    start_resolution: Vector
    start_sensor_fit: str
    start_camera_border_2d: list[Vector]
    start_camera_border_3d: list[Vector]
    start_camera_matrix: Matrix

    @property
    def is_vertical(self):
        return self.direction in ("BOTTOM", "TOP")

    @property
    def direction(self) -> str:
        return DIRECTION_ITEMS[self.camera_border_index]

    @property
    def tow_point_index(self) -> tuple[int, int]:
        a, b = 1, 0
        if self.direction == "RIGHT":
            a, b = 1, 0
        elif self.direction == "BOTTOM":
            a, b = 2, 1
        elif self.direction == "LEFT":
            a, b = 2, 3
        elif self.direction == "TOP":
            a, b = 3, 0
        return a, b

    @property
    def tow_3d_point(self) -> list[Vector]:
        a, b = self.tow_point_index
        return [self.camera_border_3d[a], self.camera_border_3d[b]]

    @property
    def tow_2d_point(self) -> list[Vector]:
        a, b = self.tow_point_index
        return [self.camera_border_2d[a], self.camera_border_2d[b]]

    @property
    def resolution_proportion(self) -> float:
        if self.is_vertical:
            ai, bi = 3, 2
        else:
            ai, bi = 3, 0
        d_2d = self.start_camera_border_2d[ai] - self.start_camera_border_2d[bi]  # 两个二维点相差
        if self.is_vertical:
            return self.start_resolution.y / d_2d.y * 2
        else:
            return self.start_resolution.x / d_2d.x * 2

    def draw(self, context):
        if self.is_corner:
            self.draw_corner(context)
            return
        shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": self.tow_2d_point}, indices=((0, 1),))

        shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", 3 if self.is_hover else 0.01)
        shader.uniform_float("color", (1, 1, 0, 1) if self.is_hover else (1, 0, 0, 0))
        batch.draw(shader)

        if self.is_hover:
            render = bpy.context.scene.render
            x, y = render.resolution_x, render.resolution_y

            mouse = self.mouse + Vector((20, 20))
            blf.size(0, 12)
            blf.position(0, mouse.x, mouse.y, 0)
            blf.draw(0, bpy.app.translations.pgettext_iface("Resolution"))
            blf.position(0, mouse.x, mouse.y - 12, 0)
            blf.draw(0, f"x:{x}px")
            blf.position(0, mouse.x, mouse.y - 24, 0)
            blf.draw(0, f"y:{y}px")
        return

    def test_select(self, context, mouse_pos):
        if self.is_corner:
            return self.test_corner_select(context, mouse_pos)
        x, y = mouse_pos
        (x1, y1), (x2, y2) = self.tow_2d_point

        margin = self.margin
        if self.is_vertical:
            y1 -= margin
            y2 += margin
            x1 += margin
            x2 -= margin
        else:
            x1 -= margin
            x2 += margin
            y1 -= margin
            y2 += margin

        x_ok = x1 < x < x2
        y_ok = y1 < y < y2
        is_hover = 0 if x_ok and y_ok else -1
        self.is_hover = is_hover == 0
        return is_hover

    def invoke(self, context, event):
        render = context.scene.render
        camera = get_active_camera(context)
        self.mouse = self.start_mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        x, y = self.start_resolution = Vector((render.resolution_x, render.resolution_y))
        self.start_sensor_fit = camera.data.sensor_fit
        self.start_camera_matrix = camera.matrix_world.copy()
        self.start_camera_border_2d = self.camera_border_2d
        self.start_camera_border_3d = self.camera_border_3d

        if self.is_vertical:
            # if camera.data.sensor_fit == "VERTICAL":
            #     camera.data.sensor_height = camera.data.sensor_width * (y / x)
            camera.data.sensor_fit = "HORIZONTAL"
        else:
            # if camera.data.sensor_fit == "HORIZONTAL":
            #     camera.data.sensor_width = camera.data.sensor_height * (y / x)
            camera.data.sensor_fit = "VERTICAL"

        bpy.ops.ed.undo_push(message="Push Undo")
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        context.area.tag_redraw()
        self.mouse = mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        if self.direction in ("BOTTOM", "RIGHT"):
            dm = self.start_mouse - mouse
        else:
            dm = mouse - self.start_mouse
        # print(event.type, event.value, mouse, dm)
        if event.type == "LEFTMOUSE" and event.value == "RELEASE":
            self.exit(context, False)
            return {"FINISHED"}
        elif event.type == "MOUSEMOVE":
            render = context.scene.render
            self.update_camera_offset(context, event)
            if self.is_vertical:
                render.resolution_y = int(self.start_resolution.y + dm.y * self.resolution_proportion)
            else:
                render.resolution_x = int(self.start_resolution.x + dm.x * self.resolution_proportion)
            self.update_camera_offset(context, event)
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        if cancel:
            render = context.scene.render
            x, y = self.start_resolution
            render.resolution_x = int(x)
            render.resolution_y = int(y)

            camera = get_active_camera(context)
            camera.data.sensor_fit = self.start_sensor_fit
            camera.matrix_world = self.start_camera_matrix

    def update_camera_offset(self, context, event):
        """
        camera_matrix.translation + (start_camera_location - now_camera_location) / 2
        """
        if not event.ctrl:
            return
        point_key = {
            "LEFT": 0,
            "RIGHT": 3,
            "BOTTOM": 0,
            "TOP": 1,
        }.get(self.direction, 0)

        s = self.start_camera_border_3d[point_key]
        n = get_3d_camera_border(context)[point_key]
        camera = get_active_camera(context)
        camera.matrix_world.translation = self.start_camera_matrix.translation
        camera.matrix_world.translation += s - n


class CameraControl(bpy.types.GizmoGroup):
    bl_idname = "CAMERA_2D_control_gizmos"
    bl_label = "Camera Control"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}

    drag_gz: bpy.types.Gizmo = None
    switch_wh: bpy.types.Gizmo = None

    @classmethod
    def poll(cls, context):
        return (
                get_active_camera(context) and
                context.space_data and
                context.space_data.region_3d and
                context.space_data.region_3d.view_perspective == "CAMERA")

    def setup(self, context):
        for i in range(len(DIRECTION_ITEMS)):
            gz = self.gizmos.new(ControlGizmo.bl_idname)
            gz.use_draw_modal = True
        self.drag_gz = drag = self.gizmos.new("GIZMO_GT_button_2d")
        drag.icon = "VIEW_PAN"
        drag.target_set_operator("transform.translate")

        from .ops import SwitchWH
        self.switch_wh = switch_wh = self.gizmos.new("GIZMO_GT_button_2d")
        switch_wh.icon = "UV_SYNC_SELECT"
        switch_wh.target_set_operator(SwitchWH.bl_idname)

    def draw_prepare(self, context):
        self.refresh(context)

    def refresh(self, context):
        camera_border_3d = get_3d_camera_border(context)
        if camera_border_2d := get_2d_camera_border(context, camera_border_3d):
            for (index, direction) in enumerate(DIRECTION_ITEMS):
                gz = self.gizmos[index]
                gz.camera_border_index = index
                gz.camera_border_2d = camera_border_2d
                gz.camera_border_3d = camera_border_3d

            x, y = camera_border_2d[1]
            self.drag_gz.matrix_basis[0][3] = x + 20
            self.drag_gz.matrix_basis[1][3] = y - 20

            self.switch_wh.matrix_basis[0][3] = x -10
            self.switch_wh.matrix_basis[1][3] = y - 20


clss = [
    ControlGizmo,
    CameraControl,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
