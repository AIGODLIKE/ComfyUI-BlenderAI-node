import bpy
from ....kclogger import logger


modules = [
    "ui",
    "gui",
    "ime",
    "operator",
    "properties",
]

reg, unreg = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    reg()
    logger.debug(f"{__package__} registered")


def unregister():
    try:
        unreg()
    except KeyError:
        # module may already be removed during shutdown
        ...
    logger.debug(f"{__package__} unregistered")
