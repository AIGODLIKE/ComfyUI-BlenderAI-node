import bpy
import gpu
import numpy as np
from .texture import TexturePool
from .app.renderer import imgui


class CustomWidgets:
    @staticmethod
    def make_texture_bpy():
        size = 128
        x = np.linspace(-1, 1, size)
        y = np.linspace(-1, 1, size)
        x, y = np.meshgrid(x, y)
        radius = np.sqrt(x**2 + y**2)
        image = np.sin(radius * 5 * np.pi)
        image = (image * 0.5 + 0.5) * 255
        image = np.stack((image, image, image, image), axis=-1)
        image[:, :, 3] = 255
        image = image.astype(np.uint8)
        image = np.clip(image, 0, 255)
        image = np.array(image, dtype=np.uint8) / np.float32(255)
        texture = bpy.data.images.new("Test Texture", size, size, alpha=True, float_buffer=True)
        texture.pixels.foreach_set(image.ravel())
        gpu_tex = gpu.texture.from_image(texture)
        gpu_tex_id = TexturePool.push_tex(gpu_tex)
        return {"id": gpu_tex_id}

    @staticmethod
    def render_shapes(tex_id: int):
        px, py = imgui.get_cursor_screen_pos()
        dl = imgui.get_window_draw_list()
        color = imgui.color_convert_float4_to_u32((0.5, 0.1, 0.5, 1.0))
        color2 = imgui.color_convert_float4_to_u32((0.5, 0.6, 0.5, 1.0))
        color3 = imgui.color_convert_float4_to_u32((0.2, 0.4, 0.8, 1))
        dl.add_line((px + 10, py + 10), (px + 50, py + 50), color, 1)
        dl.add_rect((px + 60, py + 10), (px + 100, py + 50), color, rounding=5)
        dl.add_quad_filled((px + 110, py + 10), (px + 150, py + 10), (px + 150, py + 50), (px + 110, py + 50), color2)
        dl.add_ellipse_filled((px + 180, py + 30), (20, 10), color2, num_segments=9, rot=imgui.get_time() * 0.5)
        dl.add_triangle_filled((px + 200, py + 10), (px + 240, py + 10), (px + 220, py + 50), color)
        dl.add_text((px + 250, py + 17), color, "hello")
        dl.add_bezier_quadratic((px + 300, py + 15), (px + 340, py + 15), (px + 340, py + 40), color3, thickness=2)
        dl.add_polyline([(px + 350, py + 10), (px + 370, py + 10), (px + 370, py + 50), (px + 350, py + 50)], color3, flags=imgui.DrawFlags.CLOSED, thickness=2)
        arr = np.array([(px + 350, py + 10), (px + 370, py + 10), (px + 370, py + 50), (px + 350, py + 50)], dtype=np.float32)
        dl.add_polyline(arr + np.array([25, 0], dtype=np.float32), color3, flags=imgui.DrawFlags.CLOSED, thickness=2)

        vertices = np.array([[1, 1], [4, 1], [5, 4], [2, 5], [1, 3]], dtype=np.float32)
        vertices = vertices * 10
        vertices[:, 0] += px
        vertices[:, 1] += py + 50
        dl.add_convex_poly_filled(list(vertices), color2)

        vertices = np.array([[3, 3], [4, 1], [5, 4], [2, 5], [1, 3]], dtype=np.float32)
        vertices = vertices * 10
        vertices[:, 0] += px + 50
        vertices[:, 1] += py + 50
        dl.add_concave_poly_filled(vertices.astype(np.int32), color2)  # cast to int, that should work too
        vertices[:, 0] += 50
        dl.add_concave_poly_filled(list(vertices), color)

        xx = px + 10
        yy = py + 100
        dl.add_image(tex_id, (xx, yy), (xx + 128, yy + 128), col=0xFF70FF30)

        xx += 130
        dl.add_image_rounded(tex_id, (xx, yy), (xx + 128, yy + 128), (0, 0), (1, 1), 0xFFFFFFFF, rounding=10)

    @staticmethod
    def icon_button(label: str, size: tuple[float, float] = (0.0, 0.0), icon="none", icon_size: tuple[float, float] = (0, 0), off: tuple[float, float] = (0, 0)):
        """图标按钮"""
        imgui.begin_group()
        clicked = imgui.button(label, size)
        imgui.same_line()
        pos = imgui.get_cursor_pos()
        imgui.set_cursor_pos((pos[0] + off[0], pos[1] + off[1]))
        tex_id = TexturePool.get_tex_id(icon)
        imgui.image(tex_id, icon_size)
        imgui.end_group()
        return clicked

    @staticmethod
    def clip_image(icon1, icon2, icon_size=(32, 32)):
        """裁剪图标"""
        imgui.begin_group()
        pos = imgui.get_cursor_pos()

        imgui.image(TexturePool.get_tex_id(icon1), icon_size)
        imgui.same_line()
        imgui.set_cursor_pos((pos[0], pos[1]))

        # 判断鼠标在否在图标上才开启裁剪
        enable_clip = imgui.is_item_hovered()
        if enable_clip:
            mouse_pos = imgui.get_mouse_pos()
            imgui.push_clip_rect((mouse_pos[0], pos[1]), (mouse_pos[0] + icon_size[1] * 2, mouse_pos[1] + icon_size[1] * 2), True)

        imgui.image(TexturePool.get_tex_id(icon2), icon_size)

        if enable_clip:
            imgui.pop_clip_rect()

        imgui.end_group()
