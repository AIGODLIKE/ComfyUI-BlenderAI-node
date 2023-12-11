"""
This is part of the MSS Python's module.
Source: https://github.com/BoboTiG/python-mss
"""

import os
import struct
import zlib
from typing import Optional, Tuple


def to_png(data: bytes, size: Tuple[int, int], /, *, level: int = 6, output: Optional[str] = None) -> Optional[bytes]:
    """
    Dump data to a PNG file.  If `output` is `None`, create no file but return
    the whole PNG data.

    :param bytes data: RGBRGB...RGB data.
    :param tuple size: The (width, height) pair.
    :param int level: PNG compression level.
    :param str output: Output file name.
    """
    # pylint: disable=too-many-locals

    pack = struct.pack
    crc32 = zlib.crc32

    width, height = size
    line = width * 3
    png_filter = pack(">B", 0)
    scanlines = b"".join([png_filter + data[y * line : y * line + line] for y in range(height)])

    magic = pack(">8B", 137, 80, 78, 71, 13, 10, 26, 10)

    # Header: size, marker, data, CRC32
    ihdr = [b"", b"IHDR", b"", b""]
    ihdr[2] = pack(">2I5B", width, height, 8, 2, 0, 0, 0)
    ihdr[3] = pack(">I", crc32(b"".join(ihdr[1:3])) & 0xFFFFFFFF)
    ihdr[0] = pack(">I", len(ihdr[2]))

    # Data: size, marker, data, CRC32
    idat = [b"", b"IDAT", zlib.compress(scanlines, level), b""]
    idat[3] = pack(">I", crc32(b"".join(idat[1:3])) & 0xFFFFFFFF)
    idat[0] = pack(">I", len(idat[2]))

    # Footer: size, marker, None, CRC32
    iend = [b"", b"IEND", b"", b""]
    iend[3] = pack(">I", crc32(iend[1]) & 0xFFFFFFFF)
    iend[0] = pack(">I", len(iend[2]))

    if not output:
        # Returns raw bytes of the whole PNG data
        return magic + b"".join(ihdr + idat + iend)

    with open(output, "wb") as fileh:
        fileh.write(magic)
        fileh.write(b"".join(ihdr))
        fileh.write(b"".join(idat))
        fileh.write(b"".join(iend))

        # Force write of file to disk
        fileh.flush()
        os.fsync(fileh.fileno())

    return None
