import blf
import bpy
import gpu.matrix
import gpu_extras
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


def get_active_camera(context) -> bpy.types.Camera | None:
    """
    bpy.data.screens["Shading"].areas[5].spaces[0].camera 局部相机
    bpy.context.scene.camera.data
    """
    if camera := context.space_data.camera:
        return camera
    return context.scene.camera


def get_3d_camera_border(context) -> list[Vector] | None:
    if camera := get_active_camera(context):
        return [camera.matrix_world @ v for v in camera.data.view_frame(scene=context.scene)]
    return None


def get_2d_camera_border(context, camera_border_3d=None) -> list[Vector] | None:
    if camera_border_3d is None:
        camera_border_3d = get_3d_camera_border(context)
    return [location_3d_to_region_2d(context.region, context.space_data.region_3d, v) for v in camera_border_3d]


DIRECTION_ITEMS = [
    "RIGHT",
    "BOTTOM",
    "LEFT",
    "TOP"
]


class ControlGizmo(bpy.types.Gizmo):
    bl_idname = "CAMERA_GT_gizmo"
    bl_options = {"PERSISTENT", "SCALE", "SHOW_MODAL_ALL", "UNDO", "GRAB_CURSOR"}

    camera_border_2d: list[Vector] | None
    camera_border_3d: list[Vector] | None
    camera_border_index: int
    is_hover = False
    margin = 5

    @property
    def is_vertical(self):
        return self.direction in ("BOTTOM", "TOP")

    @property
    def direction(self) -> str:
        return DIRECTION_ITEMS[self.camera_border_index]

    @property
    def tow_point_index(self) -> tuple[int, int]:
        a, b = 0, 1
        if self.direction == "RIGHT":
            a, b = 0, 1
        elif self.direction == "BOTTOM":
            a, b = 1, 2
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

    def invoke(self, context, event):
        return {"RUNNING_MODAL"}

    def modal(self, context, event, tweak):
        context.area.tag_redraw()
        return {"RUNNING_MODAL"}

    def exit(self, context, cancel):
        ...

    def draw(self, context):
        text = f"{self.camera_border_index} {self.camera_border_2d[self.camera_border_index]} {self.direction}"
        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(self.matrix_basis)
            blf.position(0, 0, 0, 0)
            blf.draw(0, text)
            gpu_extras.presets.draw_circle_2d((0, 0, 0), (1, 1, 1, 1), 20)

            # shader = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
            # batch = batch_for_shader(shader, 'POINTS', {"pos": self.camera_border_3d[self.camera_border_index]})
            # shader.uniform_float("color", (0, 0, 1, 1))
            # gpu.state.point_size_set(5)
            # batch.draw(shader)

        shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        batch = batch_for_shader(shader, 'LINES', {"pos": self.tow_3d_point}, indices=((1, 0),))

        color = (1, 1, 0, 1) if self.is_hover else (0, 0, 1, 1)
        a, b = self.tow_2d_point
        # shader.uniform_float("viewportSize", a - b)
        # shader.uniform_float("viewportSize", gpu.state.viewport_get()[2:])
        shader.uniform_float("lineWidth", 100)
        shader.uniform_float("color", color)
        batch.draw(shader)

    # def test_select(self, context, mouse_pos):
    #     x, y = mouse_pos
    #     (x1, y1), (x2, y2) = self.tow_2d_point
    #     if self.is_vertical:
    #         y1 -= self.margin
    #         y2 -= self.margin
    #     else:
    #         x1 -= self.margin
    #         x2 -= self.margin
    #     x_ok = x1 < x < x2
    #     y_ok = y1 < y < y2
    #     is_hover = 0 if x_ok and y_ok else -1
    #     self.is_hover = is_hover == 0
    #     return is_hover

    def refresh(self, context):
        ...


class CameraControl(bpy.types.GizmoGroup):
    bl_idname = "CAMERA_2D_control_gizmos"
    bl_label = "Camera Control"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE', 'SHOW_MODAL_ALL'}

    def setup(self, context):
        for i in range(4):
            gz = self.gizmos.new(ControlGizmo.bl_idname)
            gz.use_draw_modal = True
        print("setup camera")

    def draw_prepare(self, context):
        self.refresh(context)

    def refresh(self, context):
        camera_border_3d = get_3d_camera_border(context)
        if camera_border_2d := get_2d_camera_border(context, camera_border_3d):
            for (index, i) in enumerate(camera_border_2d):
                gz = self.gizmos[index]
                x, y = i
                gz.camera_border_index = index
                gz.camera_border_2d = camera_border_2d
                gz.camera_border_3d = camera_border_3d
                gz.matrix_basis[0][3] = x
                gz.matrix_basis[1][3] = y


clss = [
    ControlGizmo,
    CameraControl,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
