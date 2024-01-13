from __future__ import annotations
import bpy
import os
import json
from pathlib import Path

from .preference import get_pref
from .utils import Icon, FSWatcher, ScopeTimer
from .datas import PRESETS_DIR, PROP_CACHE, GROUPS_DIR, IMG_SUFFIX

FSWatcher.register(PRESETS_DIR)
FSWatcher.register(GROUPS_DIR)


class RenderLayerString(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Render Layer Name")


class Prop(bpy.types.PropertyGroup):
    cache = PROP_CACHE

    def mark_dirty():
        Prop.cache["presets_dir"].clear()
        Prop.cache["groups_dir"].clear()
        Prop.cache["presets"].clear()
        Prop.cache["groups"].clear()

    def update_prop_cache(search_dir: list[Path], t="presets"):
        items = []
        for item in get_pref().pref_dirs:
            if not item.enabled:
                continue
            dirpath = Path(item.path).joinpath(t)
            if not dirpath.exists() or not dirpath.is_dir():
                continue
            search_dir.append(dirpath)
        changed = [FSWatcher.consume_change(dp) for dp in search_dir]
        if Prop.cache[f"{t}_dir"] and not any(changed):  # 没有改变
            return
        # 有改变
        for dirpath in search_dir:
            for p in dirpath.iterdir():
                if p.is_file():
                    continue
                FSWatcher.register(p)
                if dirpath.parent.name == __package__:
                    dpn = "*"
                else:
                    dpn = f"[{dirpath.parent.name}]"
                abspath = dirpath.parent.resolve().as_posix()
                fpath = p.resolve().as_posix()
                items.append((fpath, f"{p.name} {dpn}", abspath, len(items)))
        if items:
            Prop.cache[f"{t}_dir"].clear()
            Prop.cache[f"{t}_dir"].extend(items)

    def presets_dir_items(self, context):
        # t = ScopeTimer("presets_dir_items")
        Prop.update_prop_cache([PRESETS_DIR], "presets")
        return Prop.cache["presets_dir"]
    presets_dir: bpy.props.EnumProperty(items=presets_dir_items, name="Presets Directory")

    def presets_items(self, context):
        pd = FSWatcher.to_path(self.presets_dir)
        if Prop.cache["presets"].get(pd) and not FSWatcher.consume_change(pd):
            return Prop.cache["presets"][pd]
        items = []
        if not pd.exists():
            return items
        for file in pd.iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in pd.iterdir():
                if not (file.name in img.stem and img.suffix in IMG_SUFFIX):
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
        Prop.update_prop_cache([GROUPS_DIR], "groups")
        return Prop.cache["groups_dir"]

    groups_dir: bpy.props.EnumProperty(items=groups_dir_items, name="Groups Directory")

    def groups_items(self, context):
        gd = FSWatcher.to_path(self.groups_dir)
        if Prop.cache["groups"].get(gd) and not FSWatcher.consume_change(gd):
            return Prop.cache["groups"][gd]
        items = []
        if not gd.exists():
            return items
        for file in gd.iterdir():
            if file.suffix != ".json":
                continue
            icon_id = Icon["None"]
            for img in gd.iterdir():
                if not (file.name in img.stem and img.suffix in IMG_SUFFIX):
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
            from .SDNode.manager import get_url
            bpy.ops.wm.url_open(url=get_url())
    open_webui: bpy.props.BoolProperty(default=False, update=open_webui_update, name="Launch ComfyUI")

    rand_all_seed: bpy.props.BoolProperty(default=False, name="Random All")
    frame_mode: bpy.props.EnumProperty(name="Frame Mode",
                                       items=[("SingleFrame", "SingleFrame", "SingleFrame", 0),
                                              ("MultiFrame", "MultiFrame", "MultiFrame", 1),
                                              ("Batch", "Batch", "Batch", 2),
                                              ])
    batch_dir: bpy.props.StringProperty(name="Batch Directory", default=Path.home().joinpath("Desktop").as_posix(), subtype="DIR_PATH")
    disable_render_all: bpy.props.BoolProperty(default=False, description="Disable Render All")
    advanced_exe: bpy.props.BoolProperty(default=False, description="Advanced Setting")
    batch_count: bpy.props.IntProperty(default=1, min=1, name="Batch exec num")
    loop_exec: bpy.props.BoolProperty(default=False, name="Loop exec")
    render_layer: bpy.props.CollectionProperty(type=RenderLayerString)
    show_pref_general: bpy.props.BoolProperty(default=False, name="General Setting", description="Show General Setting")

    def import_bookmark_update(self, context):
        from .kclogger import logger
        from .utils import PngParse, _T
        from .SDNode.tree import TREE_TYPE
        value = self.import_bookmark
        path = Path(value)
        if not path.exists() or path.suffix.lower() not in {".png", ".json"}:
            logger.error(_T("Image not found or format error(png/json)"))
            logger.error(str(path))
            logger.error(path.cwd())
            return
        data = None
        if path.suffix.lower() == ".png":
            odata = PngParse.read_text_chunk(value)
            data = odata.get("workflow")
            if not data:
                logger.error(_T("Load Preset from Image Error -> MetaData Not Found in") + " " + str(odata))
                return
        elif path.suffix.lower() == ".json":
            data = path.read_text()

        tree = getattr(bpy.context.space_data, "node_tree", None)
        if not tree:
            bpy.ops.node.new_node_tree(type=TREE_TYPE, name="NodeTree")
            tree = getattr(bpy.context.space_data, "node_tree", None)
        if not tree:
            return
        data = json.loads(data)
        if "workflow" in data:
            data = data["workflow"]
        tree.load_json(data)

    import_bookmark: bpy.props.StringProperty(name="Preset Bookmark", default=str(Path.cwd()), subtype="FILE_PATH",update=import_bookmark_update)


def render_layer_update():
    try:
        bpy.context.scene.sdn.render_layer.clear()
        if not bpy.context.scene.use_nodes:
            return 1
        for node in bpy.context.scene.node_tree.nodes:
            if node.type != "R_LAYERS":
                continue
            item = bpy.context.scene.sdn.render_layer.add()
            item.name = node.name
    except (BaseException, AttributeError):
        ...
    return 1


bpy.app.timers.register(render_layer_update, persistent=True)
