bl_info = {
    'name': '无限圣杯-节点',
    'author': '幻之境开发小组-会飞的键盘侠、只剩一瓶辣椒酱',
    'version': (1, 0, 0),
    'blender': (3, 0, 0),
    'location': '3DView->Panel',
    'category': '辣椒出品',
    'doc_url': "https://shimo.im/docs/Ee32m0w80rfLp4A2"
}

import os
import json
import bpy
from pathlib import Path
from functools import partial
from threading import Thread
from mathutils import Vector
from .translation import translations_dict, ctxt
from .utils import logger, Icon, PngParse, _T
from .SDNode import rtnode_reg, rtnode_unreg, TaskManager, Task
from .timer import Timer, timer_reg, timer_unreg
from .preference import AddonPreference, get_pref
from .datas import PRESETS_DIR, GROUPS_DIR, PROP_CACHE


def get_version():
    # from . import bl_info
    return f"无限圣杯 Node{'.'.join([str(i) for i in bl_info['version']])}"


class Panel(bpy.types.Panel):
    bl_idname = "SDN_PT_UI"
    bl_translation_context = ctxt
    bl_label = get_version()
    bl_description = ""
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "圣杯节点"

    def draw_header(self, context):
        sdn = bpy.context.scene.sdn
        row = self.layout.row(align=True)
        row.prop(sdn, 'open_pref', text="", icon="PREFERENCES", text_ctxt=ctxt)
        row.operator("wm.console_toggle", text="", icon="CONSOLE", text_ctxt=ctxt)
        # row.prop(sdn, "restart_webui", text="", icon="RECOVER_LAST")
        row.operator(Ops.bl_idname, text="", icon="RECOVER_LAST", text_ctxt=ctxt).action = "Restart"
        row.prop(sdn, "open_webui", text="", icon="URL", text_ctxt=ctxt)

    def draw(self, context: bpy.types.Context):
        scale_popup = get_pref().popup_scale
        layout = self.layout
        
        layout.operator(Ops.bl_idname, text="Execute Node Tree", text_ctxt=ctxt).action = "Submit"
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
        rrow.operator(Ops.bl_idname, text="", icon="TEXTURE", text_ctxt=ctxt).action = "Preset_from_Image"
        
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



    def show_progress(self, layout: bpy.types.UILayout):
        layout = layout.box()
        qr_num = len(TaskManager.query_server_task().get('queue_running', []))
        qp_num = TaskManager.task_queue.qsize()
        row = layout.row(align=True)
        row.alert = True
        row.alignment = "CENTER"
        row.label(text="Pending / Running", text_ctxt=ctxt)
        row.label(text=f": {qp_num} / {qr_num}", text_ctxt=ctxt)

        prog = TaskManager.progress
        if prog and prog.get("value"):
            width = bpy.context.region.width // int(10 * bpy.context.preferences.view.ui_scale) - 14
            per = prog["value"] / prog["max"]
            v = int(per * width)
            m = width
            # content = "█" * v + "░" * (m - v) + f" {v}/{m}" + f" {per*100:3.0f}%"
            content = f"{per*100:3.0f}% " + "█" * v + "░" * (m - v)
            row = layout.row()
            row.alignment = "CENTER"
            row.label(text=content[:134], text_ctxt=ctxt)

        for error_msg in TaskManager.error_msg:
            row = layout.row()
            row.alert = True
            row.label(text=error_msg, icon="ERROR", text_ctxt=ctxt)
        if TaskManager.error_msg:
            row = layout.box().row()
            row.alignment = "CENTER"
            row.alert = True
            row.label(text="Adjust node tree and try again", text_ctxt=ctxt)

class Ops(bpy.types.Operator):
    bl_idname = "sdn.ops"
    bl_description = "SD Node"
    bl_label = "SD Node"
    bl_translation_context = ctxt
    action: bpy.props.StringProperty(default="")
    save_name: bpy.props.StringProperty(name="Preset Name", default="预设")
    
    @classmethod
    def description(cls, context: bpy.types.Context,
                    properties: bpy.types.OperatorProperties) -> str:
        desc = "SD Node"
        if properties.get("action") == "Preset_from_Image":
            desc = "Load from Image"
        return desc
    
    def import_image_set(self, value):
        png = Path(value)
        if not png.exists() or png.suffix != ".png":
            logger.error(_T("Image not found or format error(png only)"))
            logger.error(str(png))
            logger.error(png.cwd())
            return
        data = PngParse.read_text_chunk(value).get("workflow")
        if not data:
            return
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return
        tree.load_json(json.loads(data))
        
    import_image: bpy.props.StringProperty(name="Preset Image", default=str(Path.cwd()), subtype="FILE_PATH", set=import_image_set)

    def draw(self, context):
        layout = self.layout
        if self.action == "Save":
            if (Path(bpy.context.scene.sdn.presets_dir) / f"{self.save_name}.json").exists():
                layout.alert = True
                layout.label(text=f"{_T('Preset')}<{self.save_name}>{_T('exists, Click Ok to Overwrite!')}", icon="ERROR", text_ctxt=ctxt)
                layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
            layout.prop(self, "save_name", text_ctxt=ctxt)
        if self.action == "SaveGroup":
            if (Path(bpy.context.scene.sdn.groups_dir) / f"{self.save_name}.json").exists():
                layout.alert = True
                layout.label(text=f"{_T('Preset')}<{self.save_name}>{_T('exists, Click Ok to Overwrite!')}", icon="ERROR", text_ctxt=ctxt)
                layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
            layout.prop(self, "save_name", text_ctxt=ctxt)

        if self.action == "Del":
            layout.alert = True
            layout.label(text=f"{_T('Preset')}<{Path(bpy.context.scene.sdn.presets).stem}>{_T('will be removed?')}", icon="ERROR", text_ctxt=ctxt)
            layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
        if self.action == "DelGroup":
            layout.alert = True
            layout.label(text=f"{_T('Preset')}<{Path(bpy.context.scene.sdn.groups).stem}>{_T('will be removed?')}", icon="ERROR", text_ctxt=ctxt)
            layout.label(text="Click Outside to Cancel!", icon="ERROR", text_ctxt=ctxt)
        if self.action == "Preset_from_Image":
            layout.label(text="Click Folder Icon to Select Image:", text_ctxt=ctxt)
            layout.prop(self, "import_image", text_ctxt=ctxt)
            
    def invoke(self, context, event: bpy.types.Event):
        # logger.error("INVOKE")
        self.select_nodes = []
        self.init_pos = context.space_data.cursor_location.copy()
        if self.action in {"Load", "Del"}:
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        if self.action in {"LoadGroup", "DelGroup"}:
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}

        wm = bpy.context.window_manager
        if self.action in {"Save", "SaveGroup", "Del", "DelGroup", "Preset_from_Image"}:
            return wm.invoke_props_dialog(self, width=200)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        # logger.debug("EXE")
        tree = bpy.context.space_data.edit_tree
        if not tree:
            return {"FINISHED"}
        if self.action == "Submit":
            prompt = tree.serialize()
            workflow = tree.save_json()
            TaskManager.push_task({"prompt": prompt, "workflow": workflow, "api": "prompt"})
        elif self.action == "Restart":
            TaskManager.restart_server()
        elif self.action == "Save":
            data = tree.save_json()
            if not self.save_name:
                self.report({"ERROR"}, _T("Invalid Preset Name!"))
                return {"CANCELLED"}
            file = Path(bpy.context.scene.sdn.presets_dir) / f"{self.save_name}.json"
            with open(file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Prop.mark_dirty()
            
        elif self.action == "Del":
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            preset = Path(bpy.context.scene.sdn.presets)
            preset.unlink()
            self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
            Prop.mark_dirty()
        elif self.action == "Load":
            if not bpy.context.scene.sdn.presets:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            tree.load_json(json.load(open(bpy.context.scene.sdn.presets)))

        elif self.action == "SaveGroup":
            data = tree.save_json_group()
            if not self.save_name:
                self.report({"ERROR"}, _T("Invalid Preset Name!"))
                return {"CANCELLED"}
            file = Path(bpy.context.scene.sdn.groups_dir) / f"{self.save_name}.json"
            with open(file, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            Prop.mark_dirty()
        elif self.action == "DelGroup":
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            preset = Path(bpy.context.scene.sdn.groups)
            preset.unlink()
            self.report({"INFO"}, f"{preset.stem} {_T('Removed')}")
            Prop.mark_dirty()
        elif self.action == "LoadGroup":
            if not bpy.context.scene.sdn.groups:
                self.report({"ERROR"}, _T("Preset Not Selected!"))
                return {"FINISHED"}
            select_nodes = tree.load_json_group(json.load(open(bpy.context.scene.sdn.groups)))
            if not select_nodes:
                return {"FINISHED"}
            self.select_nodes = select_nodes
            v = Vector([0, 0])
            for n in select_nodes:
                v += n.location
            v /= len(select_nodes)
            self.init_node_pos = {}
            for n in select_nodes:
                n.location += context.space_data.cursor_location - v
                self.init_node_pos[n] = n.location.copy()

            bpy.context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        elif self.action == "Preset_from_Image":
            return {"FINISHED"}
            # png = Path(self.import_image)
            # logger.error(self.import_image)
            # if not png.exists() or png.suffix != ".png":
            #     self.report({"ERROR"}, "魔法图鉴不存在或格式不正确(仅png)")
            #     return {"FINISHED"}
            # data = PngParse.read_text_chunk(self.import_image)
            # logger.error(data)
        return {"FINISHED"}

    def update_nodes_pos(self, event):
        for n in self.select_nodes:
            n.location = self.init_node_pos[n] + bpy.context.space_data.cursor_location - self.init_pos

    def modal(self, context, event: bpy.types.Event):
        if not self.select_nodes:
            return {"FINISHED"}
        if event.type == "MOUSEMOVE":
            self.update_nodes_pos(event)

        # exit
        if event.value == "PRESS" and event.type in {"ESC", "LEFTMOUSE", "ENTER"}:
            return {"FINISHED"}
        if event.value == "PRESS" and event.type in {"RIGHTMOUSE"}:
            tree = bpy.context.space_data.edit_tree
            tree.safe_remove_nodes(self.select_nodes[:])
            return {"CANCELLED"}

        return {"RUNNING_MODAL"}


class Prop(bpy.types.PropertyGroup):
    cache = PROP_CACHE

    def mark_dirty():
        Prop.cache["presets"].clear()
        Prop.cache["groups"].clear()

    def presets_dir_items(self, context):
        items = []
        for file in PRESETS_DIR.iterdir():
            if file.is_file():
                continue
            items.append((str(file), file.name, "", len(items)))
        if items != Prop.cache["presets_dir"]:
            Prop.cache["presets_dir"].clear()
            Prop.cache["presets_dir"].extend(items)
        return Prop.cache["presets_dir"]
    presets_dir: bpy.props.EnumProperty(items=presets_dir_items, name="Presets Directory")

    def presets_items(self, context):
        pd = self.presets_dir
        if Prop.cache["presets"].get(pd):
            return Prop.cache["presets"][pd]
        items = []
        for file in Path(pd).iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in Path(pd).iterdir():
                if not (file.name in img.stem and img.suffix in {".png", ".jpg", ".jpeg"}):
                    continue
                icon_id = Icon.reg_icon(img)
            items.append((str(file), file.stem, "", icon_id, len(items)))
        Prop.cache["presets"][pd] = items
        return Prop.cache["presets"][pd]
    presets: bpy.props.EnumProperty(items=presets_items, name="Presets")

    def update_open_presets_dir(self, context):
        if self.open_presets_dir:
            self.open_presets_dir = False
            os.startfile(str(PRESETS_DIR))

    open_presets_dir: bpy.props.BoolProperty(default=False, name="Open NodeGroup Presets Folder", update=update_open_presets_dir)

    def groups_dir_items(self, context):
        items = []
        for file in GROUPS_DIR.iterdir():
            if file.is_file():
                continue
            items.append((str(file), file.name, "", len(items)))
        if items != Prop.cache["groups_dir"]:
            Prop.cache["groups_dir"].clear()
            Prop.cache["groups_dir"].extend(items)
        return Prop.cache["groups_dir"]
    groups_dir: bpy.props.EnumProperty(items=groups_dir_items, name="Groups Directory")

    def groups_items(self, context):
        gd = self.groups_dir
        if Prop.cache["groups"].get(gd):
            return Prop.cache["groups"][gd]
        items = []
        for file in Path(gd).iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in Path(gd).iterdir():
                if not (file.name in img.stem and img.suffix in {".png", ".jpg", ".jpeg"}):
                    continue
                icon_id = Icon.reg_icon(img)
            items.append((str(file), file.stem, "", icon_id, len(items)))
        Prop.cache["groups"][gd] = items
        return Prop.cache["groups"][gd]
    groups: bpy.props.EnumProperty(items=groups_items, name="Presets")

    def update_open_groups_dir(self, context):
        if self.open_groups_dir:
            self.open_groups_dir = False
            os.startfile(str(GROUPS_DIR))

    open_groups_dir: bpy.props.BoolProperty(default=False, name="Open NodeTree Presets Folder", update=update_open_groups_dir)

    def open_pref_update(self, context):
        if self.open_pref:
            self.open_pref = False
            category = bl_info.get('category')

            import addon_utils
            bpy.ops.screen.userpref_show()
            bpy.context.preferences.active_section = 'ADDONS'
            if category is None:
                bpy.context.window_manager.addon_search = bl_info.get('name')
            else:
                bpy.context.window_manager.addon_filter = category

            addon_utils.modules(refresh=False)[0].__name__
            package = __package__.split(".")[0]
            for mod in addon_utils.modules(refresh=False):
                if mod.__name__ == package:
                    if not mod.bl_info['show_expanded']:
                        bpy.ops.preferences.addon_expand(module=package)
    open_pref: bpy.props.BoolProperty(default=False, name="Open Addon Preference", update=open_pref_update)

    def restart_webui_update(self, context):
        if self["restart_webui"]:
            self["restart_webui"] = False
            bpy.ops.sdn.ops(action="Restart")
    restart_webui: bpy.props.BoolProperty(default=False, update=restart_webui_update, name="Restart ComfyUI")

    def open_webui_update(self, context):
        if self["open_webui"]:
            self["open_webui"] = False
            from .SDNode.manager import url
            bpy.ops.wm.url_open(url=url)
    open_webui: bpy.props.BoolProperty(default=False, update=open_webui_update, name="Launch ComfyUI")

    rand_all_seed: bpy.props.BoolProperty(default=False, name="Random All")


clss = [Panel, Ops, Prop, AddonPreference]
reg, unreg = bpy.utils.register_classes_factory(clss)


def register():
    bpy.app.translations.register(__name__, translations_dict)
    reg()
    Icon.set_hq_preview()
    TaskManager.run_server()
    timer_reg()
    bpy.types.Scene.sdn = bpy.props.PointerProperty(type=Prop)


def unregister():
    bpy.app.translations.unregister(__name__)
    unreg()
    rtnode_unreg()
    timer_unreg()
    del bpy.types.Scene.sdn
