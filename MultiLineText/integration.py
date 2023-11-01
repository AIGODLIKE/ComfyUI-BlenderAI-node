# Reference from: https://github.com/eliemichel/BlenderImgui
from typing import Any

import bpy
import json
from functools import lru_cache
from math import ceil
from pathlib import Path
from ..utils import _T, logger
from ..SDNode.tree import TREE_TYPE, NodeBase
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

    @staticmethod
    def init_font():
        io = imgui.get_io()
        fonts = io.fonts
        fonts.add_font_default()
        fp = Path(__file__).parent / "bmonofont-i18n.ttf"
        fonts.clear()
        fonts.add_font_from_file_ttf(fp.as_posix(), bpy.context.preferences.view.ui_scale * 20,
                                     glyph_ranges=fonts.get_glyph_ranges_chinese_full())

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

    def __init__(self):
        self.mpos = (0, 0)

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

    def poll_mouse(self, context: bpy.types.Context, event: bpy.types.Event):
        io = imgui.get_io()
        io.mouse_pos = (self.mpos[0], context.region.height - 1 - self.mpos[1])
        if event.type == 'LEFTMOUSE':
            io.mouse_down[0] = event.value == 'PRESS'

        elif event.type == 'RIGHTMOUSE':
            io.mouse_down[1] = event.value == 'PRESS'

        elif event.type == 'WHEELUPMOUSE':
            io.mouse_wheel = +1

        elif event.type == 'WHEELDOWNMOUSE':
            io.mouse_wheel = -1
        # cause cant input mlt
        # elif event.type == 'MIDDLEMOUSE':
        #     io.mouse_down[2] = event.value == 'PRESS'

    def poll_events(self, context: bpy.types.Context, event: bpy.types.Event):
        io = imgui.get_io()

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
        self.candicates_index = 0
        self.candicates_word = ""
        self.candicates_words = []
        self.try_search = False
        self.io = imgui.get_io()
        self._timer = context.window_manager.event_timer_add(1 / 60, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if not context.area:
            self.clear()
            return {"CANCELLED"}

        # 鼠标不在 region 范围则不更新
        self.mpos = event.mouse_region_x, event.mouse_region_y
        w, h = context.region.width, context.region.height
        if 0 > self.mpos[0] or self.mpos[0] > w or 0 > self.mpos[1] or self.mpos[1] > h:
            return {"PASS_THROUGH"}

        context.area.tag_redraw()
        if event.type == "ESC":
            self.stop_search()
            return {"RUNNING_MODAL"}
        # if event.type in {'RIGHTMOUSE', 'ESC'}:
        #     return {'CANCELLED'}
        self.poll_mouse(context, event)
        # print(context.area, self.mpos, self.cover, imgui.is_any_item_focused())
        if not self.cover:
            return {"PASS_THROUGH"}
        if self.candicates_words:
            if (event.type == "UP_ARROW" and event.value == "PRESS") or event.type == "WHEELUPMOUSE":
                self.candicates_index -= 1
                return {"RUNNING_MODAL"}
            if (event.type == "DOWN_ARROW" and event.value == "PRESS") or event.type == "WHEELDOWNMOUSE":
                self.candicates_index += 1
                return {"RUNNING_MODAL"}
        self.poll_events(context, event)
        return {"RUNNING_MODAL"}

    def poll_mouse(self, context, event):
        io = imgui.get_io()
        io.mouse_pos = (self.mpos[0], context.region.height - 1 - self.mpos[1])
        if event.type == 'LEFTMOUSE':
            io.mouse_down[0] = event.value == 'PRESS'
        if not self.candicates_words:
            if event.type == 'WHEELUPMOUSE':
                io.mouse_wheel = +1
            elif event.type == 'WHEELDOWNMOUSE':
                io.mouse_wheel = -1
    def poll_events(self, context, event):
        super().poll_events(context, event)
        if event.unicode and 0 < ord(event.unicode) < 0x10000:
            self.try_search = True

    def clear(self):
        super().clear()
        self.__class__.REG_AREA.discard(self.area)

    def stop_search(self):
        self.candicates_words = []
        self.try_search = False

    def track_any_cover(self):
        # is_window_hovered 鼠标选中当前窗口的标题栏时触发
        # is_window_focused 当前窗口被聚焦
        # is_item_hovered 当前项(窗口中的)被hover
        # is_item_focused 当前项(窗口中的)被聚焦
        # is_any_item_hovered 有任何项被聚焦
        # hover 不一定 focus,  focus也不一定hover
        self.cover |= imgui.is_any_item_hovered() or imgui.is_window_hovered()

    @staticmethod
    def can_draw() -> Any | None:
        tree = bpy.context.space_data.edit_tree
        if not tree or bpy.context.space_data.tree_type != TREE_TYPE:
            return
        node = tree.nodes.active
        if not node:
            return
        if node.bl_idname == "NodeFrame":
            return
        return node

    def draw_call(self, context: bpy.types.Context):
        self.cover = False
        if not (node := self.can_draw()):
            return
        self.draw_mlt(context, node)
        self.draw_rect(context, node)

    def draw_rect(self, context: bpy.types.Context, node: NodeBase):
        if node.bl_idname != "MultiAreaConditioning":
            return
        rx = node.resolutionX
        ry = node.resolutionY
        flags = imgui.WINDOW_NO_COLLAPSE | imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS | imgui.WINDOW_NO_SAVED_SETTINGS | imgui.WINDOW_NO_FOCUS_ON_APPEARING
        imgui.begin(_T(" MultiArea") + "##" + hex(hash(context.area)), closable=False, flags=flags)
        imgui.set_window_position(50, 20, condition=imgui.ONCE)
        imgui.set_window_size(rx, ry, condition=imgui.ALWAYS)
        imgui.text("")

        # 空心矩形
        min_x, min_y = imgui.get_item_rect_min()
        imgui.get_window_draw_list().add_rect_filled(
            upper_left_x=min_x,
            upper_left_y=min_y,
            lower_right_x=min_x + rx,
            lower_right_y=min_y + ry,
            col=imgui.get_color_u32_rgba(1, 1, 0, 0.4),
        )

        # 实心矩形
        for i, rect in enumerate(json.loads(node.config)):
            x = rect["x"]
            y = rect["y"]
            w = rect["sdn_width"]
            h = rect["sdn_height"]
            col = rect["col"]
            if i == node.index:
                col[-1] = 1
            col = imgui.get_color_u32_rgba(*col)
            imgui.get_window_draw_list().add_rect_filled(
                upper_left_x=min_x + x,
                upper_left_y=min_y + y,
                lower_right_x=min_x + x + w,
                lower_right_y=min_y + y + h,
                col=col,
            )

        self.track_any_cover()
        if imgui.is_item_hovered():
            imgui.core.set_keyboard_focus_here(-1)

        imgui.end()

    def draw_mlt(self, context: bpy.types.Context, node: NodeBase):
        draw_list: list[tuple[NodeBase, str]] = []

        def try_add(node: NodeBase, prop: str):
            md = node.get_meta(prop)
            if not md or md[0] != "STRING":
                return
            if len(md) <= 1 or not isinstance(md[1], dict) or not md[1].get("multiline", ):
                return
            draw_list.append((node, prop))

        for prop in node.inp_types:
            if node.query_stat(prop):
                continue
            try_add(node, prop)
        if node.bl_idname == "PrimitiveNode" and node.outputs[0].is_linked and node.outputs[0].links:
            try_add(node.outputs[0].links[0].to_node, node.prop)

        for count, (node, prop) in enumerate(draw_list):
            self.draw_mlt_ex(context, node, count, prop)

    def draw_mlt_ex(self, context, node: NodeBase, count: int, prop: str):
        flags = imgui.WINDOW_NO_BRING_TO_FRONT_ON_FOCUS | imgui.WINDOW_NO_SAVED_SETTINGS | imgui.WINDOW_NO_FOCUS_ON_APPEARING
        imgui.begin(f"{_T(' Prompts')}: {_T(prop)} ##" + hex(hash(context.area)), closable=False, flags=flags)
        imgui.set_window_position(50, 20 + count * 300, condition=imgui.ONCE)
        imgui.set_window_size(300, 300, condition=imgui.ONCE)
        window_size = imgui.core.get_window_size()
        w, h = window_size.x, window_size.y
        lnum = max(1, int(w * 2 // imgui.get_font_size()) - 3)

        def find_word(buffer, end_pos):
            buffer = buffer.encode()[:end_pos].decode()
            end_pos = len(buffer)
            # calculate with utf8 char instead bytes
            for i in range(end_pos - 1, -1, -1):
                c = buffer[i]
                if i == 0:
                    return 0, end_pos
                if c == ",":
                    return i + 1, end_pos
            return end_pos, end_pos

        def resize(data):
            ...

        def edit(data):
            # backspace = self.io.keys_down[self.key_map['BACK_SPACE']]
            p = data.cursor_pos
            p = len(get_wrap_text(data.buffer.encode()[:p].decode(), lnum).encode())
            setattr(node, data.user_data, data.buffer.replace("\n", ""))  # node.text = data.buffer.replace("\n", "")
            text = get_wrap_text(data.buffer, lnum)
            data.delete_chars(0, data.buffer_text_length)
            data.insert_chars(0, text)
            data.buffer_dirty = True
            data.cursor_pos = p

        def completion(data):
            if not self.candicates_word:
                return
            start_pos, end_pos = find_word(data.buffer, data.cursor_pos)
            cstart_pos = len(data.buffer[:start_pos].encode())
            data.delete_chars(cstart_pos, data.cursor_pos - cstart_pos)
            candicates_word = self.candicates_word.replace("(", "\\(").replace(")", "\\)")
            data.insert_chars(cstart_pos, candicates_word + ",")
            self.candicates_word = ""
            self.stop_search()
            edit(data)

        def always(data):
            # buffer_text_length 是最后一位
            # 161 12 156 158
            # print(data.buffer_text_length, data.buffer_size, len(data.buffer), data.cursor_pos)
            # cursor_start_pos = imgui.core.get_cursor_start_pos()
            if not self.try_search:
                return
            cursor_screen_pos = imgui.core.get_cursor_screen_pos()
            rect_min = imgui.get_item_rect_min()
            bbuffer = data.buffer.encode()[:data.cursor_pos].decode()
            curpy = imgui.calc_text_size(bbuffer, wrap_width=w).y
            curpx = imgui.calc_text_size("W" * (len(bbuffer) % (lnum + 1))).x
            curpx = curpx + rect_min.x
            curpy = curpy + cursor_screen_pos.y
            # curpy = min(max(curpy, rect_min.y + h), rect_min.y)
            curp = imgui.Vec2(curpx, curpy)
            start_pos, end_pos = find_word(data.buffer, data.cursor_pos)
            word = data.buffer[start_pos: end_pos]
            self.t(curp, word)

        cb_map = {
            imgui.INPUT_TEXT_CALLBACK_RESIZE: resize,
            imgui.INPUT_TEXT_CALLBACK_EDIT: edit,
            imgui.INPUT_TEXT_CALLBACK_COMPLETION: completion,
            imgui.INPUT_TEXT_CALLBACK_ALWAYS: always,
        }

        def cb(data):
            if cb := cb_map.get(data.event_flag, None):
                try:
                    cb(data)
                except IndexError as e:
                    logger.debug(f"{cb.__name__}: {e}")
                except Exception as e:
                    logger.debug(f"{cb.__name__}: {e}")
            # fix ctrl c/v duplicate
            for k in [imgui.KEY_A, imgui.KEY_C, imgui.KEY_V, imgui.KEY_X, imgui.KEY_Y, imgui.KEY_Z]:
                self.io.keys_down[k] = False

        ttt = get_wrap_text(getattr(node, prop), lnum)
        imgui.input_text_multiline(
            "",
            ttt,
            width=-1,
            height=-1,
            flags=imgui.INPUT_TEXT_CALLBACK_RESIZE | imgui.INPUT_TEXT_CALLBACK_EDIT | imgui.INPUT_TEXT_CALLBACK_COMPLETION | imgui.INPUT_TEXT_CALLBACK_ALWAYS,
            callback=cb,
            user_data=prop
        )
        # x, y = imgui.core.get_window_position()
        # y = context.region.height - 1 - y
        # self.cover = inbox(x, y, w, h, self.mpos)
        # cx, cy = imgui.core.get_window_content_region_min()
        # cw, ch = imgui.core.get_window_content_region_max()
        # in_content = inbox(x + cx, y - cy, w + cx, ch - cy - 30, self.mpos)
        # if in_content:
        #     imgui.core.set_keyboard_focus_here(-1)
        # self.io.keys_down[self.key_map["ESC"]] = not in_content

        self.track_any_cover()
        # print(imgui.is_item_hovered(), imgui.is_window_hovered(), imgui.is_item_focused(), imgui.is_window_focused())
        # self.cover = imgui.is_any_item_focused() or imgui.is_any_item_hovered() or imgui.is_any_item_active()
        if imgui.is_item_hovered():
            imgui.core.set_keyboard_focus_here(-1)
        else:
            for code in self.io.key_map:
                self.io.keys_down[code] = False
        # self.io.keys_down[self.key_map["ESC"]] = not self.cover
        imgui.end()

    def t(self, pos, word: str):
        from .trie import Trie
        if Trie.TRIE is None:
            return
        word = word.strip().replace("\n", "").replace(" ", "_").replace("\\(", "(").replace("\\)", ")")
        if not word:
            self.stop_search()
            return
        # (83, 'girly_pred', '0', '', 'e621', {}, (173, 216, 230))
        self.candicates_words = Trie.TRIE.bl_search(word, max_size=20)
        candicates_list = self.candicates_words
        self.candicates_index = max(0, min(self.candicates_index, len(candicates_list) - 1))
        index = self.candicates_index
        imgui.set_next_window_position(pos.x, pos.y)
        imgui.set_next_window_size(-1, -1)

        def freq_to_str(freq):
            if freq <= 100:
                return str(freq)
            if freq >= 500 * 1000:
                return f"{freq / 1000 / 1000:.2f}M"
            if freq > 100:
                return f"{freq / 1000:.2f}K"

        with imgui.begin_tooltip():
            for i, t in enumerate(candicates_list):
                # with imgui.begin_group():
                col = t[-1]
                imgui.push_style_color(imgui.COLOR_TEXT, col[0] / 256, col[1] / 256, col[2] / 256)
                show_txt = t[1] + "\t==>\t" + t[3] if t[3] else t[1]
                imgui.selectable(show_txt, i == index)
                imgui.same_line(position=300)
                # imgui.text(freq_to_str(t[0]))
                imgui.label_text(freq_to_str(t[0]), "")
                imgui.pop_style_color(1)
        if candicates_list:
            c = candicates_list[index]
            self.candicates_word = c[3] if c[3] else c[1]
        else:
            self.candicates_word = ""


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
