import re
from pathlib import Path
from base64 import b64decode
from hashlib import sha256
plist = [
    Path(__file__).parent / "README.md",
    Path(__file__).parent / "README_EN.md",
]
for p in plist:
    imgdir = Path(__file__).parent / ".img"
    if not imgdir.exists():
        imgdir.mkdir()

    d = p.read_text()
    find = re.findall("(!\\[图片\\]\\(data:image/png;base64,.*?\\))", d, re.S)
    for bimg in find:
        bimgdata = bimg[len("![图片](data:image/png;base64,"): -1]
        bimgpath = imgdir / f"{sha256(bimgdata.encode()).hexdigest()}.jpg"
        print(bimgpath)
        bimgpath.write_bytes(b64decode(bimgdata))
        d = d.replace(bimg, f"![图片](.img/{bimgpath.name})\n")
    p.write_text(d)
