from pathlib import Path
PRESETS_DIR = Path(__file__).parent / "presets"
GROUPS_DIR = Path(__file__).parent / "groups"
IMG_SUFFIX = {".png", ".jpg", ".jpeg"}

VERSION = ""

def get_bl_version():
    if VERSION: return VERSION
    from . import bl_info
    return ".".join([str(i) for i in bl_info['version']])

VERSION = get_bl_version()

class MetaIn(type):
    CACHE: dict[str, dict] = {}

    def __contains__(cls, name):
        return name in cls.CACHE

    def __setitem__(cls, name, value):
        if type(value) not in {list, dict}:
            return
        cls.CACHE[name] = value

    def __getitem__(cls, name) -> dict:
        return cls.CACHE.setdefault(name, {})


class EnumCache(metaclass=MetaIn):
    CACHE: dict[str, dict] = {}

    @staticmethod
    def reg_cache(name):
        EnumCache.CACHE[name] = {}
        return EnumCache[name]

    @staticmethod
    def unreg_cache(name):
        EnumCache.CACHE.pop(name, None)

    @staticmethod
    def clear(name=None):
        if name:
            EnumCache[name].clear()
            return
        for cache in EnumCache.CACHE.values():
            cache.clear()


ENUM_ITEMS_CACHE = EnumCache["ENUM_ITEMS_CACHE"]
EnumCache["presets_dir"] = []
EnumCache["groups_dir"] = []
PROP_CACHE = {
    "presets": EnumCache.reg_cache("presets"),
    "presets_dir": EnumCache["presets_dir"],
    "groups": EnumCache.reg_cache("groups"),
    "groups_dir": EnumCache["groups_dir"],
}
