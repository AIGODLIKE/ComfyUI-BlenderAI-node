import bpy
from ..utils import PkgInstaller
from ..translations import ctxt
REGISTERED = [False]

REQUIREMENTS = ["imgui"]


def install():
    return PkgInstaller.try_install(*REQUIREMENTS)


def enable_multiline_text():
    if REGISTERED[0]:
        return True
    if not install():
        return False
    from .integration import multiline_register
    multiline_register()
    REGISTERED[0] = True
    return True


def disable_multiline_text():
    if not REGISTERED[0]:
        return
    from .integration import multiline_unregister
    multiline_unregister()
    REGISTERED[0] = False


class EnableMLT(bpy.types.Operator):
    bl_idname = "sdn.enable_mlt"
    bl_description = "Enable MLT"
    bl_label = "Enable MLT"
    bl_translation_context = ctxt

    def execute(self, context):
        if not enable_multiline_text():
            self.report({"ERROR"}, "MultiLineText Not Enabled")
        bpy.ops.sdn.multiline_text("INVOKE_DEFAULT")
        return {"FINISHED"}
