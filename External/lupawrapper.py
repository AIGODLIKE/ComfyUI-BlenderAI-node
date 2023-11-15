from __future__ import annotations
import importlib
import sys
from enum import Enum
from pathlib import Path
from platform import system
sys.path.append(Path(__file__).parent.joinpath("lupa").as_posix())


class LuaRuntime:
    __RT_DICT__ = {}

    @staticmethod
    def get_lua_runtime(name="", rt="lua54") -> LuaRuntime:
        if name not in LuaRuntime.__RT_DICT__:
            try:
                rt = LuaRuntime(name, rt)
                def_path = Path(__file__).parent.joinpath("lualib").as_posix()
                rt.add_dll_path(def_path)
            except Exception:
                import traceback
                traceback.print_exc()
        return LuaRuntime.__RT_DICT__.get(name, None)

    def __new__(cls: LuaRuntime, name="", rt="lua54") -> LuaRuntime:
        if name not in LuaRuntime.__RT_DICT__:
            rt = super().__new__(cls)
            cls.__RT_DICT__[name] = rt
        return LuaRuntime.__RT_DICT__[name]

    def __init__(self, name="", rt="lua54") -> None:
        # 如果已经注册过了，就不再注册
        if getattr(self, "initialized", None):
            return
        lupa = importlib.import_module(f"lupa.{rt}")
        self.name = name
        self.rt = rt
        self.L = lupa.LuaRuntime()
        self.globals = self.L.globals()
        dll_path = Path(__file__).parent
        self.dll = {}
        self.cdll_path = set()
        self.add_dll_path(dll_path)
        self.initialized = True

    def __del__(self):
        self.__RT_DICT__.pop(self.name, None)

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        s = f"Lua[{self.name}-{self.rt}]: Version {self.L.eval('_VERSION')}"
        info_list = [s]

        dll_path = ""
        for path in self.cdll_path:
            dll_path += f"\t\t{path}\n"
        if dll_path:
            dll_path = "\tDLL Path:\n" + dll_path
            info_list.append(dll_path)

        dll_info = ""
        for dll_name, (dll, name) in self.dll.items():
            dll_info += f"\t\t{dll_name}: {name}\n"
        if dll_info:
            dll_info = "\tDLL Info:\n" + dll_info
            info_list.append(dll_info)

        return "\n".join(info_list)

    def __hash__(self) -> int:
        return hash(self.L)

    def add_dll_path(self, path: Path):
        """
        添加dll搜索路径
        """
        path = Path(path).as_posix()
        if path in self.cdll_path:
            return
        L = self.L
        if system() == 'Windows':
            path = path.replace("/", r"\\")  # path 替换 / 为 \\
            L.execute(rf'package.cpath = package.cpath .. ";{path}\\?.dll"')
        elif system() == 'Linux':
            L.execute(f'package.cpath = package.cpath .. ";{path}/?.so"')
        elif system() == 'Darwin':
            L.execute(f'package.cpath = package.cpath .. ";{path}/?.dylib"')
        self.cdll_path.add(path)

    def load_dll(self, dll_name):
        if dll_name in self.dll:
            return self.dll[dll_name][0]
        L = self.L
        if system() == 'Windows' or dll_name.startswith("lib"):
            dll, name = L.require(dll_name)
        else:
            dll, name = L.require("lib" + dll_name)
        self.dll[dll_name] = dll, name
        return dll

    def get_dll(self, dll_name):
        return self.dll.get(dll_name, [None])[0]

    def get_logger(self, name=""):
        return Logger(self, name)


class Logger:
    """
    {"set_global_level", set_global_level},
    {"get_logger", get_logger},
    {"debug", debug},
    {"info", info},
    {"error", error},
    {"warn", warn},
    {"critical", critical},
    {"set_level", set_level},
    {"set_pattern", set_pattern},
    """

    class Level(Enum):
        TRACE = 0
        DEBUG = 1
        INFO = 2
        WARN = 3
        ERROR = 4
        CRITICAL = 5

    def __init__(self, rt: LuaRuntime, name="") -> None:
        self.rt = rt
        if not name:
            name = " " # logger名不能为空
        self.name = name
        self.liblogger = rt.load_dll("logger")
        self._logger = self.liblogger.get_logger(name)

    def set_global_level(self, level: Level):
        self.liblogger.set_global_level(level.value)

    def debug(self, msg, *args, **kwargs):
        msg = msg.format(*args, **kwargs)
        self.liblogger.debug(self._logger, msg)

    def info(self, msg, *args, **kwargs):
        msg = msg.format(*args, **kwargs)
        self.liblogger.info(self._logger, msg)

    def error(self, msg, *args, **kwargs):
        msg = msg.format(*args, **kwargs)
        self.liblogger.error(self._logger, msg)

    def warn(self, msg, *args, **kwargs):
        msg = msg.format(*args, **kwargs)
        self.liblogger.warn(self._logger, msg)

    def critical(self, msg, *args, **kwargs):
        msg = msg.format(*args, **kwargs)
        self.liblogger.critical(self._logger, msg)

    def set_level(self, level: Level):
        self.liblogger.set_level(self._logger, level.value)

    def set_pattern(self, pattern):
        self.liblogger.set_pattern(self._logger, pattern)


get_lua_runtime = LuaRuntime.get_lua_runtime


def test():
    try:
        rt = get_lua_runtime()
        logger = rt.get_logger("test")
        logger.set_level(Logger.Level.TRACE)
        logger.debug("Embeded Lua: {} {w}", rt.L.eval('_VERSION'), w="HELLO")
        logger.info("Embeded Lua: {}", rt.L.eval('_VERSION'))
        logger.warn("Embeded Lua: {}", rt.L.eval('_VERSION'))
        logger.error("Embeded Lua: {}", rt.L.eval('_VERSION'))
        logger.critical(f"Embeded Lua: {rt.L.eval('_VERSION')}")
    except Exception:
        import traceback
        traceback.print_exc()


"""
# luapath = Path(__file__).parent.joinpath(f"lualib/{rt}.dll").as_posix()
# import ctypes
# ctypes.LibraryLoader(ctypes.CDLL).LoadLibrary(luapath)

import ctypes
from ctypes import windll, wintypes
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.LoadLibraryExA.argtypes = [wintypes.LPCSTR, wintypes.HANDLE, wintypes.DWORD]
kernel32.LoadLibraryExA.restype = wintypes.HMODULE
path1 = b"Y:\\Scripts\\Addons\\a_BlenderAI_Node\\External\\lualib\\image.dll"
path = b"Y:/Scripts/Addons/a_BlenderAI_Node/External/lualib/image.dll"
kernel32.LoadLibraryExA(path, 0, 0x100)
"""
