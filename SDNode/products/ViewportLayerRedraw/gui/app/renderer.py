import gpu
import ctypes
import numpy as np
import bpy
import time
from pathlib import Path
from mathutils import Matrix
from gpu_extras.batch import batch_for_shader
from ..texture import TexturePool
from ......kclogger import logger

try:
    from slimgui import imgui
    # import imgui
except ModuleNotFoundError:
    print("ERROR: imgui was not found")

RESOURCE_PATH = Path(__file__).parent.parent / "assets"


class FontManager:
    _DEFAULT_FONT_PATH = RESOURCE_PATH / "font/bmonofont-i18n.ttf"
    _DEFAULT_FONT_PATH = RESOURCE_PATH / "font/Alibaba-PuHuiTi-Regular.ttf"
    HEAVY_FONT = RESOURCE_PATH / "font/MiSans-Heavy.ttf"
    BOLD_FONT = RESOURCE_PATH / "font/MiSans-Bold.ttf"
    MEDIUM_FONT = RESOURCE_PATH / "font/MiSans-Medium.ttf"

    def __init__(self, io: imgui.IO, ctx: imgui.Context) -> None:
        self.io = io
        self.ctx = ctx
        self.scale = 24
        self.heavy_font: imgui.Font | None = None
        self.bold_font: imgui.Font | None = None
        self.medium_font: imgui.Font | None = None

    @property
    def font_scale(self):
        return 1.25

    def load_font_default(self):
        self.heavy_font = self.load_font_from_file(self.HEAVY_FONT, self.scale)
        self.bold_font = self.load_font_from_file(self.BOLD_FONT, self.scale)
        self.medium_font = self.load_font_from_file(self.MEDIUM_FONT, self.scale)

    def load_font_from_file(self, fp: Path = None, scale: float = 40):
        ts = time.time()
        font = self.io.fonts.add_font_from_memory_ttf(fp.read_bytes(), scale)
        logger.debug(f"Font Init -> {time.time() - ts:.2f}s")
        return font

    # 30px 粗体 1级标题
    def push_h1_font(self, size_base=30):
        imgui.push_font(self.heavy_font, size_base * self.font_scale)

    # 30px 中等 1级标题
    def push_h2_font(self, size_base=30):
        imgui.push_font(self.medium_font, size_base * self.font_scale)

    # 24px 中等 3级标题
    def push_h3_font(self, size_base=24):
        imgui.push_font(self.medium_font, size_base * self.font_scale)

    # 20px 中等 4级标题
    def push_h4_font(self, size_base=20):
        imgui.push_font(self.medium_font, size_base * self.font_scale)

    # 20px 中等 5级标题
    def push_h5_font(self, size_base=18):
        imgui.push_font(self.medium_font, size_base * self.font_scale)

    # 16px 中等 正文
    def push_content_font(self, size_base=24):
        imgui.push_font(self.medium_font, size_base * self.font_scale)

    def pop_font(self, n=1):
        for _ in range(n):
            imgui.pop_font()

    def destroy(self):
        pass


class Renderer:
    def __init__(self):
        self._ctx = imgui.create_context()
        self.io = imgui.get_io()
        self.io.delta_time = 1.0 / 60.0
        self.io.backend_flags |= imgui.BackendFlags.RENDERER_HAS_VTX_OFFSET
        self.io.backend_flags |= imgui.BackendFlags.RENDERER_HAS_TEXTURES
        self.io.backend_flags |= imgui.BackendFlags.HAS_MOUSE_CURSORS
        self.font_manager = FontManager(self.io, self._ctx)
        self.font_manager.load_font_default()

        self.prepare_shader()
        self.M = Matrix.Identity(4)
        self.V = Matrix.Identity(4)
        self.P = Matrix.Identity(4)
        logger.debug("Renderer initialized")

    def prepare_shader(self):
        logger.debug("Preparing shader")
        # self._bl_shader = gpu.types.GPUShader(self.VERTEX_SHADER_SRC, self.FRAGMENT_SHADER_SRC)
        vert_out = gpu.types.GPUStageInterfaceInfo("sdn_imgui_interface")
        vert_out.smooth("VEC2", "FragUV")
        vert_out.smooth("VEC4", "InColor")
        vert_out.smooth("VEC2", "VertPos")

        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant("MAT4", "ModelViewProjectionMatrix")
        shader_info.push_constant("VEC4", "ClipRect")
        shader_info.sampler(0, "FLOAT_2D", "Texture")
        shader_info.vertex_in(0, "VEC2", "Position")
        shader_info.vertex_in(1, "VEC2", "UV")
        shader_info.vertex_in(2, "VEC4", "Color")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, "VEC4", "FragColor")

        shader_info.vertex_source("""
        void main() {
            FragUV = UV;
            InColor = Color;
            VertPos = Position;
            gl_Position = ModelViewProjectionMatrix * vec4(Position.xy, 0, 1);
        }
        """)

        shader_info.fragment_source("""
        bool ShouldClip(vec2 pos, vec4 rect) {
            return pos.x < rect.x || pos.x > rect.z || pos.y < rect.y || pos.y > rect.w;
        }
        
        vec3 LinearToSrgb(vec3 linear) {
            return pow(linear, 1.0 / 2.2);
        }
        
        vec3 SrgbToLinear(vec3 srgb) {
            return pow(srgb, 2.2);
        }
        
        void main() {
            if (ShouldClip(VertPos, ClipRect)) discard; // 如果超出裁剪区域，则不渲染
            FragColor = InColor * texture(Texture, FragUV);
            FragColor = vec4(SrgbToLinear(FragColor.rgb), FragColor.a);
        }
        """)

        self._bl_shader: gpu.types.GPUShader = gpu.shader.create_from_info(shader_info)

    @staticmethod
    def test_write_buf_to_image():
        w = 100
        h = 100
        pixels = np.random.randint(0, 255, (w, h, 4), dtype=np.uint8)
        gpu_buf = gpu.types.Buffer("FLOAT", (w, h, 4), pixels)
        gpu_tex = gpu.types.GPUTexture(gpu_buf.dimensions[:2], format="RGBA8", data=gpu_buf)
        img_name = f"111_{id(gpu_tex)}"
        img = bpy.data.images.new(img_name, w, h, alpha=True)
        img.pixels.foreach_set(pixels.ravel())
        # img_name = f"000_{id(tex)}"
        # img = bpy.data.images.new(img_name, tex.width, tex.height, alpha=True)
        # img.pixels.foreach_set(pixels)

    def ensure_ctx(self):
        if not self._ctx:
            return
        imgui.set_current_context(self._ctx)

    def begin(self):
        self.font_manager.push_content_font()

    def end(self):
        self.font_manager.pop_font()

    def set_mvp_matrix(self, m, v, p):
        self.M = m
        self.V = v
        self.P = p

    def _update_texture(self, tex: imgui.TextureData):
        # OK / DESTROYED / WANT_CREATE / WANT_UPDATES / WANT_DESTROY
        if tex.status == imgui.TextureStatus.WANT_CREATE:
            pixels = np.frombuffer(tex.get_pixels(), dtype=np.uint8) / np.float32(255)
            gpu_buf = gpu.types.Buffer("FLOAT", (tex.width, tex.height, 4), pixels)
            gpu_tex = gpu.types.GPUTexture(gpu_buf.dimensions[:2], data=gpu_buf)
            tex_id = TexturePool.push_tex(gpu_tex)
            tex.set_tex_id(tex_id)
            tex.set_status(imgui.TextureStatus.OK)
        elif tex.status == imgui.TextureStatus.WANT_UPDATES:
            TexturePool.pop_tex(tex.get_tex_id())
            pixels = np.frombuffer(tex.get_pixels(), dtype=np.uint8) / np.float32(255)
            gpu_buf = gpu.types.Buffer("FLOAT", (tex.width, tex.height, 4), pixels)
            gpu_tex = gpu.types.GPUTexture(gpu_buf.dimensions[:2], data=gpu_buf)
            tex_id = TexturePool.push_tex(gpu_tex)
            tex.set_tex_id(tex_id)
            tex.set_status(imgui.TextureStatus.OK)
        elif tex.status == imgui.TextureStatus.WANT_DESTROY and tex.unused_frames > 0:
            self._destroy_texture(tex)

    def _destroy_texture(self, tex: imgui.TextureData):
        TexturePool.pop_tex(tex.get_tex_id())
        tex.set_tex_id(0)
        tex.set_status(imgui.TextureStatus.DESTROYED)

    def debug_clip_rect(self, draw_data: imgui.DrawData):
        # io = self.io
        # fb_scale = draw_data.framebuffer_scale
        # dfb_scale = io.display_framebuffer_scale
        # print((fb_scale[0] / dfb_scale[0], fb_scale[1] / dfb_scale[1]))
        # draw_data.scale_clip_rects((fb_scale[0] / dfb_scale[0], fb_scale[1] / dfb_scale[1]))

        dl = imgui.get_foreground_draw_list()
        for cmds in draw_data.commands_lists:
            for cmd in cmds.commands:
                x1, y1, x2, y2 = cmd.clip_rect
                y2 = y1 + (y2 - y1) * 0.5
                x2 = x1 + (x2 - x1) * 0.5
                col = imgui.get_color_u32((0, 1, 0, 1))
                dl.add_rect((x1, y1), (x2, y2), col, thickness=2)

    def render(self, draw_data: imgui.DrawData):
        # self.debug_clip_rect(draw_data)

        io = self.io
        shader = self._bl_shader

        display_width, display_height = io.display_size
        fb_scale = draw_data.framebuffer_scale
        fb_width = int(display_width * fb_scale[0])
        fb_height = int(display_height * fb_scale[1])

        if fb_width == 0 or fb_height == 0:
            return

        if draw_data.textures is not None:
            for tex_data in draw_data.textures:
                self._update_texture(tex_data)

        # draw_data.scale_clip_rects((fb_scale[0] / dfb_scale[0], fb_scale[1] / dfb_scale[1]))
        gpu.matrix.push()
        # 模型矩阵需要变换到屏幕坐标
        old_vm = gpu.matrix.get_model_view_matrix()
        old_pm = gpu.matrix.get_projection_matrix()
        gpu.matrix.load_matrix(self.V @ self.M)
        gpu.matrix.load_projection_matrix(self.P)
        shader.bind()
        # shader.uniform_float("ModelViewProjectionMatrix", _proj_matrix)
        gpu.state.blend_set("ALPHA")
        gpu.state.depth_mask_set(False)
        gpu.state.face_culling_set("NONE")
        gpu.state.depth_test_set("NONE")
        gpu.state.scissor_test_set(True)
        gpu.state.point_size_set(5.0)
        gpu.state.program_point_size_set(False)
        """
        // idx_buffer_data : Vector<ImDrawIdx>
        typedef unsigned short ImDrawIdx; // 16-bit index size

        // vtx_buffer_data : Vector<ImDrawVert>
        struct ImDrawVert
        {
            ImVec2  pos; // float[2] 64bit 8
            ImVec2  uv;  // float[2] 64bit 8
            ImU32   col; //   uint32 32bit 4
        };
        """
        idx_ele_size = imgui.INDEX_SIZE
        vtx_ele_size = imgui.VERTEX_SIZE // 4
        for cmds in draw_data.commands_lists:
            idx_size = cmds.idx_buffer_size * idx_ele_size
            idx_ptr = ctypes.cast(cmds.idx_buffer_data, ctypes.POINTER(ctypes.c_ushort))
            idx_buf = np.ctypeslib.as_array(idx_ptr, shape=(idx_size,))

            vtx_size = cmds.vtx_buffer_size * vtx_ele_size
            vtx_ptr = ctypes.cast(cmds.vtx_buffer_data, ctypes.POINTER(ctypes.c_float))
            vtx_buf = np.ctypeslib.as_array(vtx_ptr, shape=(vtx_size,))
            vtx_buf = vtx_buf.reshape(-1, vtx_ele_size)

            # Decompose geo data
            vertices = vtx_buf[:, :2]
            uvs = vtx_buf[:, 2:4]
            colors = vtx_buf[:, 4:]
            colors = colors.view(np.uint8) / np.float32(255.0)

            for cmd in cmds.commands:
                tex_id = cmd.tex_ref.get_tex_id()
                tex = TexturePool.get_tex(tex_id)
                if not tex:
                    continue
                shader.uniform_sampler("Texture", tex)
                x1, y1, x2, y2 = cmd.clip_rect
                # x2 = x1 + (x2 - x1) * 0.5
                # y2 = y1 + (y2 - y1) * 0.5
                shader.uniform_float("ClipRect", (x1, y1, x2, y2))

                indices = idx_buf[cmd.idx_offset : cmd.idx_offset + cmd.elem_count].astype(np.int32)

                content = {
                    "Position": vertices,
                    "UV": uvs,
                    "Color": colors,
                }

                batch = batch_for_shader(shader, "TRIS", content, indices=indices)
                batch.draw(shader)
        gpu.matrix.pop()
        gpu.matrix.load_matrix(old_vm)
        gpu.matrix.load_projection_matrix(old_pm)

    def shutdown(self):
        # Destroy all textures
        for tex in imgui.get_platform_io().textures:
            if tex.ref_count != 1:
                continue
            self._destroy_texture(tex)
        self.font_manager.destroy()
        imgui.destroy_context(self._ctx)
        self._ctx = None
