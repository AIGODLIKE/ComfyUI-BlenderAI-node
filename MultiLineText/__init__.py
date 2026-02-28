import bpy
from .words_collection import words
from ..utils import PkgInstaller
from ..translations.translation import ctxt
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
    bl_label = "Enable MLT"
    bl_description = "Toggle multiline text editor for this node"
    bl_translation_context = ctxt

    def execute(self, context):
        if not enable_multiline_text():
            self.report({"ERROR"}, "MultiLineText Not Enabled")
            return {"FINISHED"}
        node = context.active_node
        if not node:
            self.report({"ERROR"}, "No active node")
            return {"FINISHED"}
        ops = bpy.ops.sdn.multiline_text
        # determine current active operator if any
        from .integration import MLTOps
        active = MLTOps.ACTIVE_OP
        tree_name = context.space_data.edit_tree.name if context.space_data.edit_tree else ""
        target_prop = "text"
        if active and active._target_equals(tree_name, node.name, target_prop):
            active.cancel(context)
            node.mlt_active = False
            return {"FINISHED"}
        if active:
            active.switch_target(tree_name, node.name, target_prop)
        else:
            props = {"tree_name": tree_name, "node_name": node.name, "prop": target_prop}
            ops("INVOKE_DEFAULT", **props)
        node.mlt_active = True
        return {"FINISHED"}


class PasteClipboardToMLT(bpy.types.Operator):
    bl_idname = "sdn.paste_clipboard_to_mlt"
    bl_label = "Paste Clipboard"
    bl_description = "Paste clipboard to multiline text"
    bl_translation_context = ctxt
    socket_name: bpy.props.StringProperty()

    def execute(self, context):
        clipboard = bpy.context.window_manager.clipboard
        if not clipboard:
            self.report({"ERROR"}, "Clipboard is empty")
            return {"FINISHED"}
        node = context.active_node
        setattr(node, self.socket_name, clipboard)
        return {"FINISHED"}