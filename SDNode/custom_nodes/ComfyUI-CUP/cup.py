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
import random
import gc
import execution
import folder_paths
import nodes
import time
import asyncio
import logging as logger
from comfy.cli_args import args
from threading import Thread
from aiohttp import web
from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
from PIL.PngImagePlugin import PngInfo

FORCE_LOG = False
CATEGORY_ = "Blender"
TEMPDIR = Path(__file__).parent.parent.parent / "SDNodeTemp"
HOST_PATH = Path("XXXHOST-PATHXXX")
if not HOST_PATH.parent.exists():
    HOST_PATH = Path(__file__).parent


def remove_old_version():
    cup = Path(__file__).parent.parent.joinpath("cup.py")
    if cup.exists():
        cup.unlink()


remove_old_version()


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
    try:
        info['input'] = obj_class.INPUT_TYPES()
    except Exception:
        ...
    info['output'] = obj_class.RETURN_TYPES
    info['output_is_list'] = obj_class.OUTPUT_IS_LIST if hasattr(obj_class, 'OUTPUT_IS_LIST') else [False] * len(obj_class.RETURN_TYPES)
    info['output_name'] = obj_class.RETURN_NAMES if hasattr(obj_class, 'RETURN_NAMES') else info['output']
    info['name'] = node_class
    info['display_name'] = nodes.NODE_DISPLAY_NAME_MAPPINGS[node_class] if node_class in nodes.NODE_DISPLAY_NAME_MAPPINGS.keys() else node_class
    info['description'] = ''
    info['category'] = 'sd'
    if hasattr(obj_class, 'OUTPUT_NODE') and obj_class.OUTPUT_NODE is True:
        info['output_node'] = True
    else:
        info['output_node'] = False
    if hasattr(obj_class, 'CATEGORY'):
        info['category'] = obj_class.CATEGORY
    return info


class NodeCacheManager:
    def __init__(self):
        self.cached_nodes = {}
        self.diff = {}
        self.filter_node = {"Note", "PrimitiveNode", "Cache Node"}

    def calc_diff(self):
        if self.diff:
            return self.diff

        for x in list(nodes.NODE_CLASS_MAPPINGS):
            if x in self.filter_node:
                continue
            ni = node_info(x)
            if x not in self.cached_nodes or self.cached_nodes[x] != ni:
                self.diff[x] = ni
            self.cached_nodes[x] = ni
        return self.diff

    def update_cached_nodes(self, remote=False):
        # 本地部署 但差异路径不存在
        if not remote and not HOST_PATH.parent.exists():
            return {}
        from copy import deepcopy
        self.calc_diff()
        diff = self.diff
        if remote:
            diff = deepcopy(self.diff)
            self.diff.clear()
        else:
            try:
                # 本地部署时写入差异后清理
                diff_path = HOST_PATH.joinpath("diff_object_info.json")
                with diff_path.open("w", encoding="utf-8") as f:
                    f.write(json.dumps(self.diff))
                self.diff.clear()
            except Exception as e:
                # 写入失败后
                # print(f"Failed to write diff: {e}")
                ...
        return diff


cache_manager = NodeCacheManager()


def diff_listen_loop():
    while True:
        time.sleep(5)
        cache_manager.update_cached_nodes()


Thread(target=diff_listen_loop, daemon=True).start()


@server.PromptServer.instance.routes.post("/cup/get_temp_directory")
async def get_temp_directory(request):
    return web.Response(status=200, body=folder_paths.get_temp_directory())


async def queue_msg():
    queue = {}
    current_queue = server.PromptServer.instance.prompt_queue.get_current_queue()
    queue['queue_running'] = current_queue[0]
    queue['queue_pending'] = current_queue[1]
    server.PromptServer.instance.send_sync("cup.queue", queue)


async def diff_msg():
    diff = cache_manager.update_cached_nodes(remote=True)
    server.PromptServer.instance.send_sync("cup.diff", diff)


async def msg_loop():
    while True:
        await queue_msg()
        await diff_msg()
        await asyncio.sleep(1)

Thread(target=asyncio.run, args=(msg_loop(),), daemon=True).start()


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
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        self.prefix_append = ""
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                {"images": ("IMAGE", ),
                 "filename_prefix": ("STRING", {"default": "ComfyUI"}),
                 "output_dir": ("STRING", {"default": ""}),
                 },
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }

    RETURN_TYPES = ()
    FUNCTION = "save_images"

    OUTPUT_NODE = True

    CATEGORY = CATEGORY_

    def save_images(self, images, filename_prefix="ComfyUI", output_dir="", prompt=None, extra_pnginfo=None):
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        for (batch_number, image) in enumerate(images):
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            metadata = None
            if not args.disable_metadata:
                metadata = PngInfo()
                if prompt is not None:
                    metadata.add_text("prompt", json.dumps(prompt))
                if extra_pnginfo is not None:
                    for x in extra_pnginfo:
                        metadata.add_text(x, json.dumps(extra_pnginfo[x]))

            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.png"
            img.save(os.path.join(full_output_folder, file), pnginfo=metadata, compress_level=self.compress_level)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        return {"ui": {"images": results}}


class PreviewImage(SaveImage):
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + ''.join(random.choice("abcdefghijklmnopqrstupvxyz") for _ in range(5))
        self.compress_level = 1

    @classmethod
    def INPUT_TYPES(s):
        return {"required":
                {"images": ("IMAGE", ), },
                "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }


class LoadImage:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
                "mode": (["输入", "渲染", "序列图", "视口"], ),
            },
        }

    CATEGORY = CATEGORY_

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"

    def load_image(self, image, mode=None):
        if image:
            image = image.replace("\\\\", "/").replace("\\", "/")
        image = Path(image).name
        image = f"SDN/{image}"
        image_path = folder_paths.get_annotated_filepath(image)
        # image_path = image
        img = Image.open(image_path)
        output_images = []
        output_masks = []
        for i in ImageSequence.Iterator(img):
            i = ImageOps.exif_transpose(i)
            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
            if 'A' in i.getbands():
                mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
                mask = 1. - torch.from_numpy(mask)
            else:
                mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
            output_images.append(image)
            output_masks.append(mask.unsqueeze(0))

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        return (output_image, output_mask)
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


class Screenshot(LoadImage):
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
    "截图": Screenshot,
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
    "截图": "Screenshot",
    "Mask": "Mask",
    "存储": "Save",
    "预览": "Preview",
}
WEB_DIRECTORY = "./"
