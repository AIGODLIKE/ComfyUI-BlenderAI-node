# Refeence: https://github.com/DominikDoom/a1111-sd-webui-tagcomplete
from __future__ import annotations
import time
import pickle
from pathlib import Path
from threading import Thread
from functools import lru_cache
DEBUG = True

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


def timeit(func):
    def wrap(*args, **kwargs):
        ts = time.time()
        res = func(*args, **kwargs)
        if DEBUG:
            print(f"Func {func.__name__}: {time.time()-ts:.4f}s")
        return res
    return wrap


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


class Utils:
    def is_word(self):
        return self.get("id")

    def eval_color(self):
        #  freq,    key,   type,  content,   wtype, node
        # (250, 'exelzior', '1', 'exelzior', 'e621')
        cat, wtype = self[2], self[-1]
        return COLOR_MAP.get(wtype).get(cat, [(173, 216, 230)])[0]

    def eval_info(self):
        #  freq, key, type, content, wtype
        # [word, 0,   5000,   word, "default"]
        return *self, Utils.eval_color(self)


class Trie:
    TRIE: Trie = None
    SEARCH_CACHE = {}
    FLAGS = set()
    CACHE_PATH = Path(__file__).parent / "trie.cache"

    def __init__(self):
        self.root: dict = {}
        self.word_list: list[tuple] = []

    def insert(self, word: tuple) -> None:
        # print(word)
        key = word[1]
        if self.search(key):
            return
        # [freq, key, type, content, wtype]
        assert isinstance(word, tuple), str(word)
        node: dict = self.root
        for char in key:
            if char not in node:
                node[char] = {}
            node = node[char]
        node["id"] = len(self.word_list)
        self.word_list.append(word)

    def info_from_words(self, words: list[dict], max_size=100, sort=False, test=False):
        if test and sort:
            import heapq
            words = heapq.nlargest(max_size, words, key=lambda x: x[0])
            return [Utils.eval_info(word) for word in words]
        if sort:
            words = sorted(words, key=lambda x: x[0], reverse=True)[:max_size]
        info = [Utils.eval_info(word) for word in words]
        return info
        info = [Utils.eval_info(word) for word in words]
        if sort:
            info.sort(reverse=True)
        return info[:max_size]

    def search(self, word) -> bool:
        """
            单个搜索: 搜索word是否存在
        """
        node = self.root
        for chars in word:
            node = node.get(chars)
            if not node:
                return False
        return Utils.is_word(node)

    def starts_with(self, prefix) -> bool:
        """
            前缀判断: 判断前缀是否存在
        """
        node = self.root
        for chars in prefix:
            node = node.get(chars)
            if not node:
                return False
        return True

    def search_all(self, prefix, pre_node: dict = None, words: list = None, ) -> list[tuple]:
        """
            模糊搜索: 前缀符合的所有words
        """
        if words is None:
            words = []
        if not pre_node:
            pre_node = self.root
            for chars in prefix:
                pre_node = pre_node.get(chars)
        if Utils.is_word(pre_node):
            words.append(self.word_list[pre_node["id"]])
        for c, node in pre_node.items():
            if len(c) != 1:
                continue
            self.search_all(prefix + c, node, words, )
        return words

    def prefix_search(self, prefix) -> list[dict]:
        """
            前缀搜索: 如果前缀存在则搜索所有符合前缀的words
        """
        if not self.starts_with(prefix):
            return []
        # pre_node = self.root
        # for chars in prefix:
        #     pre_node = pre_node.data.get(chars)
        # return pre_node.child
        words = self.search_all(prefix)
        return words

    @lru_cache
    def fuzzy_search(self, substr, max_size=100) -> list[dict]:
        words = [word for word in self.word_list if not (word[1].startswith(substr) or word[3].startswith(substr)) and (substr in word[1] or substr in word[3])]

        info = [Utils.eval_info(word) for word in sorted(words, reverse=True)[:20]]
        return info

    @lru_cache
    def bl_search1(self, prefix, max_size=100):
        words = Trie.TRIE.prefix_search(prefix)
        info2 = Trie.TRIE.info_from_words(words, max_size, sort=True, test=True)
        return info2[:max_size]

    @timeit
    def bl_search(self, prefix, max_size=100):
        if prefix in Trie.SEARCH_CACHE:
            return Trie.SEARCH_CACHE[prefix]
        w1 = self.bl_search1(prefix, max_size)
        w2 = self.fuzzy_search(prefix, max_size)
        if w2:
            w1.extend(w2)
            w1.sort(reverse=True)
            Trie.SEARCH_CACHE[prefix] = w1
        return w1

    @timeit
    def from_cache(self):
        if not self.CACHE_PATH.exists():
            return
        # ts = time.time()
        data: dict = pickle.load(open(self.CACHE_PATH.as_posix(), "rb+"))
        # print(time.time()- ts)
        self.root = data.pop("root", None)
        self.word_list = data.pop("word_list", None)

    @timeit
    def to_cache(self):
        data = {"root": self.root, "word_list": self.word_list}
        # ts = time.time()
        pickle.dump(data, open(self.CACHE_PATH.as_posix(), "wb+"))
        # print(time.time()- ts)


@timeit
def csv_to_trie() -> Trie:
    trie = Trie()
    trie.from_cache()
    if trie.root:
        return trie
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
                row.append(Path(file).stem)
                # 变更为 freq, key, type, content, wtype
                row = (int(row[2]), row[0], row[1], *row[3:])
                # trie.insert(tuple(row))
                words.append(tuple(row))
    for w in words:
        trie.insert(w)
    # extra1
    extra_word = ["masterpiece",
                  "best_quality",
                  "high_quality",
                  "normal_quality",
                  "low_quality",
                  "worst_quality",]
    for word in extra_word:
        trie.insert((5000, word, 0, word, "default"))
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
        trie.insert((5000, word["name"], 0, word["content"], "default"))
    trie.to_cache()
    return trie


@timeit
def init_trie(debug=False):
    trie = csv_to_trie()
    Trie.TRIE = trie
    global DEBUG
    DEBUG = debug


if __name__ == "__main__":
    init_trie()
    while True:
        inp = input("输入搜索单词: ")
        if inp.lower() == "quit":
            break
        words = Trie.TRIE.bl_search(inp)
        # print(words[0])
        for w in words:
            print(w)
        continue
        ts = time.time()
        words = Trie.TRIE.prefix_search(inp)
        print(f"Search Time: {time.time() - ts:.4f} s")
        result = words[:10]
        print("---------RESULT-----------")
        print(len(words))
        print(result)
        print("---------CONTENT----------")
        for w in result:
            # print(f"{w}: [{TRIE.content_from_word(w)}]")
            print(f"\t{Utils.eval_info(w)}")
        print("--------------------------")

        ts = time.time()
        words = Trie.TRIE.prefix_search(inp)
        info1 = Trie.TRIE.info_from_words(words, sort=True)
        print(f"Info Gen Time: {time.time() - ts:.4f} s")

        ts = time.time()
        words = Trie.TRIE.prefix_search(inp)
        info2 = Trie.TRIE.info_from_words(words, sort=True, test=True)
        # info2 = Trie.TRIE.bl_search(inp)
        print(f"Info Gen Time(sort): {time.time() - ts:.4f} s")
        # for i in info2:
        #     print(i)
        print(info1 == info2)
else:
    Thread(target=init_trie, args=(False,)).start()
