from __future__ import annotations
import bpy
import os
import json
import time
from pathlib import Path
from .MultiLineText.trie import Trie

from .preference import get_pref
from .utils import Icon, FSWatcher, ScopeTimer, popup_folder, get_bl_info, get_name, get_ai_mat_tree
from .datas import PRESETS_DIR, PROP_CACHE, GROUPS_DIR, IMG_SUFFIX

FSWatcher.register(PRESETS_DIR)
FSWatcher.register(GROUPS_DIR)


class RenderLayerString(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Render Layer Name")


class MLTWord(bpy.types.PropertyGroup):
    value: bpy.props.StringProperty(name="Value")
    freq: bpy.props.IntProperty(name="Frequency")


class Prop(bpy.types.PropertyGroup):
    cache = PROP_CACHE

    @classmethod
    def mark_dirty(cls):
        cls.cache["presets_dir"].clear()
        cls.cache["groups_dir"].clear()
        cls.cache["presets"].clear()
        cls.cache["groups"].clear()

    @classmethod
    def update_prop_cache(cls, search_dir: list[Path], t="presets"):
        items = []
        for item in get_pref().pref_dirs:
            if not item.enabled:
                continue
            dirpath = Path(item.path).joinpath(t)
            if not dirpath.exists() or not dirpath.is_dir():
                continue
            search_dir.append(dirpath)
        changed = [FSWatcher.consume_change(dp) for dp in search_dir]
        if cls.cache[f"{t}_dir"] and not any(changed):  # 没有改变
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
            items.sort(key=lambda x: x[1])
            cls.cache[f"{t}_dir"].clear()
            cls.cache[f"{t}_dir"].extend(items)

    def presets_dir_items(self, context):
        # t = ScopeTimer("presets_dir_items")
        self.update_prop_cache([PRESETS_DIR], "presets")
        return self.cache["presets_dir"]

    presets_dir: bpy.props.EnumProperty(items=presets_dir_items, name="Presets Directory")

    def presets_items(self, context):
        pd = FSWatcher.to_path(self.presets_dir)
        if self.cache["presets"].get(pd) and not FSWatcher.consume_change(pd):
            return self.cache["presets"][pd]
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
        items.sort(key=lambda x: x[1])
        self.cache["presets"][pd] = items
        return self.cache["presets"][pd]
    presets: bpy.props.EnumProperty(items=presets_items, name="Presets")

    def update_open_presets_dir(self, context):
        if self.open_presets_dir:
            self.open_presets_dir = False
            popup_folder(PRESETS_DIR)

    open_presets_dir: bpy.props.BoolProperty(default=False, name="Open NodeGroup Presets Folder", update=update_open_presets_dir)

    def groups_dir_items(self, context):
        self.update_prop_cache([GROUPS_DIR], "groups")
        return self.cache["groups_dir"]

    groups_dir: bpy.props.EnumProperty(items=groups_dir_items, name="Groups Directory")

    def groups_items(self, context):
        gd = FSWatcher.to_path(self.groups_dir)
        if self.cache["groups"].get(gd) and not FSWatcher.consume_change(gd):
            return self.cache["groups"][gd]
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
        items.sort(key=lambda x: x[1])
        self.cache["groups"][gd] = items
        return self.cache["groups"][gd]

    groups: bpy.props.EnumProperty(items=groups_items, name="Presets")

    def update_open_groups_dir(self, context):
        if self.open_groups_dir:
            self.open_groups_dir = False
            popup_folder(GROUPS_DIR)

    open_groups_dir: bpy.props.BoolProperty(default=False, name="Open NodeTree Presets Folder", update=update_open_groups_dir)

    def open_pref_update(self, context):
        if not self.open_pref:
            return
        bl_info = get_bl_info()
        self.open_pref = False

        bpy.ops.screen.userpref_show()
        bpy.context.preferences.active_section = 'ADDONS'
        bpy.context.window_manager.addon_search = bl_info.get('name')
        try:
            bpy.context.window_manager.addon_filter = bl_info.get("category", "")
        except TypeError:
            pass
        bpy.ops.preferences.addon_expand(module=get_name())
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

    import_bookmark: bpy.props.StringProperty(name="Preset Bookmark", default=str(Path.cwd()), subtype="FILE_PATH", update=import_bookmark_update)

    def search_tag_update(self, context):
        from .MultiLineText.words_collection import words
        from .kclogger import logger
        if not Trie.TRIE:
            return
        mtw = bpy.context.window_manager.mlt_words
        mtw.clear()
        ts = time.time()
        candicates_words = Trie.TRIE.bl_search(self.search_tag, max_size=200)
        for word in candicates_words:
            it = mtw.add()
            if word[1] not in words.word_map:
                it.value = word[1]
                it.name = word[1]
                continue
            word = words.word_map[word[1]]
            it.value = word[0]
            it.name = word[0]
            if len(word) == 3 and word[2]:
                it.name = f"{word[0]} <== {word[2]}"
            it.freq = int(word[1])
        logger.info(f"Update Search Words: {time.time()-ts:.4f}s")

    search_tag: bpy.props.StringProperty(update=search_tag_update)

    LANG_SUFFIXES = {
        "en_US": "EN",
        "zh_CN": "CN",
        "zh_HANS": "CN",
    }

    @classmethod
    def _get_locale(cls):
        if not bpy.context.preferences.view.use_translate_interface:
            return "en_US"
        return bpy.app.translations.locale

    @classmethod
    def _get_locale_suffix(cls):
        return cls.LANG_SUFFIXES.get(cls._get_locale(), "EN")

    @classmethod
    def get_resource_dir(cls) -> Path:
        return Path(__file__).parent / "SDNode/resource"

    @classmethod
    def get_solution_dir(cls) -> Path:
        return cls.get_resource_dir() / "solutions" / cls._get_locale_suffix()

    @classmethod
    def find_icon(cls, name: str, path: Path) -> Path:
        SUFFIXES = [".png", ".jpg", ".jpeg", ".tiff"]
        for suf in SUFFIXES:
            img = path.joinpath(name).with_suffix(suf)
            if not img.exists():
                continue
            return img
        return cls.get_resource_dir().joinpath("icons/none.jpeg")

    _ref_items = {}

    def ai_gen_solution_items(self, context):
        rdir = self.get_solution_dir()
        FSWatcher.register(rdir)
        if not FSWatcher.consume_change(rdir) and rdir in self._ref_items:
            return self._ref_items.get(rdir, [])
        items = []
        self._ref_items[rdir] = items
        for f in sorted(rdir.glob("*.blend"), key=lambda x: x.name):
            icon_path = self.find_icon(f.stem, rdir)
            Icon.reg_icon(icon_path.as_posix(), hq=True)
            icon_id = Icon.get_icon_id(icon_path)
            items.append((f.as_posix(), f.stem, f.stem, icon_id, len(items)))
        return self._ref_items.get(rdir, [])

    ai_gen_solution: bpy.props.EnumProperty(name="AI Mat Solution", items=ai_gen_solution_items)
    clear_material_slots: bpy.props.BoolProperty(name="Clear Material Slots", default=True)

    def update_open_ai_sol_dir(self, context):
        if self.open_ai_sol_dir:
            self.open_ai_sol_dir = False
            popup_folder(self.get_solution_dir())

    open_ai_sol_dir: bpy.props.BoolProperty(default=False, name="Open NodeTree Presets Folder", update=update_open_ai_sol_dir)

    def update_ai_mat_tex_size(self, context):
        if self.ai_mat_tex_size % 32 == 0:
            return
        self.ai_mat_tex_size = self.ai_mat_tex_size // 32 * 32

    ai_mat_tex_size: bpy.props.IntProperty(name="AI Mat Tex Size", default=1024, min=64, max=2**16, step=32, update=update_ai_mat_tex_size)

    _bake_trees = []

    def tree_items(self, context):
        trees = []
        for node_group in bpy.data.node_groups:
            if node_group.bl_idname != "BakeNodeTree":
                continue
            trees.append((node_group.name, node_group.name, node_group.name))
        if trees:
            self._bake_trees.clear()
            self._bake_trees.extend(trees)
        return self._bake_trees

    bake_tree: bpy.props.EnumProperty(items=tree_items)

    send_ai_tree_to_editor: bpy.props.BoolProperty(name="Sync AI Mat Tree to Editor", default=False)

    apply_bake_pass: bpy.props.EnumProperty(items=[("COMBINED", "Combined", "", "NONE", 2 ** 0),
                                                   ("AO", "Ambient Occlusion", "", "NONE", 2 ** 1),
                                                   ("SHADOW", "Shadow", "", "NONE", 2 ** 2),
                                                   ("POSITION", "Position", "", "NONE", 2 ** 3),
                                                   ("NORMAL", "Normal", "", "NONE", 2 ** 4),
                                                   ("UV", "UV", "", "NONE", 2 ** 5),
                                                   ("ROUGHNESS", "Roughness", "", "NONE", 2 ** 6),
                                                   ("EMIT", "Emit", "", "NONE", 2 ** 7),
                                                   ("ENVIRONMENT", "Environment", "", "NONE", 2 ** 8),
                                                   ("DIFFUSE", "Diffuse", "", "NONE", 2 ** 9),
                                                   ("GLOSSY", "Glossy", "", "NONE", 2 ** 10),
                                                   ("TRANSMISSION", "Transmission", "", "NONE", 2 ** 11),
                                                   ],
                                            default="COMBINED",
                                            name="Pass")


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


def send_ai_tree_to_editor():
    if not bpy.context.object:
        return 1
    node_tree = get_ai_mat_tree(bpy.context.object)
    if not bpy.context.scene.sdn.send_ai_tree_to_editor or not node_tree:
        return 1

    from .SDNode.tree import TREE_TYPE
    for area in bpy.context.screen.areas:
        for space in area.spaces:
            if space.type != "NODE_EDITOR" or space.tree_type != TREE_TYPE:
                continue
            try:
                if space.node_tree != node_tree:
                    space.node_tree = node_tree
            except BaseException:
                ...
    return 1


@bpy.app.handlers.persistent
def clear_cache(_):
    Icon.clear()
    Prop._ref_items.clear()


def prop_reg():
    bpy.app.timers.register(render_layer_update, persistent=True)
    bpy.app.timers.register(send_ai_tree_to_editor, persistent=True)
    bpy.app.handlers.load_post.append(clear_cache)


def prop_unreg():
    bpy.app.timers.unregister(render_layer_update)
    bpy.app.timers.unregister(send_ai_tree_to_editor)
    bpy.app.handlers.load_post.remove(clear_cache)
