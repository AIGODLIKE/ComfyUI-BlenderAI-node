import OpenImageIO as oiio
import bpy
import numpy as np
from OpenImageIO import ImageBuf, ImageSpec
from mathutils import Vector, Matrix


def linear_to_srgb(c_linear):
    # 对每个颜色分量进行伽马校正
    c_srgb = np.where(c_linear <= 0.0031308, 12.92 * c_linear, 1.055 * (c_linear ** (1 / 2.4)) - 0.055)
    return c_srgb  # 假设image是一个linear RGB图像


def srgb_to_linear(c_srgb):
    # 对每个颜色分量进行逆伽马校正
    c_linear = np.where(c_srgb <= 0.04045, c_srgb / 12.92, ((c_srgb + 0.055) / 1.055) ** 2.4)
    return c_linear


def scale_to_matrix(scale: Vector) -> Matrix:
    matrix = Matrix()
    for i in range(3):
        matrix[i][i] = scale[i]
    return matrix


def get_image(obj: "bpy.types.Object"):
    """
    获取当前图片的数据
    [(bpy.types.Material, bpy.types.Node, bpy.types.Image), ]
    """
    image_list = []
    for mat in obj.data.materials:
        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.image:
                image_list.append((mat, node, node.image))
    return image_list


def blender_image_to_image_buf_with_numpy(image: bpy.types.Image) -> ImageBuf:
    width, height = image.size
    channels = image.channels

    # 将像素数据转换为numpy数组
    pixels_np = np.array(image.pixels, dtype=np.float32)
    pixels_reshaped = srgb_to_linear(pixels_np).reshape(height, width, channels)

    # 创建OpenImageIO ImageBuf
    spec = ImageSpec(width, height, channels, 'float')
    image_buf = ImageBuf(spec)

    # 使用set_pixels批量设置像素
    image_buf.set_pixels(oiio.ROI(), pixels_reshaped)

    return image_buf


def resize_move_crop_image_buf(
        image_buf: ImageBuf,
        scale_factor: tuple | float,
        position="center",
        crop=None,
        background=None,
):
    """
    缩放图像像素但保持画布尺寸不变，可控制位置

    参数:
        input_path: 输入图像路径
        output_path: 输出图像路径
        scale_factor: 缩放因子
        position: 位置，可以是 "center", "top-left", "top-right", "bottom-left", "bottom-right"
                  或自定义偏移量 (x, y)
        background: 背景色
    """

    # 读取原始图像
    spec = image_buf.spec()

    if crop is None:
        crop = Vector((0, 0, spec.height, spec.width))

    if spec.nchannels < 4:
        # 创建新的图像规格，增加Alpha通道
        new_spec = oiio.ImageSpec(spec.width, spec.height, 4, spec.format)

        # 创建新的ImageBuf，并设置所有像素为完全透明
        buf_with_alpha = oiio.ImageBuf(new_spec)
        oiio.ImageBufAlgo.fill(buf_with_alpha, [1, 1, 0, 1])  # R,G,B,A 全为0

        # 将原始图像的RGB通道复制到新图像的前三个通道
        # 这里使用'copy'操作将原图的RGB通道复制到新图的前三个通道
        oiio.ImageBufAlgo.copy(buf_with_alpha, image_buf, roi=oiio.ROI(0, spec.width, 0, spec.height, 0, 1, 0, 3))
        image_buf = buf_with_alpha
        spec = image_buf.spec()

    w, h = spec.width, spec.height
    # 计算缩放后的图像尺寸
    if isinstance(scale_factor, tuple):
        sx, sy = scale_factor[:]
    else:
        sx = sy = scale_factor
    scale_width = int(w * sx)
    scale_height = int(h * sy)

    # 创建缩放后的图像
    resized_buf = oiio.ImageBuf(oiio.ImageSpec(scale_width, scale_height, 4, spec.format))
    success_resize = oiio.ImageBufAlgo.resize(resized_buf, image_buf)

    if not success_resize:
        print("缩放错误:", resized_buf.geterror())
        return None
    # 创建与原始图像相同尺寸的画布
    canvas_buf = oiio.ImageBuf(spec)

    # 设置背景色
    if background is not None:
        oiio.ImageBufAlgo.fill(canvas_buf, background)
    # 计算位置
    if position == "center":
        xoffset = (w - scale_width) // 2
        yoffset = (h - scale_height) // 2
    elif position == "top-left":
        xoffset = 0
        yoffset = h - scale_height
    elif position == "top-right":
        xoffset = w - scale_width
        yoffset = h - scale_height
    elif position == "bottom-left":
        xoffset = 0
        yoffset = 0
    elif position == "bottom-right":
        xoffset = w - scale_width
        yoffset = 0
    else:  # 自定义位置
        xoffset, yoffset = position

    # # 确保位置在合理范围内
    # xoffset = max(0, min(xoffset, w - 1))
    # yoffset = max(0, min(yoffset, h - 1))

    # 将缩放后的图像粘贴到画布上 - 使用正确的参数
    success = oiio.ImageBufAlgo.paste(
        canvas_buf,
        xoffset, yoffset, 0, 0,  # 目标位置: xbegin, ybegin, zbegin, chbegin
        resized_buf,  # 源图像
        roi=oiio.ROI(0, scale_width, 0, scale_height, 0, 1, 0, spec.nchannels)  # 使用roi而不是src_roi
    )

    if not success:
        print("粘贴错误:", canvas_buf.geterror())
        return None
    return canvas_buf
    # 定义裁剪区域：x起始, y起始, z起始, x宽度, y高度, z深度
    # 例如：从(100, 50)开始，裁剪一个200x150的区域
    l, r, t, b = crop[:]
    region = oiio.ROI(int(l), int(w - r), int(t), int(h - b))
    # 执行裁剪
    cropped_buf = oiio.ImageBufAlgo.cut(canvas_buf, region)
    return cropped_buf


def image_buf_to_blender_image(image_buf: ImageBuf, image_name: str) -> bpy.types.Image:
    """
    根据OpenImageIO的ImageBuf在Blender中创建新图像并填充像素。
    """
    spec = image_buf.spec()
    width, height, channels = spec.width, spec.height, spec.nchannels
    # 1. 在Blender中创建新图像
    # Blender图像通常需要RGBA通道，如果OIIO图像不是4通道，可能需要转换
    if channels not in [3, 4]:
        print(f"警告: 图像通道数({channels})可能不被Blender完美支持。")
    bl_image = bpy.data.images.new(image_name, width=width, height=height, alpha=channels == 4, float_buffer=True)

    # 2. 准备像素数据
    # 获取OIIO像素数据 (浮点数列表)
    oiio_pixels = image_buf.get_pixels(oiio.FLOAT)

    # 3. 处理数据格式以匹配Blender
    # Blender的pixels属性是一个扁平的、每像素4个分量(RGBA)的浮点数列表
    # bl_pixels = srgb_to_linear(oiio_pixels.ravel())
    # bl_pixels = linear_to_srgb(oiio_pixels.ravel())
    bl_pixels = linear_to_srgb(oiio_pixels.ravel())

    # 如果OIIO图像是3通道(RGB)，需要添加Alpha通道变成RGBA
    if channels == 3:
        rgba_pixels = []
        for i in range(0, len(bl_pixels), 3):
            r, g, b = bl_pixels[i], bl_pixels[i + 1], bl_pixels[i + 2]
            rgba_pixels.extend((r, g, b, 1.0))  # 添加不透明的Alpha值1.0
        bl_pixels = rgba_pixels
    # 如果OIIO图像已经是4通道(RGBA)，则可以直接使用
    elif channels == 4:
        pass  # 无需转换
    # 如果OIIO图像不是3或4通道，可能需要更复杂的处理
    # print("width, height, channels", width, height, channels)
    # print("oiio_pixels", type(oiio_pixels), oiio_pixels)
    # print("bl_pixels", len(bl_pixels), len(bl_image.pixels))
    # 4. 将像素数据分配给Blender图像
    bl_image.pixels.foreach_set(bl_pixels)

    # 5. 更新图像
    bl_image.update()
    return bl_image


if __name__ == "__main__":
    a = r"C:\Users\32099\Desktop\23FF1D14639FD0527F1B3A6355C789B4.png"
    buf = oiio.ImageBuf(a)
    nb = resize_move_crop_image_buf(buf, 0.5, background=(0, 0, 0, 0), crop=Vector((10, 100, 100, 200)))
    nb.write(r"C:\Users\32099\Desktop\output_ww.png")
