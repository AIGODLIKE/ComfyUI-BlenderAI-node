import bpy

from ....kclogger import logger

modules = ["gizmo", "camera_to_board", "board_to_camera"]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    reg()
    logger.debug(f"{__package__} registered")


def unregister():
    unreg()
    logger.debug(f"{__package__} unregistered")
