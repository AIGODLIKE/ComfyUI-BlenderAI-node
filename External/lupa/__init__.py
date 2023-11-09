from __future__ import absolute_import


# We need to enable global symbol visibility for lupa in order to
# support binary module loading in Lua.  If we can enable it here, we
# do it temporarily.

def _try_import_with_global_library_symbols():
    try:
        from os import RTLD_NOW, RTLD_GLOBAL
    except ImportError:
        from DLFCN import RTLD_NOW, RTLD_GLOBAL  # Py2.7
    dlopen_flags = RTLD_NOW | RTLD_GLOBAL

    import sys
    old_flags = sys.getdlopenflags()
    try:
        sys.setdlopenflags(dlopen_flags)
        import lupa._lupa
    finally:
        sys.setdlopenflags(old_flags)

try:
    _try_import_with_global_library_symbols()
except:
    pass

del _try_import_with_global_library_symbols


# Find the implementation with the latest Lua version available.
_newest_lib = None


def _import_newest_lib():
    global _newest_lib
    if _newest_lib is not None:
        return _newest_lib

    import os.path
    import re

    package_dir = os.path.dirname(__file__)
    modules = [
        match.groups() for match in (
            re.match(r"((lua[a-z]*)([0-9]*))\..*", filename)
            for filename in os.listdir(package_dir)
        )
        if match
    ]
    if not modules:
        raise RuntimeError("Failed to import Lupa binary module.")
    # prefer Lua over LuaJIT and high versions over low versions.
    module_name = max(modules, key=lambda m: (m[1] == 'lua', tuple(map(int, m[2] or '0'))))
    _newest_lib = __import__(module_name[0], level=1, fromlist="*", globals=globals())

    return _newest_lib


def __getattr__(name):
    """
    Get a name from the latest available Lua (or LuaJIT) module.
    Imports the module as needed.
    """
    lua = _newest_lib if _newest_lib is not None else _import_newest_lib()
    return getattr(lua, name)


import sys
if sys.version_info < (3, 7):
    # Module level "__getattr__" requires Py3.7 or later => import latest Lua now
    _import_newest_lib()
    globals().update(
        (name, getattr(_newest_lib, name))
        for name in _newest_lib.__all__
    )
del sys

try:
    from lupa.version import __version__
except ImportError:
    pass
