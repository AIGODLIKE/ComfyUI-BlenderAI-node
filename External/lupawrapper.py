import importlib
from pathlib import Path
from platform import system


class LuaRuntime:
    def __init__(self, rt="lua54") -> None:
        lupa = importlib.import_module(f"lupa.{rt}")
        self.L = lupa.LuaRuntime()
        self.globals = self.L.globals()
        dll_path = Path(__file__).parent.as_posix()
        self.dll = {}
        self.cdll_path = set()
        self.add_dll_path(dll_path)

    def add_dll_path(self, path):
        """
        添加dll搜索路径
        """
        if path in self.cdll_path:
            return
        self.cdll_path.add(path)
        L = self.L
        if system() == 'Windows':
            L.execute(f'package.cpath = package.cpath .. ";{path}/?.dll"')
        elif system() == 'Linux':
            L.execute(f'package.cpath = package.cpath .. ";{path}/?.so"')
        elif system() == 'Darwin':
            L.execute(f'package.cpath = package.cpath .. ";{path}/?.dylib"')

    def load_dll(self, dll_name):
        if dll_name in self.dll:
            return self.dll[dll_name][0]
        L = self.L
        dll, name = L.require(dll_name)
        self.dll[dll_name] = dll, name
        return dll

    def get_dll(self, dll_name):
        return self.dll.get(dll_name, [None])[0]


__irt__ = LuaRuntime()
def_path = Path(__file__).parent.joinpath("lualib").as_posix()
__irt__.add_dll_path(def_path)

def get_lua_runtime():
    return __irt__
