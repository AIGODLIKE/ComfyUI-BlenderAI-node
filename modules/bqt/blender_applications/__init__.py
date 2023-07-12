"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""
import sys
from .blender_application import BlenderApplication

if sys.platform == "darwin":
    from .darwin_blender_application import DarwinBlenderApplication
if sys.platform in ["linux", "linux2"]:
    # TODO: LINUX module
    pass
elif sys.platform == "win32":
    from .win32_blender_application import Win32BlenderApplication
