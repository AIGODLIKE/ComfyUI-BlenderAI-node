import sys
from pathlib import Path
sys.path.append(Path(__file__).parent.as_posix())
try:
    from time import time
    # ori = sys.getdlopenflags()
    # sys.setdlopenflags(8)
    ts = time()
    #from .lupawrapper import test
    # print(f"Load lua runtime: {time() - ts:.2f}s")
    # test()
    # sys.setdlopenflags(ori)
except BaseException:
    import traceback
    traceback.print_exc()
# try:
#     from . import listen
# except BaseException:
#     traceback.print_exc()