from typing import Any

import OpenImageIO as oiio
import bpy
import numpy as np
from OpenImageIO import ImageBuf, ImageSpec, ImageBufAlgo
from mathutils import Vector, Matrix


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
    pixels_reshaped = pixels_np.reshape(height, width, channels)

    # 创建OpenImageIO ImageBuf
    spec = ImageSpec(width, height, channels, 'float')
    image_buf = ImageBuf(spec)

    # 使用set_pixels批量设置像素
    image_buf.set_pixels(oiio.ROI(), pixels_reshaped)

    return image_buf


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
    bl_image = bpy.data.images.new(image_name, width=width, height=height, alpha=channels == 4)

    # 2. 准备像素数据
    # 获取OIIO像素数据 (浮点数列表)
    oiio_pixels = image_buf.get_pixels(oiio.FLOAT)

    # 3. 处理数据格式以匹配Blender
    # Blender的pixels属性是一个扁平的、每像素4个分量(RGBA)的浮点数列表
    bl_pixels = oiio_pixels.ravel()

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


def offset_scale_image(image_buf: ImageBuf, offset: Vector, scale: Vector,
                       background=None,

                       ) -> ImageBuf | None:
    spec = image_buf.spec()

    width, height, channels = spec.width, spec.height, spec.nchannels

    # 设置填充值
    if background is None:
        background = [0.0] * channels

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

    scale_width = int(np.multiply(width, scale.x))
    scale_height = int(np.multiply(height, scale.y))
    # 创建缩放后的图像
    scaled_buf = ImageBufAlgo.resize(
        image_buf,
        roi=oiio.ROI(0, scale_width, 0, scale_height),
    )
    if scaled_buf.has_error:
        print("缩放图像错误:", scaled_buf.geterror())
        return output_buf
    # 计算居中放置的位置
    pos_x = int((width - scale_width) // 2)
    pos_y = int((height - scale_height) // 2)

    # 如果缩放后的尺寸为0，则直接返回填充图像
    if scale_width <= 0 or scale_height <= 0:
        print("警告: 缩放系数过小，缩放后图像尺寸为0")
        return None

    res_buf = oiio.ImageBuf(spec)  # 输出的buf
    ImageBufAlgo.fill(res_buf, background)

    # 将缩放后的图像粘贴到输出图像的中心位置
    success = ImageBufAlgo.paste(
        res_buf,
        int(offset.x + pos_x),
        int(offset.y + pos_y),
        0,
        0,  # 目标位置
        scaled_buf,  # 源图像
        oiio.ROI(0, scale_width, 0, scale_height)  # 源区域
    )

    if not success:
        print("粘贴操作失败:", ImageBufAlgo.geterror())
        return None
    return res_buf

    # 定义裁剪区域：x起始, y起始, z起始, x宽度, y高度, z深度
    # 例如：从(100, 50)开始，裁剪一个200x150的区域
    l, r, t, b = crop[:]
    region = oiio.ROI(int(l), int(w - r), int(t), int(h - b))
    # 执行裁剪
    cropped_buf = oiio.ImageBufAlgo.cut(canvas_buf, region)
    return cropped_buf

def line_factor_point(point_a, point_b, t):
    x = point_a[0] + t * (point_b[0] - point_a[0])
    y = point_a[1] + t * (point_b[1] - point_a[1])
    return Vector((x, y))