import bpy
from threading import Thread
from pathlib import Path
from time import sleep
from ...External.lupawrapper import get_lua_runtime
from ...utils import update_screen
from ...timer import Timer
from ...kclogger import logger


rt = get_lua_runtime()
imglib = rt.load_dll("image")

# gif = "C:/Users/KC/Desktop/中文.gif"
# gif = "C:/Users/KC/Desktop/R.gif"
# gif = "C:/Users/KC/Desktop/B.gif"
# f, w, h, c, d = imglib.test(gif)
# logger.info("Image Read Test")
# logger.info([f, w, h, c, list(d.values())])

# PREV = bpy.utils.previews.new()
# TEST = PREV.new("test")


def read_frame_to_preview(gif, p: bpy.types.ImagePreview, frame):
    f, w, h, c, d = imglib.cache_gif(gif)
    p.icon_size = (32, 32)
    p.image_size = (w, h)
    imglib.read_frame(gif, frame, p.as_pointer())


class GifPlayer:
    def __init__(self, prev: bpy.types.ImagePreview, gif: str, destroycb=None) -> None:
        self.prev = prev
        self.destroy = destroycb
        self.gif = gif
        f, w, h, c, d = imglib.cache_gif(self.gif)
        self.w = w
        self.h = h
        self.delays = list(d.values())
        self.frames = f
        self.prev.icon_size = (32, 32)
        self.prev.image_size = (w, h)
        self.cframe = 0
        self.playing = False
        imglib.read_frame(self.gif, 0, self.prev.as_pointer())

    def next_frame(self):
        self.cframe = (self.cframe + 1) % self.frames
        try:
            ptr = self.prev.as_pointer()
            imglib.read_frame(self.gif, self.cframe, ptr)
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
            if delay < 5:
                delay = 100
            sleep(delay / 1000)
            Timer.put(self.next_frame)

    def __del__(self):
        if not self.destroy:
            return
        self.destroy()


# gifplayer = GifPlayer(TEST, gif)
# gifplayer.auto_play()
