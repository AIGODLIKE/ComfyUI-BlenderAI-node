# Reference from: https://github.com/eliemichel/BlenderImgui

import bpy
import bgl as gl
import gpu
import numpy as np
import ctypes

from functools import lru_cache
from math import ceil
from pathlib import Path
from bpy.types import SpaceNodeEditor
from gpu_extras.batch import batch_for_shader
from ..utils import _T, logger
from ..SDNode.tree import TREE_TYPE
try:
    import imgui
except ModuleNotFoundError:
    print("ERROR: imgui was not found, run 'python -m pip install imgui' using Blender's Python.")
from imgui.integrations.base import BaseOpenGLRenderer


class BlenderImguiRenderer(BaseOpenGLRenderer):
    """Integration of ImGui into Blender."""

    VERTEX_SHADER_SRC = """
    uniform mat4 ProjMtx;
    in vec2 Position;
    in vec2 UV;
    in vec4 Color;
    out vec2 Frag_UV;
    out vec4 Frag_Color;

    void main() {
        Frag_UV = UV;
        Frag_Color = Color;

        gl_Position = ProjMtx * vec4(Position.xy, 0, 1);
    }
    """

    FRAGMENT_SHADER_SRC = """
    uniform sampler2D Texture;
    in vec2 Frag_UV;
    in vec4 Frag_Color;
    out vec4 Out_Color;

    vec4 linear_to_srgb(vec4 linear) {
        return mix(
            1.055 * pow(linear, vec4(1.0 / 2.4)) - 0.055,
            12.92 * linear,
            step(linear, vec4(0.00031308))
        );
    }

    vec4 srgb_to_linear(vec4 srgb) {
        return mix(
            pow((srgb + 0.055) / 1.055, vec4(2.4)),
            srgb / 12.92,
            step(srgb, vec4(0.04045))
        );
    }

    void main() {
        Out_Color = Frag_Color * texture(Texture, Frag_UV.st);
        Out_Color.rgba = srgb_to_linear(Out_Color.rgba);
    }
    """

    def __init__(self):
        self._shader_handle = None
        self._vert_handle = None
        self._fragment_handle = None

        self._attrib_location_tex = None
        self._attrib_proj_mtx = None
        self._attrib_location_position = None
        self._attrib_location_uv = None
        self._attrib_location_color = None

        self._vbo_handle = None
        self._elements_handle = None
        self._vao_handle = None

        super().__init__()

    def refresh_font_texture(self):
        # save texture state

        buf = gl.Buffer(gl.GL_INT, 1)
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, buf)
        last_texture = buf[0]

        width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
        if self._font_texture is not None:
            gl.glDeleteTextures([self._font_texture])

        gl.glGenTextures(1, buf)
        self._font_texture = buf[0]

        gl.glBindTexture(gl.GL_TEXTURE_2D, self._font_texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

        pixel_buffer = gl.Buffer(gl.GL_BYTE, [4 * width * height])
        pixel_buffer[:] = pixels  # 非常慢
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixel_buffer)

        self.io.fonts.texture_id = self._font_texture
        gl.glBindTexture(gl.GL_TEXTURE_2D, last_texture)
        self.io.fonts.clear_tex_data()

    def _create_device_objects(self):
        self._bl_shader = gpu.types.GPUShader(self.VERTEX_SHADER_SRC, self.FRAGMENT_SHADER_SRC)

    def render(self, draw_data):
        io = self.io
        shader = self._bl_shader

        display_width, display_height = io.display_size
        fb_width = int(display_width * io.display_fb_scale[0])
        fb_height = int(display_height * io.display_fb_scale[1])

        if fb_width == 0 or fb_height == 0:
            return

        draw_data.scale_clip_rects(*io.display_fb_scale)

        # backup GL state
        (
            last_program,
            last_texture,
            last_active_texture,
            last_array_buffer,
            last_element_array_buffer,
            last_vertex_array,
            last_blend_src,
            last_blend_dst,
            last_blend_equation_rgb,
            last_blend_equation_alpha,
            last_viewport,
            last_scissor_box,
        ) = self._backup_integers(
            gl.GL_CURRENT_PROGRAM, 1,
            gl.GL_TEXTURE_BINDING_2D, 1,
            gl.GL_ACTIVE_TEXTURE, 1,
            gl.GL_ARRAY_BUFFER_BINDING, 1,
            gl.GL_ELEMENT_ARRAY_BUFFER_BINDING, 1,
            gl.GL_VERTEX_ARRAY_BINDING, 1,
            gl.GL_BLEND_SRC, 1,
            gl.GL_BLEND_DST, 1,
            gl.GL_BLEND_EQUATION_RGB, 1,
            gl.GL_BLEND_EQUATION_ALPHA, 1,
            gl.GL_VIEWPORT, 4,
            gl.GL_SCISSOR_BOX, 4,
        )

        last_enable_blend = gl.glIsEnabled(gl.GL_BLEND)
        last_enable_cull_face = gl.glIsEnabled(gl.GL_CULL_FACE)
        last_enable_depth_test = gl.glIsEnabled(gl.GL_DEPTH_TEST)
        last_enable_scissor_test = gl.glIsEnabled(gl.GL_SCISSOR_TEST)

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendEquation(gl.GL_FUNC_ADD)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(gl.GL_CULL_FACE)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glActiveTexture(gl.GL_TEXTURE0)

        gl.glViewport(0, 0, int(fb_width), int(fb_height))

        ortho_projection = (
            2.0 / display_width, 0.0, 0.0, 0.0,
            0.0, 2.0 / -display_height, 0.0, 0.0,
            0.0, 0.0, -1.0, 0.0,
            -1.0, 1.0, 0.0, 1.0
        )
        shader.bind()
        shader.uniform_float("ProjMtx", ortho_projection)
        shader.uniform_int("Texture", 0)

        for commands in draw_data.commands_lists:
            size = commands.idx_buffer_size * imgui.INDEX_SIZE // 4
            address = commands.idx_buffer_data
            ptr = ctypes.cast(address, ctypes.POINTER(ctypes.c_int))
            idx_buffer_np = np.ctypeslib.as_array(ptr, shape=(size,))

            size = commands.vtx_buffer_size * imgui.VERTEX_SIZE // 4
            address = commands.vtx_buffer_data
            ptr = ctypes.cast(address, ctypes.POINTER(ctypes.c_float))
            vtx_buffer_np = np.ctypeslib.as_array(ptr, shape=(size,))
            vtx_buffer_shaped = vtx_buffer_np.reshape(-1, imgui.VERTEX_SIZE // 4)

            idx_buffer_offset = 0
            for command in commands.commands:
                x, y, z, w = command.clip_rect
                gl.glScissor(int(x), int(fb_height - w), int(z - x), int(w - y))

                vertices = vtx_buffer_shaped[:, :2]
                uvs = vtx_buffer_shaped[:, 2:4]
                colors = vtx_buffer_shaped.view(np.uint8)[:, 4 * 4:]
                colors = colors.astype('f') / 255.0

                indices = idx_buffer_np[idx_buffer_offset:idx_buffer_offset + command.elem_count]

                gl.glBindTexture(gl.GL_TEXTURE_2D, command.texture_id)

                batch = batch_for_shader(shader, 'TRIS', {
                    "Position": vertices,
                    "UV": uvs,
                    "Color": colors,
                }, indices=indices)
                batch.draw(shader)

                idx_buffer_offset += command.elem_count

        # restore modified GL state
        gl.glUseProgram(last_program)
        gl.glActiveTexture(last_active_texture)
        gl.glBindTexture(gl.GL_TEXTURE_2D, last_texture)
        gl.glBindVertexArray(last_vertex_array)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, last_array_buffer)
        gl.glBindBuffer(gl.GL_ELEMENT_ARRAY_BUFFER, last_element_array_buffer)
        gl.glBlendEquationSeparate(last_blend_equation_rgb, last_blend_equation_alpha)
        gl.glBlendFunc(last_blend_src, last_blend_dst)

        if last_enable_blend:
            gl.glEnable(gl.GL_BLEND)
        else:
            gl.glDisable(gl.GL_BLEND)

        if last_enable_cull_face:
            gl.glEnable(gl.GL_CULL_FACE)
        else:
            gl.glDisable(gl.GL_CULL_FACE)

        if last_enable_depth_test:
            gl.glEnable(gl.GL_DEPTH_TEST)
        else:
            gl.glDisable(gl.GL_DEPTH_TEST)

        if last_enable_scissor_test:
            gl.glEnable(gl.GL_SCISSOR_TEST)
        else:
            gl.glDisable(gl.GL_SCISSOR_TEST)

        gl.glViewport(last_viewport[0], last_viewport[1], last_viewport[2], last_viewport[3])
        gl.glScissor(last_scissor_box[0], last_scissor_box[1], last_scissor_box[2], last_scissor_box[3])

    def _invalidate_device_objects(self):
        if self._font_texture > -1:
            gl.glDeleteTextures([self._font_texture])
        self.io.fonts.texture_id = 0
        self._font_texture = 0

    def _backup_integers(self, *keys_and_lengths):
        """Helper to back up opengl state"""
        keys = keys_and_lengths[::2]
        lengths = keys_and_lengths[1::2]
        buf = gl.Buffer(gl.GL_INT, max(lengths))
        values = []
        for k, n in zip(keys, lengths):
            gl.glGetIntegerv(k, buf)
            values.append(buf[0] if n == 1 else buf[:n])
        return values

# -------------------------------------------------------------------


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
        x = context.region.x
        in_area = x < self.mpos[0] < x + w and 0 < self.mpos[1] < h
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
        x = context.region.x
        in_area = x < self.mpos[0] < x + w and 0 < self.mpos[1] < h
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
