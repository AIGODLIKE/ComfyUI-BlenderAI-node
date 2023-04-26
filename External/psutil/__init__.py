import sys
if sys.platform == "win32":
    from . import psutil_win as psutil
elif sys.platform == "arm64":
    from . import psutil_macosx_arm64 as psutil
else:
    from . import psutil_macosx_arm64 as psutil