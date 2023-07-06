# Reference: https://github.com/DominikDoom/a1111-sd-webui-tagcomplete

from __future__ import annotations
import pickle
import atexit
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from functools import lru_cache

Pool = ThreadPoolExecutor()
atexit.register(Pool.shutdown)

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
LINES: list[str] = []


class InvTuple(tuple):
    def __lt__(self, __value: tuple) -> bool:
        return not super().__lt__(__value)


class TrieNode(dict):
    __slots__ = ("id",)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.id = -1

    def __str__(self):
        data = {}
        for char in self:
            # json.dumps(self.data[char])
            data[char] = str(self[char])
        # return json.dumps({'d': data, 'child': [str(c) for c in self.child]})

    def __repr__(self) -> str:
        return str(self.id)

    def __hash__(self) -> int:
        return self.id

    def get_word(self):
        return Trie.TRIE.word_list[self.id]

    def is_word(self):
        return self.id != -1

    def info(self) -> dict:
        data = {}
        for char, word in self.data.items():
            data[char] = word.info()
        # data["child"] = self.child
        return data

    def eval_color(self, word):
        cat = -1
        wtype = "default"
        #  freq,    key,   type,  content,   wtype, node
        # (250, 'exelzior', '1', 'exelzior', 'e621')
        cat = word[2]
        wtype = word[-2]
        return COLOR_MAP.get(wtype).get(cat, [(173, 216, 230), (30, 144, 255)])[0]

    def eval_info(self):
        #  freq, key, type, content, wtype
        # [word, 0,   5000,   word, "default"]
        word = self.get_word()
        return *word, self.eval_color(word)


class Trie:
    TRIE: Trie = None
    FUZZY_SEARCH = {}
    CMP_SEARCH = {}
    FLAGS = set()

    def __init__(self):

        self.root = TrieNode()
        self.word_list: list[InvTuple] = []

    def __str__(self) -> str:
        return str(self.root.info())

    def insert(self, word: tuple) -> None:
        # print(word)
        key = word[1]
        # [freq, key, type, content, wtype]
        assert isinstance(word, tuple), str(word)
        node: TrieNode = self.root
        for char in key:
            if char not in node:
                node[char] = TrieNode()
            node = node[char]
        node.id = len(self.word_list)
        self.word_list.append((*word, node))

    def info_from_words(self, words: list[TrieNode], max_size=100, sort=False, test=False):
        if test and sort:
            import heapq
            words = heapq.nlargest(max_size, words, key=lambda x: x.get_word()[0])
            return [word.eval_info() for word in words]
        info = [word.eval_info() for word in words]
        if sort:
            info.sort(reverse=True)
        return info[:max_size]

    def search(self, word) -> bool:
        """
            单个搜索: 搜索word是否存
        """
        node = self.root
        for chars in word:
            node = node.get(chars)
            if not node:
                return False
        return node.is_word()

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

    def search_all(self, prefix, pre_node: TrieNode = None, words: list = None, ) -> list[TrieNode]:
        """
            模糊搜索: 前缀符合的所有words
        """
        if words is None:
            words = []
        if not pre_node:
            pre_node = self.root
            for chars in prefix:
                pre_node = pre_node.get(chars)
        if pre_node.is_word():
            words.append(pre_node)
        for c, node in pre_node.items():
            self.search_all(prefix + c, node, words, )
        return words

    def prefix_search(self, prefix) -> list[TrieNode]:
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

    def fuzzy_search(self, substr, max_size=100) -> list[TrieNode]:
        if substr not in Trie.FUZZY_SEARCH:
            self.mark_search(substr, max_size)

        return Trie.FUZZY_SEARCH.get(substr, [])

    @lru_cache
    def bl_search1(self, prefix, max_size=100):
        words = Trie.TRIE.prefix_search(prefix)
        info2 = Trie.TRIE.info_from_words(words, max_size, sort=True, test=True)
        return info2[:max_size]

    def bl_search(self, prefix, max_size=100):
        if prefix in Trie.CMP_SEARCH:
            return Trie.CMP_SEARCH[prefix]
        w1 = self.bl_search1(prefix, max_size)
        w2 = self.fuzzy_search(prefix, max_size)
        if w2:
            w1.extend(w2)
            w1.sort()
            Trie.CMP_SEARCH[prefix] = w1
        return w1

    def mark_search(self, substr, max_size=100):
        if self.is_marked(substr):
            return

        def fuzzy_search_ex(self: Trie, substr, max_size=100):
            info = sorted([word[-1].eval_info() for word in self.word_list if not (word[1].startswith(substr) or word[3].startswith(substr)) and (substr in word[1] or substr in word[3])])
            Trie.FUZZY_SEARCH[substr] = info[:max_size]
        # fuzzy_search_ex(self, substr)
        Pool.submit(fuzzy_search_ex, self, substr, max_size)

    def is_marked(self, flag):
        return flag in Trie.FLAGS

    def mark(self, flag):
        Trie.FLAGS.add(flag)


@timeit
def csv_to_trie() -> Trie:
    trie = Trie()
    words = []
    ts = time.time()
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
    print(f"Func read_csv: {time.time()-ts:.4f}s")
    ts = time.time()
    for w in words:
        trie.insert(w)
    print(f"Func insert_words: {time.time()-ts:.4f}s")
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
    return trie


@timeit
def save_to_file(data, path: Path, with_lzma=False):
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
def init_trie(with_lzma=False, fake=False):
    if fake:
        Trie.TRIE = Trie()
        return
    if with_lzma:
        data_path = Path(__file__).parent / "data.xz"
    else:
        data_path = Path(__file__).parent / "data.pk"

    trie = csv_to_trie()
    # save_to_file(trie, data_path, with_lzma)
    # trie = load_from_file(data_path, with_lzma)

    Trie.TRIE = trie


if __name__ == "__main__":
    init_trie()
    while True:
        inp = input("输入搜索单词: ")
        if inp.lower() == "quit":
            break
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
            print(f"\t{w.eval_info()}")
        print("--------------------------")

        words = Trie.TRIE.prefix_search(inp)
        ts = time.time()
        info1 = Trie.TRIE.info_from_words(words, sort=True)
        print(f"Info Gen Time: {time.time() - ts:.4f} s")

        ts = time.time()
        info2 = Trie.TRIE.info_from_words(words, sort=True, test=True)
        # info2 = Trie.TRIE.bl_search(inp)
        print(f"Info Gen Time(sort): {time.time() - ts:.4f} s")
        for i in info2[:20]:
            print(i)
else:
    Pool.submit(init_trie)
