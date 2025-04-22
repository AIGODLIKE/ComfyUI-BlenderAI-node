import bpy
import platform
from bl_ui.properties_paint_common import UnifiedPaintPanel
from bpy.types import Context
from .ops import Ops, Load_History, Copy_Tree, Load_Batch, Fetch_Node_Status, Clear_Node_Cache, SDNode_To_Image, Image_To_SDNode, Image_Set_Channel_Packed, Open_Log_Window, Sync_Stencil_Image
from .translations import ctxt
from .SDNode import TaskManager, FakeServer
from .SDNode.tree import TREE_TYPE
from .SDNode.nodes import NodeBase
from .SDNode.rt_tracker import Tracker_Loop, is_looped
from .SDNode.operators import AIMatSolutionLoad, AIMatSolutionRun, AIMatSolutionSave, AIMatSolutionDel, AIMatSolutionApply, AIMatSolutionRestore, AIBrushLoad, AIBrushSolutionRun, AIBrushDel
from .utils import Icon
from .preference import get_pref, AddonPreference
from .utils import get_addon_name, _T, get_ai_mat_tree, get_ai_brush_tree


class Panel(bpy.types.Panel):
    bl_idname = "SDN_PT_UI"
    bl_translation_context = ctxt
    bl_label = get_addon_name()
    bl_description = ""
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "ComfyUI"

    @classmethod
    def poll(cls, context):
        return context.space_data.type == 'NODE_EDITOR' and context.space_data.tree_type == TREE_TYPE

    def draw_header(self, context: Context):
        row = self.layout.row(align=True)
        if not hasattr(bpy.context.scene, "sdn"):
            row.operator(Clear_Node_Cache.bl_idname, text="", icon="MODIFIER", text_ctxt=ctxt)
            return
        sdn = bpy.context.scene.sdn
        row.prop(sdn, 'open_pref', text="", icon="PREFERENCES", text_ctxt=ctxt)

    def draw_header_preset(self, context: Context):
        row = self.layout.row(align=True)
        if not hasattr(bpy.context.scene, "sdn"):
            row.operator(Clear_Node_Cache.bl_idname, text="", icon="MODIFIER", text_ctxt=ctxt)
            return
        sdn = bpy.context.scene.sdn
        if platform.system() not in ['Linux', 'Darwin']:
            row.operator("wm.console_toggle", text="", icon="CONSOLE", text_ctxt=ctxt)
        # row.prop(sdn, "restart_webui", text="", icon="RECOVER_LAST")
        if TaskManager.server == FakeServer._instance:
            row.operator(Ops.bl_idname, text="", icon="QUIT", text_ctxt=ctxt).action = "Launch"
        else:
            row.alert = True
            row.operator(Ops.bl_idname, text="", icon="QUIT", text_ctxt=ctxt).action = "Close"
            row.alert = False

        row.operator(Fetch_Node_Status.bl_idname, text="", icon="FILE_REFRESH", text_ctxt=ctxt)
        row.operator(Ops.bl_idname, text="", icon="RECOVER_LAST", text_ctxt=ctxt).action = "Restart"
        row.prop(sdn, "open_webui", text="", icon="URL", text_ctxt=ctxt)
        row.operator(Clear_Node_Cache.bl_idname, text="", icon="BRUSH_DATA", text_ctxt=ctxt)

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        if not hasattr(bpy.context.scene, "sdn"):
            row = layout.row()
            row.operator(Clear_Node_Cache.bl_idname, text="Clear Node Cache", icon="MODIFIER")
            row.alert = True
            row.scale_y = 2
            return
        if get_pref().debug:
            self.show_debug(layout)
        elif TaskManager.server == FakeServer._instance:
            self.show_launch_cnn(layout)
            return
        elif TaskManager.is_launching():
            box = layout.box()
            box.alert = True
            box.scale_y = 2
            row = box.row()
            row.alignment = "CENTER"
            row.label(text="ComfyUI Launching/Connecting...", icon="INFO")
            row = box.row()
            row.alignment = "CENTER"
            row.label(text=TaskManager.server.get_running_info(), icon="TIME")
            return
        self.show_common(layout)
        self.show_custom(layout)

    def show_common(self, layout: bpy.types.UILayout):
        scale_popup = get_pref().popup_scale
        col = layout.column()
        row1 = col.row(align=True)
        row1.alert = True
        row1.scale_y = 2
        if Ops.is_advanced_enable:
            row1.operator(Ops.bl_idname, text="Stop Loop", icon="PAUSE").action = "StopLoop"
        else:
            row1.operator(Ops.bl_idname, text="Execute Node Tree", icon="PLAY").action = "Submit"
        row1.prop(bpy.context.scene.sdn, "advanced_exe", text="", icon="SETTINGS")
        if is_looped():
            icon = "PAUSE"
            action = "STOP"
        else:
            icon = "TIME"
            action = "START"
        layout.operator(Tracker_Loop.bl_idname, text="", icon=icon).action = action
        if bpy.context.scene.sdn.advanced_exe:
            adv_col = col.box().column(align=True)
            adv_col.prop(bpy.context.scene.sdn, "loop_exec", text_ctxt=ctxt, toggle=True)
            if not bpy.context.scene.sdn.loop_exec:
                adv_col.prop(bpy.context.scene.sdn, "batch_count", text_ctxt=ctxt)

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

    def show_custom(self, layout: bpy.types.UILayout):
        from .SDNode import crystools_monitor
        crystools_monitor.draw(layout)

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

    def show_debug(self, layout: bpy.types.UILayout):
        self.show_launch_cnn(layout)
        return
        rv3d = bpy.context.space_data.region_3d
        layout.prop(rv3d, "view_camera_offset")
        layout.prop(rv3d, "view_camera_zoom")

        layout.prop(rv3d, "view_distance")
        layout.prop(rv3d, "view_location")
        layout.prop(rv3d, "view_matrix")
        layout.prop(rv3d, "view_perspective")
        layout.prop(rv3d, "window_matrix")

    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        from .SDNode.custom_support import cup_monitor
        cup_monitor.draw(layout)
        self.show_error(layout)
        if TaskManager.get_error_msg():
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)

    def show_error(self, layout: bpy.types.UILayout):
        for error_msg in TaskManager.get_error_msg():
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)


def draw_header_button(self: bpy.types.Menu, context):
    if context.space_data.tree_type == TREE_TYPE:
        layout = self.layout
        col = layout.column()
        col.alert = True
        col.operator(Ops.bl_idname, text="", text_ctxt=ctxt, icon="PLAY").action = "Submit"


def draw_sdn_tofrom(self: bpy.types.Menu, context):
    layout = self.layout
    if context.space_data.tree_type == TREE_TYPE:
        layout.separator()
        layout.operator(SDNode_To_Image.bl_idname, text="To Image Editor", text_ctxt=ctxt, icon="EXPORT")
        props = layout.operator(Image_To_SDNode.bl_idname, text="From Image Editor", text_ctxt=ctxt, icon="IMPORT")
        props.force_centered = True


def draw_imeditor_tofrom(self: bpy.types.Menu, context):
    layout = self.layout
    layout.separator()
    layout.operator(Image_Set_Channel_Packed.bl_idname, text_ctxt=ctxt)  # , icon="MOD_MASK")
    layout.operator(Image_To_SDNode.bl_idname, text="To ComfyUI Node Editor", text_ctxt=ctxt, icon="EXPORT")
    layout.operator(SDNode_To_Image.bl_idname, text="From ComfyUI Node Editor", text_ctxt=ctxt, icon="IMPORT")


class HistoryItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="")


class HISTORY_UL_UIList(bpy.types.UIList):

    def draw_item(self,
                  context: bpy.types.Context,
                  layout: bpy.types.UILayout,
                  data, item, icon, active_data, active_property, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.label(text="  " + item.name)
        row.operator(Load_History.bl_idname, text="", icon="TIME").name = item.name


class AIMatPanel(bpy.types.Panel):
    bl_idname = "SDN_AIMAT_PT_UI"
    bl_translation_context = ctxt
    bl_label = get_addon_name()
    bl_description = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI"
    bl_order = 0

    def draw_header_preset(self, context: Context):
        layout = self.layout
        layout.prop(bpy.context.scene.sdn, "open_ai_sol_dir", text="", icon="FILE_FOLDER")

    def draw(self, context: Context):
        layout = self.layout
        # if not hasattr(bpy.context.scene, "sdn"):
        #     row = layout.row()
        #     row.operator(Clear_Node_Cache.bl_idname, text="Clear Node Cache", icon="MODIFIER")
        #     row.alert = True
        #     row.scale_y = 2
        #     return
        # if TaskManager.server == FakeServer._instance:
        #     self.show_launch_cnn(layout)
        #     return
        # elif TaskManager.is_launching():
        #     box = layout.box()
        #     box.alert = True
        #     box.scale_y = 2
        #     row = box.row()
        #     row.alignment = "CENTER"
        #     row.label(text="ComfyUI Launching/Connecting...", icon="INFO")
        #     row = box.row()
        #     row.alignment = "CENTER"
        #     row.label(text=TaskManager.server.get_running_info(), icon="TIME")
        #     return
        self.show_common(layout)
        self.show_nodes(layout)

    def show_common(self, layout: bpy.types.UILayout):
        row = layout.row(align=True)
        row.prop(bpy.context.scene.sdn, "ai_gen_solution", text="")
        row.prop(bpy.context.scene.sdn, "clear_material_slots", text="", icon="CON_TRANSLIKE")
        row.operator(AIMatSolutionSave.bl_idname, text="", icon="FILE_TICK")
        row.operator(AIMatSolutionDel.bl_idname, text="", icon="TRASH")
        layout.template_icon_view(bpy.context.scene.sdn, "ai_gen_solution", show_labels=True, scale_popup=5)
        row = layout.row(align=True)
        row.prop(bpy.context.scene.sdn, "ai_mat_tex_size", text="")
        row.operator(AIMatSolutionLoad.bl_idname, text_ctxt=ctxt)
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.alert = bool(get_ai_mat_tree(bpy.context.object))
        crow = col.row(align=True)
        crow.operator(AIMatSolutionRun.bl_idname, text_ctxt=ctxt, icon="PLAY")
        crcol = crow.column(align=True)
        crcol.enabled = bool(get_ai_mat_tree(bpy.context.object))
        crcol.prop(bpy.context.scene.sdn, "send_ai_mat_tree_to_editor", text="", icon="FILE_REFRESH")
        row = layout.row(align=True)
        if bpy.context.object and bpy.context.object.get("AI_Mat_Gen_Applied", None):
            row.alert = True
            row.label(text="Applying...", icon="RECORD_ON")
            row.label(text="", icon="RECORD_ON")
            row.label(text="", icon="RECORD_ON")
            row.label(text="", icon="RECORD_ON")
            row.label(text="", icon="RECORD_ON")
            row.label(text="", icon="RECORD_ON")
        else:
            row.operator(AIMatSolutionApply.bl_idname, text_ctxt=ctxt, icon="EVENT_RETURN")  # KEY_RETURN_FILLED
            row.operator(AIMatSolutionRestore.bl_idname, text_ctxt=ctxt, icon="LOOP_BACK")  # KEY_BACKSPACE_FILLED
            layout.prop(bpy.context.scene.sdn, "apply_bake_pass", text="")
        self.show_progress(layout)
        # if bpy.context.object and "AI_Mat_Gen_TexID" in bpy.context.object:
        #     layout.template_icon(bpy.context.object["AI_Mat_Gen_TexID"], scale=10)
        #     # layout.template_preview(bpy.context.object["AI_Mat_Gen_Tex"].preview.icon_id)

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

    def show_error(self, layout):
        for error_msg in TaskManager.get_error_msg():
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)

    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        from .SDNode.custom_support import cup_monitor
        cup_monitor.draw(layout)
        self.show_error(layout)
        if TaskManager.get_error_msg():
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)

    def show_nodes(self, layout: bpy.types.UILayout):
        tree = get_ai_mat_tree(bpy.context.object)
        if not tree:
            return
        nodes: list[NodeBase] = []
        for node in tree.nodes:
            if len(node.label) != 3:
                continue
            # 判断 label 为 001 - 999 之间的字符串
            if not node.label.isdigit() or int(node.label) < 1 or int(node.label) > 999:
                continue
            nodes.append(node)
        nodes.sort(key=lambda x: x.label)
        for node in nodes:
            box = layout.box()
            row = box.row()
            row.prop(node, "ac_expand", icon="TRIA_DOWN" if node.ac_expand else "TRIA_RIGHT", text="", emboss=False)
            if node.type != "GROUP":
                row.label(text=node.name)
            elif node.node_tree:
                row.label(text=node.node_tree.name)
            if node.ac_expand is False:
                continue
            if bpy.app.version >= (4, 2):
                box.separator(type="LINE")
            else:
                box.separator()
            node.draw_buttons(bpy.context, box)

    def find_node_input(self, node: bpy.types.Node) -> list[bpy.types.NodeSocket]:
        sockets = []
        for inp in node.inputs:
            if inp.is_linked:
                continue
            if inp.enabled is False or inp.hide:
                continue
            if inp.type == "RGBA" and inp.hide_value:
                continue
            sockets.append(inp)
        return sockets


class AIBrushPanel(bpy.types.Panel):
    bl_idname = "SDN_AIBRUSH_PT_UI"
    bl_translation_context = ctxt
    bl_label = "AI Brush"
    bl_description = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI"
    bl_order = 0

    def draw_header_preset(self, context: Context):
        layout = self.layout
        layout.prop(bpy.context.scene.sdn, "open_ai_brush_dir", text="", icon="FILE_FOLDER")

    def draw(self, context: Context):
        # for i in bpy.data.images:
        #     icon = bpy.app.icons.new_triangles_from_file("/Users/karrycharon/Desktop/BlenderAll/Blender 4.4.0Arm.app/Contents/Resources/4.4/datafiles/icons/brush.generic.dat")
        #     layout.label(text=i.name, icon_value=icon)
        layout = self.layout
        # if not hasattr(bpy.context.scene, "sdn"):
        #     row = layout.row()
        #     row.operator(Clear_Node_Cache.bl_idname, text="Clear Node Cache", icon="MODIFIER")
        #     row.alert = True
        #     row.scale_y = 2
        #     return
        # if TaskManager.server == FakeServer._instance:
        #     self.show_launch_cnn(layout)
        #     return
        # elif TaskManager.is_launching():
        #     box = layout.box()
        #     box.alert = True
        #     box.scale_y = 2
        #     row = box.row()
        #     row.alignment = "CENTER"
        #     row.label(text="ComfyUI Launching/Connecting...", icon="INFO")
        #     row = box.row()
        #     row.alignment = "CENTER"
        #     row.label(text=TaskManager.server.get_running_info(), icon="TIME")
        #     return
        self.show_common(layout)
        self.show_nodes(layout)

    def show_common(self, layout: bpy.types.UILayout):
        row = layout.row(align=True)
        row.prop(bpy.context.scene.sdn, "ai_brush", text="")
        row.operator(AIBrushDel.bl_idname, text="", icon="TRASH")
        layout.template_icon_view(bpy.context.scene.sdn, "ai_brush", show_labels=True, scale_popup=5)
        row = layout.row(align=True)
        row.prop(bpy.context.scene.sdn, "ai_brush_tex_size", text="")
        row.operator(AIBrushLoad.bl_idname, text_ctxt=ctxt)
        col = layout.column(align=True)
        col.scale_y = 1.5
        col.alert = bool(get_ai_brush_tree(bpy.context.object))
        crow = col.row(align=True)
        crow.operator(AIBrushSolutionRun.bl_idname, text_ctxt=ctxt, icon="PLAY")
        crcol = crow.column(align=True)
        crcol.enabled = bool(get_ai_brush_tree(bpy.context.object))
        crcol.prop(bpy.context.scene.sdn, "send_ai_brush_tree_to_editor", text="", icon="FILE_REFRESH")
        self.show_stencil_sync(crow)
        self.show_progress(layout)
        # if bpy.context.object and "AI_Mat_Gen_TexID" in bpy.context.object:
        #     layout.template_icon(bpy.context.object["AI_Mat_Gen_TexID"], scale=10)
        #     # layout.template_preview(bpy.context.object["AI_Mat_Gen_Tex"].preview.icon_id)

    def show_stencil_sync(self, layout: bpy.types.UILayout):
        if bpy.context.space_data.type != "VIEW_3D":
            return
        if bpy.context.area in Sync_Stencil_Image.areas:
            col = layout.column()
            col.alert = True
            col.operator(Sync_Stencil_Image.bl_idname, text="", icon="PAUSE").action = "Clear"
        else:
            layout.operator(Sync_Stencil_Image.bl_idname, text="", icon="GP_MULTIFRAME_EDITING")

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

    def show_error(self, layout):
        for error_msg in TaskManager.get_error_msg():
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)

    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        from .SDNode.custom_support import cup_monitor
        cup_monitor.draw(layout)
        self.show_error(layout)
        if TaskManager.get_error_msg():
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)

    def show_nodes(self, layout: bpy.types.UILayout):
        tree = get_ai_brush_tree(bpy.context.object)
        if not tree:
            return
        nodes: list[NodeBase] = []
        for node in tree.nodes:
            if len(node.label) != 3:
                continue
            # 判断 label 为 001 - 999 之间的字符串
            if not node.label.isdigit() or int(node.label) < 1 or int(node.label) > 999:
                continue
            nodes.append(node)
        nodes.sort(key=lambda x: x.label)
        for node in nodes:
            box = layout.box()
            row = box.row()
            row.prop(node, "ac_expand", icon="TRIA_DOWN" if node.ac_expand else "TRIA_RIGHT", text="", emboss=False)
            if node.type != "GROUP":
                row.label(text=node.name)
            elif node.node_tree:
                row.label(text=node.node_tree.name)
            if node.ac_expand is False:
                continue
            if bpy.app.version >= (4, 2):
                box.separator(type="LINE")
            else:
                box.separator()
            node.draw_buttons(bpy.context, box)

    def find_node_input(self, node: bpy.types.Node) -> list[bpy.types.NodeSocket]:
        sockets = []
        for inp in node.inputs:
            if inp.is_linked:
                continue
            if inp.enabled is False or inp.hide:
                continue
            if inp.type == "RGBA" and inp.hide_value:
                continue
            sockets.append(inp)
        return sockets


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


def status_bar_draw(self: bpy.types.Header, context: bpy.types.Context):
    layout = self.layout
    layout.label(text="[")
    from .SDNode.custom_support import cup_monitor
    cup_monitor.draw(layout, use_region_width=False)
    layout.operator(Open_Log_Window.bl_idname, text="", icon="WORDWRAP_ON")
    layout.label(text="]")


clss = (
    AIMatPanel,
    AIBrushPanel,
)

register, unregister = bpy.utils.register_classes_factory(clss)


def ui_reg():
    register()
    bpy.types.NODE_HT_header.append(draw_header_button)
    bpy.types.IMAGE_MT_image.append(draw_imeditor_tofrom)
    bpy.types.NODE_MT_node.append(draw_sdn_tofrom)
    bpy.types.STATUSBAR_HT_header.append(status_bar_draw)


def ui_unreg():
    bpy.types.STATUSBAR_HT_header.remove(status_bar_draw)
    bpy.types.NODE_HT_header.remove(draw_header_button)
    bpy.types.IMAGE_MT_image.remove(draw_imeditor_tofrom)
    bpy.types.NODE_MT_node.remove(draw_sdn_tofrom)
    unregister()
