import os
import json
import sys
import numpy as np
import builtins
import torch
import shutil
import hashlib
import atexit
from pathlib import Path
from PIL import Image
from PIL.PngImagePlugin import PngInfo


CATEGORY_ = "Blender"
TEMPDIR = Path(__file__).parent.parent / "SDNodeTemp"


def removetemp():
    try:
        if TEMPDIR.exists():
            shutil.rmtree(TEMPDIR, ignore_errors=True)
        TEMPDIR.mkdir(parents=True)
    except Exception as e:
        sys.stdout.write(e)


removetemp()
atexit.register(removetemp)


def hk(func):
    def wrap(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            ...
        sys.stdout.flush()
        # sys.stderr.flush()
    return wrap


builtins.print = hk(print)

sys.stdout.write = hk(sys.stdout.write)
sys.stderr.write = builtins.print


def try_write_config():
    config_path = r"XXXMODEL-CFGXXX"
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
                "mode": (["输入", "渲染"], ),
            },
        }

    CATEGORY = CATEGORY_

    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_image"

    def load_image(self, image, mode):
        try:
            image_path = image
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
    def IS_CHANGED(s, image, mode):
        image_path = image
        if not os.path.exists(image_path):
            return ""
        m = hashlib.sha256()
        with open(image_path, 'rb') as f:
            m.update(f.read())
        return m.digest().hex()


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
        i = Image.open(image_path)
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


# A dictionary that contains all nodes you want to export with their names
# NOTE: names should be globally unique
NODE_CLASS_MAPPINGS = {
    "输入图像": LoadImage,
    "Mask": Mask,
    "存储": SaveImage,
    # "导入": ToBlender,
    "预览": PreviewImage,
}
