import os
import json
import sys
import io
import traceback
import numpy as np
import builtins
import torch
import torchaudio
import struct
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
import requests
import aiohttp
from aiohttp import web
from comfy.cli_args import args
from threading import Thread
from aiohttp import web
from pathlib import Path
from PIL import Image, ImageOps, ImageSequence
from PIL.PngImagePlugin import PngInfo
from comfy.comfy_types import IO, FileLocator, ComfyNodeABC
from comfy_api.input import ImageInput, AudioInput, VideoInput
from comfy_api.util import VideoContainer, VideoCodec, VideoComponents
from server import PromptServer
from queue import Queue

__CATEGORY__ = "Blender"

BLENDER_IO_PORT_RANGE = (53819, 53824)


async def send_socket_catch_exception(function, message):
    try:
        await function(message)
    except (aiohttp.ClientError, aiohttp.ClientPayloadError, ConnectionResetError, BrokenPipeError, ConnectionError) as err:
        print("send error: {}".format(err))


def create_vorbis_comment_block(comment_dict, last_block):
    vendor_string = b"ComfyUI"
    vendor_length = len(vendor_string)

    comments = []
    for key, value in comment_dict.items():
        comment = f"{key}={value}".encode("utf-8")
        comments.append(struct.pack("<I", len(comment)) + comment)

    user_comment_list_length = len(comments)
    user_comments = b"".join(comments)

    comment_data = struct.pack("<I", vendor_length) + vendor_string + struct.pack("<I", user_comment_list_length) + user_comments
    if last_block:
        id = b"\x84"
    else:
        id = b"\x04"
    comment_block = id + struct.pack(">I", len(comment_data))[1:] + comment_data

    return comment_block


def insert_or_replace_vorbis_comment(flac_io, comment_dict):
    if len(comment_dict) == 0:
        return flac_io

    flac_io.seek(4)

    blocks = []
    last_block = False

    while not last_block:
        header = flac_io.read(4)
        last_block = (header[0] & 0x80) != 0
        block_type = header[0] & 0x7F
        block_length = struct.unpack(">I", b"\x00" + header[1:])[0]
        block_data = flac_io.read(block_length)

        if block_type == 4 or block_type == 1:
            pass
        else:
            header = bytes([(header[0] & (~0x80))]) + header[1:]
            blocks.append(header + block_data)

    blocks.append(create_vorbis_comment_block(comment_dict, last_block=True))

    new_flac_io = io.BytesIO()
    new_flac_io.write(b"fLaC")
    for block in blocks:
        new_flac_io.write(block)

    new_flac_io.write(flac_io.read())
    return new_flac_io


class CupException(Exception):
    pass


class DataChain:
    chain: Queue[dict] = Queue()
    last_data: dict = None

    @classmethod
    def put(cls, data):
        while not cls.chain.empty():
            cls.chain.get()
        cls.chain.put(data)

    @classmethod
    def get(cls, default=None) -> dict:
        if cls.chain.empty():
            return cls.last_data or default
        cls.last_data = cls.chain.get()
        return cls.last_data

    @classmethod
    def peek(cls, default=None):
        if cls.chain.empty():
            return cls.last_data or default
        return cls.chain.queue[0]


class BlenderInputs:
    timeout = 30

    @classmethod
    def INPUT_TYPES(s):
        return {
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }
        return {
            "optional": {
                "linked_outputs": (
                    IO.ANY,
                    {
                        "default": None,
                        "tooltip": "链接输出.",
                    },
                )
            }
        }

    #     return {
    #         "required": {
    #             "camera_viewport": (
    #                 IO.IMAGE,
    #                 {
    #                     "default": None,
    #                     "tooltip": "相机视口图.",
    #                 },
    #             ),
    #             "render_viewport": (
    #                 IO.IMAGE,
    #                 {
    #                     "default": None,
    #                     "tooltip": "视口渲染图.",
    #                 },
    #             ),
    #             "depth_viewport": (
    #                 IO.IMAGE,
    #                 {
    #                     "default": None,
    #                     "tooltip": "视口深度图.",
    #                 },
    #             ),
    #             "mist_viewport": (
    #                 IO.IMAGE,
    #                 {
    #                     "default": None,
    #                     "tooltip": "视口雾场图.",
    #                 },
    #             ),
    #             "active_model": (
    #                 IO.STRING,
    #                 {
    #                     "default": None,
    #                     "tooltip": "当前活动模型路径.",
    #                 },
    #             ),
    #             "custom_image": (
    #                 IO.IMAGE,
    #                 {
    #                     "default": None,
    #                     "tooltip": "自定义图像.",
    #                 },
    #             ),
    #         },
    #     }

    CATEGORY = __CATEGORY__

    RETURN_TYPES = (
        IO.IMAGE,
        IO.IMAGE,
        IO.IMAGE,
        IO.IMAGE,
        IO.STRING,
        IO.IMAGE,
    )

    RETURN_NAMES = (
        "camera_viewport",
        "render_viewport",
        "depth_viewport",
        "mist_viewport",
        "active_model",
        "custom_image",
    )

    FUNCTION = "build_inputs"
    unique_id = -1

    def build_inputs(self, prompt=None, unique_id=None, extra_pnginfo=None):
        # print("Combined Outputs: ", prompt, unique_id, extra_pnginfo)
        _prompt = {
            "20": {
                "inputs": {
                    "model_file": ["27", 4],
                    "image": "",
                },
                "class_type": "Preview3D",
                "_meta": {
                    "title": "预览3D",
                },
            },
            "27": {
                "inputs": {
                    "linkedOutputs": ["active_model"],
                },
                "class_type": "CombineInput",
                "_meta": {
                    "title": "Combine Input",
                },
            },
            "28": {
                "inputs": {
                    "ckpt_name": "AIGODLIKE华丽_4000.ckpt",
                    "+": None,
                },
                "class_type": "CheckpointLoaderSimple",
                "_meta": {
                    "title": "Checkpoint加载器（简易）",
                },
            },
        }
        unique_id = int(unique_id)
        self.unique_id = unique_id
        _extra_pnginfo = {
            "workflow": {
                "id": "9fa3da5b-449d-4a82-8896-216471fe0f41",
                "revision": 0,
                "last_node_id": 28,
                "last_link_id": 18,
                "nodes": [
                    {
                        "id": 20,
                        "type": "Preview3D",
                        "pos": [910, 580],
                        "size": [400, 550],
                        "flags": {},
                        "order": 2,
                        "mode": 0,
                        "inputs": [
                            {
                                "name": "camera_info",
                                "shape": 7,
                                "type": "LOAD3D_CAMERA",
                                "link": None,
                            },
                            {
                                "name": "model_file",
                                "type": "STRING",
                                "widget": {"name": "model_file"},
                                "link": 18,
                            },
                        ],
                        "outputs": [],
                        "properties": {"Node name for S&R": "Preview3D"},
                        "widgets_values": ["3d/未命名.glb", ""],
                    },
                    {
                        "id": 27,
                        "type": "CombineInput",
                        "pos": [460, 580],
                        "size": [210, 126],
                        "flags": {},
                        "order": 0,
                        "mode": 0,
                        "inputs": [],
                        "outputs": [
                            {"name": "camera_viewport", "type": "IMAGE", "links": None},
                            {"name": "render_viewport", "type": "IMAGE", "links": None},
                            {"name": "depth_viewport", "type": "IMAGE", "links": None},
                            {"name": "mist_viewport", "type": "IMAGE", "links": None},
                            {"name": "active_model", "type": "STRING", "links": [18]},
                            {"name": "custom_image", "type": "IMAGE", "links": None},
                        ],
                        "properties": {"Node name for S&R": "CombineInput"},
                        "widgets_values": [["active_model"]],
                    },
                    {
                        "id": 28,
                        "type": "CheckpointLoaderSimple",
                        "pos": [123.9921875, 372.69140625],
                        "size": [315, 122],
                        "flags": {},
                        "order": 1,
                        "mode": 0,
                        "inputs": [],
                        "outputs": [
                            {
                                "name": "MODEL",
                                "type": "MODEL",
                                "links": None,
                            },
                            {
                                "name": "CLIP",
                                "type": "CLIP",
                                "links": None,
                            },
                            {
                                "name": "VAE",
                                "type": "VAE",
                                "links": None,
                            },
                        ],
                        "properties": {"Node name for S&R": "CheckpointLoaderSimple"},
                        "widgets_values": ["AIGODLIKE华丽_4000.ckpt", None],
                    },
                ],
                "links": [[18, 27, 4, 20, 1, "STRING"]],
                "groups": [],
                "config": {},
                "extra": {"ds": {"scale": 1, "offset": [0, 0]}, "frontendVersion": "1.17.11", "groupNodes": {}},
                "version": 0.4,
                "widget_idx_map": {},
                "seed_widgets": {},
            }
        }

        workflow = extra_pnginfo.get("workflow", {})
        node_outputs = {}
        for node in workflow.get("nodes", {}):
            if node.get("id") != unique_id:
                continue
            for output in node.get("outputs", []):
                node_outputs[output["name"]] = output
        res = []
        for data_name in self.RETURN_NAMES:
            res.append(self.get_data_from_blender(data_name, node_outputs))
        return res

    def get_data_from_blender(self, data_name, node_outputs: dict[str, str]):
        """
        通过网络向Blender发送请求并获取数据
        """
        node_output = node_outputs.get(data_name)
        if not node_output or not node_output.get("links"):
            print("No link found for data_name: ", data_name)
            return None
        print("Called get_data_from_blender: ", data_name)
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_data_ws_ex(data_name))
        return self.get_data_ws_ex(data_name)

    async def get_data_ws_ex(self, data_name):
        ws: web.WebSocketResponse = None
        # 场景连接blender的ws客户端
        for sid in PromptServer.instance.sockets:
            if sid.startswith("ComfyUICUP"):
                ws = PromptServer.instance.sockets[sid]
        if ws is None:
            print("Blender Connection not found")
            return None
        request_data = {
            "unique_id": self.unique_id,
            "message": {
                "data_name": data_name,
            },
            "event": "run",
        }
        message = {
            "type": "get_data_from_blender",
            "data": request_data,
        }
        result_data: dict = None
        try:
            timeout = self.timeout
            await ws.send_json(message)
            queue = asyncio.Queue()
            old_receive = ws.receive

            async def receive_ex(*args, **kwargs):
                res = await old_receive(*args, **kwargs)
                try:
                    queue.put_nowait(res)
                except asyncio.QueueFull:
                    pass
                return res

            ws.receive = receive_ex
            res: aiohttp.WSMessage = None
            message: dict = None
            while timeout > 0:
                await asyncio.sleep(1)
                timeout -= 1
                try:
                    res = queue.get_nowait()
                    if not res or res.type != aiohttp.WSMsgType.TEXT:
                        continue
                    # {
                    #     "type": "get_data_from_blender_res",
                    #     "data": {"res": "True Data"},
                    # }
                    _message = res.json()
                    mtype = _message.get("type")
                    if mtype == "get_data_from_blender_res":
                        message = _message
                        break
                except asyncio.QueueEmpty:
                    pass
                except Exception as err:
                    print("get_data_from_blender error: {}".format(err))
                    traceback.print_exc()
                    continue
            ws.receive = old_receive
            result_data = message.get("data", {})
        except Exception as err:
            print("Send error: {}".format(err))
            traceback.print_exc()
        if not result_data:
            print("No data received from Blender")
            return None
        print("[Get Data from Blender JSON]: ", result_data)
        # 图片的默认数据
        img_data = torch.zeros((64, 64), dtype=torch.float32, device="cpu").unsqueeze(0)
        data_path = Path(result_data.get("subfolder"), result_data.get("name"))
        upload_dir, data_upload_type = get_dir_by_type("output")
        full_data_path = Path(upload_dir, data_path)
        if full_data_path.is_dir() or not full_data_path.exists():
            return None
        if data_name == "active_model":
            return data_path.as_posix()
        else:
            img = Image.open(full_data_path.as_posix())
            for i in ImageSequence.Iterator(img):
                i = ImageOps.exif_transpose(i)
                if i.mode == "I":
                    i = i.point(lambda i: i * (1 / 255))
                image = i.convert("RGB")
                image = np.array(image).astype(np.float32) / 255.0
                img_data = torch.from_numpy(image)[None,]
        return img_data

    def get_data_post_ex(self, data_name):
        # 尝试连接blender服务器
        # POST: http://localhost:[Port_Range]/api/get_data_from_blender
        url = f"http://localhost:{BLENDER_IO_PORT_RANGE[0]}/api/get_data_from_blender"
        for port in range(*BLENDER_IO_PORT_RANGE):
            try:
                url = f"http://localhost:{port}/api/get_data_from_blender"
                echo_data = {
                    "unique_id": self.unique_id,
                    "message": {},
                    "event": "echo",
                }
                resp = requests.post(url, json=echo_data)
                if resp.status_code == 200:
                    print(f"Connected to Blender server on port {port}")
                    break
            except Exception as e:
                print(f"Error connecting to Blender server on port {port}: {e}")
                continue
        request_data = {
            "unique_id": self.unique_id,
            "message": {
                "data_name": data_name,
            },
            "event": "run",
        }
        resp = requests.post(url, json=request_data)
        if resp.status_code != 201:
            print(f"Error getting data from Blender server: {resp.status_code}")
            return None
        resp_json = resp.json()
        # {
        #     "unique_id": unique_id,
        #     "message": {
        #         "data_name": data_name,
        #         "data_result": data_result,
        #     },
        #     "event": "run",
        # }
        return resp_json.get("message", {}).get("data_result", None)

    @classmethod
    def IS_CHANGED(s, prompt=None, unique_id=None, extra_pnginfo=None):
        return time.time()


class BlenderOutputs:
    timeout = 30

    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix_append = "_temp_" + "".join(random.choice("abcdefghijklmnopqrstupvxyz") for x in range(5))
        self.compress_level = 4

    @classmethod
    def INPUT_TYPES(s):
        return {
            "optional": {
                "image": (
                    IO.IMAGE,
                    {
                        "default": None,
                        "tooltip": "图片.",
                    },
                ),
                "model": (
                    IO.STRING,
                    {
                        "default": None,
                        "tooltip": "模型.",
                    },
                ),
                "video": (
                    IO.VIDEO,
                    {
                        "default": None,
                        "tooltip": "视频.",
                    },
                ),
                "audio": (
                    IO.AUDIO,
                    {
                        "default": None,
                        "tooltip": "音频.",
                    },
                ),
                "text": (
                    IO.STRING,
                    {
                        "default": None,
                        "tooltip": "文本内容.",
                    },
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    CATEGORY = __CATEGORY__
    OUTPUT_NODE = True
    FUNCTION = "build_outputs"

    def build_outputs(self, image=None, model=None, video=None, audio=None, text=None, prompt=None, extra_pnginfo=None):
        # print(f"[Build Outputs]: {image}, {model}, {video}, {audio}, {text}")
        # Image Type: <class 'torch.Tensor'>
        # Model Type: <class 'str'>
        # Video Type: <class 'comfy_api.input_impl.video_types.VideoFromComponents'>
        # Audio Type: <class 'dict'>  # 示例数据: {'waveform': tensor([[[0., 0., 0.,  ..., 0., 0., 0.]]]), 'sample_rate': 24000}
        # Text Type: <class 'str'>
        # print(f"\t Image Type: {type(image)}")
        # print(f"\t Model Type: {type(model)}")
        # print(f"\t Video Type: {type(video)}")
        # print(f"\t Audio Type: {type(audio)}")
        # print(f"\t  Text Type: {type(text)}")
        # 发送数据到blender服务器
        data = {
            "images": self.save_images(image, prompt=prompt, extra_pnginfo=extra_pnginfo),
            "models": model,
            "videos": self.save_video(video, prompt=prompt, extra_pnginfo=extra_pnginfo),
            "audios": self.save_audio(audio, prompt=prompt, extra_pnginfo=extra_pnginfo),
            "texts": text,
            "timestamp": [time.time_ns()],
        }
        # asyncio.set_event_loop(asyncio.new_event_loop())
        try:
            loop = asyncio.get_event_loop()
        except Exception:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(self.send_data_ws_ex(data))
        data["apngs"] = self.save_webp(video)
        DataChain.put(
            {
                "origin": {
                    "image": image,
                    "model": model,
                    "video": video,
                    "audio": audio,
                    "text": text,
                },
                "ui": data,
            }
        )
        return {"ui": data}

    async def send_data_ws_ex(self, data):
        ws: web.WebSocketResponse = None
        # 场景连接blender的ws客户端
        for sid in PromptServer.instance.sockets:
            if sid.startswith("ComfyUICUP"):
                ws = PromptServer.instance.sockets[sid]
        if ws is None:
            print("Blender Connection not found")
            return
        message = {
            "type": "send_data_to_blender",
            "data": data,
        }
        try:
            await ws.send_json(message)
        except Exception as err:
            print("Send error: {}".format(err))
            traceback.print_exc()

    def save_images(self, images, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        if images is None or len(images) == 0:
            return []
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        for batch_number, image in enumerate(images):
            i = 255.0 * image.cpu().numpy()
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
            results.append({"filename": file, "subfolder": subfolder, "type": self.type})
            counter += 1
        return results

    def save_video(self, video: VideoInput, filename_prefix="video/ComfyUI", format="mp4", codec="h264", prompt=None, extra_pnginfo=None):
        if not video:
            return []
        filename_prefix += self.prefix_append
        width, height = video.get_dimensions()
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, width, height)
        results: list[FileLocator] = list()
        saved_metadata = None
        if not args.disable_metadata:
            metadata = {}
            if extra_pnginfo is not None:
                metadata.update(extra_pnginfo)
            if prompt is not None:
                metadata["prompt"] = prompt
            if len(metadata) > 0:
                saved_metadata = metadata
        file = f"{filename}_{counter:05}_.{VideoContainer.get_extension(format)}"
        video.save_to(os.path.join(full_output_folder, file), format=format, codec=codec, metadata=saved_metadata)

        results.append({"filename": file, "subfolder": subfolder, "type": self.type})
        counter += 1

        return results

    def save_audio(self, audio, filename_prefix="ComfyUI", prompt=None, extra_pnginfo=None):
        if not audio:
            return []
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir)
        results: list[FileLocator] = []

        metadata = {}
        if not args.disable_metadata:
            if prompt is not None:
                metadata["prompt"] = json.dumps(prompt)
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])

        for batch_number, waveform in enumerate(audio["waveform"].cpu()):
            filename_with_batch_num = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch_num}_{counter:05}_.flac"

            buff = io.BytesIO()
            torchaudio.save(buff, waveform, audio["sample_rate"], format="FLAC")

            buff = insert_or_replace_vorbis_comment(buff, metadata)

            with open(os.path.join(full_output_folder, file), "wb") as f:
                f.write(buff.getbuffer())

            results.append({"filename": file, "subfolder": subfolder, "type": self.type})
            counter += 1

        return results

    def save_apng(self, video: VideoInput, filename_prefix="ComfyUI"):
        if not video:
            return []
        # components.images, components.audio, float(components.frame_rate)
        components = video.get_components()
        images = components.images
        fps = components.frame_rate
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = list()
        pil_images = []
        for image in images:
            i = 255.0 * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            pil_images.append(img)

        file = f"{filename}_{counter:05}_.png"
        pil_images[0].save(os.path.join(full_output_folder, file), save_all=True, duration=int(1000.0 / fps), append_images=pil_images[1:])
        results.append({"filename": file, "subfolder": subfolder, "type": self.type})

        return results


    def save_webp(self, video: VideoInput, filename_prefix="ComfyUI"):
        if not video:
            return []
        # components.images, components.audio, float(components.frame_rate)
        components = video.get_components()
        images = components.images
        fps = components.frame_rate
        method = {"default": 4, "fastest": 0, "slowest": 6}.get("fastest", 4)
        filename_prefix += self.prefix_append
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(filename_prefix, self.output_dir, images[0].shape[1], images[0].shape[0])
        results = []
        pil_images = []
        for image in images:
            i = 255. * image.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            pil_images.append(img)

        metadata = pil_images[0].getexif()

        num_frames = len(pil_images)

        c = len(pil_images)
        for i in range(0, c, num_frames):
            file = f"{filename}_{counter:05}_.webp"
            pil_images[i].save(os.path.join(full_output_folder, file), save_all=True, duration=int(1000.0/fps), append_images=pil_images[i + 1:i + num_frames], exif=metadata, lossless=True, quality=80, method=method)
            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": self.type
            })
            counter += 1

        return results

class ComfyUIInputs:
    timeout = 30

    @classmethod
    def INPUT_TYPES(s):
        return {
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            }
        }

    CATEGORY = __CATEGORY__

    RETURN_TYPES = (
        IO.IMAGE,
        IO.STRING,
        IO.VIDEO,
        IO.AUDIO,
        IO.STRING,
    )

    RETURN_NAMES = (
        "image",
        "model",
        "video",
        "audio",
        "text",
    )

    FUNCTION = "build_inputs"
    unique_id = -1

    def build_inputs(self, prompt=None, unique_id=None, extra_pnginfo=None):
        ori_default = {
            "image": None,
            "model": "",
            "video": None,
            "audio": None,
            "text": "",
        }
        default = {
            "origin": ori_default,
            "ui": {},
        }
        res = DataChain.get(default=default).get("origin", ori_default)
        return list(res.values())

    @classmethod
    def IS_CHANGED(s, prompt=None, unique_id=None, extra_pnginfo=None):
        return time.time()


@PromptServer.instance.routes.post("/bio/fetch/comfyui_queue")
async def fetch_comfyui_queue(request: web.Request):
    ori_default = {
        "image": None,
        "model": "",
        "video": None,
        "audio": None,
        "text": "",
    }
    default = {
        "origin": ori_default,
        "ui": {},
    }
    res = DataChain.peek(default).get("ui", {})
    return web.json_response(res)


@PromptServer.instance.routes.post("/upload/blender_inputs")
async def upload_inputs(request: web.Request):
    post = await request.post()
    input_data = post.get("input_data")
    overwrite = post.get("overwrite")
    data_is_duplicate = False

    data_upload_type = post.get("type")
    upload_dir, data_upload_type = get_dir_by_type(data_upload_type)

    if input_data and input_data.file:
        filename = input_data.filename
        if not filename:
            return web.Response(status=400)

        subfolder = post.get("subfolder", "")
        full_output_folder = os.path.join(upload_dir, os.path.normpath(subfolder))
        filepath = os.path.abspath(os.path.join(full_output_folder, filename))

        if os.path.commonpath((upload_dir, filepath)) != upload_dir:
            return web.Response(status=400)

        if not os.path.exists(full_output_folder):
            os.makedirs(full_output_folder)

        split = os.path.splitext(filename)

        if overwrite is not None and (overwrite == "true" or overwrite == "1"):
            pass
        else:
            i = 1
            while os.path.exists(filepath):
                if compare_data_hash(filepath, input_data):
                    data_is_duplicate = True
                    break
                filename = f"{split[0]} ({i}){split[1]}"
                filepath = os.path.join(full_output_folder, filename)
                i += 1

        if not data_is_duplicate:
            with open(filepath, "wb") as f:
                f.write(input_data.file.read())
        resp_data = {
            "name": filename,
            "subfolder": subfolder,
            "type": data_upload_type,
        }
        return web.json_response(resp_data)
    else:
        return web.Response(status=400)


def get_dir_by_type(dir_type=None):
    if dir_type is None:
        dir_type = "input"
    if dir_type == "input":
        type_dir = folder_paths.get_input_directory()
    elif dir_type == "temp":
        type_dir = folder_paths.get_temp_directory()
    elif dir_type == "output":
        type_dir = folder_paths.get_output_directory()
    return type_dir, dir_type


def compare_data_hash(filepath, data):
    hashfuncs = {"md5": hashlib.md5, "sha1": hashlib.sha1, "sha256": hashlib.sha256, "sha512": hashlib.sha512}
    hasher = hashfuncs["md5"]
    # function to compare hashes of two data to see if it already exists, fix to # 3465
    if os.path.exists(filepath):
        a = hasher()
        b = hasher()
        with open(filepath, "rb") as f:
            a.update(f.read())
            b.update(data.file.read())
            data.file.seek(0)
            f.close()
        return a.hexdigest() == b.hexdigest()
    return False


NODE_CLASS_MAPPINGS = {
    "BlenderInputs": BlenderInputs,
    "BlenderOutputs": BlenderOutputs,
    "ComfyUIInputs": ComfyUIInputs,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BlenderInputs": "Blender Inputs",
    "BlenderOutputs": "Blender Outputs",
    "ComfyUIInputs": "ComfyUI Inputs",
}

WEB_DIRECTORY = "./web"
