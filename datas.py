from pathlib import Path
PRESETS_DIR = Path(__file__).parent / "presets"
GROUPS_DIR = Path(__file__).parent / "groups"


class MetaIn(type):
    def __contains__(self, name):
        return name in EnumCache.CACHE

    def __setitem__(self, name, value):
        if type(value) not in {list, dict}:
            return
        EnumCache.CACHE[name] = value

    def __getitem__(cls, name):
        return EnumCache.CACHE.setdefault(name, {})


class EnumCache(metaclass=MetaIn):
    CACHE = {}

    def reg_cache(name):
        EnumCache.CACHE[name] = {}
        return EnumCache[name]

    def unreg_cache(name):
        EnumCache.CACHE.pop(name)

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
