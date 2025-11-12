import bpy

modules = ["texture_space"]

reg_submodule, unreg_submodule = bpy.utils.register_submodule_factory(__package__, modules)


def register():
    reg_submodule()


def unregister():
    unreg_submodule()
