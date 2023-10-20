import gpu
import ctypes
import numpy as np
import bgl as gl
import bpy
import time
import platform
# from OpenGL import GL as gl
from gpu_extras.batch import batch_for_shader
from ..utils import logger
try:
    import imgui
except ModuleNotFoundError:
    print("ERROR: imgui was not found")


from imgui.integrations.base import BaseOpenGLRenderer
from .old_renderer import Renderer340


class Renderer(BaseOpenGLRenderer):
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
    instance = None

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
        Renderer.instance = self

        super().__init__()

    def refresh_font_texture(self):
        self.refresh_font_texture_ex(self)
        if self.refresh_font_texture_ex not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(self.refresh_font_texture_ex)

    @staticmethod
    @bpy.app.handlers.persistent
    def refresh_font_texture_ex(scene=None):
        # save texture state
        self = Renderer.instance
        if not (img := bpy.data.images.get(".imgui_font", None)) or img.bindcode == 0:
            ts = time.time()
            width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
            if not img:
                img = bpy.data.images.new(".imgui_font", width, height, alpha=True, float_buffer=True)
            pixels = np.frombuffer(pixels, dtype=np.uint8) / np.float32(256)
            img.pixels.foreach_set(pixels)
            self.io.fonts.clear_tex_data()
            logger.debug(f"MLT Init -> {time.time() - ts:.2f}s")
        img.gl_load()
        self._font_texture = img.bindcode
        self.io.fonts.texture_id = self._font_texture
        #  a_BlenderAI_Node.MultiLineText.renderer.Renderer.instance._font_texture
        #  a_BlenderAI_Node.MultiLineText.renderer.Renderer.instance.io.fonts.texture_id

    def refresh_font_texture_opgngl(self):

        last_texture = gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)

        width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
        if self._font_texture is not None:
            gl.glDeleteTextures([self._font_texture])

        buf = gl.glGenTextures(1)
        self._font_texture = buf

        gl.glBindTexture(gl.GL_TEXTURE_2D, self._font_texture)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

        # pixel_buffer = gl.Buffer(gl.GL_BYTE, [4 * width * height])
        # pixel_buffer[:] = pixels  # 非常慢
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, width, height, 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, pixels)
        # logger.error(self._font_texture)
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
        self.refresh_font_texture_ex()
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
                # logger.error(command.texture_id)
                gl.glBindTexture(gl.GL_TEXTURE_2D, command.texture_id)
                # print(dir(command))
                batch = batch_for_shader(shader, 'TRIS', {
                    "Position": vertices,
                    "UV": uvs,
                    "Color": colors,
                }, indices=indices)
                batch.draw(shader)

                idx_buffer_offset += command.elem_count

        # restore modified GL state 以下代码貌似影响不大
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

        # buf = gl.Buffer(gl.GL_INT, max(lengths))
        # values = []
        # for k, n in zip(keys, lengths):
        #     buf = gl.glGetIntegerv(k)
        #     values.append(buf)
        # return values

        buf = gl.Buffer(gl.GL_INT, max(lengths))
        values = []
        for k, n in zip(keys, lengths):
            gl.glGetIntegerv(k, buf)
            values.append(buf[0] if n == 1 else buf[:n])
        return values


class Renderer400(BaseOpenGLRenderer):
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
    instance = None

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
        self._font_tex = None
        Renderer.instance = self

        super().__init__()

    def refresh_font_texture(self):
        self.refresh_font_texture_ex(self)
        if self.refresh_font_texture_ex not in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.append(self.refresh_font_texture_ex)

    @staticmethod
    @bpy.app.handlers.persistent
    def refresh_font_texture_ex(scene=None):
        # save texture state
        self = Renderer.instance
        if not (img := bpy.data.images.get(".imgui_font", None)) \
            or (platform.platform == "win32" and img.bindcode == 0):
            ts = time.time()
            width, height, pixels = self.io.fonts.get_tex_data_as_rgba32()
            if not img:
                img = bpy.data.images.new(".imgui_font", width, height, alpha=True, float_buffer=True)
            pixels = np.frombuffer(pixels, dtype=np.uint8) / np.float32(256)
            img.pixels.foreach_set(pixels)
            self.io.fonts.clear_tex_data()
            logger.debug(f"MLT Init -> {time.time() - ts:.2f}s")
        img.gl_load()
        self._font_tex = gpu.texture.from_image(img)
        self._font_texture = img.bindcode
        self.io.fonts.texture_id = self._font_texture

    def _create_device_objects(self):
        # self._bl_shader = gpu.types.GPUShader(self.VERTEX_SHADER_SRC, self.FRAGMENT_SHADER_SRC)
        vert_out = gpu.types.GPUStageInterfaceInfo("imgui_interface")
        vert_out.smooth('VEC2', "Frag_UV")
        vert_out.smooth('VEC4', "Frag_Color")

        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "ProjMtx")
        shader_info.sampler(0, 'FLOAT_2D', "Texture")
        shader_info.vertex_in(0, 'VEC2', "Position")
        shader_info.vertex_in(1, 'VEC2', "UV")
        shader_info.vertex_in(2, 'VEC4', "Color")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "Out_Color")

        shader_info.vertex_source("""
        void main() {
            Frag_UV = UV;
            Frag_Color = Color;
            gl_Position = ProjMtx * vec4(Position.xy, 0, 1);
        }
        """
        )

        shader_info.fragment_source("""
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
            Out_Color.rgba = srgb_to_linear(Out_Color.rgba)*1.25;
        }
                                    """
        )

        self._bl_shader = gpu.shader.create_from_info(shader_info)

    def render(self, draw_data):
        io = self.io
        shader = self._bl_shader

        display_width, display_height = io.display_size
        fb_width = int(display_width * io.display_fb_scale[0])
        fb_height = int(display_height * io.display_fb_scale[1])

        if fb_width == 0 or fb_height == 0:
            return

        draw_data.scale_clip_rects(*io.display_fb_scale)

        # last_enable_blend = gl.glIsEnabled(gl.GL_BLEND)
        # last_enable_cull_face = gl.glIsEnabled(gl.GL_CULL_FACE)
        # last_enable_depth_test = gl.glIsEnabled(gl.GL_DEPTH_TEST)
        # last_enable_scissor_test = gl.glIsEnabled(gl.GL_SCISSOR_TEST)

        # gl.glEnable(gl.GL_BLEND)
        # gl.glBlendEquation(gl.GL_FUNC_ADD)
        # gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        # gl.glDisable(gl.GL_CULL_FACE)
        # gl.glDisable(gl.GL_DEPTH_TEST)
        # gl.glEnable(gl.GL_SCISSOR_TEST)
        # gl.glActiveTexture(gl.GL_TEXTURE0)

        # gl.glViewport(0, 0, int(fb_width), int(fb_height))

        ortho_projection = (
            2.0 / display_width, 0.0, 0.0, 0.0,
            0.0, 2.0 / -display_height, 0.0, 0.0,
            0.0, 0.0, -1.0, 0.0,
            -1.0, 1.0, 0.0, 1.0
        )
        self.refresh_font_texture_ex()
        shader.bind()
        shader.uniform_float("ProjMtx", ortho_projection)
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_mask_set(False)
        gpu.state.depth_test_set("NONE")
        gpu.state.face_culling_set("NONE")
        gpu.state.scissor_test_set(True)
        gpu.state.point_size_set(5.0)
        gpu.state.program_point_size_set(False)
        shader.uniform_sampler("Texture", self._font_tex)
        gpu.state.viewport_set(0, 0, int(fb_width), int(fb_height))
        # shader.uniform_int("Texture", 0)
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
                # x, y, z, w = command.clip_rect
                # gl.glScissor(int(x), int(fb_height - w), int(z - x), int(w - y))

                vertices = vtx_buffer_shaped[:, :2]
                uvs = vtx_buffer_shaped[:, 2:4]
                colors = vtx_buffer_shaped.view(np.uint8)[:, 4 * 4:]
                colors = colors.astype('f') / 255.0

                indices = idx_buffer_np[idx_buffer_offset:idx_buffer_offset + command.elem_count]
                # logger.error(command.texture_id)
                # shader.uniform_sampler("Texture", self._font_tex)
                # gl.glBindTexture(gl.GL_TEXTURE_2D, command.texture_id)

                # print(dir(command))
                batch = batch_for_shader(shader, 'TRIS', {
                    "Position": vertices,
                    "UV": uvs,
                    "Color": colors,
                }, indices=indices)
                batch.draw(shader)

                idx_buffer_offset += command.elem_count

    def _invalidate_device_objects(self):
        if self._font_texture > -1:
            gl.glDeleteTextures([self._font_texture])
        self.io.fonts.texture_id = 0
        self._font_texture = 0


BlenderImguiRenderer = Renderer400
if bpy.app.version < (3, 4):
    BlenderImguiRenderer = Renderer340
if bpy.app.version < (4, 0):
    BlenderImguiRenderer = Renderer
