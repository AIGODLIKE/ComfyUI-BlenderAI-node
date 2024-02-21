import bpy
from threading import Thread
from pathlib import Path
from time import sleep
from ...External.lupawrapper import get_lua_runtime
from ...utils import update_screen, ScopeTimer, PrevMgr
from ...timer import Timer
from ...kclogger import logger


rt = get_lua_runtime("AnimatedImage")
imglib = rt.load_dll("image")


def read_frame_to_preview(imgpath, p: bpy.types.ImagePreview, frame):
    f, w, h, c, d = imglib.cache_animated_image(imgpath)
    p.icon_size = (32, 32)
    p.image_size = (w, h)
    imglib.read_frame(imgpath, frame, p.as_pointer())


class AnimatedImagePlayer:
    def __init__(self, prev: bpy.types.ImagePreview, imgpath: str, destroycb=None) -> None:
        self.prev = prev
        self.destroy = destroycb
        self.imgpath = imgpath
        f, w, h, c, d = imglib.cache_animated_image(self.imgpath)
        self.w = w
        self.h = h
        self.delays = list(d.values())
        self.frames = f
        self.prev.icon_size = (32, 32)
        self.prev.image_size = (w, h)
        self.cframe = 0
        self.playing = False
        if not Path(self.imgpath).exists():
            return
        imglib.read_frame(self.imgpath, 0, self.prev.as_pointer())

    def next_frame(self):
        if not Path(self.imgpath).exists():
            return
        if not self.playing:
            return
        if not self.prev:
            return
        self.cframe = (self.cframe + 1) % self.frames
        try:
            ptr = self.prev.as_pointer()
            imglib.read_frame(self.imgpath, self.cframe, ptr)
            # 更新窗口
            update_screen()
        except Exception as e:
            logger.error(e)

    def pause(self):
        self.playing = False

    def auto_play(self):
        if self.playing:
            return
        self.playing = True
        Thread(target=self.auto_play_ex, daemon=True).start()

    def auto_play_ex(self):
        while self.playing:
            delay = self.delays[self.cframe]
            sleep(delay)
            Timer.put(self.next_frame)
        imglib.free_image(self.imgpath)
        logger.info("Freed image: %s", self.imgpath)

    def free(self):
        self.playing = False
        self.prev = None

    def __del__(self):
        self.free()
        if not self.destroy:
            return
        self.destroy()


PREV = PrevMgr.new()
TEST = PREV.new("IMG_LIB_TEST")
gif_test = ["C:/Users/KC/Desktop/B.gif", "/Volumes/CDownload/B.gif"]
gif = ""
for g in gif_test:
    if not Path(g).exists():
        continue
    gif = g


def test():
    t = ScopeTimer("Cache 2000x2000")
    gifplayer = AnimatedImagePlayer(TEST, gif)
    f, w, h, c, d = imglib.cache_animated_image(gif)
    logger.info("Image Read Test")
    logger.info([f, w, h, c, list(d.values())])
    gifplayer.auto_play()
