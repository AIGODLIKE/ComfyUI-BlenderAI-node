from ..utils import PkgInstaller
from ..timer import Timer

REGISTERED = [False]

REQUIREMENTS = ["imgui"]

def install():
    return PkgInstaller.try_install(*REQUIREMENTS)


def enable_multiline_text():
    if REGISTERED[0]:
        return True
    if not install():
        return False
    from .integration import multiline_register
    multiline_register()
    REGISTERED[0] = True
    return True


def disable_multiline_text():
    if not REGISTERED[0]:
        return
    from .integration import multiline_unregister
    multiline_unregister()
    REGISTERED[0] = False
