import struct
import queue
import platform
import time
import re
import json
import bpy
import addon_utils
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse
from ast import literal_eval
from .kclogger import logger
from .translations import LANG_TEXT
from .timer import Timer
from .datas import IMG_SUFFIX, get_bl_version
translation = {}
meta_info = {}


def get_bl_info() -> dict:
    module = get_bl_module()
    return addon_utils.module_bl_info(module) or meta_info.get("bl_info", {})


def get_name():
    return meta_info.get("package", "")


def get_bl_module(name=None):
    if not name:
        name = get_name()
    try:
        return addon_utils.addons_fake_modules[name]
    except Exception:
        for mod in addon_utils.modules(refresh=False):
            if mod.__name__ == name:
                return mod


def popup_folder(path: Path):
    import os
    if platform.system() == "Windows":
        if path.is_file():
            path = path.parent
        path = path.as_posix()
        os.startfile(path)
    else:
        os.system(f"open {path}")


def get_ai_mat_tree(obj: bpy.types.Object):
    if not obj or obj.type != "MESH":
        return None
    if hasattr(obj, "ai_mat_tree"):
        return getattr(obj, "ai_mat_tree")
    tree_name = obj.get("AI_Mat_Gen", "")
    if not tree_name:
        return None
    sdn_time_code = obj.get("AI_Mat_Gen_Id", "-1")
    tree = bpy.data.node_groups.get(tree_name, None)
    if not tree or tree.get("sdn_time_code", "0") != sdn_time_code:
        for ng in bpy.data.node_groups:
            if ng.get("sdn_time_code", "0") == sdn_time_code:
                return ng
        return None
    return tree


def set_ai_mat_tree(obj: bpy.types.Object, tree: bpy.types.NodeTree):
    obj["AI_Mat_Gen"] = tree.name
    tree.set_sdn_time_code()
    obj["AI_Mat_Gen_Id"] = tree.sdn_time_code


def read_json(path: Path | str) -> dict:
    import json
    encodings = ["utf8", "gbk"]
    for encoding in encodings:
        try:
            return json.loads(Path(path).read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError:
            continue
    return {}


def rmtree(path: Path):
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        for child in path.iterdir():
            rmtree(child)
        try:
            path.rmdir()  # nas 的共享盘可能会有残留
        except BaseException:
            ...


def get_addon_name():
    return "AI Node" + get_bl_version()


def _T(word):
    if not isinstance(word, str):
        return word
    import bpy
    from bpy.app.translations import pgettext
    locale = bpy.context.preferences.view.language
    culture = translation.setdefault(locale, {})
    if t := culture.get(word):
        return t

    def f(word):
        culture[word] = pgettext(word)
    Timer.put((f, word))
    return LANG_TEXT.get(locale, {}).get(word, word)


logger.set_translate(_T)


def _T2(word):
    import bpy
    from .translations.translation import REPLACE_DICT
    locale = bpy.context.preferences.view.language
    return REPLACE_DICT.get(locale, {}).get(word, word)


def find_areas_of_type(screen: bpy.types.Screen, area_type) -> list[bpy.types.Area]:
    return [area for area in screen.areas if area.type == area_type]


def find_area_by_type(screen: bpy.types.Screen, area_type, index) -> bpy.types.Area:
    areas = find_areas_of_type(screen, area_type)
    if areas:
        return areas[index]
    return None

def find_region_by_type(area: bpy.types.Area, region_type) -> bpy.types.Region:
    for region in area.regions:
        if region.type == region_type:
            return region
    return None

def update_screen():
    try:
        import bpy
        for area in bpy.context.screen.areas:
            area.tag_redraw()
        bpy.context.workspace.status_text_set_internal(None)
    except BaseException:
        ...


def update_node_editor():
    try:
        import bpy
        for area in bpy.context.screen.areas:
            for space in area.spaces:
                if space.type != "NODE_EDITOR":
                    continue
                space.node_tree = space.node_tree
            if area.type == "NODE_EDITOR":
                area.tag_redraw()
    except Exception:
        ...


def clear_cache(d=None):
    from shutil import rmtree as shutil_rmtree
    if not d:
        clear_cache(Path(__file__).parent)
    else:

        for file in Path(d).iterdir():
            if not file.is_dir():
                continue
            clear_cache(file)
            if file.name == "__pycache__":
                shutil_rmtree(file)


def rgb2hex(r, g, b, *args):
    hex_val = f"#{int(r*256):02x}{int(g*256):02x}{int(b*256):02x}"
    return hex_val


def hex2rgb(hex_val):
    hex_val = hex_val.lstrip('#')
    if len(hex_val) == 3:
        return [int(h, 16) / 16 for h in hex_val]
    return [int(hex_val[i:i + 2], 16) / 256 for i in (0, 2, 4)]


@lru_cache(maxsize=16)
def is_ipv6(ip):
    import ipaddress
    try:
        ipaddress.IPv6Address(ip)
        return True
    except ValueError:
        return False


@lru_cache(maxsize=16)
def is_ipv4(ip):
    import ipaddress
    try:
        ipaddress.IPv4Address(ip)
        return True
    except ValueError:
        return False

class PrevMgr:
    __PREV__ = {}

    @staticmethod
    def new():
        import bpy.utils.previews
        import random
        prev = bpy.utils.previews.new()
        while (i := random.randint(0, 999999999)) in PrevMgr.__PREV__:
            continue
        PrevMgr.__PREV__[i] = prev
        return prev

    @staticmethod
    def remove(prev):
        import bpy.utils.previews
        bpy.utils.previews.remove(prev)

    @staticmethod
    def clear():
        for prev in PrevMgr.__PREV__.values():
            prev.clear()
            prev.close()
        PrevMgr.__PREV__.clear()


def __del__():
    PrevMgr.clear()


class MetaIn(type):
    def __contains__(cls, name):
        return cls.__contains__(cls, name)


class Icon(metaclass=MetaIn):
    PREV_DICT = PrevMgr.new()
    NONE_IMAGE = ""
    IMG_STATUS = {}
    PIX_STATUS = {}
    PATH2BPY = {}
    ENABLE_HQ_PREVIEW = False
    INSTANCE = None

    def __init__(self) -> None:
        if Icon.NONE_IMAGE and Icon.NONE_IMAGE not in Icon:
            Icon.NONE_IMAGE = FSWatcher.to_str(Icon.NONE_IMAGE)
            self.reg_icon(Icon.NONE_IMAGE)

    def __new__(cls, *args, **kwargs):
        if cls.INSTANCE is None:
            cls.INSTANCE = object.__new__(cls, *args, **kwargs)
        return cls.INSTANCE

    @staticmethod
    def update_path2bpy():
        import bpy
        Icon.PATH2BPY.clear()
        for i in bpy.data.images:
            Icon.PATH2BPY[FSWatcher.to_str(i.filepath)] = i

    @staticmethod
    def apply_alpha(img):
        if img.file_format != "PNG" or img.channels < 4:
            return
        # 预乘alpha 到rgb
        import numpy as np
        pixels = np.zeros(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(pixels)
        sized_pixels = pixels.reshape(-1, 4)
        sized_pixels[:, :3] *= sized_pixels[:, 3].reshape(-1, 1)
        img.pixels.foreach_set(pixels)

    @staticmethod
    def clear():
        Icon.PREV_DICT.clear()
        Icon.IMG_STATUS.clear()
        Icon.PIX_STATUS.clear()
        Icon.PATH2BPY.clear()
        Icon.reg_icon(Icon.NONE_IMAGE)

    @staticmethod
    def set_hq_preview():
        from .preference import get_pref
        Icon.ENABLE_HQ_PREVIEW = get_pref().enable_hq_preview

    @staticmethod
    def try_mark_image(path) -> bool:
        p = FSWatcher.to_path(path)
        path = FSWatcher.to_str(path)
        if not p.exists():
            return False
        if Icon.IMG_STATUS.get(path, -1) == p.stat().st_mtime_ns:
            return False
        return True

    @staticmethod
    def can_mark_image(path) -> bool:
        p = FSWatcher.to_path(path)
        path = FSWatcher.to_str(path)
        if not Icon.try_mark_image(p):
            return False
        Icon.IMG_STATUS[path] = p.stat().st_mtime_ns
        return True

    @staticmethod
    def can_mark_pixel(prev, name) -> bool:
        name = FSWatcher.to_str(name)
        if Icon.PIX_STATUS.get(name) == hash(prev.pixels):
            return False
        Icon.PIX_STATUS[name] = hash(prev.pixels)
        return True

    @staticmethod
    def remove_mark(name) -> bool:
        name = FSWatcher.to_str(name)
        Icon.IMG_STATUS.pop(name, None)
        Icon.PIX_STATUS.pop(name, None)
        Icon.PREV_DICT.pop(name, None)
        return True

    @staticmethod
    def reg_none(none: Path):
        none = FSWatcher.to_str(none)
        if none in Icon:
            return
        Icon.NONE_IMAGE = none
        Icon.reg_icon(Icon.NONE_IMAGE)

    @staticmethod
    def reg_icon(path, reload=False, hq=False):
        path = FSWatcher.to_str(path)
        if not Icon.can_mark_image(path):
            return Icon[path]
        if Icon.ENABLE_HQ_PREVIEW and hq:
            try:
                Icon.reg_icon_hq(path)
            except BaseException:
                Timer.put((Icon.reg_icon_hq, path))
            return Icon[path]
        else:
            if path not in Icon:
                Icon.PREV_DICT.load(path, path, 'IMAGE')
            if reload:
                Timer.put(Icon.PREV_DICT[path].reload)
            return Icon[path]

    @staticmethod
    def reg_icon_hq(path):
        import bpy
        p = FSWatcher.to_path(path)
        path = FSWatcher.to_str(path)
        if path in Icon:
            return
        if p.exists() and p.suffix.lower() in IMG_SUFFIX:
            img = bpy.data.images.load(path)
            Icon.apply_alpha(img)
            Icon.reg_icon_by_pixel(img, path)
            Timer.put((bpy.data.images.remove, img))  # 直接使用 bpy.data.images.remove 会导致卡死

    @staticmethod
    def find_image(path):
        img = Icon.PATH2BPY.get(FSWatcher.to_str(path), None)
        if not img:
            return None
        try:
            _ = img.name  # hack ref detect
            return img
        except ReferenceError:
            Icon.update_path2bpy()
        return None

    @staticmethod
    def load_icon(path):
        import bpy
        p = FSWatcher.to_path(path)
        path = FSWatcher.to_str(path)
        # ctrl + z 导致bpy.data中的图像被删除
        if path not in Icon.PATH2BPY:
            Icon.IMG_STATUS.pop(path, None)
        if not Icon.can_mark_image(path):
            return

        # if p.name[:63] in bpy.data.images:
        #     img = bpy.data.images[p.name[:63]]
        #     Icon.update_icon_pixel(img.name, img)
        if img := Icon.find_image(path):
            Icon.update_icon_pixel(path, img)
            return img
        elif p.suffix.lower() in IMG_SUFFIX:
            img = bpy.data.images.load(path)
            img.filepath = path
            Icon.apply_alpha(img)
            Icon.update_path2bpy()
            # img.name = path
            return img

    @staticmethod
    def reg_icon_by_pixel(prev, name):
        name = FSWatcher.to_str(name)
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
        p = Icon.PREV_DICT.get(FSWatcher.to_str(name), None)
        if not p:
            p = Icon.PREV_DICT.get(FSWatcher.to_str(Icon.NONE_IMAGE), None)
        return p.icon_id if p else 0

    @staticmethod
    def update_icon_pixel(name, prev):
        """
        更新bpy.data.image 时一并更新(因为pixel 的hash 不变)
        """
        prev.reload()
        p = Icon.PREV_DICT.get(name, None)
        if not p:
            # logger.error("No")
            return
        p.icon_size = (32, 32)
        p.image_size = (prev.size[0], prev.size[1])
        p.image_pixels_float[:] = prev.pixels[:]

    def __getitem__(self, name):
        return Icon.get_icon_id(name)

    def __contains__(self, name):
        return FSWatcher.to_str(name) in Icon.PREV_DICT

    def __class_getitem__(cls, name):
        return cls.__getitem__(cls, name)


class PngParse:

    @staticmethod
    def read_head(pngpath):
        with open(pngpath, 'rb') as f:
            png_header = f.read(25)
            file_sig, ihdr_sig, width, height, bit_depth, color_type, \
                compression_method, filter_method, interlace_method = \
                struct.unpack('>8s4sIIBBBBB', png_header)
            # 输出 PNG 文件头
            _ = {
                "PNG file signature": file_sig,
                "IHDR_signature": ihdr_sig,
                "Image_size": [width, height],
                "Bit_depth": bit_depth,
                "Color_type": color_type,
                "Compression_method": compression_method,
                "Filter_method": filter_method,
                "Interlace_method": interlace_method
            }

    @staticmethod
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
                chunk_type = file.read(4)       # Read chunk type (4 bytes)
                chunk_data = file.read(length)  # Read chunk data (length bytes)
                _ = file.read(4)                # Read CRC (4 bytes)
                if chunk_type in {b'IHDR', b'PLTE'}:  # header and Palette
                    continue
                elif chunk_type == b'tEXt':
                    keyword, text = chunk_data.decode().split('\0', 1)
                    data[keyword] = text
                elif chunk_type == b'IEND':
                    break
        return data


class PkgInstaller:
    source = [
        "https://mirrors.aliyun.com/pypi/simple/",
        "https://pypi.tuna.tsinghua.edu.cn/simple/",
        "https://pypi.mirrors.ustc.edu.cn/simple/",
        "https://pypi.python.org/simple/",
        "https://pypi.org/simple",
    ]
    fast_url = ""

    @staticmethod
    def select_pip_source():
        if not PkgInstaller.fast_url:
            import requests
            t, PkgInstaller.fast_url = 999, PkgInstaller.source[0]
            for url in PkgInstaller.source:
                try:
                    tping = requests.get(url, timeout=1).elapsed.total_seconds()
                except Exception as e:
                    logger.warning(e)
                    continue
                if tping < 0.1:
                    PkgInstaller.fast_url = url
                    break
                if tping < t:
                    t, PkgInstaller.fast_url = tping, url
        return PkgInstaller.fast_url

    @staticmethod
    def is_installed(package):
        import importlib
        try:
            return importlib.import_module(package)
        except ModuleNotFoundError:
            return False

    @staticmethod
    def prepare_pip():
        import ensurepip
        if PkgInstaller.is_installed("pip"):
            return True
        try:
            ensurepip.bootstrap()
            return True
        except BaseException:
            ...
        return False

    @staticmethod
    def try_install(*packages):
        if not PkgInstaller.prepare_pip():
            return False
        need = [pkg for pkg in packages if not PkgInstaller.is_installed(pkg)]
        from pip._internal import main
        if need:
            url = PkgInstaller.select_pip_source()
        for pkg in need:
            try:
                site = urlparse(url)
                # 避免build
                command = ['install', pkg, "-i", url, "--prefer-binary"]
                command.append("--trusted-host")
                command.append(site.netloc)
                main(command)
                if not PkgInstaller.is_installed(pkg):
                    return False
            except Exception:
                return False
        return True


class FSWatcher:
    """
    监听文件/文件夹变化的工具类
        register: 注册监听, 传入路径和回调函数(可空)
        unregister: 注销监听
        run: 监听循环, 使用单例,只在第一次初始化时调用
        stop: 停止监听, 释放资源
        consume_change: 消费变化, 当监听对象发生变化时记录为changed, 主动消费后置False, 用于自定义回调函数
    """
    _watcher_path: dict[Path, bool] = {}
    _watcher_stat = {}
    _watcher_callback = {}
    _watcher_queue = queue.Queue()
    _running = False
    _use_threading = False

    @classmethod
    def init(cls) -> None:
        cls._run()

    @classmethod
    def register(cls, path, callback=None):
        path = cls.to_path(path)
        if path in cls._watcher_path:
            return
        cls._watcher_path[path] = False
        cls._watcher_callback[path] = callback

    @classmethod
    def unregister(cls, path):
        path = cls.to_path(path)
        cls._watcher_path.pop(path, None)
        cls._watcher_callback.pop(path, None)

    @classmethod
    def _run(cls):
        if cls._running:
            return
        cls._running = True
        if cls._use_threading:
            # use threading
            from threading import Thread
            Thread(target=cls._loop, daemon=True).start()
            Thread(target=cls._run_ex, daemon=True).start()
        else:
            # use timer
            import bpy
            bpy.app.timers.register(cls._loop_timer, persistent=True)
            bpy.app.timers.register(cls._run_ex_timer, persistent=True)

    @classmethod
    def _run_ex_timer(cls):
        cls._run_ex_one()
        return 0.5

    @classmethod
    def _run_ex(cls):
        while cls._running:
            cls._run_ex_one()
            time.sleep(0.1)

    @classmethod
    def _run_ex_one(cls):
        if not cls._running:
            return
        while not cls._watcher_queue.empty():
            path = cls._watcher_queue.get()
            if path not in cls._watcher_path:
                continue
            if callback := cls._watcher_callback[path]:
                callback(path)

    @classmethod
    def _loop_timer(cls):
        cls._loop_one()
        return 1

    @classmethod
    def _loop(cls):
        """
            监听所有注册的路径, 有变化时记录为changed
        """
        while cls._running:
            cls._loop_one()
            time.sleep(0.5)

    @classmethod
    def _loop_one(cls):
        if not cls._running:
            return
        for path, changed in list(cls._watcher_path.items()):
            if changed:
                continue
            if not path.exists():
                continue
            mtime = path.stat().st_mtime_ns
            if cls._watcher_stat.get(path, None) == mtime:
                continue
            cls._watcher_stat[path] = mtime
            cls._watcher_path[path] = True
            cls._watcher_queue.put(path)

    @classmethod
    def stop(cls):
        cls._watcher_queue.put(None)
        cls._running = False

    @classmethod
    def consume_change(cls, path) -> bool:
        path = cls.to_path(path)
        if path in cls._watcher_path and cls._watcher_path[path]:
            cls._watcher_path[path] = False
            return True
        return False

    @classmethod
    @lru_cache(maxsize=1024)
    def get_nas_mapping(cls):
        if platform.system() != "Windows":
            return {}
        import subprocess
        try:
            result = subprocess.run("net use", capture_output=True, text=True, encoding="gbk", check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(e)
            return {}
        if result.returncode != 0 or result.stdout is None:
            return {}
        nas_mapping = {}
        try:
            lines = result.stdout.strip().split("\n")[4:]
            for line in lines:
                columns = line.split()
                if len(columns) < 3:
                    continue
                local_drive = columns[1] + "/"
                nas_path = Path(columns[2]).resolve().as_posix()
                nas_mapping[local_drive] = nas_path
        except Exception:
            ...
        return nas_mapping

    @classmethod
    @lru_cache(maxsize=1024)
    def to_str(cls, path: Path):
        p = Path(path)
        try:
            res_str = p.resolve().as_posix()
        except FileNotFoundError as e:
            res_str = p.as_posix()
            logger.warning(e)
        # 处理nas路径
        for local_drive, nas_path in cls.get_nas_mapping().items():
            if not res_str.startswith(nas_path):
                continue
            return res_str.replace(nas_path, local_drive)
        return res_str

    @classmethod
    @lru_cache(maxsize=1024)
    def to_path(cls, path: Path):
        return Path(path)


class ScopeTimer:
    def __init__(self, name: str = "", prt=print):
        self.name = name
        self.time_start = time.time()
        self.echo = prt

    def __del__(self):
        self.echo(f"{self.name} cost {time.time() - self.time_start:.4f}s")


class CtxTimer:
    def __init__(self, name: str = "", prt=print):
        self.name = name
        self.time_start = time.time()
        self.echo = prt

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.echo(f"{self.name} cost {time.time() - self.time_start:.4f}s")


class WebUIToComfyUI:
    SAMPLERNAME_W2C = {
        "Euler": "euler",
        "Euler a": "euler_ancestral",
        "Heun": "heun",
        "DPM fast": "dpm_fast",
        "DPM adaptive": "dpm_adaptive",
        "DPM2": "dpm_2",
        "DPM2 a": "dpm_2_ancestral",
        "DPM++ 2M": "dpmpp_2m",
        "DPM++ SDE": "dpmpp_sde_gpu",
        "DPM++ 2M SDE": "dpmpp_2m_sde_gpu",
        "DPM++ 3M SDE": "dpmpp_3m_sde",
        "DDIM": "ddim",
        "LMS": "lms",
        "LCM": "LCM",
        "UniPC": "uni_pc",
    }
    SCHEDULERNAME_W2C = {
        "Automatic": "normal",
        "Karras": "karras",
        "Exponential": "exponential",
        "SGM Uniform": "sgm_uniform",
    }
    PREPROCESSOR_W2C = {
        "animal_openpose": "AnimalPosePreprocessor",
        "blur_gaussian": "*TilePreprocessor",
        "canny": "CannyEdgePreprocessor",
        "densepose (pruple bg & purple torso)": "DensePosePreprocessor",
        "densepose_parula (black bg & blue torso)": "DensePosePreprocessor",
        "depth_anything": "DepthAnythingPreprocessor",
        "depth_anything_v2": "DepthAnythingV2Preprocessor",
        "depth_hand_refiner": "MeshGraphormer+ImpactDetector-DepthMapPreprocessor",
        "depth_leres": "LeReS-DepthMapPreprocessor",
        "depth_leres++": "*LeReS-DepthMapPreprocessor",
        "depth_midas": "MiDaS-DepthMapPreprocessor",
        "depth_zoe": "Zoe-DepthMapPreprocessor",
        "dw_openpose_full": "DWPreprocessor",
        "facexlib": "",
        "inpaint_global_harmonious": "",
        "inpaint_only": "InpaintPreprocessor",
        "inpaint_only+lama": "",
        "instant_id_face_embedding": "",
        "instant_id_face_keypoints": "",
        "invert (from white bg & black line)": "ImageInvert",
        "ip-adapter-auto": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_g": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_h": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_clip_sdxl_plus_vith": "IPAdapter+IPAdapterUnifiedLoader",
        "ip-adapter_face_id": "IPAdapterFaceID+IPAdapterUnifiedLoaderFaceID",
        "ip-adapter_face_id_plus": "IPAdapterFaceID+IPAdapterUnifiedLoaderFaceID",
        "ip-adapter_pulid": "",
        "lineart_anime": "AnimeLineArtPreprocessor",
        "lineart_anime_denoise": "",
        "lineart_coarse": "LineArtPreprocessor",
        "lineart_realistic": "LineArtPreprocessor",
        "lineart_standard (from white bg & black line)": "LineartStandardPreprocessor",
        "mediapipe_face": "MediaPipe-FaceMeshPreprocessor",
        "mlsd": "M-LSDPreprocessor",
        "none": "",
        "normal_bae": "BAE-NormalMapPreprocessor",
        "normal_dsine": "DSINE-NormalMapPreprocessor",
        "normal_midas": "MiDaS-NormalMapPreprocessor",
        "openpose": "OpenposePreprocessor",
        "openpose_face": "OpenposePreprocessor",
        "openpose_faceonly": "OpenposePreprocessor",
        "openpose_full": "OpenposePreprocessor",
        "openpose_hand": "OpenposePreprocessor",
        "recolor_intensity": "ImageIntensityDetector",
        "recolor_luminance": "ImageLuminanceDetector",
        "reference_adain": "",
        "reference_adain+attn": "",
        "reference_only": "",
        "revision_clipvision": "",
        "revision_ignore_prompt": "",
        "scribble_hed": "FakeScribblePreprocessor",
        "scribble_pidinet": "Scribble_PiDiNet_Preprocessor",
        "scribble_xdog": "Scribble_XDoG_Preprocessor",
        "seg_anime_face": "AnimeFace_SemSegPreprocessor",
        "seg_ofade20k": "OneFormer-ADE20K-SemSegPreprocessor",
        "seg_ofcoco": "OneFormer-COCO-SemSegPreprocessor",
        "seg_ufade20k": "UniFormer-SemSegPreprocessor",
        "shuffle": "ShufflePreprocessor",
        "softedge_anyline": "",
        "softedge_hed": "HEDPreprocessor",
        "softedge_hedsafe": "HEDPreprocessor",
        "softedge_pidinet": "PiDiNetPreprocessor",
        "softedge_pidisafe": "PiDiNetPreprocessor",
        "softedge_teed": "TEED_Preprocessor",
        "t2ia_color_grid": "ColorPreprocessor",
        "t2ia_sketch_pidi": "",
        "t2ia_style_clipvision": "",
        "threshold": "BinaryPreprocessor",
        "tile_colorfix": "",
        "tile_colorfix+sharp": "",
        "tile_resample": "TilePreprocessor",
    }

    def __init__(self, text: str = "", ):
        self.text: str = text
        self.params: dict = {}
        self.parse_cn = False

    def is_webui_format(self):
        return "Negative prompt: " in self.text and "Steps: " in self.text

    def get_registered_node_types(self):
        from .SDNode.nodes import NodeBase
        registered_node_types = {n.class_type: n.__metadata__ for n in NodeBase.__subclasses__()}
        return registered_node_types

    def with_efficient(self):
        registered_node_types = self.get_registered_node_types()
        return "Efficient Loader" in registered_node_types and "KSampler (Efficient)" in registered_node_types

    def apply_nodes_offset(this, nodes, offset=None):
        if offset is None:
            return
        for node in nodes:
            node["pos"][0] += offset[0]
            node["pos"][1] += offset[1]

    def find_following_nodes(self, wk, node, _nodes=None):
        if _nodes is None:
            _nodes = []
        for out in node.get("outputs", []):
            for link_id in out.get("links", []) or []:
                _l = next((l for l in wk["links"] if l[0] == link_id), None)
                if not _l:
                    continue
                _in = next((n for n in wk["nodes"] if n["id"] == _l[3]), None)
                if not _in:
                    continue
                if _in not in _nodes:
                    _nodes.append(_in)
                self.find_following_nodes(wk, _in, _nodes)
        return _nodes

    def make_link(self, workflow, out_node, out_index, in_node, in_index):
        last_link_id = workflow["last_link_id"] + 1
        workflow["last_link_id"] = last_link_id
        ltype = out_node["outputs"][out_index]["type"] or None
        link = [last_link_id, out_node["id"], out_index, in_node["id"], in_index, ltype]
        out_node["outputs"][out_index]["links"].append(last_link_id)
        old_in_link = in_node["inputs"][in_index]["link"]
        if old_in_link and old_in_link != last_link_id:
            self.remove_link(workflow, old_in_link)
        in_node["inputs"][in_index]["link"] = last_link_id
        workflow["links"].append(link)

    def remove_link(self, workflow, link_id):
        if link_id is None:
            return
        if link_id == workflow["last_link_id"]:
            workflow["last_link_id"] = workflow["last_link_id"] - 1
        for i in range(len(workflow["links"])):
            link = workflow["links"][i]
            if link[0] != link_id:
                continue
            workflow["links"].pop(i)
            return

    def remove_node_by_id(self, workflow, node_id):
        if not node_id:
            return
        find_node = None
        find_node_index = -1
        for i in range(len(workflow["nodes"])):
            if (workflow["nodes"][i]["id"] == node_id):
                find_node = workflow["nodes"][i]
                find_node_index = i
                break
        if not find_node:
            return
        # 移除关联的link
        for inp in find_node.get("inputs", []):
            link_id = inp["link"]
            if not link_id:
                continue
            for node in workflow["nodes"]:
                for output in node["outputs"]:
                    try:
                        output["links"].remove(link_id)
                        break
                    except ValueError:
                        ...
            self.remove_link(workflow, link_id)
        for out in find_node.get("outputs", []):
            for link_id in out.get("links", []):
                if link_id is None:
                    continue
                for node in workflow["nodes"]:
                    for inp in node.get("inputs", []):
                        inp["link"] = None if inp["link"] == link_id else inp["link"]
            self.remove_link(workflow, link_id)
        # 移除节点
        workflow["nodes"].pop(find_node_index)

    def to_comfyui_format(self):
        if self.with_efficient():
            return self.to_comfyui_format_efficient()
        return self.to_comfyui_format_base()

    def to_comfyui_format_base(self):
        params = self.params.copy()
        wk = self.base_workflow()
        self.apply_nodes_offset(wk["nodes"], (-200, 63))
        np = wk["nodes"][0]
        pp = wk["nodes"][1]
        empty_image = wk["nodes"][2]
        ksampler = wk["nodes"][3]
        checkpoint_loader = wk["nodes"][6]
        clip_last_layer = wk["nodes"][7]
        if "Negative prompt" in params:
            np["widgets_values"][0] = params["Negative prompt"]
        if "Positive prompt" in params:
            pp["widgets_values"][0] = params["Positive prompt"]
        if "Size" in params:
            width = 512
            height = 512
            if "x" in params["Size"]:
                size_list = params["Size"].split("x")
                width = size_list[0]
                height = size_list[1]
            empty_image["widgets_values"][0] = width
            empty_image["widgets_values"][1] = height

        if "Seed" in params:
            ksampler["widgets_values"][0] = params["Seed"]
        if "Steps" in params:
            ksampler["widgets_values"][2] = params["Steps"]
        if "CFG scale" in params:
            ksampler["widgets_values"][3] = params["CFG scale"]
        if "Sampler" in params:
            sampler_name: str = params["Sampler"]
            scheduler_name: str = "normal"
            if "Schedule type" in params:
                sampler_name = params["Sampler"]
                scheduler_name = params["Schedule type"]
            else:
                # samper存储 sampler_name + " " + scheduler_name
                for one_sch_name in self.SCHEDULERNAME_W2C:
                    if one_sch_name in sampler_name:
                        scheduler_name = one_sch_name
                        sampler_name = sampler_name.replace(one_sch_name, "").strip()
                        break

            if sampler_name in self.SAMPLERNAME_W2C:
                ksampler["widgets_values"][4] = self.SAMPLERNAME_W2C[sampler_name]
            if scheduler_name in self.SCHEDULERNAME_W2C:
                ksampler["widgets_values"][5] = self.SCHEDULERNAME_W2C[scheduler_name]
            self._gen_control_net(wk, ksampler, pp, np)

        if "Denoising strength" in params:
            ksampler["widgets_values"][6] = params["Denoising strength"]
            if float(params["Denoising strength"]) < 1:
                # 图生图, 需要添加图片输入
                last_node_id = wk["last_node_id"]
                load_image = {
                    "id": last_node_id + 1,
                    "type": "LoadImage",
                    "pos": [250, -110],
                    "size": [320, 310],
                    "mode": 0,
                    "outputs": [
                        {
                            "name": "IMAGE",
                            "type": "IMAGE",
                            "links": [],
                            "shape": 3,
                            "label": "图像",
                            "slot_index": 0,
                        },
                        {
                            "name": "MASK",
                            "type": "MASK",
                            "links": None,
                            "shape": 3,
                            "label": "遮罩",
                        },
                    ],
                    "properties": {"Node name for S&R": "LoadImage"},
                    "widgets_values": ["xxx.png", "image"],
                }
                vae_encode = {
                    "id": last_node_id + 2,
                    "type": "VAEEncode",
                    "pos": [640, 10],
                    "size": {0: 210, 1: 50},
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "pixels",
                            "type": "IMAGE",
                            "link": 0,
                            "label": "图像",
                        },
                        {
                            "name": "vae",
                            "type": "VAE",
                            "link": None,
                            "label": "VAE",
                        },
                    ],
                    "outputs": [
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": [],
                            "shape": 3,
                            "label": "Latent",
                            "slot_index": 0,
                        },
                    ],
                    "properties": {"Node name for S&R": "VAEEncode"},
                }
                wk["nodes"].append(load_image)
                wk["nodes"].append(vae_encode)
                wk["last_node_id"] = last_node_id + 2
                self.remove_node_by_id(wk, empty_image["id"])
                self.make_link(wk, load_image, 0, vae_encode, 0)
                self.make_link(wk, checkpoint_loader, 2, vae_encode, 1)
                self.make_link(wk, vae_encode, 0, ksampler, 3)
        if "Model" in params:
            model = params["Model"]  # TODO: 模型得加后缀名字, 和webui不同
            registered_node_types = self.get_registered_node_types()
            node_type = registered_node_types[checkpoint_loader["type"]]
            model_list = node_type.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            for _m in model_list:
                sep_i = _m.rfind("/")
                if _m[sep_i + 1:].split(".")[0] != model:
                    continue
                checkpoint_loader["widgets_values"][0] = _m

        if "Clip skip" in params:
            clip_last_layer["widgets_values"][0] = -int(params["Clip skip"])
        return json.dumps(wk)

    def to_comfyui_format_efficient(self):
        params = self.params.copy()
        wk = self.efficient_workflow()
        loader = wk["nodes"][1]
        ksampler = wk["nodes"][2]
        if "Negative prompt" in params:
            loader["widgets_values"][7] = params["Negative prompt"]
        if "Positive prompt" in params:
            loader["widgets_values"][6] = params["Positive prompt"]
        if "Size" in params:
            width = 512
            height = 512
            if "x" in params["Size"]:
                size_list = params["Size"].split("x")
                width = size_list[0]
                height = size_list[1]
            loader["widgets_values"][10] = width
            loader["widgets_values"][11] = height

        if "Seed" in params:
            ksampler["widgets_values"][0] = params["Seed"]
        if "Steps" in params:
            ksampler["widgets_values"][2] = params["Steps"]
        if "CFG scale" in params:
            ksampler["widgets_values"][3] = params["CFG scale"]
        if "Sampler" in params:
            sampler_name: str = params["Sampler"]
            scheduler_name: str = "normal"
            if "Schedule type" in params:
                sampler_name = params["Sampler"]
                scheduler_name = params["Schedule type"]
            else:
                # samper存储 sampler_name + " " + scheduler_name
                for one_sch_name in self.SCHEDULERNAME_W2C:
                    if one_sch_name in sampler_name:
                        scheduler_name = one_sch_name
                        sampler_name = sampler_name.replace(one_sch_name, "").strip()
                        break

            if sampler_name in self.SAMPLERNAME_W2C:
                ksampler["widgets_values"][4] = self.SAMPLERNAME_W2C[sampler_name]
            if scheduler_name in self.SCHEDULERNAME_W2C:
                ksampler["widgets_values"][5] = self.SCHEDULERNAME_W2C[scheduler_name]
            self._gen_control_net(wk, ksampler, loader, loader)

        if "Denoising strength" in params:
            ksampler["widgets_values"][6] = params["Denoising strength"]
            if float(params["Denoising strength"]) < 1:
                # 图生图, 需要添加图片输入
                last_node_id = wk["last_node_id"]
                load_image = {
                    "id": last_node_id + 1,
                    "type": "输入图像",
                    "pos": [210, -110],
                    "size": {0: 200, 1: 100},
                    "mode": 0,
                    "inputs": [],
                    "outputs": [
                        {
                            "name": "IMAGE",
                            "type": "IMAGE",
                            "links": [],
                            "slot_index": 0
                        },
                        {
                            "name": "MASK",
                            "type": "MASK",
                            "links": [],
                            "slot_index": 1
                        }
                    ],
                    "title": "输入图像",
                    "properties": {},
                    "widgets_values": ["", "输入"]
                }
                vae_encode = {
                    "id": last_node_id + 2,
                    "type": "VAEEncode",
                    "pos": [640, 10],
                    "size": {0: 210, 1: 50},
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "pixels",
                            "type": "IMAGE",
                            "link": 0,
                            "label": "图像",
                        },
                        {
                            "name": "vae",
                            "type": "VAE",
                            "link": None,
                            "label": "VAE",
                        },
                    ],
                    "outputs": [
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": [],
                            "shape": 3,
                            "label": "Latent",
                            "slot_index": 0,
                        },
                    ],
                    "properties": {"Node name for S&R": "VAEEncode"},
                }
                wk["nodes"].append(load_image)
                wk["nodes"].append(vae_encode)
                wk["last_node_id"] = last_node_id + 2
                self.make_link(wk, load_image, 0, vae_encode, 0)
                self.make_link(wk, loader, 4, vae_encode, 1)
                self.make_link(wk, vae_encode, 0, ksampler, 3)
        if "Model" in params:
            model = params["Model"]  # 模型得加后缀名字, 和webui不同
            registered_node_types = self.get_registered_node_types()
            node_type = registered_node_types[loader["type"]]
            model_list = node_type.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            for _m in model_list:
                sep_i = _m.rfind("/")
                if _m[sep_i + 1:].split(".")[0] != model:
                    continue
                loader["widgets_values"][0] = _m

        if "Clip skip" in params:
            loader["widgets_values"][2] = -int(params["Clip skip"])
        return json.dumps(wk)

    def parse(self, text=None):
        self.text = text or self.text
        # self.test()
        self.parse_cn = True
        self._parse(text)
        return self.params

    def _parse(self, text=None):
        if text:
            self.text = text.strip()
            self.params = {}
        self._prompt()
        self._base()
        self._control_net()
        self._ti_hashes()
        self._tiled_diffusion()
        self._adetailer()
        self._version()
        return self.params

    def _prompt(self):
        pp = re.search("^(.*?)Negative prompt:", self.text, re.S)
        if pp:
            pp = pp[1].strip()
            pp_str = pp[:-1].strip() if pp[-1] == "," else pp
            if pp_str.startswith("parameters"):
                pp_str = pp_str[len("parameters"):].strip()
            self.params["Positive prompt"] = pp_str
            self.text = self.text.replace(pp, "").strip()
        np = re.search("(Negative prompt: .*?)(?:Steps: )", self.text, re.S)
        np = np if np else re.search("Negative prompt: (.*?)(?:,\r\n)", self.text, re.S)
        np = np if np else re.search("Negative prompt: (.*?)(?:,\n)", self.text, re.S)
        np = np if np else re.search("Negative prompt: (.*?)(?:\n)", self.text, re.S)
        if np:
            prompt = np[1][len("Negative prompt: "):].strip()
            prompt = prompt[:-1].strip() if prompt[-1] == "," else prompt
            self.params["Negative prompt"] = prompt
            self.text = self.text.replace(np[1], "").strip()

    def _control_net(self):
        if not re.search(r"(Control[nN]et \d+): ", self.text, re.S):
            return

        def parse_cn_params(text):
            params = {}
            new_ver = "preprocessor params: " in text
            if new_ver:
                # Controlnet 0: "preprocessor: dw_openpose_full, model:
                # control_v11p_sd15_openpose, weight: 1.0, starting/ending: (0.0, 1.0),
                # resize mode: Crop and Resize, pixel_perfect: False, control mode:
                # Balanced, preprocessor params: (1024, None, None)",
                preprocessor = re.search("preprocessor: (.*?), ", text, re.S)[1]
                model = re.search("model: (.*?), ", text, re.S)[1]
                weight = re.search("weight: (.*?), ", text, re.S)[1]
                starting_end = re.search(r"starting\/ending: \((.*?)\),", text, re.S)[1]
                starting_end = literal_eval(f"[{starting_end}]") if starting_end else []
                resize_mode = re.search("resize mode: (.*?), ", text, re.S)[1]
                pixel_perfect = re.search("pixel_perfect: (.*?), ", text, re.S)[1] == "True"
                control_mode = re.search("control mode: (.*?),", text, re.S)[1]
                pp_params = re.search(r"preprocessor params: \((.*?)\)", text, re.S)[1]
                # 去掉括号并按逗号分割
                pp_params = literal_eval(f"[{pp_params}]") if pp_params else []

                params = {
                    "preprocessor": preprocessor,
                    "model": model,
                    "weight": weight,
                    "starting_end": starting_end,
                    "resize_mode": resize_mode,
                    "preprocessor_params": pp_params,
                    "pixel_perfect": pixel_perfect,
                    "control_mode": control_mode,
                }
            else:
                # "ControlNet 0": "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
                preprocessor = re.search("Module: (.*?), ", text, re.S)[1]
                model = re.search("Model: (.*?), ", text, re.S)[1]
                weight = re.search("Weight: (.*?), ", text, re.S)[1]
                resize_mode = re.search("Resize Mode: (.*?), ", text, re.S)[1]

                pp_param_res = re.search("Processor Res: (.*?), ", text, re.S)[1]
                pp_param_a = re.search("Threshold A: (.*?), ", text, re.S)[1]
                pp_param_b = re.search("Threshold B: (.*?), ", text, re.S)[1]

                starting = re.search("Guidance Start: (.*?), ", text, re.S)[1]
                end = re.search("Guidance End: (.*?), ", text, re.S)[1]
                pixel_perfect = re.search("Pixel Perfect: (.*?), ", text, re.S)[1]
                pixel_perfect = pixel_perfect == "True"
                control_mode = re.search("Control Mode: (.*?)$", text, re.S)[1]
                params = {
                    "preprocessor": preprocessor,
                    "model": model,
                    "weight": weight,
                    "starting_end": [starting, end],
                    "resize_mode": resize_mode,
                    "preprocessor_params": [pp_param_res, pp_param_a, pp_param_b],
                    "pixel_perfect": pixel_perfect,
                    "control_mode": control_mode,
                }
            return params
        for cn in re.finditer(r'(Control[nN]et \d+): "(.*?)",', self.text, re.S):
            self.params[cn[1]] = parse_cn_params(cn[2]) if self.parse_cn else cn[2]
            self.text = self.text.replace(cn[0], "")

    def _gen_control_net(this, wk, ksampler, out_p, out_n):
        offset = 500
        # CN部分
        load_image_cn = {
            "id": wk["last_node_id"] + 1,
            "type": "LoadImage",
            "pos": [320, 800],
            "mode": 0,
            "outputs": [
                {
                    "name": "IMAGE",
                    "type": "IMAGE",
                    "links": [],
                    "shape": 3,
                    "label": "图像",
                    "slot_index": 0,
                },
                {
                    "name": "MASK",
                    "type": "MASK",
                    "links": None,
                    "shape": 3,
                    "label": "遮罩",
                },
            ],
            "widgets_values": ["xxx.png", "image"],
        }
        wk["nodes"].append(load_image_cn)
        wk["last_node_id"] += 1
        count = -1
        for key, value in this.params.items():
            if not key.lower().startswith("controlnet"):
                continue
            count += 1
            last_node_id = wk["last_node_id"]
            # 新增 aux 集成 preproccessor
            aux_preprocessor = {
                "id": last_node_id + 1,
                "type": "AIO_Preprocessor",
                "pos": [700 + offset * count, 640],
                "mode": 0,
                "inputs": [
                    {
                        "name": "image",
                        "type": "IMAGE",
                        "link": None,
                        "label": "图像",
                    },
                ],
                "outputs": [
                    {
                        "name": "IMAGE",
                        "type": "IMAGE",
                        "links": [],
                        "shape": 3,
                        "label": "图像",
                        "slot_index": 0,
                    },
                ],
                "widgets_values": ["CannyEdgePreprocessor", 512],
            }
            # 新增 apply controlnet
            apply_controlnet = {
                "id": last_node_id + 2,
                "type": "ControlNetApplyAdvanced",
                "pos": [710 + offset * count, 270],
                "mode": 0,
                "inputs": [
                    {
                        "name": "positive",
                        "type": "CONDITIONING",
                        "link": None,
                        "label": "正面条件",
                    },
                    {
                        "name": "negative",
                        "type": "CONDITIONING",
                        "link": None,
                        "label": "负面条件",
                    },
                    {
                        "name": "control_net",
                        "type": "CONTROL_NET",
                        "link": None,
                        "label": "ControlNet",
                    },
                    {
                        "name": "image",
                        "type": "IMAGE",
                        "link": None,
                        "label": "图像",
                    },
                ],
                "outputs": [
                    {
                        "name": "positive",
                        "type": "CONDITIONING",
                        "links": [],
                        "shape": 3,
                        "label": "正面条件",
                        "slot_index": 0,
                    },
                    {
                        "name": "negative",
                        "type": "CONDITIONING",
                        "links": [20],
                        "shape": 3,
                        "label": "负面条件",
                        "slot_index": 1,
                    },
                ],
                "widgets_values": [1, 0, 1],
            }
            controlnet_loader = {
                "id": last_node_id + 3,
                "type": "ControlNetLoader",
                "pos": [720 + offset * count, 500],
                "mode": 0,
                "outputs": [
                    {
                        "name": "CONTROL_NET",
                        "type": "CONTROL_NET",
                        "links": [],
                        "shape": 3,
                        "label": "ControlNet",
                    },
                ],
                "widgets_values": ["xxx.pth", None],
            }
            wk["last_node_id"] += 3
            wk["nodes"].extend([aux_preprocessor, apply_controlnet, controlnet_loader])
            # 参数处理
            if value["preprocessor"] in this.PREPROCESSOR_W2C:
                pmodel = this.PREPROCESSOR_W2C[value["preprocessor"]]
                pmodel = pmodel or aux_preprocessor["widgets_values"][0]
                aux_preprocessor["widgets_values"][0] = pmodel

            aux_preprocessor["widgets_values"][1] = value["preprocessor_params"][0]
            # controlnet_loader["widgets_values"][0] = value["model"]

            cn_model = value["model"]
            if "[" in cn_model and "]" in cn_model:
                cn_model = cn_model[: cn_model.find("[")].strip()
            cn_model2 = cn_model.replace("_", "-")

            registered_node_types = this.get_registered_node_types()
            node_type = registered_node_types[controlnet_loader["type"]]
            ml = node_type.get("input", {}).get("required", {}).get("control_net_name", [[]])[0]
            ml = ml or []
            find_cn_model = ml[0] if ml else ""
            for _m in ml or []:
                sep_i = _m.rfind("/")
                if (_m[:sep_i + 1].split(".")[0] in [cn_model, cn_model2]):
                    find_cn_model = _m
            controlnet_loader["widgets_values"][0] = find_cn_model
            apply_controlnet["widgets_values"][0] = value["weight"]
            apply_controlnet["widgets_values"][1] = value["starting_end"][0]
            apply_controlnet["widgets_values"][2] = value["starting_end"][1]
            this.make_link(wk, load_image_cn, 0, aux_preprocessor, 0)
            this.make_link(wk, controlnet_loader, 0, apply_controlnet, 2)
            this.make_link(wk, aux_preprocessor, 0, apply_controlnet, 3)
            # 完美像素
            if value["pixel_perfect"]:
                aux_preprocessor["inputs"].append({
                    "name": "resolution",
                    "type": "INT",
                    "link": None,
                    "widget": {
                        "name": "resolution",
                    },
                    "label": "分辨率",
                })
                gen_res = {
                    "id": wk["last_node_id"] + 1,
                    "type": "ImageGenResolutionFromImage",
                    "pos": [690 + offset * count, 950],
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "image",
                            "type": "IMAGE",
                            "link": None,
                            "label": "图像",
                        },
                    ],
                    "outputs": [
                        {
                            "name": "IMAGE_GEN_WIDTH (INT)",
                            "type": "INT",
                            "links": [],
                            "shape": 3,
                            "label": "宽度(整数)",
                            "slot_index": 0,
                        },
                        {
                            "name": "IMAGE_GEN_HEIGHT (INT)",
                            "type": "INT",
                            "links": [],
                            "shape": 3,
                            "label": "高度(整数)",
                            "slot_index": 1,
                        },
                    ],
                }
                pixel_perfect = {
                    "id": wk["last_node_id"] + 2,
                    "type": "PixelPerfectResolution",
                    "pos": [680 + offset * count, 780],
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "original_image",
                            "type": "IMAGE",
                            "link": None,
                            "label": "图像",
                        },
                        {
                            "name": "image_gen_width",
                            "type": "INT",
                            "link": None,
                            "widget": {
                                "name": "image_gen_width",
                            },
                            "label": "宽度",
                        },
                        {
                            "name": "image_gen_height",
                            "type": "INT",
                            "link": None,
                            "widget": {
                                "name": "image_gen_height",
                            },
                            "label": "高度",
                        },
                    ],
                    "outputs": [
                        {
                            "name": "RESOLUTION (INT)",
                            "type": "INT",
                            "links": [],
                            "shape": 3,
                            "label": "分辨率(整数)",
                            "slot_index": 0,
                        },
                    ],
                    "widgets_values": [512, 512, "Just Resize"],
                }
                wk["last_node_id"] += 2
                wk["nodes"].extend([gen_res, pixel_perfect])
                this.make_link(wk, load_image_cn, 0, gen_res, 0)
                this.make_link(wk, load_image_cn, 0, pixel_perfect, 0)
                this.make_link(wk, gen_res, 0, pixel_perfect, 1)
                this.make_link(wk, gen_res, 1, pixel_perfect, 2)
                this.make_link(wk, pixel_perfect, 0, aux_preprocessor, 1)

            if out_p["type"] == "Efficient Loader":
                this.make_link(wk, out_p, 1, apply_controlnet, 0)
                this.make_link(wk, out_n, 2, apply_controlnet, 1)
            elif out_p["type"] == "CLIPTextEncode":
                this.make_link(wk, out_p, 0, apply_controlnet, 0)
                this.make_link(wk, out_n, 0, apply_controlnet, 1)
            elif out_p["type"] == "ControlNetApplyAdvanced":
                this.make_link(wk, out_p, 0, apply_controlnet, 0)
                this.make_link(wk, out_n, 1, apply_controlnet, 1)
            out_p = apply_controlnet
            out_n = apply_controlnet
            this.make_link(wk, apply_controlnet, 0, ksampler, 1)
            this.make_link(wk, apply_controlnet, 1, ksampler, 2)
            follow_nodes = [ksampler]
            this.find_following_nodes(wk, ksampler, follow_nodes)
            this.apply_nodes_offset(follow_nodes, (offset, 0))

    def _ti_hashes(self):
        th = re.search('TI hashes: (".*?"),', self.text, re.S)
        if not th:
            return
        self.params["TI hashes"] = th[1].strip()
        self.text = self.text.replace(th[0], "").strip()

    def _tiled_diffusion(self):
        td = re.search("Tiled Diffusion: ({.*?}),", self.text, re.S)
        if not td:
            return
        self.params["Tiled Diffusion"] = td[1].strip()
        self.text = self.text.replace(td[0], "").strip()

    def _adetailer(self):
        ad_p = re.search('ADetailer prompt: (".*?"),', self.text, re.S)
        if ad_p:
            self.params["ADetailer prompt"] = ad_p[1].strip()
            self.text = self.text.replace(ad_p[0], "").strip()
        ads = re.finditer("(ADetailer .*?): (.*?),", self.text, re.S)
        for ad in ads:
            self.params[ad[1]] = ad[2]
            self.text = self.text.replace(ad[0], "")

    def _version(self):
        v = re.search(r"Version: (.*?)(?:.\s|$)", self.text, re.S)
        if not v:
            return
        self.params["Version"] = v[1].strip()
        self.text = self.text.replace(v[0], "").strip()

    def _base(self):
        step = re.search("Steps: (.*?),", self.text, re.S)
        if step:
            self.params["Steps"] = step[1].strip()
            self.text = self.text.replace(step[0], "").strip()
        sampler = re.search("Sampler: (.*?),", self.text, re.S)
        if sampler:
            self.params["Sampler"] = sampler[1].strip()
            self.text = self.text.replace(sampler[0], "").strip()
        scheduler = re.search("Schedule type: (.*?),", self.text, re.S)
        if scheduler:
            self.params["Schedule type"] = scheduler[1].strip()
            self.text = self.text.replace(scheduler[0], "").strip()
        cfg = re.search("CFG scale: (.*?),", self.text, re.S)
        if cfg:
            self.params["CFG scale"] = cfg[1].strip()
            self.text = self.text.replace(cfg[0], "").strip()
        seed = re.search("Seed: (.*?),", self.text, re.S)
        if seed:
            self.params["Seed"] = seed[1].strip()
            self.text = self.text.replace(seed[0], "").strip()
        size = re.search("Size: (.*?),", self.text, re.S)
        if size:
            self.params["Size"] = size[1].strip()
            self.text = self.text.replace(size[0], "").strip()
        model_hash = re.search("Model hash: (.*?),", self.text, re.S)
        if model_hash:
            self.params["Model hash"] = model_hash[1].strip()
            self.text = self.text.replace(model_hash[0], "").strip()
        model = re.search("Model: (.*?),", self.text, re.S)
        if model:
            self.params["Model"] = model[1].strip()
            self.text = self.text.replace(model[0], "").strip()
        denoising = re.search("Denoising strength: (.*?),", self.text, re.S)
        if denoising:
            self.params["Denoising strength"] = denoising[1].strip()
            self.text = self.text.replace(denoising[0], "").strip()
        clip_skip = re.search("Clip skip: (.*?),", self.text, re.S)
        if clip_skip:
            self.params["Clip skip"] = clip_skip[1].strip()
            self.text = self.text.replace(clip_skip[0], "").strip()
        vae = re.search("VAE: (.*?),", self.text, re.S)
        if vae:
            self.params["VAE"] = vae[1].strip()
            self.text = self.text.replace(vae[0], "").strip()
        vae_hash = re.search("VAE hash: (.*?),", self.text, re.S)
        if vae_hash:
            self.params["VAE hash"] = vae_hash[1].strip()
            self.text = self.text.replace(vae_hash[0], "").strip()

    def test(self):
        in_t0 = """
masterpiece,best quality,1girl,
BREAK thighhighs,
BREAK (colorful spot black:1.5),color gradient,
BREAK multicolored background,
Negative prompt: nsfw,nipples,navel,cameltoe,lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,fewer digits,cropped,worst quality,low quality,normal quality,jpeg artifacts,signature,watermark,username,blurry,
Steps: 8, Sampler: DPM++ 2M Karras, CFG scale: 2, Seed: 3627297328, Size: 768x1024, Model hash: bbd321d4a3, Model: raemuXL_v35Lightning, Denoising strength: 0.5, Clip skip: 2, ADetailer model: face_yolov8n.pt, ADetailer prompt: "black eyes, black hair, ", ADetailer confidence: 0.3, ADetailer dilate erode: 4, ADetailer mask blur: 4, ADetailer denoising strength: 0.4, ADetailer inpaint only masked: True, ADetailer inpaint padding: 32, ADetailer version: 24.5.1, Hires upscale: 2, Hires steps: 4, Hires upscaler: ESRGAN_4x, Downcast alphas_cumprod: True, Version: 1.8.0-RC
        """
        out_t0 = {
            "Positive prompt": """
masterpiece,best quality,1girl,
BREAK thighhighs,
BREAK (colorful spot black:1.5),color gradient,
BREAK multicolored background
            """.strip(),
            "Negative prompt": "nsfw,nipples,navel,cameltoe,lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,fewer digits,cropped,worst quality,low quality,normal quality,jpeg artifacts,signature,watermark,username,blurry",
            "Steps": "8",
            "Sampler": "DPM++ 2M Karras",
            "CFG scale": "2",
            "Seed": "3627297328",
            "Size": "768x1024",
            "Model hash": "bbd321d4a3",
            "Model": "raemuXL_v35Lightning",
            "Denoising strength": "0.5",
            "Clip skip": "2",
            "ADetailer model": "face_yolov8n.pt",
            "ADetailer prompt": "\"black eyes, black hair, \"",
            "ADetailer confidence": "0.3",
            "ADetailer dilate erode": "4",
            "ADetailer mask blur": "4",
            "ADetailer denoising strength": "0.4",
            "ADetailer inpaint only masked": "True",
            "ADetailer inpaint padding": "32",
            "ADetailer version": "24.5.1",
            # "Hires upscale": "2",
            # "Hires steps": "4",
            # "Hires upscaler": "ESRGAN_4x",
            # "Downcast alphas_cumprod": "True",
            "Version": "1.8.0-RC"
        }
        assert self._parse(in_t0) == out_t0, "Test 0 failed"
        in_t1 = """
masterpiece,ultra high quality,highest quality,super fine,1girl,solo,(black background:1.3),(silhouette:1.1),sparkle,looking at viewer,upper body,simple background,glowing,(dim lighting:1.2),crystal clear,colorful clothes,
Negative prompt: Easy Negative,bad handv4,ng_deepnegative_v1_75t,(worst quality:2),(low quality:2),(normal quality:2),lowres,((monochrome)),((grayscale)),bad anatomy,DeepNegative,skin spots,acnes,skin blemishes,(fat:1.2),facing away,looking away,tilted head,lowres,bad anatomy,bad hands,missing fingers,extra digit,fewer digits,bad feet,poorly drawn hands,poorly drawn face,mutation,deformed,extra fingers,extra limbs,extra arms,extra legs,malformed limbs,fused fingers,too many fingers,long neck,cross-eyed,mutated hands,polar lowres,bad body,bad proportions,gross proportions,missing arms,missing legs,extra digit,extra arms,extra leg,extra foot,teethcroppe,signature,watermark,username,blurry,cropped,jpeg artifacts,text,Lower body exposure,
Steps: 30, Sampler: UniPC, Schedule type: Karras, CFG scale: 7, Seed: 3620085674, Size: 1024x1536, Model hash: 3d1b3c42ec, Model: AWPainting_v1.2, ControlNet 0: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced", TI hashes: "ng_deepnegative_v1_75t: 54e7e4826d53", Pad conds: True, Version: v1.9.4
        """
        out_t1 = {
            "Positive prompt": "masterpiece,ultra high quality,highest quality,super fine,1girl,solo,(black background:1.3),(silhouette:1.1),sparkle,looking at viewer,upper body,simple background,glowing,(dim lighting:1.2),crystal clear,colorful clothes",
            "Negative prompt": "Easy Negative,bad handv4,ng_deepnegative_v1_75t,(worst quality:2),(low quality:2),(normal quality:2),lowres,((monochrome)),((grayscale)),bad anatomy,DeepNegative,skin spots,acnes,skin blemishes,(fat:1.2),facing away,looking away,tilted head,lowres,bad anatomy,bad hands,missing fingers,extra digit,fewer digits,bad feet,poorly drawn hands,poorly drawn face,mutation,deformed,extra fingers,extra limbs,extra arms,extra legs,malformed limbs,fused fingers,too many fingers,long neck,cross-eyed,mutated hands,polar lowres,bad body,bad proportions,gross proportions,missing arms,missing legs,extra digit,extra arms,extra leg,extra foot,teethcroppe,signature,watermark,username,blurry,cropped,jpeg artifacts,text,Lower body exposure",
            "Steps": "30",
            "Sampler": "UniPC",
            "Schedule type": "Karras",
            "CFG scale": "7",
            "Seed": "3620085674",
            "Size": "1024x1536",
            "Model hash": "3d1b3c42ec",
            "Model": "AWPainting_v1.2",
            "ControlNet 0": "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.6, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced",
            "TI hashes": "\"ng_deepnegative_v1_75t: 54e7e4826d53\"",
            # "Pad conds": "True",
            "Version": "v1.9.4"
        }
        assert self._parse(in_t1) == out_t1, "Test 1 failed"

        in_t2 = """
(official art:1.2),(colorful:1.1),(masterpiece:1.2),best quality,masterpiece,highres,original,extremely detailed wallpaper,1girl,solo,very long hair,(loli:1.3),vibrant color palette,dazzling hues,kaleidoscopic patterns,enchanting young maiden,radiant beauty,chromatic harmony,iridescent hair,sparkling eyes,lush landscapes,vivid blossoms,mesmerizing sunsets,brilliant rainbows,prismatic reflections,whimsical attire,captivating accessories,stunning chromatic display,artful composition,picturesque backdrop,breathtaking scenery,visual symphony,spellbinding chromatic enchantment,
(shiny:1.2),(Oil highlights:1.2),[wet with oil:0.7],(shiny:1.2),[wet with oil:0.5],
Negative prompt: (worst quality, low quality, blurry:1.5),(bad hands:1.4),watermark,(greyscale:0.88),multiple limbs,(deformed fingers, bad fingers:1.2),(ugly:1.3),monochrome,horror,geometry,bad anatomy,bad limbs,(Blurry pupil),(bad shading),error,bad composition,Extra fingers,NSFW,badhandv4,charturnerv2,corneo_dva,EasyNegative,EasyNegativeV2,ng_deepnegative_v1_75t,
Steps: 25, Sampler: Euler, Schedule type: Automatic, CFG scale: 7, Seed: 848680687, Size: 1024x1536, Model hash: 099e07547a, Model: Dark Sushi Mix 大颗寿司Mix_BrighterPruned, VAE hash: f921fb3f29, VAE: kl-f8-anime2.ckpt, Denoising strength: 0.75, Clip skip: 2, Tiled Diffusion: {"Method": "MultiDiffusion", "Tile tile width": 96, "Tile tile height": 96, "Tile Overlap": 48, "Tile batch size": 4, "Keep input size": true, "NoiseInv": true, "NoiseInv Steps": 10, "NoiseInv Retouch": 1, "NoiseInv Renoise strength": 0.5, "NoiseInv Kernel size": 64}, ControlNet 0: "Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.5, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced", Pad conds: True, Version: v1.9.4
        """
        out_t2 = {
            "Positive prompt": """
parameters(official art:1.2),(colorful:1.1),(masterpiece:1.2),best quality,masterpiece,highres,original,extremely detailed wallpaper,1girl,solo,very long hair,(loli:1.3),vibrant color palette,dazzling hues,kaleidoscopic patterns,enchanting young maiden,radiant beauty,chromatic harmony,iridescent hair,sparkling eyes,lush landscapes,vivid blossoms,mesmerizing sunsets,brilliant rainbows,prismatic reflections,whimsical attire,captivating accessories,stunning chromatic display,artful composition,picturesque backdrop,breathtaking scenery,visual symphony,spellbinding chromatic enchantment,
(shiny:1.2),(Oil highlights:1.2),[wet with oil:0.7],(shiny:1.2),[wet with oil:0.5]
            """.strip(),
            "Negative prompt": "(worst quality, low quality, blurry:1.5),(bad hands:1.4),watermark,(greyscale:0.88),multiple limbs,(deformed fingers, bad fingers:1.2),(ugly:1.3),monochrome,horror,geometry,bad anatomy,bad limbs,(Blurry pupil),(bad shading),error,bad composition,Extra fingers,NSFW,badhandv4,charturnerv2,corneo_dva,EasyNegative,EasyNegativeV2,ng_deepnegative_v1_75t",
            "Steps": "25",
            "Sampler": "Euler",
            "Schedule type": "Automatic",
            "CFG scale": "7",
            "Seed": "848680687",
            "Size": "1024x1536",
            "Model hash": "099e07547a",
            "Model": "Dark Sushi Mix 大颗寿司Mix_BrighterPruned",
            "VAE hash": "f921fb3f29",
            "VAE": "kl-f8-anime2.ckpt",
            "Denoising strength": "0.75",
            "Clip skip": "2",
            "Tiled Diffusion": '{"Method": "MultiDiffusion", "Tile tile width": 96, "Tile tile height": 96, "Tile Overlap": 48, "Tile batch size": 4, "Keep input size": true, "NoiseInv": true, "NoiseInv Steps": 10, "NoiseInv Retouch": 1, "NoiseInv Renoise strength": 0.5, "NoiseInv Kernel size": 64}',
            "ControlNet 0": 'Module: tile_resample, Model: control_v11f1e_sd15_tile_fp16 [3b860298], Weight: 0.5, Resize Mode: Crop and Resize, Processor Res: 512, Threshold A: 1.0, Threshold B: 0.5, Guidance Start: 0.0, Guidance End: 1.0, Pixel Perfect: True, Control Mode: Balanced',
            # "Pad conds": "True",
            "Version": "v1.9.4",
        }
        assert self._parse(in_t2) == out_t2, "Test 2 failed"
        in_t3 = """
masterpiece, best quality, girl,woman,female, short hair, light smile, closed_eyes, cat_ears, overskirt,white dress,frills, pale blue Clothes,tiara
Negative prompt: easynegative, ng_deepnegative_v1_75t, By bad artist -neg, verybadimagenegative_v1.3
Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 3850677924, Size: 768x1024, Model hash: 19dbfda152, Model: 二次元_mixProV45Colorbox_v45, Clip skip: 2, ENSD: 31337
        """
        out_t3 = {
            "Positive prompt": """
masterpiece, best quality, girl,woman,female, short hair, light smile, closed_eyes, cat_ears, overskirt,white dress,frills, pale blue Clothes,tiara
          """.strip(),
            "Negative prompt": "easynegative, ng_deepnegative_v1_75t, By bad artist -neg, verybadimagenegative_v1.3",
            "Steps": "20",
            "Sampler": "Euler a",
            "CFG scale": "7",
            "Seed": "3850677924",
            "Size": "768x1024",
            "Model hash": "19dbfda152",
            "Model": "二次元_mixProV45Colorbox_v45",
            "Clip skip": "2",
        }
        assert self._parse(in_t3) == out_t3, "Test 3 failed"
        in_t4 = """
masterpiece, best quality, 1girl, solo, voxel art,
gazebo, white girl,
rust hair, ochre eyes,
long hair, folded ponytail,
evening gown, trim dress,
ribbon, Gift Hat Hair Band , Opera-length necklaces, Arm harnesses,
classic, medieval, noble
Negative prompt: lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, badhandv4, easynegative, ng_deepnegative_v1_75t, verybadimagenegative_v1.3
Steps: 20, Sampler: Euler a, CFG scale: 7, Seed: 1825312441, Size: 640x960, Model hash: 149fe7d36c, Model: 二次元_meinaalter_v1, ENSD: 31337, Wildcard prompt: "masterpiece, best quality, 1girl, solo, voxel art,
__scene-location__, white girl,
__color__ hair, __color__ eyes,
__character-hair-Size__, __character-hair-Style__,
__character-clothing-Dress__, trim dress,
ribbon, __character-accessories-Hair__, __character-accessories-Neck__, __character-accessories-Arm__,
classic, medieval, noble"
        """
        out_t4 = {
            "Positive prompt": """
masterpiece, best quality, 1girl, solo, voxel art,
gazebo, white girl,
rust hair, ochre eyes,
long hair, folded ponytail,
evening gown, trim dress,
ribbon, Gift Hat Hair Band , Opera-length necklaces, Arm harnesses,
classic, medieval, noble
          """.strip(),
            "Negative prompt": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, badhandv4, easynegative, ng_deepnegative_v1_75t, verybadimagenegative_v1.3",
            "Steps": "20",
            "Sampler": "Euler a",
            "CFG scale": "7",
            "Seed": "1825312441",
            "Size": "640x960",
            "Model hash": "149fe7d36c",
            "Model": "二次元_meinaalter_v1",
        }
        assert self._parse(in_t4) == out_t4, "Test 4 failed"

    def base_workflow(self):
        wk = {
            "last_node_id": 11,
            "last_link_id": 13,
            "nodes": [
                {
                    "id": 7,
                    "type": "CLIPTextEncode",
                    "pos": [
                        413,
                        389
                    ],
                    "size": {
                        "0": 425.27801513671875,
                        "1": 180.6060791015625
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "clip",
                            "type": "CLIP",
                            "link": 12,
                            "label": "CLIP"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "CONDITIONING",
                            "type": "CONDITIONING",
                            "links": [
                                6
                            ],
                            "slot_index": 0,
                            "label": "条件"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "CLIPTextEncode"
                    },
                    "widgets_values": [
                        "text, watermark"
                    ]
                },
                {
                    "id": 6,
                    "type": "CLIPTextEncode",
                    "pos": [
                        415,
                        186
                    ],
                    "size": {
                        "0": 422.84503173828125,
                        "1": 164.31304931640625
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "clip",
                            "type": "CLIP",
                            "link": 11,
                            "label": "CLIP"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "CONDITIONING",
                            "type": "CONDITIONING",
                            "links": [
                                4
                            ],
                            "slot_index": 0,
                            "label": "条件"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "CLIPTextEncode"
                    },
                    "widgets_values": [
                        "beautiful scenery nature glass bottle landscape, , purple galaxy bottle,"
                    ]
                },
                {
                    "id": 5,
                    "type": "EmptyLatentImage",
                    "pos": [
                        473,
                        609
                    ],
                    "size": {
                        "0": 315,
                        "1": 106
                    },
                    "mode": 0,
                    "outputs": [
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": [
                                2
                            ],
                            "slot_index": 0,
                            "label": "Latent"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "EmptyLatentImage"
                    },
                    "widgets_values": [
                        512,
                        512,
                        1
                    ]
                },
                {
                    "id": 3,
                    "type": "KSampler",
                    "pos": [
                        863,
                        186
                    ],
                    "size": {
                        "0": 315,
                        "1": 262
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "model",
                            "type": "MODEL",
                            "link": 1,
                            "label": "模型"
                        },
                        {
                            "name": "positive",
                            "type": "CONDITIONING",
                            "link": 4,
                            "label": "正面条件"
                        },
                        {
                            "name": "negative",
                            "type": "CONDITIONING",
                            "link": 6,
                            "label": "负面条件"
                        },
                        {
                            "name": "latent_image",
                            "type": "LATENT",
                            "link": 2,
                            "label": "Latent"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": [
                                7
                            ],
                            "slot_index": 0,
                            "label": "Latent"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "KSampler"
                    },
                    "widgets_values": [
                        156680208700286,
                        "fixed",
                        20,
                        8,
                        "euler",
                        "normal",
                        1
                    ]
                },
                {
                    "id": 8,
                    "type": "VAEDecode",
                    "pos": [
                        1209,
                        188
                    ],
                    "size": {
                        "0": 210,
                        "1": 46
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "samples",
                            "type": "LATENT",
                            "link": 7,
                            "label": "Latent"
                        },
                        {
                            "name": "vae",
                            "type": "VAE",
                            "link": 8,
                            "label": "VAE"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "IMAGE",
                            "type": "IMAGE",
                            "links": [
                                9,
                                13
                            ],
                            "slot_index": 0,
                            "label": "图像"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "VAEDecode"
                    }
                },
                {
                    "id": 9,
                    "type": "SaveImage",
                    "pos": [
                        1451,
                        189
                    ],
                    "size": {
                        "0": 210,
                        "1": 58
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "images",
                            "type": "IMAGE",
                            "link": 9,
                            "label": "图像"
                        }
                    ],
                    "properties": {},
                    "widgets_values": [
                        "ComfyUI"
                    ]
                },
                {
                    "id": 4,
                    "type": "CheckpointLoaderSimple",
                    "pos": [
                        -348,
                        179
                    ],
                    "size": {
                        "0": 315,
                        "1": 98
                    },
                    "mode": 0,
                    "outputs": [
                        {
                            "name": "MODEL",
                            "type": "MODEL",
                            "links": [
                                1
                            ],
                            "slot_index": 0,
                            "label": "模型"
                        },
                        {
                            "name": "CLIP",
                            "type": "CLIP",
                            "links": [
                                10
                            ],
                            "slot_index": 1,
                            "label": "CLIP"
                        },
                        {
                            "name": "VAE",
                            "type": "VAE",
                            "links": [
                                8
                            ],
                            "slot_index": 2,
                            "label": "VAE"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "CheckpointLoaderSimple"
                    },
                    "widgets_values": [
                        "mixProV4_v4.safetensors"
                    ]
                },
                {
                    "id": 10,
                    "type": "CLIPSetLastLayer",
                    "pos": [
                        17,
                        181
                    ],
                    "size": {
                        "0": 315,
                        "1": 58
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "clip",
                            "type": "CLIP",
                            "link": 10,
                            "label": "CLIP"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "CLIP",
                            "type": "CLIP",
                            "links": [
                                11,
                                12
                            ],
                            "shape": 3,
                            "label": "CLIP",
                            "slot_index": 0
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "CLIPSetLastLayer"
                    },
                    "widgets_values": [
                        -1
                    ]
                },
                {
                    "id": 11,
                    "type": "PreviewImage",
                    "pos": [
                        1450,
                        380
                    ],
                    "size": {
                        "0": 210,
                        "1": 30
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "images",
                            "type": "IMAGE",
                            "link": 13,
                            "label": "图像"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "PreviewImage"
                    }
                },
            ],
            "links": [
                [
                    1,
                    4,
                    0,
                    3,
                    0,
                    "MODEL"
                ],
                [
                    2,
                    5,
                    0,
                    3,
                    3,
                    "LATENT"
                ],
                [
                    4,
                    6,
                    0,
                    3,
                    1,
                    "CONDITIONING"
                ],
                [
                    6,
                    7,
                    0,
                    3,
                    2,
                    "CONDITIONING"
                ],
                [
                    7,
                    3,
                    0,
                    8,
                    0,
                    "LATENT"
                ],
                [
                    8,
                    4,
                    2,
                    8,
                    1,
                    "VAE"
                ],
                [
                    9,
                    8,
                    0,
                    9,
                    0,
                    "IMAGE"
                ],
                [
                    10,
                    4,
                    1,
                    10,
                    0,
                    "CLIP"
                ],
                [
                    11,
                    10,
                    0,
                    6,
                    0,
                    "CLIP"
                ],
                [
                    12,
                    10,
                    0,
                    7,
                    0,
                    "CLIP"
                ],
                [
                    13,
                    8,
                    0,
                    11,
                    0,
                    "IMAGE"
                ],
            ],
            "groups": [],
            "config": {},
            "extra": {
                "ds": {
                    "scale": 1.2100000000000004,
                    "offset": [
                        253.97393794242356,
                        53.4865032972739
                    ]
                }
            },
            "version": 0.4
        }
        return wk

    def efficient_workflow(self):
        wk = {
            "last_node_id": 5,
            "last_link_id": 9,
            "nodes": [
                {
                    "id": 4,
                    "type": "SaveImage",
                    "pos": [
                        1040,
                        250
                    ],
                    "size": {
                        "0": 320,
                        "1": 60
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "images",
                            "type": "IMAGE",
                            "link": 8,
                            "label": "图像"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "SaveImage"
                    },
                    "widgets_values": [
                        "ComfyUI"
                    ]
                },
                {
                    "id": 2,
                    "type": "Efficient Loader",
                    "pos": [
                        210,
                        250
                    ],
                    "size": {
                        "0": 400,
                        "1": 462
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "lora_stack",
                            "type": "LORA_STACK",
                            "link": None,
                            "label": "LoRA堆"
                        },
                        {
                            "name": "cnet_stack",
                            "type": "CONTROL_NET_STACK",
                            "link": None,
                            "label": "ControlNet堆"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "MODEL",
                            "type": "MODEL",
                            "links": [
                                7
                            ],
                            "shape": 3,
                            "label": "模型",
                            "slot_index": 0
                        },
                        {
                            "name": "CONDITIONING+",
                            "type": "CONDITIONING",
                            "links": [
                                3
                            ],
                            "shape": 3,
                            "label": "正面条件",
                            "slot_index": 1
                        },
                        {
                            "name": "CONDITIONING-",
                            "type": "CONDITIONING",
                            "links": [
                                4
                            ],
                            "shape": 3,
                            "label": "负面条件",
                            "slot_index": 2
                        },
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": [
                                5
                            ],
                            "shape": 3,
                            "label": "Latent",
                            "slot_index": 3
                        },
                        {
                            "name": "VAE",
                            "type": "VAE",
                            "links": [
                                6
                            ],
                            "shape": 3,
                            "label": "VAE",
                            "slot_index": 4
                        },
                        {
                            "name": "CLIP",
                            "type": "CLIP",
                            "links": None,
                            "shape": 3,
                            "label": "CLIP"
                        },
                        {
                            "name": "DEPENDENCIES",
                            "type": "DEPENDENCIES",
                            "links": None,
                            "shape": 3,
                            "label": "依赖"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "Efficient Loader"
                    },
                    "widgets_values": [
                        "animagineXLV3_v30.safetensors",
                        "Baked VAE",
                        -1,
                        "None",
                        1,
                        1,
                        "CLIP_POSITIVE",
                        "CLIP_NEGATIVE",
                        "none",
                        "A1111",
                        512,
                        512,
                        1
                    ],
                    "bgcolor": "#335555",
                    "shape": 1
                },
                {
                    "id": 1,
                    "type": "KSampler (Efficient)",
                    "pos": [
                        660,
                        250
                    ],
                    "size": {
                        "0": 330,
                        "1": 370
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "model",
                            "type": "MODEL",
                            "link": 7,
                            "label": "模型",
                            "slot_index": 0
                        },
                        {
                            "name": "positive",
                            "type": "CONDITIONING",
                            "link": 3,
                            "label": "正面条件"
                        },
                        {
                            "name": "negative",
                            "type": "CONDITIONING",
                            "link": 4,
                            "label": "负面条件"
                        },
                        {
                            "name": "latent_image",
                            "type": "LATENT",
                            "link": 5,
                            "label": "Latent"
                        },
                        {
                            "name": "optional_vae",
                            "type": "VAE",
                            "link": 6,
                            "label": "VAE(可选)"
                        },
                        {
                            "name": "script",
                            "type": "SCRIPT",
                            "link": None,
                            "label": "脚本"
                        }
                    ],
                    "outputs": [
                        {
                            "name": "MODEL",
                            "type": "MODEL",
                            "links": None,
                            "shape": 3,
                            "label": "模型"
                        },
                        {
                            "name": "CONDITIONING+",
                            "type": "CONDITIONING",
                            "links": None,
                            "shape": 3,
                            "label": "正面条件"
                        },
                        {
                            "name": "CONDITIONING-",
                            "type": "CONDITIONING",
                            "links": None,
                            "shape": 3,
                            "label": "负面条件"
                        },
                        {
                            "name": "LATENT",
                            "type": "LATENT",
                            "links": None,
                            "shape": 3,
                            "label": "Latent"
                        },
                        {
                            "name": "VAE",
                            "type": "VAE",
                            "links": None,
                            "shape": 3,
                            "label": "VAE"
                        },
                        {
                            "name": "IMAGE",
                            "type": "IMAGE",
                            "links": [
                                8,
                                9
                            ],
                            "shape": 3,
                            "label": "图像",
                            "slot_index": 5
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "KSampler (Efficient)"
                    },
                    "widgets_values": [
                        800315283332510,
                        "fixed",
                        20,
                        7,
                        "euler",
                        "normal",
                        1,
                        "auto",
                        "true"
                    ],
                    "bgcolor": "#333355",
                    "shape": 1
                },
                {
                    "id": 5,
                    "type": "PreviewImage",
                    "pos": [
                        1050,
                        520
                    ],
                    "size": {
                        "0": 210,
                        "1": 30
                    },
                    "mode": 0,
                    "inputs": [
                        {
                            "name": "images",
                            "type": "IMAGE",
                            "link": 9,
                            "label": "图像"
                        }
                    ],
                    "properties": {
                        "Node name for S&R": "PreviewImage"
                    }
                }
            ],
            "links": [
                [
                    3,
                    2,
                    1,
                    1,
                    1,
                    "CONDITIONING"
                ],
                [
                    4,
                    2,
                    2,
                    1,
                    2,
                    "CONDITIONING"
                ],
                [
                    5,
                    2,
                    3,
                    1,
                    3,
                    "LATENT"
                ],
                [
                    6,
                    2,
                    4,
                    1,
                    4,
                    "VAE"
                ],
                [
                    7,
                    2,
                    0,
                    1,
                    0,
                    "MODEL"
                ],
                [
                    8,
                    1,
                    5,
                    4,
                    0,
                    "IMAGE"
                ],
                [
                    9,
                    1,
                    5,
                    5,
                    0,
                    "IMAGE"
                ]
            ],
            "groups": [],
            "config": {},
            "extra": {
                "ds": {
                    "scale": 1.2100000000000006,
                    "offset": [
                        -639.1956340693308,
                        -38.20042379820701
                    ]
                }
            },
            "version": 0.4
        }
        return wk


if __name__ == "__main__":
    webui_parser = WebUIToComfyUI("")
    webui_parser.test()
