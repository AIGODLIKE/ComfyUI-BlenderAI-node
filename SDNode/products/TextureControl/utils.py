import bpy
import OpenImageIO as oiio


def get_image(obj: bpy.types.Object):
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


def resize_and_position(input_path, output_path, scale_factor, position="center", background=None):
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
    buf = oiio.ImageBuf(input_path)
    spec = buf.spec()

    print("spec.nchannels", spec.nchannels, spec.format)
    if spec.nchannels < 4:
        # 创建新的图像规格，增加Alpha通道
        new_spec = oiio.ImageSpec(spec.width, spec.height, 4, spec.format)

        # 创建新的ImageBuf，并设置所有像素为完全透明
        buf_with_alpha = oiio.ImageBuf(new_spec)
        oiio.ImageBufAlgo.fill(buf_with_alpha, [1, 1, 0, 1])  # R,G,B,A 全为0

        # 将原始图像的RGB通道复制到新图像的前三个通道
        # 这里使用'copy'操作将原图的RGB通道复制到新图的前三个通道
        oiio.ImageBufAlgo.copy(buf_with_alpha, buf, roi=oiio.ROI(0, spec.width, 0, spec.height, 0, 1, 0, 3))
        buf = buf_with_alpha
        spec = buf.spec()

    # 计算缩放后的图像尺寸
    if isinstance(scale_factor, tuple):
        sx, sy = scale_factor[:]
    else:
        sx = sy = scale_factor
    new_width = int(spec.width * sx)
    new_height = int(spec.height * sy)

    print(f"原始尺寸: {spec.width} x {spec.height}")
    print(f"缩放后像素尺寸: {new_width} x {new_height}")

    # 创建缩放后的图像
    resized_buf = oiio.ImageBuf(oiio.ImageSpec(new_width, new_height, 4, spec.format))
    success_resize = oiio.ImageBufAlgo.resize(resized_buf, buf)

    if not success_resize:
        print("缩放错误:", resized_buf.geterror())
        return False

    # 创建与原始图像相同尺寸的画布
    canvas_buf = oiio.ImageBuf(spec)

    # 设置背景色
    if background is not None:
        oiio.ImageBufAlgo.fill(canvas_buf, background)

    # 计算位置
    if position == "center":
        xoffset = (spec.width - new_width) // 2
        yoffset = (spec.height - new_height) // 2
    elif position == "top-left":
        xoffset = 0
        yoffset = spec.height - new_height
    elif position == "top-right":
        xoffset = spec.width - new_width
        yoffset = spec.height - new_height
    elif position == "bottom-left":
        xoffset = 0
        yoffset = 0
    elif position == "bottom-right":
        xoffset = spec.width - new_width
        yoffset = 0
    else:  # 自定义位置
        xoffset, yoffset = position

    # 确保位置在合理范围内
    xoffset = max(0, min(xoffset, spec.width - 1))
    yoffset = max(0, min(yoffset, spec.height - 1))

    # 将缩放后的图像粘贴到画布上 - 使用正确的参数
    success = oiio.ImageBufAlgo.paste(
        canvas_buf,
        xoffset, yoffset, 0, 0,  # 目标位置: xbegin, ybegin, zbegin, chbegin
        resized_buf,  # 源图像
        roi=oiio.ROI(0, new_width, 0, new_height, 0, 1, 0, spec.nchannels)  # 使用roi而不是src_roi
    )

    if not success:
        print("粘贴错误:", canvas_buf.geterror())
        return False

    # 保存结果
    if not canvas_buf.write(output_path):
        print("保存失败:", canvas_buf.geterror())
        return False

    # 定义裁剪区域：x起始, y起始, z起始, x宽度, y高度, z深度
    # 例如：从(100, 50)开始，裁剪一个200x150的区域
    region = oiio.ROI(100, 300, 50, 200)
    # 执行裁剪
    cropped_buf = oiio.ImageBufAlgo.cut(canvas_buf, region)
    # 保存结果
    cropped_buf.write(r"C:\Users\32099\Desktop\output_cut.png")

    print("处理成功! 图像已保存至:", output_path)
    return True
