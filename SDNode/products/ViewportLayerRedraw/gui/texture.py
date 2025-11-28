import bpy
import gpu
import OpenImageIO as oiio
from pathlib import Path

ICON_PATH = Path(__file__).parent.joinpath("assets/icons")


class TexturePool:
    TEX: dict[str, gpu.types.GPUTexture] = {}
    TEX_ID: dict[int, gpu.types.GPUTexture] = {}

    @staticmethod
    def read_image_to_tex(file_path):
        file_path = Path(file_path)
        if not file_path.exists():
            file_path = ICON_PATH.joinpath(f"{file_path}.png")
        if not file_path.exists():
            file_path = ICON_PATH.joinpath("none.png")
        buf = oiio.ImageBuf(file_path.as_posix())
        spec = buf.spec()
        if spec.nchannels == 3:
            alpha_spec = oiio.ImageSpec(spec.width, spec.height, 1, oiio.FLOAT)
            alpha_buf = oiio.ImageBuf(alpha_spec)
            oiio.ImageBufAlgo.fill(alpha_buf, 1.0)
            buf = oiio.ImageBufAlgo.channel_append(buf, alpha_buf)
        spec = buf.spec()
        pixels = buf.get_pixels(oiio.FLOAT)
        gpu_buf = gpu.types.Buffer("FLOAT", (spec.width, spec.height, spec.nchannels), pixels)
        gpu_tex = gpu.types.GPUTexture(gpu_buf.dimensions[:2], format="RGBA8", data=gpu_buf)
        return gpu_tex

    @staticmethod
    def test_write_buf_to_image():
        import numpy as np

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

    @classmethod
    def push_tex(cls, tex):
        cls.TEX_ID[id(tex)] = tex
        return id(tex)

    @classmethod
    def pop_tex(cls, tex_id):
        cls.TEX_ID.pop(tex_id, None)

    @classmethod
    def get_tex_id(cls, img) -> int:
        if img not in cls.TEX:
            cls.TEX[img] = cls.read_image_to_tex(img)
        gpu_tex = cls.TEX[img]
        gpu_tex_id = id(gpu_tex)
        cls.TEX_ID[gpu_tex_id] = gpu_tex
        return gpu_tex_id

    @classmethod
    def get_tex(cls, tex_id) -> gpu.types.GPUTexture | None:
        return cls.TEX_ID.get(tex_id, None)

    @classmethod
    def prepare_builtin_icon(cls):
        il = cls.read_image_to_tex
        cls.TEX.clear()
        cls.TEX.update(
            {
                "camera": il(ICON_PATH.joinpath("camera.png").as_posix()),
                "upload": il(ICON_PATH.joinpath("upload.png").as_posix()),
                "new": il(ICON_PATH.joinpath("new.png").as_posix()),
                # "robot": il(ICON_PATH.joinpath("cube.png").as_posix()),
            }
        )

    @classmethod
    def register(cls):
        cls.prepare_builtin_icon()

    @classmethod
    def unregister(cls):
        pass


def register():
    TexturePool.register()


def unregister():
    TexturePool.unregister()
