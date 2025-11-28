import bpy
import numpy as np

from bpy.app.translations import pgettext
from pathlib import Path
from copy import deepcopy
from contextlib import contextmanager
from mathutils import Vector
from uuid import uuid4
from .texture import TexturePool
from .app.app import App, AppHud
from .app.renderer import imgui
from .app.style import Styler, Const
from .app.stats import RightPanelType
from .app.handler import LayerPanelHandler
from .widgets import CustomWidgets
from .wrapper.nodetree_wrapper import NodeTreeWrapper, get_canvas_workflow, find_node_by_type
from .wrapper import MaterialWrapper
from ....blueprints import cache_to_local
from ....manager import TaskManager, Task
from .....timer import Timer


def get_tool_panel_width():
    for region in bpy.context.area.regions:
        if region.type != "TOOLS":
            continue
        return region.width
    return 0


def get_ui_panel_width():
    for region in bpy.context.area.regions:
        if region.type != "UI":
            continue
        return region.width
    return 0


@contextmanager
def with_child(str_id: str, size: tuple[float, float] = (0.0, 0.0), child_flags: imgui.ChildFlags = imgui.ChildFlags.NONE, window_flags: imgui.WindowFlags = imgui.WindowFlags.NONE):
    imgui.begin_child(str_id, size, child_flags, window_flags)
    try:
        yield
    except Exception:
        pass
    imgui.end_child()


class ViewportGui(bpy.types.Operator):
    bl_idname = "sdn.viewport_gui"
    bl_label = "MR Gui Test"
    bl_options = {"REGISTER", "UNDO"}

    title: bpy.props.StringProperty(default="MRK")
    input_text: bpy.props.StringProperty(default="零一二三四五六七八九" * 6)

    def invoke(self, context, event):
        self._id = uuid4().hex[:4]
        self.title = "MRK"
        self.selectables = {
            "close": False,
            "edit_mode": bpy.context.mode == "EDIT_MESH",
            "object_mode": bpy.context.mode == "OBJECT",
            "sculptmode_hlt": bpy.context.mode == "SCULPT",
            "monkey": False,
        }

        self._texture = CustomWidgets.make_texture_bpy()
        self.area = bpy.context.area
        self.app = App("WINDOW", "POST_VIEW")
        self.app.draw_call_add(self.handler_draw_3d)
        self.app_hud = AppHud("WINDOW", "POST_VIEW")
        self.app_hud.draw_call_add(self.handler_draw_hud)
        self.app_hud_pos_y = bpy.context.area.y
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(1 / 60, window=context.window)

        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if context.area != self.area:
            return {"PASS_THROUGH"}
        if not context.area:
            if self.app_hud.should_exit:
                self.app_hud.shutdown()
            if self.app.should_exit:
                self.app.shutdown()
            if self.app_hud.should_exit and self.app.should_exit:
                return {"CANCELLED"}
        if event.type == "ESC":
            self.app.shutdown()
            self.app_hud.shutdown()
            return {"CANCELLED"}
        context.area.tag_redraw()
        # 先处理hud
        self.app_hud.push_event(event)
        if self.app_hud.should_pass_event():
            # 再处理主窗口
            # TODO 事件处理有问题, 不同的app鼠标事件清理交叉了
            self.app.push_event(event)
            if self.app.should_pass_event():
                return {"PASS_THROUGH"}
        return {"RUNNING_MODAL"}

    def handler_draw_hud(self, app: App, area):
        # self.show_demo_window()
        self.sdn_top_bar()
        # self.sdn_left_side_tool_bar()
        self.sdn_canvas_interactive_box()
        self.sdn_right_panel()

    def has_canvas_obj(self):
        if not (obj := bpy.context.object):
            return
        if not obj.is_sdn_canvas_layer or obj.type != "MESH":
            return
        vert_count = len(obj.data.vertices)
        if vert_count != 4:
            return
        return True

    def handler_draw_3d(self, app: App, area):
        # if not self.has_canvas_obj():
        #     return
        self.sdn_canvas_layer()
        # self.show_demo_window()

    @contextmanager
    def with_sdn_style(self, text_align_x=0.5):
        # 设置 圆角
        style = Styler()
        style.push_style_var(imgui.StyleVar.WINDOW_PADDING, Const.WINDOW_P)
        style.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.WINDOW_R)
        style.push_style_var(imgui.StyleVar.WINDOW_BORDER_SIZE, Const.WINDOW_BS)
        style.push_style_var(imgui.StyleVar.POPUP_BORDER_SIZE, Const.POPUP_BS)  # 弹出框边线(向内加宽)
        style.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.FRAME_R)
        style.push_style_var_y(imgui.StyleVar.CELL_PADDING, 0)
        style.push_style_var(imgui.StyleVar.BUTTON_TEXT_ALIGN, (text_align_x, 0.5))

        style.push_style_color(imgui.Col.POPUP_BG, Const.POPUP_BG)
        style.push_style_color(imgui.Col.WINDOW_BG, Const.WINDOW_BG)
        style.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
        style.push_style_color(imgui.Col.BUTTON_HOVERED, Const.BUTTON_HOVERED)
        style.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.BUTTON_ACTIVE)
        style.push_style_color(imgui.Col.TEXT, Const.TEXT)
        try:
            yield
        except Exception as e:
            print(e)

    def show_demo_window(self):
        from .example.demo_window import show_demo_window

        show_demo_window(True, self._texture)
        imgui.show_demo_window()

    def sdn_demo_clip_images(self):
        """两张图片对比 裁切测试"""
        img_path1 = "/Users/karrycharon/Desktop/OutputImage/WX20250208-113602.png"
        img_path2 = "/Users/karrycharon/Desktop/KCTemp/20241210-111729.jpeg"
        CustomWidgets.clip_image(img_path1, img_path2, (1024, 1024))

    def sdn_top_bar(self):
        self.app_hud.font_manager.push_h2_font()

        btn_w = 96
        btn_h = 54
        ele_size = 10
        window_size = 1330, 0
        window_pos = (bpy.context.region.width - window_size[0]) * 0.5, 100
        imgui.set_next_window_pos(window_pos, imgui.Cond.ALWAYS)
        imgui.set_next_window_size(window_size, imgui.Cond.ALWAYS)
        flags = 0
        flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS
        flags |= imgui.WindowFlags.ALWAYS_AUTO_RESIZE

        iw, ih = btn_h * 0.75, btn_h * 0.75
        isx = imgui.get_style().item_spacing[0]
        ioffx, ioffy = -btn_w * 0.5 - iw * 0.5 - isx, (btn_h - ih) * 0.5

        with self.with_sdn_style():
            imgui.begin("##TopBar", flags=flags)
            imgui.push_style_var_x(imgui.StyleVar.CELL_PADDING, 5 / 2)
            imgui.push_style_color(imgui.Col.BUTTON, Const.TRANSPARENT)
            imgui.begin_table("BarTable", ele_size + 1)
            for i in range(4):
                imgui.table_setup_column(f"{i}", imgui.TableColumnFlags.WIDTH_FIXED, btn_w, i)

            imgui.table_next_column()
            imgui.push_id("新建图层")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "new", (iw, ih), (ioffx, ioffy)):
                self.app_hud.state.set_active_right_panel(RightPanelType.LAYERS)
                print("按下新建图层")
            imgui.pop_id()

            imgui.table_next_column()
            imgui.push_id("上传")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "upload", (iw, ih), (ioffx, ioffy)):
                self.app_hud.state.set_active_right_panel(RightPanelType.NONE)
                print("上传 按下")
            imgui.pop_id()

            imgui.table_next_column()
            imgui.push_id("渲染")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "camera", (iw, ih), (ioffx, ioffy)):
                self.app_hud.state.set_active_right_panel(RightPanelType.NONE)
                print("渲染 按下")
            imgui.pop_id()

            imgui.table_next_column()
            imgui.push_id("生成")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "robot", (iw, ih), (ioffx, ioffy)):
                self.app_hud.state.set_active_right_panel(RightPanelType.GENERATION)
                print("生成 按下")
            imgui.pop_id()

            # 竖直线
            imgui.table_next_column()
            imgui.begin_group()
            dl = imgui.get_window_draw_list()
            x, y = imgui.get_cursor_screen_pos()
            y += (btn_h - ih) * 0.5
            color = imgui.color_convert_float4_to_u32((65 / 255, 65 / 255, 65 / 255, 1))
            dl.add_rect((x, y), (x + 3, y + ih), color, 1)
            imgui.dummy((3 + imgui.get_style().cell_padding[0] / 2, btn_h))
            imgui.end_group()

            imgui.table_next_column()
            imgui.push_id("生成1")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "hash", (iw, ih), (ioffx, ioffy)):
                print("# 按下")
            imgui.pop_id()

            imgui.table_next_column()
            imgui.push_id("生成2")
            if CustomWidgets.icon_button("", (btn_w, btn_h), "font", (iw, ih), (ioffx, ioffy)):
                print("T 按下")
            imgui.pop_id()

            imgui.table_next_column()

            imgui.end_table()
            imgui.pop_style_var()
            imgui.pop_style_color()
            imgui.end()
        self.app_hud.font_manager.pop_font()

    def sdn_canvas_layer(self):
        obj = bpy.context.object
        objs = [o for o in bpy.context.selected_objects if o.is_sdn_canvas_layer]
        if obj and obj.is_sdn_canvas_layer and obj not in objs:
            objs.append(obj)
        elif objs:
            obj = objs[0]
        if not objs:
            return
        # self.app.font_manager.push_h4_font()
        # blender坐标系 -> imgui坐标系
        verts = []
        for o in objs:
            for v in o.bound_box:
                verts.append(o.matrix_world @ Vector(v))
        verts = np.array(verts)
        min_x = verts[:, 0].min()
        min_z = verts[:, 2].min()
        max_x = verts[:, 0].max()
        max_z = verts[:, 2].max()
        lt_pos = Vector((min_x, 0, max_z))
        rb_pos = Vector((max_x, 0, min_z))
        lt_pos_imgui = self.app.blender_to_imgui_pos(lt_pos)
        rb_pos_imgui = self.app.blender_to_imgui_pos(rb_pos)

        obj_width = rb_pos_imgui[0] - lt_pos_imgui[0]
        obj_height = lt_pos_imgui[1] - rb_pos_imgui[1]
        style = imgui.get_style()
        img_hud_text_height = max(30, imgui.get_text_line_height_with_spacing())
        img_hud_pos = lt_pos_imgui[0], lt_pos_imgui[1] - img_hud_text_height - style.cell_padding[1]
        img_hud_size = obj_width, img_hud_text_height
        imgui.set_next_window_pos(img_hud_pos, cond=imgui.Cond.ALWAYS)
        imgui.set_next_window_size(img_hud_size, cond=imgui.Cond.ALWAYS)

        flags = 0
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        # flags |= imgui.WindowFlags.ALWAYS_AUTO_RESIZE
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS

        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, (0, 0))
        imgui.push_style_var(imgui.StyleVar.WINDOW_BORDER_SIZE, 0)
        imgui.push_style_var_x(imgui.StyleVar.CELL_PADDING, 0)
        imgui.push_style_color(imgui.Col.WINDOW_BG, Const.TRANSPARENT)
        imgui.begin("CanvasLayer", flags=flags)
        imgui.begin_table("Table", 2)
        # 设置列属性 两列
        imgui.table_setup_column("Layer")
        table_col_flags = imgui.TableColumnFlags.WIDTH_FIXED

        canvas_width = round((max_x - min_x) * 100 * 72 / 2.54)
        canvas_height = round((max_z - min_z) * 100 * 72 / 2.54)

        table_content = f"{canvas_width} x {canvas_height} px"
        pixel_size_content_width = imgui.calc_text_size(table_content)[0]
        imgui.table_setup_column("PixelSize", table_col_flags, pixel_size_content_width)

        # 开始绘制
        imgui.table_next_column()
        imgui.text(f"图层: {obj.name if len(objs) == 1 else '多图层'}")

        imgui.table_next_column()
        imgui.text(table_content)

        imgui.end_table()
        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(3)
        dl = imgui.get_foreground_draw_list()
        col = imgui.get_color_u32((1, 1, 0, 1))
        dl.add_rect(lt_pos_imgui[:2], rb_pos_imgui[:2], col, thickness=0.8)
        # self.app.font_manager.pop_font()

    def sdn_canvas_interactive_box(self):
        if not self.has_canvas_obj():
            return
        window_width = 1330
        imgui.set_next_window_pos((0, 0), cond=imgui.Cond.FIRST_USE_EVER)
        imgui.set_next_window_size((window_width, -1), cond=imgui.Cond.ALWAYS)
        flags = 0
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        # flags |= imgui.WindowFlags.NO_RESIZE
        # flags |= imgui.WindowFlags.ALWAYS_AUTO_RESIZE

        styler = Styler()
        # 设置 圆角
        styler.push_style_var(imgui.StyleVar.WINDOW_PADDING, Const.CB_WINDOW_P)  # 向外加宽
        styler.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.CB_WINDOW_R)
        styler.push_style_var(imgui.StyleVar.FRAME_BORDER_SIZE, Const.CB_FRAME_BS)  # 帧边线宽度
        styler.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.CB_FRAME_R)
        styler.push_style_var(imgui.StyleVar.POPUP_BORDER_SIZE, Const.CB_POPUP_BS)  # 弹出框边线(向内加宽)

        styler.push_style_color(imgui.Col.WINDOW_BG, Const.WINDOW_BG)
        styler.push_style_color(imgui.Col.FRAME_BG, Const.CB_FRAME_BG)
        styler.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
        styler.push_style_color(imgui.Col.BUTTON_HOVERED, Const.BUTTON_HOVERED)
        styler.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.BUTTON_ACTIVE)
        styler.push_style_color(imgui.Col.TEXT, Const.TEXT)

        imgui.begin("##InteractiveBox", flags=flags)

        # 第一行
        icon = TexturePool.get_tex_id("edit_mode")
        size = 85, 85
        imgui.image(icon, size)
        imgui.same_line()
        imgui.image(icon, size)
        imgui.same_line()
        imgui.image(icon, size)

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # 第二行
        self.app_hud.font_manager.push_content_font()
        mlt_flags = 0
        mlt_flags |= imgui.InputTextFlags.WORD_WRAP
        text_height = imgui.get_text_line_height() * 4
        changed, self.input_text = imgui.input_text_multiline("##BottomMLT", self.input_text, (-1, text_height), mlt_flags)
        if not self.input_text:
            imgui.same_line(60)
            old_pos = imgui.get_cursor_pos()
            styler.push_style_color(imgui.Col.TEXT, (0.5, 0.5, 0.5, 1))
            imgui.text("开始创作")
            styler.pop_style_color()
            imgui.set_cursor_pos((old_pos[0], old_pos[1]))
        self.app_hud.font_manager.pop_font()

        imgui.spacing()
        imgui.separator()
        imgui.spacing()

        # 第三行
        # 左侧：图标+文字
        if imgui.button("Nano Banana", (236, 54)):
            print("Left button clicked")

        imgui.same_line()
        imgui.button("1:1", (122, 54))

        imgui.same_line()
        imgui.button("相机", (139, 54))

        imgui.same_line()
        imgui.button("覆盖", (139, 54))

        # 中间空白：使用相同的空间推到右侧
        imgui.same_line()
        imgui.dummy((imgui.get_content_region_avail()[0] - 100, 0))  # 留出右边空间

        # 右侧：图标
        imgui.same_line()
        if imgui.button("R", (134, 54)):
            print("Right icon clicked")

        styler.pop_all()
        imgui.end()

    def sdn_layers_panel(self):
        if self.app_hud.state.active_right_panel != RightPanelType.LAYERS:
            return
        window_size = 540, 1359
        window_pos = bpy.context.region.width - window_size[0] - get_ui_panel_width(), 400
        imgui.set_next_window_pos(window_pos, imgui.Cond.ALWAYS)
        imgui.set_next_window_size(window_size, imgui.Cond.ALWAYS)
        flags = 0
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        # flags |= imgui.WindowFlags.ALWAYS_AUTO_RESIZE
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS
        layer = self.app_hud.state.right_panels_data.layer
        dummy_size = 0, 26 / 2

        with self.with_sdn_style():
            imgui.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.LP_WINDOW_R)
            imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, Const.LP_WINDOW_P)  # 向外加宽
            imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.LP_FRAME_R)

            imgui.begin("Layers", flags=flags)

            imgui.push_style_var_x(imgui.StyleVar.CELL_PADDING, Const.LP_CELL_P[0])
            imgui.push_style_var_y(imgui.StyleVar.BUTTON_TEXT_ALIGN, 0.9)
            imgui.push_style_color(imgui.Col.BUTTON, Const.BUTTON)

            # region 新建图层
            if True:
                self.app_hud.font_manager.push_h1_font()
                imgui.text("新建图层")
                self.app_hud.font_manager.pop_font()
                imgui.same_line()
                # 关闭按钮
                h = imgui.get_text_line_height_with_spacing()
                aw = imgui.get_content_region_avail()[0]
                imgui.dummy((aw - Const.LP_WINDOW_P[0] - h * 0.5, h))
                imgui.same_line()
                imgui.push_style_color(imgui.Col.BUTTON, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.TRANSPARENT)

                if imgui.button("##CloseBtn", (h, h)):
                    self.app_hud.state.active_right_panel = RightPanelType.NONE
                imgui.pop_style_color(3)
                col = Const.CLOSE_BUTTON_NORMAL
                if imgui.is_item_active():
                    col = Const.CLOSE_BUTTON_ACTIVE
                elif imgui.is_item_hovered():
                    col = Const.CLOSE_BUTTON_HOVERED
                col = imgui.get_color_u32(col)
                icon = TexturePool.get_tex_id("close")
                dl = imgui.get_window_draw_list()
                dl.add_image(icon, imgui.get_item_rect_min(), imgui.get_item_rect_max(), col=col)
            # endregion

            # region 通用
            if True:
                imgui.dummy(dummy_size)
                self.app_hud.font_manager.push_h2_font()
                imgui.text("通用")
                imgui.dummy(dummy_size)
                self.app_hud.font_manager.pop_font()
                common_presets = layer.common_presets

                imgui.begin_table("##LayersPresets", len(common_presets))
                imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, 9)
                presets_size = -imgui.FLT_MIN, 100
                isx = imgui.get_style().item_spacing[0]
                fpy = imgui.get_style().frame_padding[1]
                for preset, config in common_presets.items():
                    imgui.table_next_column()
                    imgui.begin_group()
                    if imgui.button(preset, presets_size):
                        LayerPanelHandler.create_layer(deepcopy(config))
                    btn_w = imgui.get_column_width()
                    iw, ih = btn_w * 0.5, btn_w * 0.5
                    ioffx, ioffy = -btn_w - isx + (btn_w - iw) * 0.5, (presets_size[1] - ih) * 0.3 - fpy
                    imgui.same_line()
                    pos = imgui.get_cursor_pos()
                    imgui.set_cursor_pos((pos[0] + ioffx, pos[1] + ioffy))
                    tex_id = TexturePool.get_tex_id("CommonPresets/" + preset.replace(":", "-"))
                    imgui.image(tex_id, (iw, ih))
                    imgui.end_group()
                imgui.pop_style_var()
                imgui.end_table()

            # endregion
            imgui.pop_style_var(2)
            imgui.pop_style_color()

            # region 行业控件
            # 行业分类
            if True:
                imgui.dummy(dummy_size)
                self.app_hud.font_manager.push_h2_font()
                imgui.text("行业")
                self.app_hud.font_manager.pop_font()
                imgui.dummy(dummy_size)

                dl = imgui.get_window_draw_list()
                col = imgui.color_convert_float4_to_u32((56 / 255, 56 / 255, 56 / 255, 1))
                fp = imgui.get_cursor_screen_pos()
                tp = fp[0] + imgui.get_content_region_avail()[0] + 6, fp[1] + 54 + 12
                dl.add_rect_filled((fp[0] - 6, fp[1]), tp, col, Const.LP_FRAME_R)

                btn_w = 155
                btn_h = 54
                isx = imgui.get_style().item_spacing[0]
                fpy = imgui.get_style().frame_padding[1]
                presets_size = -imgui.FLT_MIN, 54
                iw, ih = btn_h * 0.75, btn_h * 0.75
                ioffx, ioffy = -btn_w + isx, (btn_h - ih) * 0.5 - fpy

                industrial_presets = layer.industrial_presets
                tab_flags = 0
                # tab_flags |= imgui.TableFlags.BORDERS
                imgui.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.LP_FRAME_R)
                imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, btn_h / 2)
                imgui.push_style_var(imgui.StyleVar.CELL_PADDING, Const.LP_INDUSTRIAL_CELL_P)
                imgui.push_style_var_x(imgui.StyleVar.BUTTON_TEXT_ALIGN, Const.LP_INDUSTRIAL_BUTTON_TEXT_ALIGNX)
                imgui.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
                imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.LP_INDUSTRIAL_BUTTON_ACTIVE)
                imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.LP_INDUSTRIAL_BUTTON_HOVERED)

                imgui.begin_table("##IndustrialPresets", len(industrial_presets), tab_flags)
                for preset_name in industrial_presets:
                    imgui.table_next_column()
                    should_highlight = preset_name == layer.industrial_preset_id
                    if should_highlight:
                        imgui.push_style_color(imgui.Col.BUTTON, Const.LP_INDUSTRIAL_BUTTON_HOVERED)
                    # if imgui.button(preset_name, presets_size):
                    if CustomWidgets.icon_button(preset_name, presets_size, "camera", (iw, ih), (ioffx, ioffy)):
                        layer.industrial_preset_id = preset_name
                    if should_highlight:
                        imgui.pop_style_color()
                imgui.end_table()

                imgui.pop_style_var(4)
                imgui.pop_style_color(3)

            # endregion

            # region 行业控件列表
            if True:
                imgui.dummy(dummy_size)

                tab_flags = 0
                tab_flags |= imgui.TableFlags.SCROLL_Y

                dummy_size = 0, 12 / 2
                btn_h = 66
                isy = imgui.get_style().item_spacing[1]
                fpy = imgui.get_style().frame_padding[1]
                base_btn_h = btn_h + isy + dummy_size[1]
                outer_size = 0, base_btn_h * 10

                imgui.push_style_var(imgui.StyleVar.SCROLLBAR_SIZE, 0)
                imgui.push_style_var_x(imgui.StyleVar.BUTTON_TEXT_ALIGN, 0.05)
                imgui.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
                imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.BUTTON_ACTIVE)

                self.app_hud.font_manager.push_h3_font()
                imgui.begin_table("##IndustrialPresetsList", 1, tab_flags, outer_size)
                text_h = imgui.get_text_line_height_with_spacing()
                for label, config in layer.industrial_preset.items():
                    imgui.table_next_column()
                    imgui.begin_group()
                    if imgui.button(label, (-imgui.FLT_MIN, btn_h)):
                        LayerPanelHandler.create_layer(deepcopy(config))
                    imgui.same_line()
                    cursor_pos = imgui.get_cursor_pos()
                    size = config["pixel_size"]
                    dpi = config["dpi"]
                    text = config.get("display_content", f"{size[0]}x{size[1]} px({dpi})")
                    text_width = imgui.calc_text_size(text)[0]

                    imgui.set_cursor_pos((cursor_pos[0] - text_width - 35, cursor_pos[1] + (btn_h - text_h) * 0.5 - fpy))
                    imgui.text(text)
                    imgui.dummy(dummy_size)
                    imgui.end_group()
                imgui.end_table()
                self.app_hud.font_manager.pop_font()

                imgui.pop_style_var(2)
                imgui.pop_style_color(2)

            # endregion
            imgui.end()
            imgui.pop_style_var(3)

    def sdn_right_panel(self):
        self.sdn_layers_panel()
        self.sdn_canvas_generation_panel()
        self.sdn_canvas_material_panel()

    def sdn_canvas_generation_panel(self):
        if self.app_hud.state.active_right_panel != RightPanelType.GENERATION:
            return
        if not bpy.context.object:
            return
        window_size = 540, 1359
        window_pos = bpy.context.region.width - window_size[0] - get_ui_panel_width(), 400
        imgui.set_next_window_pos(window_pos, imgui.Cond.ALWAYS)
        imgui.set_next_window_size(window_size, imgui.Cond.ALWAYS)
        flags = 0
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS

        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, Const.RP_WINDOW_P)
        imgui.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.RP_WINDOW_R)
        imgui.push_style_var(imgui.StyleVar.FRAME_PADDING, Const.RP_FRAME_P)
        imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.RP_FRAME_R)
        imgui.push_style_var(imgui.StyleVar.CELL_PADDING, Const.RP_CELL_P)
        imgui.push_style_var_x(imgui.StyleVar.ITEM_SPACING, 0)

        imgui.push_style_color(imgui.Col.WINDOW_BG, Const.RP_L_BOX_BG)
        imgui.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
        imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.BUTTON_ACTIVE)
        imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.BUTTON_HOVERED)

        istyle = imgui.get_style()
        fp = istyle.frame_padding
        cp = istyle.cell_padding

        imgui.begin("##RightPanel", False, flags)
        # Left
        if True:
            imgui.begin_group()
            imgui.set_cursor_pos((fp[0], fp[1] - cp[1]))

            btn_size = 40, 40
            left_w = btn_size[0] + (fp[0] + fp[0]) * 2
            imgui.begin_table("CategoryTable", 1, outer_size=(left_w - fp[0], 0))
            for i in range(8):
                if i == 3:
                    # 水平线
                    imgui.table_next_column()
                    imgui.begin_group()
                    x, y = imgui.get_cursor_screen_pos()
                    x += 7
                    y += 10
                    col = imgui.get_color_u32((65 / 255, 65 / 255, 65 / 255, 1))
                    dl = imgui.get_window_draw_list()
                    dl.add_rect((x, y), (x + btn_size[0] + fp[0] * 2 - 14, y + 3), col, 3)
                    imgui.dummy((0, 3 + 20))
                    imgui.end_group()

                imgui.table_next_column()
                icon = TexturePool.get_tex_id(f"RightPanel/p{i + 1}")
                if imgui.image_button(f"##Btn{i}", icon, btn_size):
                    print(f"RP Left Button {i} pressed")

            imgui.end_table()
            imgui.end_group()

        imgui.same_line()
        imgui.pop_style_var(6)

        # Right
        if True:
            wx, wy = imgui.get_window_pos()
            ww, wh = imgui.get_window_size()

            lt = wx + left_w, wy
            rb = wx + ww, wy + wh
            col = imgui.get_color_u32(Const.RP_R_BOX_BG)
            r = Const.LP_WINDOW_R + 4
            dl = imgui.get_window_draw_list()
            dl.add_rect_filled(lt, rb, col, r, imgui.DrawFlags.ROUND_CORNERS_RIGHT)

            cx, cy = imgui.get_cursor_pos()
            cx += Const.RP_R_WINDOW_P[0]
            cy += Const.RP_R_WINDOW_P[1]
            imgui.set_cursor_pos((cx, cy - cp[1]))
            imgui.begin_table("##RightInner", 1, outer_size=(ww - left_w - Const.RP_R_WINDOW_P[0] * 2, 0))

            imgui.table_next_column()
            imgui.begin_group()
            self._sdn_canvas_generation_panel()
            imgui.end_group()

            imgui.end_table()

        imgui.end()
        imgui.pop_style_color(4)

    def _sdn_canvas_generation_panel(self):
        canvas = self.app_hud.state.right_panels_data.canvas
        dummy_size = 0, 26 / 2
        imgui.push_style_var_x(imgui.StyleVar.CELL_PADDING, Const.LP_CELL_P[0])

        # region 新建图层
        if True:
            self.app_hud.font_manager.push_h1_font()
            imgui.text("生成")
            imgui.same_line()
            imgui.text(" CREATE ")
            self.app_hud.font_manager.pop_font()
            imgui.same_line()
            # 关闭按钮
            if True:
                h = imgui.get_text_line_height_with_spacing()
                aw = imgui.get_content_region_avail()[0]
                imgui.dummy((aw - Const.LP_WINDOW_P[0] - h * 0.5, h))
                imgui.same_line()
                imgui.push_style_color(imgui.Col.BUTTON, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.TRANSPARENT)

                if imgui.button("##CloseBtn", (h, h)):
                    self.app_hud.state.active_right_panel = RightPanelType.NONE
                imgui.pop_style_color(3)
                col = Const.CLOSE_BUTTON_NORMAL
                if imgui.is_item_active():
                    col = Const.CLOSE_BUTTON_ACTIVE
                elif imgui.is_item_hovered():
                    col = Const.CLOSE_BUTTON_HOVERED
                col = imgui.get_color_u32(col)
                icon = TexturePool.get_tex_id("close")
                dl = imgui.get_window_draw_list()
                dl.add_image(icon, imgui.get_item_rect_min(), imgui.get_item_rect_max(), col=col)

            if False:
                imgui.dummy(dummy_size)
                gen_presets = {
                    "去背景": None,
                    "擦除": None,
                    "补全": None,
                    "超清": None,
                }

                imgui.begin_table("##GenerationPresets", len(gen_presets))
                imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, 9)
                imgui.push_style_color(imgui.Col.BUTTON, Const.RP_R_BUTTON)

                presets_size = -imgui.FLT_MIN, 104
                isx = imgui.get_style().item_spacing[0]
                fpy = imgui.get_style().frame_padding[1]
                for preset, _config in gen_presets.items():
                    imgui.table_next_column()
                    imgui.begin_group()
                    if imgui.button(preset, presets_size):
                        print("Button pressed: " + preset)
                    btn_w = imgui.get_column_width()
                    iw, ih = btn_w * 0.5, btn_w * 0.5
                    ioffx, ioffy = -btn_w - isx + (btn_w - iw) * 0.5, (presets_size[1] - ih) * 0.3 - fpy
                    imgui.same_line()
                    pos = imgui.get_cursor_pos()
                    imgui.set_cursor_pos((pos[0] + ioffx, pos[1] + ioffy))
                    tex_id = TexturePool.get_tex_id("CommonPresets/" + preset.replace(":", "-"))
                    imgui.image(tex_id, (iw, ih))
                    imgui.end_group()

                imgui.pop_style_var()
                imgui.pop_style_color()
                imgui.end_table()

        # endregion
        # region 工作流
        if True:
            imgui.dummy(dummy_size)
            self.app_hud.font_manager.push_h2_font()
            imgui.text("工作流")
            self.app_hud.font_manager.pop_font()
            imgui.dummy((dummy_size[0], dummy_size[1] - 8))

            imgui.push_style_var_y(imgui.StyleVar.WINDOW_PADDING, 24)
            imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.CHILD_R)
            imgui.push_style_var(imgui.StyleVar.FRAME_PADDING, Const.CHILD_P)
            imgui.push_style_var(imgui.StyleVar.FRAME_BORDER_SIZE, Const.CHILD_BS)
            imgui.push_style_var(imgui.StyleVar.POPUP_ROUNDING, 24)
            imgui.push_style_var(imgui.StyleVar.ITEM_SPACING, (8, 8))

            imgui.push_style_color(imgui.Col.FRAME_BG, Const.WINDOW_BG)
            imgui.push_style_color(imgui.Col.POPUP_BG, Const.POPUP_BG)
            imgui.push_style_color(imgui.Col.HEADER, Const.BUTTON)
            imgui.push_style_color(imgui.Col.HEADER_ACTIVE, Const.BUTTON_ACTIVE)
            imgui.push_style_color(imgui.Col.HEADER_HOVERED, Const.BUTTON_HOVERED)
            flags = 0
            flags |= imgui.ChildFlags.FRAME_STYLE
            flags |= imgui.ChildFlags.AUTO_RESIZE_Y
            flags |= imgui.ChildFlags.ALWAYS_AUTO_RESIZE

            if True:
                imgui.push_style_var(imgui.StyleVar.FRAME_PADDING, (12, 12))
                with with_child("##WorkflowSelection", (0, 0), child_flags=flags):
                    self.app_hud.font_manager.push_h3_font()
                    imgui.text("角色变更1.2")
                    self.app_hud.font_manager.pop_font()
                imgui.pop_style_var()

            if True:
                # TODO 优化: 不需要每次都重新解析
                obj = bpy.context.object
                wrapper = NodeTreeWrapper()
                wrapper.load(obj, filter=lambda n: n.get("title", "").startswith("#"))
                for node in wrapper.nodes.values():
                    node.display(wrapper, self.app_hud)
            # 底部按钮
            if True:
                cr = imgui.get_content_region_avail()
                cpos = imgui.get_cursor_pos()
                h = 54
                wp = imgui.get_style().window_padding
                imgui.set_cursor_pos_y(cpos[1] + cr[1] - h - wp[1])
                imgui.push_style_var(imgui.StyleVar.CELL_PADDING, (0, 0))
                imgui.push_style_color(imgui.Col.BUTTON, Const.TRANSPARENT)

                imgui.begin_table("##GenerationBottom", 3)

                imgui.table_setup_column("##Widget1", imgui.TableColumnFlags.WIDTH_FIXED)
                imgui.table_setup_column("##Widget2", imgui.TableColumnFlags.WIDTH_STRETCH)
                imgui.table_setup_column("##Widget3", imgui.TableColumnFlags.WIDTH_FIXED)

                imgui.table_next_column()
                imgui.push_style_var_x(imgui.StyleVar.BUTTON_TEXT_ALIGN, 0.7)
                imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, h / 2)

                imgui.push_style_color(imgui.Col.BUTTON, Const.SLIDER_NORMAL)
                if imgui.button(f"{self.app_hud.state.user_data.coins}", (148, h)):
                    self._sdn_execute_canvas_generation()
                imgui.pop_style_color()

                pmin = imgui.get_item_rect_min()
                bsize = imgui.get_item_rect_size()
                isize = imgui.get_text_line_height_with_spacing()
                icon = TexturePool.get_tex_id("RightPanel/coins")
                dl = imgui.get_window_draw_list()
                ipos = pmin[0] + bsize[0] * 0.15, pmin[1] + bsize[1] * 0.5 - isize * 0.5
                dl.add_image(icon, ipos, (ipos[0] + isize, ipos[1] + isize))

                imgui.pop_style_var(2)

                imgui.table_next_column()
                imgui.dummy((0, 0))

                imgui.table_next_column()
                with with_child("##GenTypesChild", (218, 0), child_flags=flags):
                    gen_types = ["Overwrite", "NewCanvas"]
                    imgui.begin_table("##GenTypesChildTable", len(gen_types))
                    imgui.table_setup_column("##Widget1", imgui.TableColumnFlags.WIDTH_STRETCH)
                    imgui.table_setup_column("##Widget2", imgui.TableColumnFlags.WIDTH_STRETCH)
                    for gen_type in gen_types:
                        imgui.table_next_column()
                        should_highlight = gen_type == canvas.gen_type
                        if should_highlight:
                            imgui.push_style_color(imgui.Col.BUTTON, Const.SLIDER_NORMAL)
                            imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.SLIDER_NORMAL)
                        w = imgui.get_content_region_avail()[0]
                        th = imgui.get_text_line_height()
                        fp = (h - imgui.get_style().frame_padding[1] * 2 - th) / 2
                        imgui.push_style_var_y(imgui.StyleVar.FRAME_PADDING, fp)
                        imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, 10)
                        if imgui.button(pgettext(gen_type), (w, 0)):
                            canvas.gen_type = gen_type
                        imgui.pop_style_var(2)
                        if should_highlight:
                            imgui.pop_style_color(2)
                    imgui.end_table()

                imgui.end_table()

                imgui.pop_style_var(1)
                imgui.pop_style_color()

            imgui.pop_style_var(6)
            imgui.pop_style_color(5)

        # endregion
        imgui.pop_style_var(1)

    def _sdn_execute_canvas_generation(self):
        obj = bpy.context.object
        if not TaskManager.is_launched():
            return
        tree = get_canvas_workflow(obj)
        if not tree:
            print("未找到画布工作流")
            return
        task_info = tree.get_task()
        task = Task(task_info, tree=tree)
        gen_type = self.app_hud.state.right_panels_data.canvas.gen_type
        mat = obj.active_material

        def cb(t: Task, result: dict):
            print("生成画布完成")
            img_paths = result.get("output", {}).get("images", [])
            if not img_paths:
                return

            img_node: bpy.types.ShaderNodeTexImage = find_node_by_type(mat.node_tree, "TEX_IMAGE")
            if gen_type == "Overwrite" and not img_node:
                return
            for data in img_paths:
                img_path = cache_to_local(data)
                if not img_path:
                    continue
                img_path = Path(img_path)
                if not img_path.exists():
                    continue
                if gen_type == "Overwrite":
                    print("覆盖:", img_path)
                    img_node.image = bpy.data.images.load(img_path.as_posix())
                else:
                    print("新建:", img_path)

        task.add_result_cb(cb)
        TaskManager.task_queue.put(task)

    def sdn_canvas_material_panel(self):
        if self.app_hud.state.active_right_panel != RightPanelType.MATERIAL:
            return
        if not bpy.context.object:
            return
        window_size = 540, 1359
        window_pos = bpy.context.region.width - window_size[0] - get_ui_panel_width(), 400
        imgui.set_next_window_pos(window_pos, imgui.Cond.ALWAYS)
        imgui.set_next_window_size(window_size, imgui.Cond.ALWAYS)
        flags = 0
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_MOVE
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_TITLE_BAR
        flags |= imgui.WindowFlags.NO_SCROLL_WITH_MOUSE
        flags |= imgui.WindowFlags.NO_SCROLLBAR
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS

        imgui.push_style_var(imgui.StyleVar.WINDOW_PADDING, Const.RP_WINDOW_P)
        imgui.push_style_var(imgui.StyleVar.WINDOW_ROUNDING, Const.RP_WINDOW_R)
        imgui.push_style_var(imgui.StyleVar.FRAME_PADDING, Const.RP_FRAME_P)
        imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.RP_FRAME_R)
        imgui.push_style_var(imgui.StyleVar.CELL_PADDING, Const.RP_CELL_P)
        imgui.push_style_var_x(imgui.StyleVar.ITEM_SPACING, 0)

        imgui.push_style_color(imgui.Col.WINDOW_BG, Const.RP_L_BOX_BG)
        imgui.push_style_color(imgui.Col.BUTTON, Const.BUTTON)
        imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.BUTTON_ACTIVE)
        imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.BUTTON_HOVERED)

        istyle = imgui.get_style()
        fp = istyle.frame_padding
        cp = istyle.cell_padding

        imgui.begin("##RightPanel", False, flags)
        # Left
        if True:
            imgui.begin_group()
            imgui.set_cursor_pos((fp[0], fp[1] - cp[1]))

            btn_size = 40, 40
            left_w = btn_size[0] + (fp[0] + fp[0]) * 2
            imgui.begin_table("CategoryTable", 1, outer_size=(left_w - fp[0], 0))
            for i in range(8):
                if i == 3:
                    # 水平线
                    imgui.table_next_column()
                    imgui.begin_group()
                    x, y = imgui.get_cursor_screen_pos()
                    x += 7
                    y += 10
                    col = imgui.get_color_u32((65 / 255, 65 / 255, 65 / 255, 1))
                    dl = imgui.get_window_draw_list()
                    dl.add_rect((x, y), (x + btn_size[0] + fp[0] * 2 - 14, y + 3), col, 3)
                    imgui.dummy((0, 3 + 20))
                    imgui.end_group()

                imgui.table_next_column()
                icon = TexturePool.get_tex_id(f"RightPanel/p{i + 1}")
                if imgui.image_button(f"##Btn{i}", icon, btn_size):
                    print(f"RP Left Button {i} pressed")

            imgui.end_table()
            imgui.end_group()

        imgui.same_line()
        imgui.pop_style_var(6)

        # Right
        if True:
            wx, wy = imgui.get_window_pos()
            ww, wh = imgui.get_window_size()

            lt = wx + left_w, wy
            rb = wx + ww, wy + wh
            col = imgui.get_color_u32(Const.RP_R_BOX_BG)
            r = Const.LP_WINDOW_R + 4
            dl = imgui.get_window_draw_list()
            dl.add_rect_filled(lt, rb, col, r, imgui.DrawFlags.ROUND_CORNERS_RIGHT)

            cx, cy = imgui.get_cursor_pos()
            cx += Const.RP_R_WINDOW_P[0]
            cy += Const.RP_R_WINDOW_P[1]
            imgui.set_cursor_pos((cx, cy - cp[1]))
            imgui.begin_table("##RightInner", 1, outer_size=(ww - left_w - Const.RP_R_WINDOW_P[0] * 2, 0))

            imgui.table_next_column()
            imgui.begin_group()
            self._sdn_canvas_material_panel()
            imgui.end_group()

            imgui.end_table()

        imgui.end()
        imgui.pop_style_color(4)

    def _sdn_canvas_material_panel(self):
        dummy_size = 0, 26 / 2
        imgui.push_style_var_x(imgui.StyleVar.CELL_PADDING, Const.LP_CELL_P[0])

        # region 新建图层
        if True:
            self.app_hud.font_manager.push_h1_font()
            imgui.text("材质")
            imgui.same_line()
            imgui.text(" MATERIAL ")
            self.app_hud.font_manager.pop_font()
            imgui.same_line()
            # 关闭按钮
            if True:
                h = imgui.get_text_line_height_with_spacing()
                aw = imgui.get_content_region_avail()[0]
                imgui.dummy((aw - Const.LP_WINDOW_P[0] - h * 0.5, h))
                imgui.same_line()
                imgui.push_style_color(imgui.Col.BUTTON, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_ACTIVE, Const.TRANSPARENT)
                imgui.push_style_color(imgui.Col.BUTTON_HOVERED, Const.TRANSPARENT)

                if imgui.button("##CloseBtn", (h, h)):
                    self.app_hud.state.active_right_panel = RightPanelType.NONE
                imgui.pop_style_color(3)
                col = Const.CLOSE_BUTTON_NORMAL
                if imgui.is_item_active():
                    col = Const.CLOSE_BUTTON_ACTIVE
                elif imgui.is_item_hovered():
                    col = Const.CLOSE_BUTTON_HOVERED
                col = imgui.get_color_u32(col)
                icon = TexturePool.get_tex_id("close")
                dl = imgui.get_window_draw_list()
                dl.add_image(icon, imgui.get_item_rect_min(), imgui.get_item_rect_max(), col=col)

        # endregion
        # region 按钮
        if True:
            imgui.dummy(dummy_size)
            self.app_hud.font_manager.push_h2_font()
            imgui.text("属性")
            self.app_hud.font_manager.pop_font()
            imgui.dummy((dummy_size[0], dummy_size[1] - 8))

            imgui.push_style_var_y(imgui.StyleVar.WINDOW_PADDING, 24)
            imgui.push_style_var(imgui.StyleVar.FRAME_ROUNDING, Const.CHILD_R)
            imgui.push_style_var(imgui.StyleVar.FRAME_PADDING, Const.CHILD_P)
            imgui.push_style_var(imgui.StyleVar.FRAME_BORDER_SIZE, Const.CHILD_BS)
            imgui.push_style_var(imgui.StyleVar.POPUP_ROUNDING, 24)
            imgui.push_style_var(imgui.StyleVar.ITEM_SPACING, (8, 8))

            imgui.push_style_color(imgui.Col.FRAME_BG, Const.WINDOW_BG)
            imgui.push_style_color(imgui.Col.POPUP_BG, Const.POPUP_BG)
            imgui.push_style_color(imgui.Col.HEADER, Const.BUTTON)
            imgui.push_style_color(imgui.Col.HEADER_ACTIVE, Const.BUTTON_ACTIVE)
            imgui.push_style_color(imgui.Col.HEADER_HOVERED, Const.BUTTON_HOVERED)
            flags = 0
            flags |= imgui.ChildFlags.FRAME_STYLE
            flags |= imgui.ChildFlags.AUTO_RESIZE_Y
            flags |= imgui.ChildFlags.ALWAYS_AUTO_RESIZE

            if True:
                obj = bpy.context.object
                mat = obj.active_material
                wrapper = MaterialWrapper()
                wrapper.load(mat, filter=lambda n: n.type == "GROUP")
                for node in wrapper.node_descriptors.values():
                    node.display(wrapper, self.app_hud)

            imgui.pop_style_var(6)
            imgui.pop_style_color(5)

        # endregion
        imgui.pop_style_var(1)

    def proc_selectable_click(self, label):
        old_state = self.selectables[label]
        if old_state is True:
            return

        def init_selectable():
            for k in self.selectables:
                self.selectables[k] = False

        def cb():
            obj = bpy.context.object
            if label == "close":
                self.app.should_exit = True
            elif label == "edit_mode":
                init_selectable()
                self.selectables[label] = True
                bpy.ops.object.mode_set(mode="EDIT")
            elif label == "object_mode":
                init_selectable()
                self.selectables[label] = True
                bpy.ops.object.mode_set(mode="OBJECT")
            elif label == "sculptmode_hlt" and obj and obj.type == "MESH":
                init_selectable()
                self.selectables[label] = True
                bpy.ops.object.mode_set(mode="SCULPT")
            elif label == "monkey":
                bpy.ops.mesh.primitive_monkey_add()

        Timer.put(cb)

    def sdn_left_side_tool_bar(self):
        self.update_selectable_status()
        bg_color = imgui.get_style().colors[imgui.Col.WINDOW_BG]
        bg_color = *bg_color[0:3], 0.85
        imgui.push_style_color(imgui.Col.WINDOW_BG, bg_color)
        # 设置窗口位置
        imgui.set_next_window_pos(pos=(100, 1200), cond=imgui.Cond.ONCE)
        flags = 0
        flags |= imgui.WindowFlags.NO_COLLAPSE
        flags |= imgui.WindowFlags.NO_SAVED_SETTINGS
        flags |= imgui.WindowFlags.NO_FOCUS_ON_APPEARING
        flags |= imgui.WindowFlags.ALWAYS_AUTO_RESIZE
        flags |= imgui.WindowFlags.NO_RESIZE
        flags |= imgui.WindowFlags.NO_TITLE_BAR

        imgui.begin(f"{self.title}##{self._id}", flags=flags)
        self._enable_when_drag_window()
        btn_color = imgui.get_style().colors[imgui.Col.BUTTON]
        imgui.begin_table("", len(self.selectables))
        for label in self.selectables:
            imgui.table_next_column()
            imgui.push_id(label)

            _btn_color = btn_color if self.selectables[label] else (0, 0, 0, 0)
            imgui.push_style_color(imgui.Col.BUTTON, _btn_color)
            icon = TexturePool.get_tex_id(label)
            if imgui.image_button("", icon, (100, 100)):
                self.proc_selectable_click(label)

            imgui.pop_style_color()
            imgui.pop_id()
        imgui.end_table()
        imgui.end()

        imgui.pop_style_color()

    def update_selectable_status(self):
        self.selectables["edit_mode"] = bpy.context.mode == "EDIT_MESH"
        self.selectables["object_mode"] = bpy.context.mode == "OBJECT"
        self.selectables["sculptmode_hlt"] = bpy.context.mode == "SCULPT"

    def _enable_when_drag_window(self):
        # 判断鼠标是否在窗口内
        if not imgui.is_window_hovered() or not imgui.is_mouse_dragging(imgui.MouseButton.RIGHT):
            return

        # 获取鼠标拖动量
        drag_delta = imgui.get_mouse_drag_delta(imgui.MouseButton.RIGHT)
        # 更新窗口位置

        old_pos = imgui.get_window_pos()
        imgui.set_window_pos(pos=(old_pos[0] + drag_delta[0], old_pos[1] + drag_delta[1]))
        # 重置拖动量
        imgui.reset_mouse_drag_delta(imgui.MouseButton.RIGHT)


clss = [
    ViewportGui,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
