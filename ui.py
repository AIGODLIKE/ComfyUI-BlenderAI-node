import bpy
import platform
from bl_ui.properties_paint_common import UnifiedPaintPanel
from bpy.types import Context
from .ops import Ops, Load_History, Copy_Tree, Load_Batch, Fetch_Node_Status
from .translations import ctxt
from .SDNode import TaskManager
from .SDNode.tree import TREE_TYPE
from .preference import get_pref
from .utils import get_addon_name, _T


class Panel(bpy.types.Panel):
    bl_idname = "SDN_PT_UI"
    bl_translation_context = ctxt
    bl_label = get_addon_name()
    bl_description = ""
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "圣杯节点"

    @classmethod
    def poll(cls, context):
        return context.space_data.tree_type == TREE_TYPE

    def draw_header(self, context):
        sdn = bpy.context.scene.sdn
        row = self.layout.row(align=True)
        row.prop(sdn, 'open_pref', text="", icon="PREFERENCES", text_ctxt=ctxt)
        if platform.system() != "Darwin":
            row.operator("wm.console_toggle", text="", icon="CONSOLE", text_ctxt=ctxt)
        # row.prop(sdn, "restart_webui", text="", icon="RECOVER_LAST")
        row.operator(Ops.bl_idname, text="", icon="QUIT", text_ctxt=ctxt).action = "Launch"
        row.operator(Fetch_Node_Status.bl_idname, text="", icon="FILE_REFRESH" , text_ctxt=ctxt)
        row.operator(Ops.bl_idname, text="", icon="RECOVER_LAST", text_ctxt=ctxt).action = "Restart"
        row.prop(sdn, "open_webui", text="", icon="URL", text_ctxt=ctxt)

    def draw(self, context: bpy.types.Context):
        scale_popup = get_pref().popup_scale
        layout = self.layout
        col = layout.column()
        row1 = col.row(align=True)
        row1.alert = True
        row1.scale_y = 2
        if Ops.is_advanced_enable:
            row1.operator(Ops.bl_idname, text="Stop Loop", icon="PAUSE").action = "StopLoop"
        else:
            row1.operator(Ops.bl_idname, text="Execute Node Tree", icon="PLAY").action = "Submit"
        row1.prop(bpy.context.scene.sdn, "advanced_exe", text="", icon="SETTINGS")
        if bpy.context.scene.sdn.advanced_exe:
            adv_col = col.box().column(align=True)
            adv_col.prop(bpy.context.scene.sdn, "loop_exec", text_ctxt=ctxt, toggle=True)
            if not bpy.context.scene.sdn.loop_exec:
                adv_col.prop(bpy.context.scene.sdn, "batch_count", text_ctxt=ctxt)
        # col.operator(Ops.bl_idname,
        #         text="Disconnect from ComfyUI" if TaskManager.connect_existing else "Connect Existing ComfyUI",
        #         icon="LINKED" if TaskManager.connect_existing else "UNLINKED").action = "Connect"
        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator(Ops.bl_idname, text="Cancel", icon="CANCEL").action = "Cancel"
        row.operator(Ops.bl_idname, text="ClearTask", icon="TRASH").action = "ClearTask"
        layout.operator(Load_Batch.bl_idname, text_ctxt=ctxt, icon="PLAY")
        layout.prop(bpy.context.scene.sdn, "frame_mode", text="")
        if bpy.context.scene.sdn.frame_mode == "Batch":
            box = layout.box()
            tree = bpy.context.space_data.edit_tree
            box.prop(bpy.context.scene.sdn, "batch_dir", text="")
            if tree and (select_node := tree.nodes.active):
                box.label(text=_T("Selected Node: ") + select_node.name)
        self.show_progress(layout)
        box = layout.box()
        row = box.row()
        row.label(text="Node Tree", text_ctxt=ctxt)
        row.prop(bpy.context.scene.sdn, "open_presets_dir", text="", icon="FILEBROWSER", text_ctxt=ctxt)
        col = box.column(align=True)
        col.prop(bpy.context.scene.sdn, "presets_dir", text="", text_ctxt=ctxt)
        col.template_icon_view(bpy.context.scene.sdn, "presets", show_labels=True, scale_popup=scale_popup, scale=scale_popup)
        # col.prop(bpy.context.scene.sdn, "presets", text="")
        row = col.row(align=True)
        row.operator(Ops.bl_idname, text="Save", text_ctxt=ctxt).action = "Save"
        row.operator(Ops.bl_idname, text="Delete", text_ctxt=ctxt).action = "Del"
        rrow = col.row(align=True)
        rrow.operator(Ops.bl_idname, text="Replace Node Tree", text_ctxt=ctxt).action = "Load"
        rrow.operator(Ops.bl_idname, text="", icon="TEXTURE", text_ctxt=ctxt).action = "PresetFromBookmark"
        rrow.operator(Copy_Tree.bl_idname, text="", icon="COPYDOWN")
        rrow.operator(Ops.bl_idname, text="", icon="PASTEDOWN", text_ctxt=ctxt).action = "PresetFromClipBoard"

        box = layout.box()
        row = box.row()
        row.label(text="Node Group", text_ctxt=ctxt)
        row.prop(bpy.context.scene.sdn, "open_groups_dir", text="", icon="FILEBROWSER", text_ctxt=ctxt)
        col = box.column(align=True)
        col.prop(bpy.context.scene.sdn, "groups_dir", text="", text_ctxt=ctxt)
        col.template_icon_view(bpy.context.scene.sdn, "groups", show_labels=True, scale_popup=scale_popup, scale=scale_popup)
        # col.prop(bpy.context.scene.sdn, "groups", text="")
        row = col.row(align=True)
        row.operator(Ops.bl_idname, text="Save", text_ctxt=ctxt).action = "SaveGroup"
        row.operator(Ops.bl_idname, text="Delete", text_ctxt=ctxt).action = "DelGroup"
        col.operator(Ops.bl_idname, text="Append Node Group", text_ctxt=ctxt).action = "LoadGroup"
        sce = bpy.context.scene
        if len(sce.sdn_history_item) == 0:
            return
        layout.template_list("HISTORY_UL_UIList", "", sce, "sdn_history_item", sce, "sdn_history_item_index")

    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        qr_num = len(TaskManager.query_server_task().get('queue_running', []))
        qp_num = TaskManager.get_task_num()
        row = layout.row(align=True)
        row.alert = True
        row.alignment = "CENTER"
        row.label(text="Pending / Running", text_ctxt=ctxt)
        row.label(text=f": {qp_num} / {qr_num}", text_ctxt=ctxt)
        prog = TaskManager.get_progress()
        if prog and prog.get("value"):
            import blf
            per = prog["value"] / prog["max"]
            content = f"{per*100:3.0f}% "
            lnum = int(bpy.context.region.width / bpy.context.preferences.view.ui_scale / 7 - 21)
            lnum = int(lnum * 0.3)
            lnum = int((bpy.context.region.width - blf.dimensions(0, content)[0]) / blf.dimensions(0, "█")[0]) - 10
            v = int(per * lnum)
            content = content + "█" * v + "░" * (lnum - v)
            row = layout.row()
            row.alignment = "CENTER"
            row.label(text=content[:134], text_ctxt=ctxt)

        for error_msg in TaskManager.get_error_msg():
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)
        if TaskManager.get_error_msg():
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)


class HistoryItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="")


class HISTORY_UL_UIList(bpy.types.UIList):

    def draw_item(self,
                  context: bpy.types.Context,
                  layout: bpy.types.UILayout,
                  data, item, icon, active_data, active_property, index, flt_flag):
        row = layout.row(align=True)
        row.label(text="  " + item.name)
        row.operator(Load_History.bl_idname, text="", icon="TIME").name = item.name

class PanelViewport(bpy.types.Panel):
    bl_idname = "SDNV_PT_UI"
    bl_translation_context = ctxt
    bl_label = get_addon_name()
    bl_description = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "圣杯节点"

    def draw(self, context: Context):
        rv3d = bpy.context.space_data.region_3d
        self.layout.prop(rv3d, "view_camera_offset")
        self.layout.prop(rv3d, "view_camera_zoom")

        self.layout.prop(rv3d, "view_distance")
        self.layout.prop(rv3d, "view_location")
        self.layout.prop(rv3d, "view_matrix")
        self.layout.prop(rv3d, "view_perspective")
        self.layout.prop(rv3d, "window_matrix")
        area = context.area
        # zoom to fac powf((float(M_SQRT2) + camzoom / 50.0f), 2.0f) / 4.0f;
        # max(area.width, area.height) * fac
        fac = (2**0.5 + rv3d.view_camera_zoom / 50)**2 / 4
        length = max(area.width, area.height) * fac

        self.layout.prop(area, "width")
        self.layout.prop(area, "height")
        self.layout.prop(area, "x")
        self.layout.prop(area, "y")
        space_data = context.space_data
        self.layout.label(text=f"{length:.2f}")
        self.layout.label(text=f"{fac:.6f}")

        settings = UnifiedPaintPanel.paint_settings(context)
        brush = settings.brush  # 可能报错 没brush(settings为空)
        tex_slot = brush.texture_slot
        col = self.layout.column()
        col.template_ID_preview(tex_slot, "texture", new="texture.new", rows=3, cols=8)

        # print(context.space_data.render_border_max_x)
        from .timer import Timer

        def f(brush, length, width, height):
            if not brush:
                return
            offset_top = bpy.context.preferences.view.ui_scale * 26
            enable_cam_offset = False
            if enable_cam_offset:
                coffx, coffy = rv3d.view_camera_offset
                coffw = coffx * width
                coffh = coffy * height
                hwidth = width / 2
                hheight = height / 2
                fac = (2**0.5 + rv3d.view_camera_zoom / 50)**2 / 4
                brush.stencil_pos = (hwidth - coffw, hheight - offset_top - coffh)
            else:
                rv3d.view_camera_offset = (0, 0)
                brush.stencil_pos = (width / 2, (height) / 2 - offset_top)
            brush.stencil_dimension = (length / 2, length / 2)
        Timer.put((f, brush, length, area.width, area.height))
