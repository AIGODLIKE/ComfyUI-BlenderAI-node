"""
An ultra fast cross-platform multiple screenshots module in pure python
using ctypes.

This module is maintained by Mickaël Schoentgen <contact@tiger-222.fr>.

You can always get the latest version of this module at:
    https://github.com/BoboTiG/python-mss
If that URL should fail, try contacting the author.
"""
from .exception import ScreenShotError
from .factory import mss

__version__ = "9.0.1"
__author__ = "Mickaël 'Tiger-222' Schoentgen"
__copyright__ = """
Copyright (c) 2013-2023, Mickaël 'Tiger-222' Schoentgen

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee or royalty is hereby
granted, provided that the above copyright notice appear in all copies
and that both that copyright notice and this permission notice appear
in supporting documentation or portions thereof, including
modifications, that you make.
"""
__all__ = ("ScreenShotError", "mss")
