from __future__ import annotations
import pickle
import json
import time
from pathlib import Path
from functools import lru_cache
import difflib

def timeit(func):
    def wrap(*args, **kwargs):
        ts = time.time()
        res = func(*args, **kwargs)
        print(f"Func {func.__name__}: {time.time()-ts:.4f}s")
        return res
    return wrap


danbooru_type = {"0": "General",
                 "1": "Artist",
                 "3": "Copyright",
                 "4": "Character",
                 "5": "Meta"}
e621_type = {"-1": "Invalid",
             "0": "General",
             "1": "Artist",
             "3": "Copyright",
             "4": "Character",
             "5": "Species",
             "6": "Invalid",
             "7": "Meta",
             "8": "Lore", }
COLOR_MAP = {
    "danbooru": {
        "-1": [(255, 0, 0), (128, 0, 0)],
        "0": [(173, 216, 230), (30, 144, 255)],
        "1": [(205, 92, 92), (178, 34, 34)],
        "3": [(143, 0, 255), (153, 50, 204)],
        "4": [(144, 238, 144), (0, 100, 0)],
        "5": [(255, 165, 0), (255, 140, 0)]
    },
    "e621": {
        "-1": [(255, 0, 0), (128, 0, 0)],
        "0": [(173, 216, 230), (30, 144, 255)],
        "1": [(255, 215, 0), (218, 165, 32)],
        "3": [(143, 0, 255), (153, 50, 204)],
        "4": [(144, 238, 144), (0, 100, 0)],
        "5": [(255, 99, 71), (233, 150, 122)],
        "6": [(255, 0, 0), (128, 0, 0)],
        "7": [(245, 245, 245), (0, 0, 0)],
        "8": [(46, 139, 87), (143, 188, 143)]
    },
    "default": {"-1": [(255, 0, 0), (128, 0, 0)], }
}
LINES: list[str] = []


class Word:
    def __init__(self, key, type, freq, content, cat, color):
        self.key = key
        self.type = type
        self.freq = freq
        self.content = content
        self.cat = cat
        self.color = color

    def contains(self, substr):
        return substr in self.key or substr in self.content

    def __str__(self) -> str:
        return f"{self.key}  {self.freq}"


class Words:
    WORDS: Words = None

    def __init__(self) -> None:
        self.words: list[Word] = []
        # self.word_map: dict[str, str] = {}
        # self.color_map: dict[str, tuple] = {}
        # self.freq_map: dict[str, int] = {}

    def insert(self, word) -> None:
        key = word
        content = word
        wtype = "default"
        cat = -1
        freq = 0
        # key, type, freq, content
        if isinstance(word, list):
            key = word[0]
            cat = word[1]
            freq = int(word[2])
            content = word[3]
            wtype = word[4]
        # self.word_map[key] = content
        # self.color_map[key] = COLOR_MAP.get(wtype).get(cat, [(173, 216, 230), (30, 144, 255)])[0]
        # self.freq_map[key] = freq
        color = COLOR_MAP.get(wtype).get(cat, [(173, 216, 230), (30, 144, 255)])[0]
        self.words.append(Word(key, wtype, freq, content, cat, color))

    # @lru_cache
    def search(self, substr, sort=False) -> list[str]:
        """
            模糊搜索: 搜索所有包含substr 的词条
        """
        res = [word for word in self.words if (substr in word.key or substr in word.content)]
        if sort:
            res.sort(key=lambda x: -x.freq)
        return res


@timeit
def csv_to_words() -> Words:
    csvs = ["/Volumes/P2/a1111-sd-webui-tagcomplete/tags/e621.csv", "/Volumes/P2/a1111-sd-webui-tagcomplete/tags/danbooru.csv"]
    words = Words()
    # key, type, freq, content
    for file in csvs:
        with open(file, "rt") as f:
            import csv
            data = csv.reader(f)
            for row in data:
                row.append(Path(file).stem)
                words.insert(row)
    # extra1
    extra_word = ["masterpiece",
                  "best_quality",
                  "high_quality",
                  "normal_quality",
                  "low_quality",
                  "worst_quality",]
    for word in extra_word:
        words.insert(word)
    # extra2
    extra_word = [
        {
            "name": "Basic-NegativePrompt",
            "terms": "Basic,Negative,Low,Quality",
            "content": "(worst quality, low quality, normal quality)",
            "color": 3
        },
        {
            "name": "Basic-HighQuality",
            "terms": "Basic,Best,High,Quality",
            "content": "(masterpiece, best quality, high quality, highres, ultra-detailed)",
            "color": 1
        },
        {
            "name": "Basic-Start",
            "terms": "Basic, Start, Simple, Demo",
            "content": "(masterpiece, best quality, high quality, highres), 1girl, extremely beautiful detailed face, short curly hair, light smile, flower dress, outdoors, leaf, tree, best shadow",
            "color": 5
        },
        {
            "name": "Fancy-FireMagic",
            "terms": "Fire, Magic, Fancy",
            "content": "(extremely detailed CG unity 8k wallpaper), (masterpiece), (best quality), (ultra-detailed), (best illustration),(best shadow), (an extremely delicate and beautiful), dynamic angle, floating, fine detail, (bloom), (shine), glinting stars, classic, (painting), (sketch),\n\na girl, solo, bare shoulders, flat_chest, diamond and glaring eyes, beautiful detailed cold face, very long blue and sliver hair, floating black feathers, wavy hair, extremely delicate and beautiful girls, beautiful detailed eyes, glowing eyes,\n\npalace, the best building, ((Fire butterflies, Flying sparks, Flames))",
            "color": 5
        },
        {
            "name": "Fancy-WaterMagic",
            "terms": "Water, Magic, Fancy",
            "content": "(extremely detailed CG unity 8k wallpaper), (masterpiece), (best quality), (ultra-detailed), (best illustration),(best shadow), (an extremely delicate and beautiful), classic, dynamic angle, floating, fine detail, Depth of field, classic, (painting), (sketch), (bloom), (shine), glinting stars,\n\na girl, solo, bare shoulders, flat chest, diamond and glaring eyes, beautiful detailed cold face, very long blue and sliver hair, floating black feathers, wavy hair, extremely delicate and beautiful girls, beautiful detailed eyes, glowing eyes,\n\nriver, (forest),palace, (fairyland,feather,flowers, nature),(sunlight),Hazy fog, mist",
            "color": 5
        }
    ]
    for word in extra_word:
        words.insert([word["name"], 0, 5000, word["content"], "default"])
    return words


@timeit
def save_to_file(data, path, with_lzma=False):
    if with_lzma:
        import lzma
        f = lzma.open(path.as_posix(), "wb")
    else:
        f = open(path.as_posix(), "wb")
    try:
        pickle.dump(data, f)
    finally:
        f.close()


@timeit
def load_from_file(data_path: Path, with_lzma=False):
    trie = None
    if not data_path.exists():
        ...
    if with_lzma:
        import lzma
        with lzma.open(data_path.as_posix(), "rb") as f:
            trie = pickle.load(f)
    else:
        with open(data_path.as_posix(), "rb") as f:
            trie = pickle.load(f)
    return trie


@timeit
def init_words(with_lzma=False, fake=False):
    if fake:
        Words.WORDS = Words()
        return
    if with_lzma:
        data_path = Path(__file__).parent / "words.xz"
    else:
        data_path = Path(__file__).parent / "words.pk"

    words = csv_to_words()
    save_to_file(words, data_path, with_lzma)

    words = load_from_file(data_path, with_lzma)
    # save_to_file(trie, data_path, with_lzma)
    Words.WORDS = words


init_words(fake=False)
while True:
    inp = input("输入搜索单词: ")
    if inp.lower() == "quit":
        break
    ts = time.time()
    words = Words.WORDS.search(inp)
    print(f"Search Time: {time.time() - ts:.4f} s")
    result = words[:10]
    print("---------RESULT-----------")
    print(len(words))
    print("---------CONTENT----------")
    for w in result:
        # print(f"{w}: [{TRIE.content_from_word(w)}]")
        print(f"\t{w}")
    print("--------------------------")

    ts = time.time()
    words1 = Words.WORDS.search(inp, sort=True)
    print(f"Info Gen Time(sort): {time.time() - ts:.4f} s")
    ts = time.time()
    words2 = Words.WORDS.search(inp)
    print(f"Info Gen Time: {time.time() - ts:.4f} s")
    ts = time.time()
    l = []
    for line in LINES:
        if inp in line:
            l.append(l)
    print(f"Line Search Time: {time.time() - ts:.4f} s")
    print(f"Line Search Result: {len(l)}")