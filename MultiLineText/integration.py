# Reference from: https://github.com/eliemichel/BlenderImgui

import bpy
from functools import lru_cache
from math import ceil
from pathlib import Path
from ..utils import _T, logger
from ..SDNode.tree import TREE_TYPE
from .renderer import BlenderImguiRenderer, imgui

class GlobalImgui:
    _instance = None
    imgui_ctx = None
    draw_handlers = {}
    callbacks = {}
    imgui_backend = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init_font(self):
        io = imgui.get_io()
        fonts = io.fonts
        fonts.add_font_default()
        fp = Path(__file__).parent / "bmonofont-i18n.ttf"
        fonts.clear()
        fonts.add_font_from_file_ttf(fp.as_posix(), bpy.context.preferences.view.ui_scale * 20, glyph_ranges=fonts.get_glyph_ranges_chinese_full())

    def init_imgui(self):
        if self.imgui_ctx:
            return

        self.imgui_ctx = imgui.create_context()
        self.init_font()
        self.imgui_backend = BlenderImguiRenderer()
        self.setup_key_map()

    def shutdown_imgui(self):
        for (space, area), draw_handler in self.draw_handlers.items():
            space.draw_handler_remove(draw_handler, "WINDOW")
        self.draw_handlers.clear()
        imgui.destroy_context(self.imgui_ctx)
        self.imgui_ctx = None

    def handler_add(self, callback):
        self.init_imgui()
        space, area = bpy.context.space_data.__class__, bpy.context.area
        if (space, area) not in self.draw_handlers:
            self.draw_handlers[(space, area)] = space.draw_handler_add(self.draw, (area,), "WINDOW", "POST_PIXEL")
        if area not in self.callbacks:
            self.callbacks[area] = {callback}
        else:
            self.callbacks[area].add(callback)

    def handler_remove(self, handle=None):
        # clear all
        if not handle:
            self.callbacks.clear()
            self.shutdown_imgui()
            return
        # clear handle only
        for (space, area) in self.draw_handlers:
            if area != bpy.context.area:
                continue
            self.draw_handlers.pop((space, area))
            self.callbacks[area].discard(handle)

    def apply_ui_settings(self):
        region = bpy.context.region
        imgui.get_io().display_size = region.width, region.height
        style = imgui.get_style()
        style.window_padding = (1, 1)
        style.window_rounding = 6
        style.frame_rounding = 4
        style.frame_border_size = 1
        # io.font_global_scale = context.preferences.view.ui_scale

    def draw(self, area):
        if area != bpy.context.area:
            return

        self.apply_ui_settings()

        imgui.new_frame()
        title_bg_active_color = (0.546, 0.322, 0.730, 0.9)
        frame_bg_color = (0.512, 0.494, 0.777, 0.573)
        imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND_ACTIVE, *title_bg_active_color)
        imgui.push_style_color(imgui.COLOR_FRAME_BACKGROUND, *frame_bg_color)
        invalid_callback = []
        for cb in self.callbacks[area]:
            try:
                cb(bpy.context)
            except ReferenceError:
                invalid_callback.append(cb)
        for cb in invalid_callback:
            self.callbacks[area].discard(cb)
        imgui.pop_style_color()
        imgui.pop_style_color()
        imgui.end_frame()
        imgui.render()
        self.imgui_backend.render(imgui.get_draw_data())

    def setup_key_map(self):
        io = imgui.get_io()
        keys = (
            imgui.KEY_TAB,
            imgui.KEY_LEFT_ARROW,
            imgui.KEY_RIGHT_ARROW,
            imgui.KEY_UP_ARROW,
            imgui.KEY_DOWN_ARROW,
            imgui.KEY_HOME,
            imgui.KEY_END,
            imgui.KEY_INSERT,
            imgui.KEY_DELETE,
            imgui.KEY_BACKSPACE,
            imgui.KEY_ENTER,
            imgui.KEY_ESCAPE,
            imgui.KEY_PAGE_UP,
            imgui.KEY_PAGE_DOWN,
            imgui.KEY_A,
            imgui.KEY_C,
            imgui.KEY_V,
            imgui.KEY_X,
            imgui.KEY_Y,
            imgui.KEY_Z,
        )
        for k in keys:
            # We don't directly bind Blender's event type identifiers
            # because imgui requires the key_map to contain integers only
            io.key_map[k] = k


def inbox(x, y, w, h, mpos):
    if (x < mpos[0] < x + w) and (y - h < mpos[1] < y):
        return True
    return False


class BaseDrawCall:

    key_map = {
        'TAB': imgui.KEY_TAB,
        'LEFT_ARROW': imgui.KEY_LEFT_ARROW,
        'RIGHT_ARROW': imgui.KEY_RIGHT_ARROW,
        'UP_ARROW': imgui.KEY_UP_ARROW,
        'DOWN_ARROW': imgui.KEY_DOWN_ARROW,
        'HOME': imgui.KEY_HOME,
        'END': imgui.KEY_END,
        'INSERT': imgui.KEY_INSERT,
        'DEL': imgui.KEY_DELETE,
        'BACK_SPACE': imgui.KEY_BACKSPACE,
        'SPACE': imgui.KEY_SPACE,
        'RET': imgui.KEY_ENTER,
        'ESC': imgui.KEY_ESCAPE,
        'PAGE_UP': imgui.KEY_PAGE_UP,
        'PAGE_DOWN': imgui.KEY_PAGE_DOWN,
        'A': imgui.KEY_A,
        'C': imgui.KEY_C,
        'V': imgui.KEY_V,
        'X': imgui.KEY_X,
        'Y': imgui.KEY_Y,
        'Z': imgui.KEY_Z,
        'LEFT_CTRL': 128 + 1,
        'RIGHT_CTRL': 128 + 2,
        'LEFT_ALT': 128 + 3,
        'RIGHT_ALT': 128 + 4,
        'LEFT_SHIFT': 128 + 5,
        'RIGHT_SHIFT': 128 + 6,
        'OSKEY': 128 + 7,
    }
    REG_AREA = set()
        
    def try_reg(self, area: bpy.types.Area):
        if area in self.__class__.REG_AREA:
            return
        self.__class__.REG_AREA.add(area)
        GlobalImgui().handler_add(self.draw_call)
        return True

    def draw_call(self, context: bpy.types.Context):
        imgui.show_test_window()

    def clear(self):
        GlobalImgui().handler_remove(self.draw_call)

    def poll_events(self, context: bpy.types.Context, event: bpy.types.Event):
        region = context.region
        io = imgui.get_io()
        
        io.mouse_pos = (event.mouse_region_x, region.height - 1 - event.mouse_region_y)

        if event.type == 'LEFTMOUSE':
            io.mouse_down[0] = event.value == 'PRESS'

        elif event.type == 'RIGHTMOUSE':
            io.mouse_down[1] = event.value == 'PRESS'

        elif event.type == 'MIDDLEMOUSE':
            io.mouse_down[2] = event.value == 'PRESS'

        elif event.type == 'WHEELUPMOUSE':
            io.mouse_wheel = +1

        elif event.type == 'WHEELDOWNMOUSE':
            io.mouse_wheel = -1

        if event.type in self.key_map:
            if event.value == 'PRESS':
                io.keys_down[self.key_map[event.type]] = True
            elif event.value == 'RELEASE':
                io.keys_down[self.key_map[event.type]] = False

        io.key_ctrl = (
            io.keys_down[self.key_map['LEFT_CTRL']] or
            io.keys_down[self.key_map['RIGHT_CTRL']]
        )

        io.key_alt = (
            io.keys_down[self.key_map['LEFT_ALT']] or
            io.keys_down[self.key_map['RIGHT_ALT']]
        )

        io.key_shift = (
            io.keys_down[self.key_map['LEFT_SHIFT']] or
            io.keys_down[self.key_map['RIGHT_SHIFT']]
        )

        io.key_super = io.keys_down[self.key_map['OSKEY']]

        if event.unicode and 0 < (char := ord(event.unicode)) < 0x10000:
            io.add_input_character(char)


@lru_cache
def get_wrap_text(text, lwidth):
    text = text.replace("\n", "")
    return "\n".join(text[i * lwidth: (i + 1) * lwidth] for i in range(ceil(len(text) / lwidth)))


class MLTOps(bpy.types.Operator, BaseDrawCall):
    bl_idname = "sdn.multiline_text"
    bl_label = "MLT"

    def invoke(self, context, event):
        self.area = context.area
        if not self.try_reg(self.area):
            return {"FINISHED"}
        self.mpos = (0, 0)
        self.cover = False
        self.io = imgui.get_io()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.area:
            self.clear()
            return {"CANCELLED"}
        self.mpos = event.mouse_region_x, event.mouse_region_y
        w, h = context.region.width, context.region.height
        in_area = 0 < self.mpos[0] < w and 0 < self.mpos[1] < h
        if not in_area:  # multi windows cause event miss
            return {"PASS_THROUGH"}
        context.area.tag_redraw()

        # if event.type in {'RIGHTMOUSE', 'ESC'}:
        #     self.shutdown()
        #     return {'CANCELLED'}

        if not self.cover:
            return {"PASS_THROUGH"}
        self.poll_events(context, event)
        return {"RUNNING_MODAL"}

    def clear(self):
        super().clear()
        self.__class__.REG_AREA.discard(self.area)

    def can_draw(self):
        tree = bpy.context.space_data.edit_tree
        if not tree or bpy.context.space_data.tree_type != TREE_TYPE:
            return
        node = tree.nodes.active
        if not node or node.bl_idname != "CLIPTextEncode":
            return
        return node

    def draw_call(self, context: bpy.types.Context):
        if not (node := self.can_draw()):
            return
        flags = imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS | imgui.WINDOW_NO_SAVED_SETTINGS
        imgui.begin(_T(" Prompts") + "##" + hex(hash(context.area)), closable=False, flags=flags)
        imgui.set_window_position(50, 20, condition=imgui.ONCE)
        imgui.set_window_size(300, 300, condition=imgui.ONCE)

        w, h = imgui.core.get_window_size()
        lnum = max(1, int(w * 2 // imgui.get_font_size()) - 3)

        def cb(data):
            p = data.cursor_pos
            if data.event_flag == imgui.INPUT_TEXT_CALLBACK_EDIT:
                node.text = data.buffer.replace("\n", "")
                text = get_wrap_text(data.buffer, lnum)
                data.delete_chars(0, len(data.buffer))
                data.insert_chars(0, text)
                data.buffer_dirty = True
                backspace = self.io.keys_down[self.key_map['BACK_SPACE']]

                if not backspace and p % (lnum + 1) == 0:
                    p += 1
                data.cursor_pos = min(max(0, p), data.buffer_size)

        ttt = get_wrap_text(node.text, lnum)
        imgui.input_text_multiline(
            '',
            ttt,
            width=-1,
            height=-1,
            flags=imgui.INPUT_TEXT_CALLBACK_EDIT | imgui.INPUT_TEXT_CALLBACK_COMPLETION,
            callback=cb
        )
        x, y = imgui.core.get_window_position()
        y = context.region.height - 1 - y
        self.cover = inbox(x, y, w, h, self.mpos)
        cx, cy = imgui.core.get_window_content_region_min()
        cw, ch = imgui.core.get_window_content_region_max()
        in_content = inbox(x + cx, y - cy, w + cx, ch - cy - 30, self.mpos)
        if in_content:
            imgui.core.set_keyboard_focus_here(-1)
        self.io.keys_down[self.key_map["ESC"]] = not in_content

        imgui.end()


class GuiTest(bpy.types.Operator, BaseDrawCall):
    bl_idname = "sdn.gui_test"
    bl_label = "Gui Test"
    
    REG_AREA = set()
    
    def invoke(self, context, event):
        self.area = context.area
        if not self.try_reg(self.area):
            return {"FINISHED"}
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.area:
            self.clear()
            return {"CANCELLED"}
        self.mpos = event.mouse_region_x, event.mouse_region_y
        w, h = context.region.width, context.region.height
        in_area = 0 < self.mpos[0] < w and 0 < self.mpos[1] < h
        if not in_area:  # multi windows cause event miss
            return {"PASS_THROUGH"}
        context.area.tag_redraw()
        self.poll_events(context, event)
        return {"RUNNING_MODAL"}


@bpy.app.handlers.persistent
def reload(scene):
    BaseDrawCall.REG_AREA.clear()


def multiline_register():
    bpy.utils.register_class(MLTOps)
    bpy.utils.register_class(GuiTest)
    
    bpy.app.handlers.load_pre.append(reload)


def multiline_unregister():
    GlobalImgui().handler_remove()
    bpy.utils.unregister_class(MLTOps)
    bpy.utils.unregister_class(GuiTest)
