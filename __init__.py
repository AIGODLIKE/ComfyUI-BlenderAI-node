bl_info = {
    'name': 'ComfyUI Node Editor',
    'author': '幻之境开发小组-会飞的键盘侠、只剩一瓶辣椒酱、a-One-Fan、DorotaLuna、hugeproblem、heredos、ra100',
    'version': (2, 1, 0),
    'blender': (3, 0, 0),
    'location': '3DView->Panel',
    'category': 'AI',
    'doc_url': "https://shimo.im/docs/Ee32m0w80rfLp4A2"
}
__dict__ = {}
import time
ts = time.time()


def clear_pyc(path=None, depth=2):
    # 递归删除 所有文件夹__pycache__
    if depth == 0:
        return
    import shutil
    from pathlib import Path
    if path is None:
        path = Path(__file__).parent
    for f in path.iterdir():
        if f.is_dir() and f.name == "__pycache__":
            try:
                shutil.rmtree(f)
            except Exception:
                ...
            continue
        if f.is_dir():
            clear_pyc(f, depth - 1)


clear_pyc()
import bpy
import sys
from addon_utils import disable
from .SDNode import rtnode_reg, rtnode_unreg, TaskManager
from .MultiLineText import EnableMLT, PasteClipboardToMLT

from .utils import Icon, FSWatcher, ScopeTimer, meta_info
from .timer import timer_reg, timer_unreg
from .preference import pref_register, pref_unregister
from .ops import Ops, Ops_Mask, Load_History, Popup_Load, Copy_Tree, Load_Batch, Fetch_Node_Status, Clear_Node_Cache, CopyToClipboard, Sync_Stencil_Image, NodeSearch, SDNode_To_Image, Image_To_SDNode, Image_Set_Channel_Packed, Open_Log_Window, CleanVRam
from .ui import ui_reg, ui_unreg, Panel, HISTORY_UL_UIList, HistoryItem
from .SDNode.history import History
from .SDNode.rt_tracker import reg_tracker, unreg_tracker
from .SDNode.nodegroup import nodegroup_reg, nodegroup_unreg
from .SDNode.operators import ops_register, ops_unregister
from .SDNode.custom_support import custom_support_reg, custom_support_unreg
from .prop import RenderLayerString, MLTWord, Prop, prop_reg, prop_unreg
from .Linker import linker_register, linker_unregister
from .hook import use_hook
from .translations import i18n_register, i18n_unregister

clss = [
    Panel,
    Ops,
    RenderLayerString,
    MLTWord,
    Prop,
    HISTORY_UL_UIList,
    HistoryItem,
    Ops_Mask,
    Load_History,
    Popup_Load,
    Copy_Tree,
    Load_Batch,
    Fetch_Node_Status,
    Clear_Node_Cache,
    CopyToClipboard,
    Sync_Stencil_Image,
    NodeSearch,
    SDNode_To_Image,
    Image_To_SDNode,
    Image_Set_Channel_Packed,
    Open_Log_Window,
    CleanVRam,
    EnableMLT,
    PasteClipboardToMLT,
]

reg, unreg = bpy.utils.register_classes_factory(clss)
from platform import system
meta_info["bl_info"] = bl_info
meta_info["package"] = __package__
meta_info["name"] = __name__


def dump_info():
    import json
    import os
    from .preference import get_pref
    if "--get-blender-ai-node-info" not in sys.argv:
        return
    model_path = getattr(get_pref(), 'model_path')
    info = {"Version": ".".join([str(i) for i in bl_info["version"]]), "ComfyUIPath": model_path}
    sys.stderr.write(f"BlenderComfyUIInfo: {json.dumps(info)} BlenderComfyUIend")
    sys.stderr.flush()
    print(f'Blender {os.getpid()} PID', file=sys.stderr)


def track_ae():
    mod = sys.modules.get(__package__, None)
    if mod:
        __dict__["__addon_enabled__"] = False
    return 1


def disable_reload():
    for nmod, mod in sys.modules.items():
        if nmod == __package__ or not nmod.startswith(__package__):
            continue
        if not hasattr(mod, "__addon_enabled__"):
            mod.__addon_enabled__ = False
    if bpy.app.timers.is_registered(track_ae):
        return
    bpy.app.timers.register(track_ae, persistent=True)
    # reset disable
    _disable = disable

    def hd(*args, **kwargs):
        stat = 0
        try:
            stat = 1
            mod = args[0]
            default_set = kwargs.get("default_set")
            # mod, *, default_set=False, handle_error=None
            if default_set and mod == __package__:
                __dict__["NOT_RELOAD_BUILTIN"] = True
            stat = 2
            _disable(*args, **kwargs)
            stat = 3
            if default_set and mod == __package__:
                __dict__.pop("NOT_RELOAD_BUILTIN")
        except Exception:
            ...
        if stat in (1, 2):
            _disable(*args, **kwargs)
    sys.modules["addon_utils"].disable = hd


def reload_builtin():
    if "NOT_RELOAD_BUILTIN" in __dict__:
        return False
    return __dict__.get("__addon_enabled__", None) is False


def register():
    if reload_builtin():
        return
    _ = ScopeTimer(f"{__package__} Register")
    reg_tracker()
    pref_register()
    if bpy.app.background:
        dump_info()
        return

    i18n_register()
    reg()
    ui_reg()
    prop_reg()
    Icon.set_hq_preview()
    rtnode_reg(rereg=False)
    TaskManager.run_server(fake=True)
    timer_reg()
    # mlt_words注册到 sdn中会导致访问其他属性卡顿 what?
    bpy.types.WindowManager.mlt_words = bpy.props.CollectionProperty(type=MLTWord, options={"SKIP_SAVE"})
    bpy.types.WindowManager.mlt_words_index = bpy.props.IntProperty()
    bpy.types.Scene.sdn = bpy.props.PointerProperty(type=Prop)
    bpy.types.Scene.sdn_history_item = bpy.props.CollectionProperty(type=HistoryItem)
    bpy.types.Scene.sdn_history_item_index = bpy.props.IntProperty(default=0)
    bpy.types.Node.ac_expand = bpy.props.BoolProperty(name="Expand", default=True)
    History.register_timer()
    linker_register()
    use_hook()
    FSWatcher.init()
    disable_reload()
    nodegroup_reg()
    ops_register()
    custom_support_reg()
    print(f"{__package__} Launch Time: {time.time() - ts:.4f}s")


def unregister():
    if reload_builtin():
        return
    unreg_tracker()
    pref_unregister()
    if bpy.app.background:
        return
    i18n_unregister()
    unreg()
    prop_unreg()
    ui_unreg()
    rtnode_unreg()
    timer_unreg()
    del bpy.types.Scene.sdn
    del bpy.types.Scene.sdn_history_item
    del bpy.types.Scene.sdn_history_item_index
    History.unregister_timer()
    modules_update()
    linker_unregister()
    use_hook(False)
    ops_unregister()
    nodegroup_unreg()
    custom_support_unreg()
    FSWatcher.stop()


def modules_update():
    from .kclogger import logger
    logger.close()
    modules = []
    for i in sys.modules:
        if i.startswith(__package__) and i != __package__:
            modules.append(i)
    for i in modules:
        del sys.modules[i]
    del sys.modules[__package__]
