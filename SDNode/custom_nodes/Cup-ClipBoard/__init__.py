import os
import json
import sys
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
import platform
from functools import lru_cache
from aiohttp import web
from pathlib import Path

VERSION = "0.0.1"
ADDON_NAME = "CUP-CLIPBOARD"
COMFY_PATH = Path(folder_paths.__file__).parent
EXT_PATH = COMFY_PATH.joinpath("web", "extensions", ADDON_NAME)
CUR_PATH = Path(__file__).parent

def rmtree(path: Path):
    # unlink symbolic link
    if not path.exists():
        return
    if Path(path.resolve()).as_posix() != path.as_posix():
        path.unlink()
        return
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        # 移除 .git
        if path.name == ".git":
            if platform.system() == "darwin":
                from subprocess import call
                call(['rm', '-rf', path.as_posix()])
            elif platform.system() == "Windows":
                os.system(f'rd/s/q "{path.as_posix()}"')
            return
        for child in path.iterdir():
            rmtree(child)
        try:
            path.rmdir()  # nas 的共享盘可能会有残留
        except BaseException:
            ...

def register():
    import nodes
    if hasattr(nodes, "EXTENSION_WEB_DIRS"):
        rmtree(EXT_PATH)
        return
    link_func = shutil.copytree
    if os.name == "nt":
        import _winapi
        link_func = _winapi.CreateJunction
    try:
        link_func(CUR_PATH.as_posix(), EXT_PATH.as_posix())
    except Exception as e:
        sys.stderr.write(f"[cup/register error]: {e}\n")
        sys.stderr.flush()
    return

def unregister():
    try:
        rmtree(EXT_PATH)
    except BaseException:
        ...

register()
atexit.register(unregister)
NODE_CLASS_MAPPINGS = {}
WEB_DIRECTORY = "./"