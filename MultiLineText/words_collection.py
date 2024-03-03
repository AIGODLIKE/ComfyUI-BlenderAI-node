# Refeence: https://github.com/DominikDoom/a1111-sd-webui-tagcomplete
from __future__ import annotations
import bpy
import time
import pickle
from pathlib import Path
from ..kclogger import logger

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

    def read_tags(self):
        if self.CACHE_PATH.exists():
            self.word_list = pickle.loads(self.CACHE_PATH.read_bytes())
        else:
            self.word_list = self.read_csv()
            self.CACHE_PATH.write_bytes(pickle.dumps(self.word_list))

    @timeit
    def read_csv(self):
        words = []
        for file in Path(__file__).parent.joinpath("tags").iterdir():
            if file.is_dir():
                continue
            if file.suffix.lower() != ".csv":
                continue
            with open(file, "rt") as f:
                import csv
                data = csv.reader(f)
                for row in data:
                    # key,   type, freq,    content
                    # words.append((row[0], row[2], row[3]))
                    words.append((row[0], row[2], row[3]))
                    # words.append(f"{row[0]} [★{row[2]}]")
                    # if row[3]:
                    #     words.append(f"{row[0]} [ ★{row[2]} ] ( ✎{row[3]} )")
                    # else:
                    #     words.append(f"{row[0]} [ ★{row[2]} ]")
                    continue
                    # 1girl, 0,    4114588, "1girls,sole_female"
                    content = row[3]
                    row[3] = ""
                    row.append(Path(file).stem)
                    # 变更为 freq, key, type, content, wtype
                    row = (int(row[2]), row[0], row[1], *row[3:])
                    words.append(row)
                    # content 包含多个词(有的词包含括号, 括号中也有逗号), 每个词按逗号分隔
                    # \(.*?,+.*?\)  \(.*?(?!\)),+.*?\)
                    split_words = []
                    if "(" in content and ")" in content:
                        left_bracket = 0
                        split_word = ""
                        for c in content:
                            if c == "," and left_bracket == 0:
                                split_words.append(split_word.strip())
                                split_word = ""
                            split_word += c
                            if c == "(":
                                left_bracket += 1
                            elif c == ")":
                                left_bracket -= 1
                    else:
                        split_words = content.split(",")
                    # 处理 to -> replace
                    for split_word in split_words:
                        rrow = (row[0], split_word, row[2], row[1], row[4])
                        words.append(rrow)
        # extra1
        extra_word = ["masterpiece",
                      "best_quality",
                      "high_quality",
                      "normal_quality",
                      "low_quality",
                      "worst_quality",]
        for word in extra_word:
            words.append((word, 5000))
            # words.append((word, 5000, ""))
        return words


words = Words()
words.read_tags()


@bpy.app.handlers.persistent
def f(_):
    mtw = bpy.context.window_manager.mlt_words
    if len(mtw) != 0:
        return
    ts = time.time()
    count = 0
    for word in words.word_list:
        it = mtw.add()
        it.value = word[0]
        it.name = f"[★{word[1]}] {word[0]}"
        it.freq = int(word[1])
        count += 1
    logger.info(f"Load MLT Words: {time.time()-ts:.4f}s")


if f not in bpy.app.handlers.load_post:
    bpy.app.handlers.load_post.append(f)
