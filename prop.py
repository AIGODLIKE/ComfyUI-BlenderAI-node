import bpy
import os
from pathlib import Path

from .utils import Icon, FSWatcher
from .datas import PRESETS_DIR, PROP_CACHE, GROUPS_DIR

FSWatcher.register(PRESETS_DIR)
FSWatcher.register(GROUPS_DIR)

class Prop(bpy.types.PropertyGroup):
    cache = PROP_CACHE

    def mark_dirty():
        Prop.cache["presets"].clear()
        Prop.cache["groups"].clear()

    def presets_dir_items(self, context):
        items = []
        if not Prop.cache["presets_dir"] or FSWatcher.consume_change(PRESETS_DIR):
            for file in PRESETS_DIR.iterdir():
                if file.is_file():
                    continue
                items.append((str(file), file.name, "", len(items)))
            Prop.cache["presets_dir"].clear()
            Prop.cache["presets_dir"].extend(items)
        return Prop.cache["presets_dir"]
    presets_dir: bpy.props.EnumProperty(items=presets_dir_items, name="Presets Directory")

    def presets_items(self, context):
        pd = FSWatcher.to_path(self.presets_dir)
        if Prop.cache["presets"].get(pd):
            return Prop.cache["presets"][pd]
        items = []
        if not pd.exists():
            return items
        for file in pd.iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in pd.iterdir():
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
        if not Prop.cache["groups_dir"] or FSWatcher.consume_change(GROUPS_DIR):
            for file in GROUPS_DIR.iterdir():
                if file.is_file():
                    continue
                items.append((str(file), file.name, "", len(items)))
            Prop.cache["groups_dir"].clear()
            Prop.cache["groups_dir"].extend(items)
        return Prop.cache["groups_dir"]
    groups_dir: bpy.props.EnumProperty(items=groups_dir_items, name="Groups Directory")

    def groups_items(self, context):
        gd = FSWatcher.to_path(self.groups_dir)
        if Prop.cache["groups"].get(gd):
            return Prop.cache["groups"][gd]
        items = []
        if not gd.exists():
            return items
        for file in gd.iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in gd.iterdir():
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
        from . import bl_info
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
    frame_mode: bpy.props.EnumProperty(name="Frame Mode",
                                       items=[("SingleFrame", "SingleFrame", "SingleFrame", 0),
                                              ("MultiFrame", "MultiFrame", "MultiFrame", 1),
                                              ("Batch", "Batch", "Batch", 2),
                                              ])
    batch_dir: bpy.props.StringProperty(name="Batch Directory", default=Path.home().joinpath("Desktop").as_posix(), subtype="DIR_PATH")
    disable_render_all: bpy.props.BoolProperty(default=False, description="禁用场景树所有渲染行为")