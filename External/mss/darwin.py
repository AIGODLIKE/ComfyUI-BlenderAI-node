"""
This is part of the MSS Python's module.
Source: https://github.com/BoboTiG/python-mss
"""
import ctypes
import ctypes.util
import sys
from ctypes import POINTER, Structure, c_double, c_float, c_int32, c_ubyte, c_uint32, c_uint64, c_void_p
from platform import mac_ver
from typing import Any, Optional, Type, Union

from .base import MSSBase
from .exception import ScreenShotError
from .models import CFunctions, Monitor
from .screenshot import ScreenShot, Size

__all__ = ("MSS",)


def cgfloat() -> Union[Type[c_double], Type[c_float]]:
    """Get the appropriate value for a float."""

    return c_double if sys.maxsize > 2**32 else c_float


class CGPoint(Structure):
    """Structure that contains coordinates of a rectangle."""

    _fields_ = [("x", cgfloat()), ("y", cgfloat())]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(left={self.x} top={self.y})"


class CGSize(Structure):
    """Structure that contains dimensions of an rectangle."""

    _fields_ = [("width", cgfloat()), ("height", cgfloat())]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(width={self.width} height={self.height})"


class CGRect(Structure):
    """Structure that contains information about a rectangle."""

    _fields_ = [("origin", CGPoint), ("size", CGSize)]

    def __repr__(self) -> str:
        return f"{type(self).__name__}<{self.origin} {self.size}>"


# C functions that will be initialised later.
#
# This is a dict:
#    cfunction: (attr, argtypes, restype)
#
# Available attr: core.
#
# Note: keep it sorted by cfunction.
CFUNCTIONS: CFunctions = {
    "CGDataProviderCopyData": ("core", [c_void_p], c_void_p),
    "CGDisplayBounds": ("core", [c_uint32], CGRect),
    "CGDisplayRotation": ("core", [c_uint32], c_float),
    "CFDataGetBytePtr": ("core", [c_void_p], c_void_p),
    "CFDataGetLength": ("core", [c_void_p], c_uint64),
    "CFRelease": ("core", [c_void_p], c_void_p),
    "CGDataProviderRelease": ("core", [c_void_p], c_void_p),
    "CGGetActiveDisplayList": ("core", [c_uint32, POINTER(c_uint32), POINTER(c_uint32)], c_int32),
    "CGImageGetBitsPerPixel": ("core", [c_void_p], int),
    "CGImageGetBytesPerRow": ("core", [c_void_p], int),
    "CGImageGetDataProvider": ("core", [c_void_p], c_void_p),
    "CGImageGetHeight": ("core", [c_void_p], int),
    "CGImageGetWidth": ("core", [c_void_p], int),
    "CGRectStandardize": ("core", [CGRect], CGRect),
    "CGRectUnion": ("core", [CGRect, CGRect], CGRect),
    "CGWindowListCreateImage": ("core", [CGRect, c_uint32, c_uint32, c_uint32], c_void_p),
}


class MSS(MSSBase):
    """
    Multiple ScreenShots implementation for macOS.
    It uses intensively the CoreGraphics library.
    """

    __slots__ = {"core", "max_displays"}

    def __init__(self, /, **kwargs: Any) -> None:
        """macOS initialisations."""

        super().__init__(**kwargs)

        self.max_displays = kwargs.get("max_displays", 32)

        self._init_library()
        self._set_cfunctions()

    def _init_library(self) -> None:
        """Load the CoreGraphics library."""
        version = float(".".join(mac_ver()[0].split(".")[:2]))
        if version < 10.16:
            coregraphics = ctypes.util.find_library("CoreGraphics")
        else:
            # macOS Big Sur and newer
            coregraphics = "/System/Library/Frameworks/CoreGraphics.framework/Versions/Current/CoreGraphics"

        if not coregraphics:
            raise ScreenShotError("No CoreGraphics library found.")
        self.core = ctypes.cdll.LoadLibrary(coregraphics)

    def _set_cfunctions(self) -> None:
        """Set all ctypes functions and attach them to attributes."""

        cfactory = self._cfactory
        attrs = {"core": self.core}
        for func, (attr, argtypes, restype) in CFUNCTIONS.items():
            cfactory(attrs[attr], func, argtypes, restype)

    def _monitors_impl(self) -> None:
        """Get positions of monitors. It will populate self._monitors."""

        int_ = int
        core = self.core

        # All monitors
        # We need to update the value with every single monitor found
        # using CGRectUnion.  Else we will end with infinite values.
        all_monitors = CGRect()
        self._monitors.append({})

        # Each monitor
        display_count = c_uint32(0)
        active_displays = (c_uint32 * self.max_displays)()
        core.CGGetActiveDisplayList(self.max_displays, active_displays, ctypes.byref(display_count))
        for idx in range(display_count.value):
            display = active_displays[idx]
            rect = core.CGDisplayBounds(display)
            rect = core.CGRectStandardize(rect)
            width, height = rect.size.width, rect.size.height
            if core.CGDisplayRotation(display) in {90.0, -90.0}:
                # {0.0: "normal", 90.0: "right", -90.0: "left"}
                width, height = height, width
            self._monitors.append(
                {
                    "left": int_(rect.origin.x),
                    "top": int_(rect.origin.y),
                    "width": int_(width),
                    "height": int_(height),
                }
            )

            # Update AiO monitor's values
            all_monitors = core.CGRectUnion(all_monitors, rect)

        # Set the AiO monitor's values
        self._monitors[0] = {
            "left": int_(all_monitors.origin.x),
            "top": int_(all_monitors.origin.y),
            "width": int_(all_monitors.size.width),
            "height": int_(all_monitors.size.height),
        }

    def _grab_impl(self, monitor: Monitor, /) -> ScreenShot:
        """Retrieve all pixels from a monitor. Pixels have to be RGB."""

        # pylint: disable=too-many-locals

        core = self.core
        rect = CGRect((monitor["left"], monitor["top"]), (monitor["width"], monitor["height"]))

        image_ref = core.CGWindowListCreateImage(rect, 1, 0, 0)
        if not image_ref:
            raise ScreenShotError("CoreGraphics.CGWindowListCreateImage() failed.")

        width = core.CGImageGetWidth(image_ref)
        height = core.CGImageGetHeight(image_ref)
        prov = copy_data = None
        try:
            prov = core.CGImageGetDataProvider(image_ref)
            copy_data = core.CGDataProviderCopyData(prov)
            data_ref = core.CFDataGetBytePtr(copy_data)
            buf_len = core.CFDataGetLength(copy_data)
            raw = ctypes.cast(data_ref, POINTER(c_ubyte * buf_len))
            data = bytearray(raw.contents)

            # Remove padding per row
            bytes_per_row = core.CGImageGetBytesPerRow(image_ref)
            bytes_per_pixel = core.CGImageGetBitsPerPixel(image_ref)
            bytes_per_pixel = (bytes_per_pixel + 7) // 8

            if bytes_per_pixel * width != bytes_per_row:
                cropped = bytearray()
                for row in range(height):
                    start = row * bytes_per_row
                    end = start + width * bytes_per_pixel
                    cropped.extend(data[start:end])
                data = cropped
        finally:
            if prov:
                core.CGDataProviderRelease(prov)
            if copy_data:
                core.CFRelease(copy_data)

        return self.cls_image(data, monitor, size=Size(width, height))

    def _cursor_impl(self) -> Optional[ScreenShot]:
        """Retrieve all cursor data. Pixels have to be RGB."""
        return None
