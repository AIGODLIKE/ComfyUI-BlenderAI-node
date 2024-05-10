import bpy
#from ...External.lupawrapper import get_lua_runtime
from ...External.imagesize import imagesize
from ...utils import update_screen


#rt = get_lua_runtime()
#imglib = rt.load_dll("image")


def read_image_to_preview(img, p: bpy.types.ImagePreview):
    w, h = imagesize.get(img)
    p.icon_size = (32, 32)
    p.image_size = (w, h)
    #imglib.read_image(img, p.as_pointer())
    #imglib.free_image(img)
    update_screen()
