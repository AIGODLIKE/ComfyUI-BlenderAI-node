import os
import json
import sys
import traceback
import numpy as np
import builtins
import torch
import shutil
import hashlib
import atexit
import server
import gc
import execution
import folder_paths
import nodes
import time
import logging as logger
from threading import Thread
from aiohttp import web
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo

FORCE_LOG = False
CATEGORY_ = "Blender"
TEMPDIR = Path(__file__).parent.parent / "SDNodeTemp"
HOST_PATH = Path("XXXHOST-PATHXXX")


def removetemp():
    try:
        if TEMPDIR.exists():
            shutil.rmtree(TEMPDIR, ignore_errors=True)
        TEMPDIR.mkdir(parents=True)
    except Exception as e:
        sys.stdout.write(e)


removetemp()


def execute_wrap():
    def exec_wrap(func):
        def wrap(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                traceback.print_exc()
                sys.stdout.flush()
        return wrap

    execution.PromptExecutor.execute = exec_wrap(execution.PromptExecutor.execute)


execute_wrap()

atexit.register(removetemp)


def hk(func):
    def __print_wrap__(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except BaseException:
            ...
        sys.stdout.flush()
        # sys.stderr.flush()
    return __print_wrap__


if FORCE_LOG:
    __print_wrap__ = hk(print)
    globals()["__print_wrap__"] = __print_wrap__
    builtins.print = __print_wrap__

    sys.stdout.write = hk(sys.stdout.write)
    sys.stderr.write = hk(sys.stderr.write)
    # sys.stderr.write = builtins.print


def try_write_config():
    config_path = HOST_PATH.joinpath("PATH_CFG.json")
    from folder_paths import folder_names_and_paths
    config = {}
    for k in folder_names_and_paths:
        config[k] = list(folder_names_and_paths[k])
        if isinstance(config[k][1], set):
            config[k][1] = list(config[k][1])
    Path(config_path).write_text(json.dumps(config, indent=4))


try:
    try_write_config()
except Exception as e:
    sys.stdout.write("Config Export Error")
    sys.stdout.write(str(e))
    sys.stdout.flush()

CACHED_EXECUTOR = []


@server.PromptServer.instance.routes.post("/cup/clear_cache")
async def clear_cache(request):
    inst = server.PromptServer.instance
    if inst.prompt_queue:
        inst.prompt_queue.history.clear()
    if not CACHED_EXECUTOR:
        CACHED_EXECUTOR.extend([ob for ob in gc.get_objects() if isinstance(ob, execution.PromptExecutor)])
    for ob in CACHED_EXECUTOR:
        print("Clear Node Tree Cache", ob)
        ob.outputs.clear()
        ob.outputs_ui.clear()
        ob.old_prompt.clear()
    return web.Response(status=200)


def node_info(node_class):
    """
    ref: ComfyUI/server.py PromptServer
    """
    obj_class = nodes.NODE_CLASS_MAPPINGS[node_class]
    info = {}
    info['input'] = obj_class.INPUT_TYPES()
    info['output'] = obj_class.RETURN_TYPES
    info['output_is_list'] = obj_class.OUTPUT_IS_LIST if hasattr(obj_class, 'OUTPUT_IS_LIST') else [False] * len(obj_class.RETURN_TYPES)
    info['output_name'] = obj_class.RETURN_NAMES if hasattr(obj_class, 'RETURN_NAMES') else info['output']
    info['name'] = node_class
    info['display_name'] = nodes.NODE_DISPLAY_NAME_MAPPINGS[node_class] if node_class in nodes.NODE_DISPLAY_NAME_MAPPINGS.keys() else node_class
    info['description'] = ''
    info['category'] = 'sd'
    if hasattr(obj_class, 'OUTPUT_NODE') and obj_class.OUTPUT_NODE == True:
        info['output_node'] = True
    else:
        info['output_node'] = False
    if hasattr(obj_class, 'CATEGORY'):
        info['category'] = obj_class.CATEGORY
    return info


CACHED_NODES = {}


def update_cached_nodes():
    filter_node = {"Note", "PrimitiveNode", "Cache Node"}
    diff = {}
    for x in nodes.NODE_CLASS_MAPPINGS:
        if x in filter_node:
            continue
        ni = node_info(x)
        if x not in CACHED_NODES:
            diff[x] = ni
        elif CACHED_NODES[x] != ni:
            diff[x] = ni
        CACHED_NODES[x] = ni
    if not diff or diff == CACHED_NODES:
        return
    with HOST_PATH.joinpath("diff_object_info.json").open("w") as fp:
        json.dump(diff, fp)


def diff_listen_loop():
    while True:
        time.sleep(5)
        update_cached_nodes()


Thread(target=diff_listen_loop, daemon=True).start()


@server.PromptServer.instance.routes.post("/cup/get_temp_directory")
async def get_temp_directory(request):
    return web.Response(status=200, body=folder_paths.get_temp_directory())


class ToBlender:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "批次": ("INT", {
                    "default": 0,
                    "min": 0,  # Minimum value
                    "max": 4096,  # Maximum value
                    "step": 64  # Slider's step
                }),
                "降噪": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "日志": (["enable", "disable"],)
            },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "saveto"
    CATEGORY = CATEGORY_

    def saveto(self, image, 批次, 降噪, 日志):
        image = 1.0 - image
        return (image,)


class SaveImage:
    OO = Path.home().joinpath("Desktop")

    def __init__(self):
        self.output_dir = Path.home().joinpath("Desktop")

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                {"images": ("IMAGE", ),
                 "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                 "output_dir": ("STRING", {"default": str(SaveImage.OO.absolute())}),
                 },
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }

    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = CATEGORY_

    def save_images(self, images, filename_prefix="ComfyUI", output_dir=str(OO.absolute()), prompt=None, extra_pnginfo=None):
        logger.debug(f'saving {len(images)} images to {output_dir}')
        self.output_dir = output_dir

        def map_filename(filename):
            prefix_len = len(filename_prefix)
            prefix = filename[:prefix_len + 1]
            try:
                digits = int(filename[prefix_len + 1:].split('_')[0])
            except BaseException:
                digits = 0
            return (digits, prefix)
        try:
            counter = max(filter(lambda a: a[1][:-1] == filename_prefix and a[1][-1] == "_", map(map_filename, os.listdir(self.output_dir))))[0] + 1
        except ValueError:
            counter = 1
        except FileNotFoundError:
            os.mkdir(self.output_dir)
            counter = 1

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        output_dir = Path(self.output_dir)
        paths = list()
        for image in images:
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))
            file = f"{filename_prefix}_{counter:05}_.png"
            save_path = output_dir / file
            img.save(save_path, pnginfo=metadata, optimize=True)
            paths.append(str(save_path))
            counter += 1
        # print(self.output_dir)
        # print({"ui": {"images": paths}})
        return {"ui": {"images": paths}}


class PreviewImage:
    def __init__(self):
        self.output_dir = TEMPDIR

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                {"images": ("IMAGE", ), }
                }
    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = CATEGORY_

    def save_images(self, images):
        return SaveImage.save_images(self, images, "Temp", self.output_dir)


class LoadImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
                "mode": (["输入", "渲染", "序列图"], ),
            },
        }

    CATEGORY = CATEGORY_

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"

    def load_image(self, image, mode=None):
        try:
            image_path = image
            i = Image.open(image_path)
            if 'P' in i.getbands():
                i = i.convert("RGBA")
                image = i.convert("RGB")
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
        except Exception as e:
            sys.stderr.write(f"|已忽略| Load Image Error -> {e}")
            sys.stderr.flush()
            image = np.zeros(shape=(64, 64, 3)).astype(np.float32)
            image = torch.from_numpy(image)[None,]
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            return (image, mask)
        if 'A' in i.getbands():
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        return (image, mask)

    @classmethod
    def IS_CHANGED(s, image, mode):
        image_path = image
        if not os.path.exists(image_path):
            return ""
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()


class MatImage(LoadImage):
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
            },
        }


class Mask:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
                "channel": (["alpha", "red", "green", "blue"], ),
            }
        }

    CATEGORY = CATEGORY_

    RETURN_TYPES = ("MASK",)
    FUNCTION = "load_image"

    def load_image(self, image, channel):
        image_path = image
        try:
            i = Image.open(image_path)
        except FileNotFoundError:
            print(f"FileNotFound -> {image_path}")
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            return (mask,)
        mask = None
        c = channel[0].upper()
        if c in i.getbands():
            mask = np.array(i.getchannel(c)).astype(np.float32) / 255.0
            mask = torch.from_numpy(mask)
            if c == 'A':
                mask = 1. - mask
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        return (mask,)

    @classmethod
    def IS_CHANGED(s, image, channel):
        image_path = image
        image_path = Path(image_path)
        if not image or not image_path.exists():
            return ""
        return Path(image_path).stat().st_mtime_ns


class OpenPoseBase:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
                "frame": ("INT", {
                    "default": 0,
                    "min": -2**31,  # Minimum value
                    "max": 2**31,  # Maximum value
                    "step": 1  # Slider's step
                }),
            },
        }

    CATEGORY = "OpenPose"

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"

    posetype = ""

    def load_image(self, image, frame):
        try:
            img_dir = Path(image) / self.posetype
            find_img = ""
            for file in img_dir.iterdir():
                if not file.name.startswith("Image"):
                    continue

                f = int(file.name[len("Image"): -len(file.suffix)])
                if f == frame:
                    find_img = file.as_posix()
            if not find_img:
                sys.stderr.write(f"|错误| Frame Not Found -> Image{frame:04}.png")
                sys.stderr.flush()
            image_path = find_img

            i = Image.open(image_path)
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
        except Exception as e:
            sys.stderr.write(f"|已忽略| Load Image Error -> {e}")
            sys.stderr.flush()
            image = np.zeros(shape=(64, 64, 3)).astype(np.float32)
            image = torch.from_numpy(image)[None,]
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
            return (image, mask)
        if 'A' in i.getbands():
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")
        return (image, mask)

    @classmethod
    def IS_CHANGED(s, image, frame):
        image_path = image
        if not os.path.exists(image_path):
            return ""
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()


class OpenPoseFull(OpenPoseBase):
    posetype = "openpose_full"


class OpenPoseHand(OpenPoseBase):
    posetype = "openpose_hand"


class OpenPoseMediaPipeFace(OpenPoseBase):
    posetype = "MediaPipe_face"


class OpenPoseDepth(OpenPoseBase):
    posetype = "depth"


class OpenPose(OpenPoseBase):
    posetype = "openpose"


class OpenPoseFace(OpenPoseBase):
    posetype = "openpose_face"


class OpenPoseLineart(OpenPoseBase):
    posetype = "Lineart"


class OpenPoseFullExtraLimb(OpenPoseBase):
    posetype = "openpose_full_Extra_Limb"


class OpenPoseKeyPose(OpenPoseBase):
    posetype = "keypose"


class OpenPoseCanny(OpenPoseBase):
    posetype = "canny"


[
    'openpose_full',
    'openpose_hand',
    'MediaPipe_face',
    'depth',
    'openpose',
    'openpose_face',
    'Lineart',
    'openpose_full_Extra_Limb',
    'keypose',
    'canny'
]

# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "输入图像": LoadImage,
    "材质图": MatImage,
    "Mask": Mask,
    "存储": SaveImage,
    # "导入": ToBlender,
    "预览": PreviewImage,
    'OpenPoseFull': OpenPoseFull,
    'OpenPoseHand': OpenPoseHand,
    'OpenPoseMediaPipeFace': OpenPoseMediaPipeFace,
    'OpenPoseDepth': OpenPoseDepth,
    'OpenPose': OpenPose,
    'OpenPoseFace': OpenPoseFace,
    'OpenPoseLineart': OpenPoseLineart,
    'OpenPoseFullExtraLimb': OpenPoseFullExtraLimb,
    'OpenPoseKeyPose': OpenPoseKeyPose,
    'OpenPoseCanny': OpenPoseCanny,
}


NODE_DISPLAY_NAME_MAPPINGS = {
    # Sampling
    "输入图像": "Input Image",
    "材质图": "Mat Image",
    "Mask": "Mask",
    "存储": "Save",
    "预览": "Preview",
}
