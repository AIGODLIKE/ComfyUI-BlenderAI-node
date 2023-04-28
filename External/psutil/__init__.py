import platform
if platform.sys.platform == "win32":
    from . import psutil_win as psutil
elif platform.sys.platform == "darwin":
    import platform
    if platform.machine() == "arm64":
        from . import psutil_macosx_arm64 as psutil
    else:
        from . import psutil_macosx_x86_64 as psutil
else:
    from . import psutil_linux_x86_64 as psutil