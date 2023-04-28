import struct
from pathlib import Path
from .kclogger import logger
from .translation import lang_text

translation = {}


def _T(word):
    import bpy
    from .timer import Timer
    from bpy.app.translations import pgettext
    locale = bpy.context.preferences.view.language
    culture = translation.setdefault(locale, {})
    if t := culture.get(word):
        return t

    def f(word):
        culture[word] = pgettext(word)
    Timer.put((f, word))
    return lang_text.get(locale, {}).get(word, word)


def update_screen():
    try:
        import bpy
        for area in bpy.context.screen.areas:
            area.tag_redraw()
    except BaseException:
        ...


def clear_cache(d=None):
    from pathlib import Path
    from shutil import rmtree
    if not d:
        clear_cache(Path(__file__).parent)
    else:

        for file in Path(d).iterdir():
            if not file.is_dir():
                continue
            clear_cache(file)
            if file.name == "__pycache__":
                rmtree(file)


def rgb2hex(r, g, b):
    hex_val = f"#{int(r*256):02x}{int(g*256):02x}{int(b*256):02x}"
    return hex_val


def hex2rgb(hex_val):
    hex_val = hex_val.lstrip('#')
    r, g, b = tuple(int(hex_val[i:i + 2], 16) / 256 for i in (0, 2, 4))
    return r, g, b


def to_str(path: Path):
    if isinstance(path, Path):
        return path.as_posix()
    return path


def to_path(path: Path):
    if isinstance(path, Path):
        return path
    return Path(path)


class MetaIn(type):
    def __contains__(self, name):
        return name in Icon.PREV_DICT


class Icon(metaclass=MetaIn):
    import bpy.utils.previews
    PREV_DICT = bpy.utils.previews.new()
    NONE_IMAGE = ""
    IMG_STATUS = {}
    ENABLE_HQ_PREVIEW = False
    INSTANCE = None

    def __init__(self) -> None:
        if Icon.NONE_IMAGE and Icon.NONE_IMAGE not in Icon:
            Icon.NONE_IMAGE = to_str(Icon.NONE_IMAGE)
            self.reg_icon(Icon.NONE_IMAGE)

    def __new__(cls, *args, **kwargs):
        if cls.INSTANCE is None:
            cls.INSTANCE = object.__new__(cls, *args, **kwargs)
        return cls.INSTANCE

    @staticmethod
    def clear():
        Icon.PREV_DICT.clear()
        Icon.IMG_STATUS.clear()
        Icon.reg_icon(Icon.NONE_IMAGE)

    @staticmethod
    def set_hq_preview():
        from .preference import get_pref
        Icon.ENABLE_HQ_PREVIEW = get_pref().enable_hq_preview

    @staticmethod
    def try_mark_image(path) -> bool:
        p = to_path(path)
        path = to_str(path)
        if not p.exists():
            return False
        if Icon.IMG_STATUS.get(path, -1) == p.stat().st_mtime_ns:
            return False
        return True

    @staticmethod
    def can_mark_image(path) -> bool:
        p = to_path(path)
        path = to_str(path)
        if not Icon.try_mark_image(p):
            return False
        Icon.IMG_STATUS[path] = p.stat().st_mtime_ns
        return True

    @staticmethod
    def can_mark_pixel(prev, name) -> bool:
        name = to_str(name)
        if Icon.IMG_STATUS.get(name) == hash(prev.pixels):
            return False
        Icon.IMG_STATUS[name] = hash(prev.pixels)
        return True

    @staticmethod
    def remove_mark(name) -> bool:
        name = to_str(name)
        Icon.IMG_STATUS.pop(name)
        Icon.PREV_DICT.pop(name)
        return True

    @staticmethod
    def reg_none(none: Path):
        none = to_str(none)
        if none in Icon:
            return
        Icon.NONE_IMAGE = none
        Icon.reg_icon(Icon.NONE_IMAGE)

    @staticmethod
    def reg_icon(path):
        path = to_str(path)
        if not Icon.can_mark_image(path):
            return Icon[path]
        if Icon.ENABLE_HQ_PREVIEW:
            try:
                Icon.reg_icon_hq(path)
            except BaseException:
                from .timer import Timer
                Timer.put((Icon.reg_icon_hq, path))
            return Icon[path]
        else:
            if path not in Icon:
                Icon.PREV_DICT.load(path, path, 'IMAGE')
            return Icon[path]

    @staticmethod
    def reg_icon_hq(path):
        import bpy
        p = to_path(path)
        path = to_str(path)
        if path in Icon:
            return
        if p.exists() and p.suffix in {".png", ".jpg", ".jpeg"}:
            img = bpy.data.images.load(path)
            Icon.reg_icon_by_pixel(img, path)
            bpy.data.images.remove(img)

    @staticmethod
    def load_icon(path):
        p = to_path(path)
        path = to_str(path)
        
        if not Icon.can_mark_image(path):
            return
        import bpy
        if p.name[:63] not in bpy.data.images:
            if p.suffix in {".png", ".jpg", ".jpeg"}:
                bpy.data.images.load(path)
        else:
            img = bpy.data.images[p.name[:63]]
            Icon.update_icon_pixel(img.name, img)

    @staticmethod
    def reg_icon_by_pixel(prev, name):
        if not Icon.can_mark_pixel(prev, name):
            return
        if name in Icon:
            return
        p = Icon.PREV_DICT.new(name)
        p.icon_size = (32, 32)
        p.image_size = (prev.size[0], prev.size[1])
        p.image_pixels_float[:] = prev.pixels[:]

    @staticmethod
    def get_icon_id(name: Path):
        p = Icon.PREV_DICT.get(to_str(name), None)
        if not p:
            p = Icon.PREV_DICT.get(Icon.NONE_IMAGE, None)
        return p.icon_id if p else 0

    @staticmethod
    def update_icon_pixel(name, prev):
        """
        更新bpy.data.image 时一并更新(因为pixel 的hash 不变)
        """
        prev.reload()
        p = Icon.PREV_DICT.get(name, None)
        if not p:
            logger.error("No")
            return
        p.icon_size = (32, 32)
        p.image_size = (prev.size[0], prev.size[1])
        p.image_pixels_float[:] = prev.pixels[:]

    def __getitem__(self, name):
        return Icon.get_icon_id(name)

    def __class_getitem__(cls, name):
        return Icon.get_icon_id(name)

    def __contains__(self, name):
        return to_str(name) in Icon.PREV_DICT

    def __class_contains__(cls, name):
        return to_str(name) in Icon.PREV_DICT


class PngParse:
    @staticmethod
    def read_head(pngpath):
        with open(pngpath, 'rb') as f:
            png_header = f.read(25)
            file_sig, ihdr_sig, width, height, bit_depth, color_type, \
                compression_method, filter_method, interlace_method = \
                struct.unpack('>8s4sIIBBBBB', png_header)
            # 输出 PNG 文件头
            data = {
                "PNG file signature": file_sig,
                "IHDR_signature": ihdr_sig,
                "Image_size": [width, height],
                "Bit_depth": bit_depth,
                "Color_type": color_type,
                "Compression_method": compression_method,
                "Filter_method": filter_method,
                "Interlace_method": interlace_method
            }

    def read_text_chunk(pngpath) -> dict[str, str]:
        data = {}
        with open(pngpath, 'rb') as file:
            signature = file.read(8)
            if signature != b'\x89PNG\r\n\x1a\n':
                print('Error: Not a PNG file')
                return data

            # IDHR, PLTE, sRGB, tEXt
            while True:
                length_bytes = file.read(4)
                length = struct.unpack('>I', length_bytes)[0]  # Read chunk length (4 bytes)
                chunk_type = file.read(4)      # Read chunk type (4 bytes)
                chunk_data = file.read(length)  # Read chunk data (length bytes)
                crc = file.read(4)             # Read CRC (4 bytes)
                if chunk_type in {b'IHDR', b'PLTE'}:  # header and Palette
                    continue
                elif chunk_type == b'tEXt':
                    keyword, text = chunk_data.decode().split('\0', 1)
                    data[keyword] = text
                elif chunk_type == b'IEND':
                    break
        return data
