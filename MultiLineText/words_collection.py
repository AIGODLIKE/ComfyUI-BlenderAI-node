# Refeence: https://github.com/DominikDoom/a1111-sd-webui-tagcomplete
from __future__ import annotations
import bpy
import time
import pickle
import csv
import traceback
from pathlib import Path
from ..kclogger import logger

CACHE_VERSION = (1, 0)


def timeit(func):
    def wrap(*args, **kwargs):
        ts = time.time()
        res = func(*args, **kwargs)
        print(f"Func {func.__name__}: {time.time()-ts:.4f}s")
        return res
    return wrap


class Words:
    SEARCH_CACHE = {}
    FLAGS = set()
    CACHE_PATH = Path(__file__).parent / "words_collection.cache"

    def __init__(self):
        self.word_list: list[tuple] = []
        self.word_map: dict[str, tuple] = {}

    def read_tags(self):
        if self.CACHE_PATH.exists():
            cache = pickle.loads(self.CACHE_PATH.read_bytes())
            if isinstance(cache, list):
                self.read_raw_tags()
            elif cache.get("VERSION", (0, 0)) < CACHE_VERSION:
                self.read_raw_tags()
            else:
                self.word_list = cache.get("WORDS", [])
        else:
            self.read_raw_tags()

    def read_raw_tags(self):
        self.word_list = self.read_csv()
        data = {"VERSION": CACHE_VERSION, "WORDS": self.word_list}
        if self.CACHE_PATH.exists():
            self.CACHE_PATH.unlink()
        self.CACHE_PATH.write_bytes(pickle.dumps(data))

    def read_translation(self):
        translation = {}
        try:
            translation_file = Path(__file__).parent.joinpath("translation.csv")
            if translation_file.exists():
                with open(translation_file, "rt", encoding="utf8") as f:
                    translation = dict(csv.reader(f))
        except Exception:
            traceback.print_exc()
        return translation

    @timeit
    def read_csv(self):
        translation = self.read_translation()
        words = []
        for file in Path(__file__).parent.joinpath("tags").iterdir():
            if file.is_dir():
                continue
            if file.suffix.lower() != ".csv":
                continue
            with open(file, "rt") as f:
                data = csv.reader(f)
                for row in data:
                    # key,   type, freq,    content
                    # words.append((row[0], row[2], row[3]))
                    t = translation.get(row[0], "")
                    words.append((row[0], row[2], t))
                    # words.append((row[0], row[2], row[3]))
                    continue
        # extra1
        extra_word = ["masterpiece",
                      "best_quality",
                      "high_quality",
                      "normal_quality",
                      "low_quality",
                      "worst_quality",]
        for word in extra_word:
            t = translation.get(word, "")
            words.append((word, 5000, t))
            # words.append((word, 5000, ""))
        return words

    def load_map(self):
        for word in self.word_list:
            self.word_map[word[0]] = word

words = Words()
words.read_tags()
words.load_map()

@bpy.app.handlers.persistent
def f(_):
    mtw = bpy.context.window_manager.mlt_words
    if len(mtw) != 0:
        return
    # ts = time.time()
    # count = 0
    # for word in words.word_list:
    #     it = mtw.add()
    #     it.value = word[0]
    #     it.name = word[0]
    #     if len(word) == 3 and word[2]:
    #         it.name = f"{word[0]} <== {word[2]}"
    #     it.freq = int(word[1])
    #     count += 1
    # logger.info(f"Load MLT Words: {time.time()-ts:.4f}s")


if f not in bpy.app.handlers.load_post:
    bpy.app.handlers.load_post.append(f)
