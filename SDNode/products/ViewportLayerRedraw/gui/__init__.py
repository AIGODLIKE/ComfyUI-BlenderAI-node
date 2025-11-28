import bpy
import sys
from .....utils import PkgInstaller

ori_hook = sys.excepthook

modules = [
    "app",
    "properties",
    "integration",
    "texture",
]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    PkgInstaller.try_install("slimgui", "glfw")
    reg()


def unregister():
    unreg()
