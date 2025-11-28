import bpy
from .operator import RunRedraw
from ...manager import TaskManager, FakeServer
from ....ops import Ops
from ....preference import AddonPreference, get_pref
from ....translations.translation import ctxt


class SDN_UL_ULViewportLayerList(bpy.types.UIList):
    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data, item, icon: int | None, active_data, active_property: str | None, index: int | None = 0, flt_flag: int | None = 0):
        layout.label(text=item.name)


class ViewportLayerRedrawPanel(bpy.types.Panel):
    bl_idname = "SDN_PT_VIEWPORT_LAYER_REDRAW"
    bl_translation_context = ctxt
    bl_label = "Viewport Layer Redraw"
    bl_description = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI"

    def draw(self, context):
        layout = self.layout
        self.show_launch_cnn(layout)
        self.show_layer_list(layout)
        prop = bpy.context.scene.sdn_viewport_layer_redraw
        layout.prop(prop, "prompt")
        row = layout.row()
        row.scale_y = 2
        row.operator(RunRedraw.bl_idname, text="Run Redraw")
        self.show_progress(layout)        
        try:
            from .gui.integration import ViewportGui
            layout.operator(ViewportGui.bl_idname, text="Enter Canvas", icon="PLUGIN")
        except Exception:
            pass

    def show_launch_cnn(self, layout: bpy.types.UILayout):
        if TaskManager.server != FakeServer._instance:
            return
        row = layout.row()
        row.alignment = "CENTER"
        row.label(text="↓↓ComfyUI Not Launched, Click to Launch↓↓")
        row = layout.row(align=True)
        row.alert = True
        row.scale_y = 2
        row.operator(Ops.bl_idname, text="Launch/Connect to ComfyUI", icon="PLAY").action = "Launch"
        row.prop(bpy.context.scene.sdn, "show_pref_general", text="", icon="PREFERENCES")
        if bpy.context.scene.sdn.show_pref_general:
            AddonPreference.draw_general(get_pref(), layout.box())
        self.show_error(layout)

    def show_layer_list(self, layout: bpy.types.UILayout):
        prop = bpy.context.scene.sdn_viewport_layer_redraw
        layout.label(text="Layer")
        # layout.template_list("SDN_UL_ULViewportLayerList", "", prop, "layers", prop, "active_layer_index")

    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        from ...custom_support import cup_monitor

        cup_monitor.draw(layout)
        self.show_error(layout)
        if TaskManager.get_error_msg():
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)

    def show_error(self, layout):
        for error_msg in TaskManager.get_error_msg():
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)


clss = [
    SDN_UL_ULViewportLayerList,
    ViewportLayerRedrawPanel,
]

reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    reg()


def unregister():
    unreg()
