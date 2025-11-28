import traceback
import time
import bpy
import numpy as np
from math import radians
from collections.abc import Callable
from mathutils import Matrix, Vector
from pathlib import Path
from platform import system
from queue import Queue
from uuid import uuid4

from .event import Event
from .renderer import Renderer as ImguiRenderer, imgui
from .stats import AppState
from .style import ImguiStylePurpleGray

from ...ime import IME_BUFFER
from ......kclogger import logger, DEBUG


class FakeContext:
    def __init__(self, context: bpy.types.Context):
        self.region_data = context.region_data
        self.region = context.region
        self.space_data = context.space_data
        self.window = context.window
        self.window_manager = context.window_manager
        self.screen = context.screen
        self.scene = context.scene
        self.view_layer = context.view_layer
        self.area = context.area
        self.active_object = context.active_object
        self._context = context

    def __getattr__(self, item):
        if item not in self.__dict__:
            return self._context.__getattribute__(item)
        return self.__getattribute__(item)


class ImguiFrameWrapper:
    def __init__(self, app: "App"):
        self.app = app
        self.io = app.io
        self._colors = []
        self._ids = []

    def begin_frame(self):
        imgui.new_frame()

    def push_id(self, _id):
        imgui.push_id(_id)
        self._ids.append(_id)

    def push_style_color(self, color_name, color):
        imgui.push_style_color(color_name, color)
        self._colors.append(color_name)

    def set_custom_theme(self):
        default_style = ImguiStylePurpleGray()
        # 应用颜色设置
        for color_name, color_value in default_style.style_colors.items():
            self.push_style_color(color_name, color_value)
        default_style.apply_others()

    def end_frame(self):
        for _ in self._ids:
            imgui.pop_id()
        imgui.pop_style_color(len(self._colors))

    def render(self):
        imgui.render()


class App:
    def __init__(self, rtype="WINDOW", dtype="POST_VIEW", space: bpy.types.Space = bpy.types.SpaceView3D, data_class: type = AppState):
        self.state: AppState = data_class()
        # 默认设置当前上下文
        self.context: bpy.types.Context | FakeContext | None = FakeContext(bpy.context)
        self._id = uuid4().hex
        self._gui_time = None

        self.event_queue: Queue[Event] = Queue()

        logger.debug(f"Creating app {self._id}")

        self.backend = ImguiRenderer()

        logger.debug("App Backend created")
        logger.debug(f"\t{self.backend}")

        self.io = self.backend.io
        self.io.ini_filename = Path(__file__).parent.joinpath("imgui.ini").as_posix()
        self.io.display_framebuffer_scale = 3, 3
        self.font_manager = self.backend.font_manager
        self.rtype = rtype
        self.dtype = dtype

        logger.debug(f"\tRegionType: {self.rtype}, DrawType: {self.dtype}")

        self.space: bpy.types.Space = space
        self.handler = space.draw_handler_add(self.draw, (bpy.context.area,), rtype, dtype)

        logger.debug(f"Created App {self._id} with handler {self.handler}")

        self.callbacks: dict[Callable, bpy.types.Area] = {}

        self.any_window_hovered = False
        self.any_item_hovered = False
        self.item_hovered = False

        self.any_window_focused = False
        self.any_item_focused = False
        self.item_focused = False

        self.should_exit = False
        self.is_closed = False

        self.style = imgui.get_style()
        self.screen_width = bpy.context.region.width
        self.screen_height = bpy.context.region.height

        self.M = Matrix.Identity(4)
        self.V = Matrix.Identity(4)
        self.P = Matrix.Identity(4)

        self.key_map = {
            "TAB": imgui.Key.KEY_TAB,
            "LEFT_ARROW": imgui.Key.KEY_LEFT_ARROW,
            "RIGHT_ARROW": imgui.Key.KEY_RIGHT_ARROW,
            "UP_ARROW": imgui.Key.KEY_UP_ARROW,
            "DOWN_ARROW": imgui.Key.KEY_DOWN_ARROW,
            "PAGE_UP": imgui.Key.KEY_PAGE_UP,
            "PAGE_DOWN": imgui.Key.KEY_PAGE_DOWN,
            "HOME": imgui.Key.KEY_HOME,
            "END": imgui.Key.KEY_END,
            "INSERT": imgui.Key.KEY_INSERT,
            "DEL": imgui.Key.KEY_DELETE,
            "BACK_SPACE": imgui.Key.KEY_BACKSPACE,
            "SPACE": imgui.Key.KEY_SPACE,
            "RET": imgui.Key.KEY_ENTER,
            "ESC": imgui.Key.KEY_ESCAPE,
            "A": imgui.Key.KEY_A,
            "C": imgui.Key.KEY_C,
            "V": imgui.Key.KEY_V,
            "X": imgui.Key.KEY_X,
            "Y": imgui.Key.KEY_Y,
            "Z": imgui.Key.KEY_Z,
            "LEFT_CTRL": imgui.Key.KEY_LEFT_CTRL,
            "RIGHT_CTRL": imgui.Key.KEY_RIGHT_CTRL,
            "LEFT_ALT": imgui.Key.KEY_LEFT_ALT,
            "RIGHT_ALT": imgui.Key.KEY_RIGHT_ALT,
            "LEFT_SHIFT": imgui.Key.KEY_LEFT_SHIFT,
            "RIGHT_SHIFT": imgui.Key.KEY_RIGHT_SHIFT,
            "OSKEY": imgui.Key.KEY_LEFT_SUPER,
        }

        logger.debug(f"Creating App {self._id} with style {self.style}")
        logger.debug(f"App {self._id} created")

    @property
    def screen_width(self):
        return self.io.display_size[0]

    @screen_width.setter
    def screen_width(self, value):
        self.io.display_size = value, self.screen_height

    @property
    def screen_height(self):
        return self.io.display_size[1]

    @screen_height.setter
    def screen_height(self, value):
        self.io.display_size = self.screen_width, value

    def resize(self, width, height):
        self.io.display_size = width, height

    def draw_call_add(self, cb):
        self.callbacks[cb] = None

    def draw_call_remove(self, cb):
        self.callbacks.pop(cb, None)

    def shutdown(self):
        """关闭imgui: 清理所有回调, 关闭imgui上下文"""
        if self.is_closed:
            return
        self.should_exit = True
        self.callbacks.clear()
        if self.handler:
            self.space.draw_handler_remove(self.handler, self.rtype)
            self.handler = None
        self.backend.shutdown()
        self.is_closed = True

    def _update_hovered_status(self):
        """必须在imgui.new_frame()之后调用, 否则会崩溃"""
        flags = 0
        flags |= imgui.HoveredFlags.ALLOW_WHEN_BLOCKED_BY_ACTIVE_ITEM
        flags |= imgui.HoveredFlags.ALLOW_WHEN_BLOCKED_BY_POPUP
        flags |= imgui.HoveredFlags.ANY_WINDOW

        self.any_window_hovered = imgui.is_window_hovered(flags)
        self.any_item_hovered = imgui.is_any_item_hovered()
        self.item_hovered = imgui.is_item_hovered()

    def _update_focused_status(self):
        """必须在imgui.new_frame()之后调用, 否则会崩溃"""
        self.any_window_focused = imgui.is_window_focused(imgui.FocusedFlags.ANY_WINDOW)
        self.any_item_focused = imgui.is_any_item_focused()
        self.item_focused = imgui.is_item_focused()

    def update_window_status(self):
        self._update_hovered_status()
        self._update_focused_status()

    def any_hovered(self):
        return self.any_window_hovered or self.any_item_hovered or self.item_hovered

    def any_focused(self):
        return self.any_window_focused or self.any_item_focused or self.item_focused

    def any_mouse_dragging(self):
        return imgui.is_mouse_dragging(imgui.MouseButton.LEFT) or imgui.is_mouse_dragging(imgui.MouseButton.RIGHT) or imgui.is_mouse_dragging(imgui.MouseButton.MIDDLE)

    def should_pass_event(self):
        if not self.any_hovered() and not self.any_mouse_dragging():
            self.io.clear_input_mouse()
            return True
        return False

    def draw(self, area):
        try:
            self._draw_ex(area)
        except ReferenceError:
            self.shutdown()
        except Exception:
            traceback.print_exc()

    def _draw_ex(self, area):
        if not self.context or bpy.context.area != area:
            return
        self.backend.ensure_ctx()

        frame = ImguiFrameWrapper(self)

        #  ------------------------------------帧开始------------------------------------
        frame.begin_frame()
        self.backend.begin()

        # 0. 窗口ID
        frame.push_id(self._id)

        # 2. 输入处理
        self.process_inputs()

        # 3. 窗口状态更新
        self.update_window_status()

        # 4. 绘制回调
        # frame.set_custom_theme() # 自定义主题
        self._draw_prepare()
        self._draw_callbacks(area)

        # 1. 变换更新
        self.backend.set_mvp_matrix(self.M, self.V, self.P)

        self.backend.end()
        frame.end_frame()
        # ------------------------------------帧结束------------------------------------

        # self.debug_mouse()
        frame.render()
        self.backend.render(imgui.get_draw_data())

    def _draw_prepare(self):
        self.update_gpu_matrix()

    def _draw_callbacks(self, area):
        invalid_callback = []
        for cb in self.callbacks:
            try:
                cb(self, area)
            except ReferenceError:
                invalid_callback.append(cb)
        for cb in invalid_callback:
            self.draw_call_remove(cb)

    def debug_mouse(self):
        if not DEBUG:
            return
        draw_list = imgui.get_foreground_draw_list()
        draw_list.add_circle_filled(self.io.mouse_pos, 12, imgui.get_color_u32((0, 1, 0, 1)))

    def push_event(self, event: "bpy.types.Event"):
        self.event_queue.put(Event(event))

    def process_inputs(self):
        """
        事件同步
        """
        while not self.event_queue.empty():
            event = self.event_queue.get()
            self.poll_event(event)

        current_time = time.time()
        delta_time = (current_time - self._gui_time) if self._gui_time else 1.0 / 60.0

        if delta_time <= 0.0:
            delta_time = 1.0 / 1000.0
        self.io.delta_time = delta_time
        self._gui_time = current_time

    def poll_event(self, event: "Event"):
        is_press = event.value == "PRESS"
        # 鼠标
        if event.type == "LEFTMOUSE":
            self.io.add_mouse_button_event(imgui.MouseButton.LEFT, is_press)
        elif event.type == "RIGHTMOUSE":
            self.io.add_mouse_button_event(imgui.MouseButton.RIGHT, is_press)
        elif event.type == "MIDDLEMOUSE":
            self.io.add_mouse_button_event(imgui.MouseButton.MIDDLE, is_press)
        elif event.type == "WHEELUPMOUSE":
            self.io.add_mouse_wheel_event(0, +1)
        elif event.type == "WHEELDOWNMOUSE":
            self.io.add_mouse_wheel_event(0, -1)
        elif event.type == "MOUSEMOVE":
            mpos = event.mouse_region_x, event.mouse_region_y
            self.update_mouse_pos(mpos)

        # 键盘
        #     1. 修饰
        self.io.add_key_event(imgui.Key.MOD_CTRL, event.ctrl)
        self.io.add_key_event(imgui.Key.MOD_SHIFT, event.shift)
        self.io.add_key_event(imgui.Key.MOD_ALT, event.alt)
        self.io.add_key_event(imgui.Key.MOD_SUPER, event.oskey)
        #     2. 普通
        if event.value in ["RELEASE", "PRESS"]:
            if key := self.key_map.get(event.type):
                self.io.add_key_event(key, is_press)

        # 输入
        if system() == "Windows":
            if IME_BUFFER:
                self.io.add_input_characters_utf8(IME_BUFFER.pop(0))
        elif event.unicode and 0 < (char := ord(event.unicode)) < 0x10000:
            self.io.add_input_character(char)

    def update_mouse_pos(self, mpos: tuple[float, float]):
        if self.rtype != "WINDOW":
            sh = self.screen_height
        else:
            sh = bpy.context.region.height
        self.io.add_mouse_pos_event(mpos[0], sh - 1 - mpos[1])

        if self.rtype != "WINDOW":
            return
        # 鼠标转换到3D空间
        from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
        from mathutils.geometry import intersect_line_plane

        region = bpy.context.region
        rv3d = bpy.context.region_data

        # 1. 获取鼠标往屏幕内延伸的射线
        origin = region_2d_to_origin_3d(region, rv3d, mpos)
        direction = region_2d_to_vector_3d(region, rv3d, mpos)

        # 2. 获取射线与平面矩阵的交点
        inv_y = Matrix(
            (
                (1, +0, 0, 0),
                (0, -1, 0, 0),
                (0, +0, 1, 0),
                (0, +0, 0, 1),
            )
        )
        m = self.M @ inv_y @ Matrix.Translation(Vector((0, -self.screen_height, 0)))

        # 定义XY平面 (Z=0)
        plane_point = m @ Vector((0, 0, 0))
        plane_normal = (m.to_3x3() @ Vector((0, 0, 1))).normalized()
        intersection = intersect_line_plane(origin, origin + direction, plane_point, plane_normal)
        if intersection:
            intersection = m.inverted() @ intersection
            self.io.add_mouse_pos_event(intersection[0], max(0, self.screen_height - intersection[1]))
        else:
            print("no intersection")

    def calc_objs_center(self):
        obj = bpy.context.object
        objs = {o for o in bpy.context.selected_objects if o.is_sdn_canvas_layer}
        if obj and obj.is_sdn_canvas_layer:
            objs.add(obj)

        M = Matrix.Identity(4)
        verts = []
        for o in objs:
            if not o or o.type != "MESH" or not o.is_sdn_canvas_layer:
                continue
            for v in o.bound_box:
                verts.append(o.matrix_world @ Vector(v))
        if verts:
            verts = np.array(verts)
            center = Vector(verts.sum(axis=0) / len(verts))
            M = Matrix.Translation(center)
        return M

    def update_gpu_matrix(self):
        """
        此函数涉及调用 area 和 region_data, 因此XR模式下不能在draw中调用
        会导致ACCESS_VIOLATION
        """
        if self.dtype == "POST_PIXEL":
            w, h = bpy.context.area.width, bpy.context.area.height
            self.V = Matrix.Identity(4)
            self.P = Matrix(
                (
                    (2 / w, 0, 0, -1),
                    (0, 2 / h, 0, -1),
                    (0, 0, 1, 0),
                    (0, 0, 0, 1),
                )
            )
        else:
            rv3d = self.context.region_data
            self.V = rv3d.view_matrix
            self.P = rv3d.window_matrix

        M = self.calc_objs_center()

        # Y轴反转
        inv_y = Matrix(
            (
                (1, +0, 0, 0),
                (0, -1, 0, 0),
                (0, +0, 1, 0),
                (0, +0, 0, 1),
            )
        )
        # 增量变换
        del_scl = Matrix.Scale(1 / 500, 4)
        del_rot = Matrix.Rotation(radians(90), 4, "X")
        del_trans = Matrix.Translation(Vector((-self.screen_width, self.screen_height, 0)) * 0.5)
        self.M = M @ del_scl @ del_rot @ del_trans @ inv_y

    def blender_to_imgui_pos(self, pos: Vector):
        return self.M.inverted() @ pos


class AppHud(App):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.io.display_framebuffer_scale = 1, 1

    def update_mouse_pos(self, mpos: tuple[float, float]):
        self.io.add_mouse_pos_event(mpos[0], self.screen_height - 1 - mpos[1])

    def update_gpu_matrix(self):
        """
        此函数涉及调用 area 和 region_data, 因此XR模式下不能在draw中调用
        会导致ACCESS_VIOLATION
        """
        area = bpy.context.area
        region = bpy.context.region
        self.screen_width = region.width
        self.screen_height = region.height

        w, h = area.width, area.height
        self.P = Matrix(
            (
                (2 / w, 0, 0, -1),
                (0, 2 / h, 0, -1),
                (0, 0, 1, 0),
                (0, 0, 0, 1),
            )
        )
        self.V = Matrix.Identity(4)
        # rv3d = self.context.region_data
        # self.V = rv3d.view_matrix
        # self.P = rv3d.window_matrix
        self.M = Matrix(
            (
                (1, 0, 0, 0),
                (0, -1, 0, region.height),
                (0, 0, 1, 0),
                (0, 0, 0, 1),
            )
        )
