import bpy
from platform import system
from ...External.imagesize import imagesize
from ...utils import update_screen


if system() != "Linux": #TODO: Linux lupa
    from ...External.lupawrapper import get_lua_runtime
    rt = get_lua_runtime("AnimatedImage")
    imglib = rt.load_dll("image")


def read_image_to_preview(img, p: bpy.types.ImagePreview):
    w, h = imagesize.get(img)
    p.icon_size = (32, 32)
    p.image_size = (w, h)
    if system() != "Linux": #TODO: Linux lupa
        imglib.read_image(img, p.as_pointer())
        imglib.free_image(img)
    update_screen()
