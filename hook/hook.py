import bpy
from pathlib import Path
from functools import partial
from ..External.lupawrapper import get_lua_runtime, LuaRuntime
from ..utils import _T
from ..timer import Timer
from ..Linker.linker import P
from ..SDNode.tree import TREE_TYPE
from ..kclogger import logger

CACHED_DPFILES: list[Path] = []


def pop_menu(self, context):
    layout: bpy.types.UILayout = self.layout
    for file in CACHED_DPFILES:
        name = file.name
        itype = ""
        if file.suffix.lower() == ".csv":
            itype = _T("BatchTaskTable")
        else:
            itype = _T("NodeTree")
        info = _T("Import [{}] as {}?").format(name, itype)
        op = layout.operator("sdn.popup_load", text=info, icon="IMPORT")
        op.filepath = file.as_posix()


def get_region_by_type(area, type):
    for region in area.regions:
        if region.type == type:
            return region
    return None


def get_active_area(tree_type):
    bpy.ops.sdn.mouse_pos_rec("INVOKE_DEFAULT")
    mloc = P.x, P.y
    # 获取鼠标所在的区域 如果不是 NodeEditor 则不弹窗
    for area in bpy.context.screen.areas:
        if area.type != "NODE_EDITOR":
            continue
        sp = area.spaces[0]
        if sp.tree_type != tree_type:
            continue
        region = get_region_by_type(area, "WINDOW")
        w, h = region.width, region.height
        x, y = region.x, region.y
        # 如果鼠标在区域内则弹窗
        if x < mloc[0] < x + w and y < mloc[1] < y + h:
            return area


def exec():
    area = get_active_area(TREE_TYPE)
    if not area:
        return
    bpy.context.window_manager.popup_menu(pop_menu, title=_T("Import"), icon="QUESTION")


def track(rt: LuaRuntime):
    luahook = rt.get_dll("luahook")
    if not luahook:
        return
    drag_file = luahook.get_dragfiles()
    if not drag_file:
        return
    drag_file = Path(drag_file)
    if drag_file.suffix.lower() not in {".png", ".json", ".csv"}:
        return
    logger.info(f'{_T("Find Drag file")}: {drag_file}')
    luahook.clear_dragfiles()
    CACHED_DPFILES.clear()
    CACHED_DPFILES.append(Path(drag_file))

    Timer.put(exec)

def hook_init():
    rt = get_lua_runtime()
    try:
        h = rt.load_dll("luahook")
    except rt.lupa.LuaError:
        return
    h.set_cb(partial(track, rt))
    h.set_hook(True)

def hook_uninit():
    rt = get_lua_runtime()
    try:
        h = rt.load_dll("luahook")
    except rt.lupa.LuaError:
        return
    h.set_hook(False)
    h.set_cb(lambda: None)