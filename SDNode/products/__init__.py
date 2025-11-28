import bpy

modules = [
    "ViewportLayerRedraw",
    "CameraControl",
]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)


def products_reg():
    reg()


def products_unreg():
    unreg()
