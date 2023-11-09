import os
import sys
import bpy
from functools import partial
from pathlib import Path
from ctypes import RTLD_GLOBAL, POINTER, CDLL, c_int64, c_longlong, c_uint64, cdll, cast, c_void_p, c_int, c_float, c_bool, c_wchar_p
from array import array as Array
from threading import Thread
from time import sleep
from ...timer import Timer
from ...utils import _T


def set_hook(action):
    ...


def set_wheel_status(s):
    ...


def get_wheel_status():
    return 0


def clear_dragfiles():
    ...


def get_dragfiles():
    return ""


def is_support():
    return sys.platform == "win32"


if is_support():
    cur_path = Path(__file__).parent
    if sys.platform == "darwin":
        dll_path = cur_path.joinpath("hook.dylib").as_posix()
        dll = cdll.LoadLibrary(dll_path)
    elif sys.platform == "win32":
        from ctypes import WinDLL
        dll_path = cur_path.joinpath("hook.dll").as_posix()
        if sys.version_info >= (3, 9, 0):
            os.add_dll_directory(cur_path.as_posix())
            try:
                dll = WinDLL(dll_path, winmode=RTLD_GLOBAL)
            except BaseException:
                dll = CDLL(dll_path, winmode=RTLD_GLOBAL)
        else:
            dll = cdll.LoadLibrary(dll_path)

    dll.set_hook.argtypes = [c_int]
    dll.set_hook.restype = None
    dll.set_wheel_status.argtypes = [c_int]
    dll.get_wheel_status.restype = c_int
    dll.get_dragfiles.restype = c_void_p

    def set_hook(action):
        if action:
            dll.set_hook(1)
        else:
            dll.set_hook(0)

    def set_wheel_status(s):
        dll.set_wheel_status(s)

    def get_wheel_status():
        return dll.get_wheel_status()

    def get_dragfiles():
        p = dll.get_dragfiles()
        return cast(p, c_wchar_p).value

    def clear_dragfiles():
        dll.clear_dragfiles()
    set_hook(1)
    # dll.set_debug(True)


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


def track():
    while True:
        sleep(1 / 30)
        drag_file = get_dragfiles()
        if not drag_file:
            continue
        drag_file = Path(drag_file)
        if drag_file.suffix.lower() not in {".png", ".json", ".csv"}:
            continue
        CACHED_DPFILES.clear()
        CACHED_DPFILES.append(Path(drag_file))

        def f():
            from ...SDNode.tree import TREE_TYPE
            from ...utils import _T

            def get_active_area(tree_type):
                def get_region_by_type(area, type):
                    for region in area.regions:
                        if region.type == type:
                            return region
                    return None
                from ...Linker.linker import P
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
            area = get_active_area(TREE_TYPE)
            if not area:
                return
            bpy.context.window_manager.popup_menu(pop_menu, title=_T("Import"), icon="QUESTION")
        Timer.put(f)
        clear_dragfiles()


t = Thread(target=track, daemon=True)
t.start()
