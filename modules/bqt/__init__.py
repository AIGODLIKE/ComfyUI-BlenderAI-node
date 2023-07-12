"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""
import bqt
import bqt.focus
import atexit
import os
import sys
import bpy
import PySide2.QtCore as QtCore
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QDir
import logging
from pathlib import Path


bl_info = {
        "name": "PySide2 Qt wrapper (bqt)",
        "description": "Enable PySide2 QtWidgets in Blender",
        "author": "tech-artists.org",
        "version": (1, 0),
        "blender": (2, 80, 0),
        # "location": "",
        # "warning": "", # used for warning icon and text in add-ons panel
        # "wiki_url": "http://my.wiki.url",
        # "tracker_url": "http://my.bugtracker.url",
        "support": "COMMUNITY",
        "category": "UI"
        }


# CONSTANT


# CORE FUNCTIONS #

def instantiate_application() -> "bqt.blender_applications.BlenderApplication":
    """
    Create an instance of Blender Application

    Returns BlenderApplication: Application Instance

    """
    # enable dpi scale, run before creating QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
    image_directory = str(Path(__file__).parent / "images")
    QDir.addSearchPath('images', image_directory)
    app = QApplication.instance()
    if not app:
        app = load_os_module()

    return app


def load_os_module() -> object:
    """
    Loads the correct OS platform Application Class

    Returns: Instance of BlenderApplication

    """
    operating_system = sys.platform
    if operating_system == "darwin":
        from .blender_applications.darwin_blender_application import DarwinBlenderApplication

        return DarwinBlenderApplication(sys.argv)
    if operating_system in ["linux", "linux2"]:
        # TODO: LINUX module
        pass
    elif operating_system == "win32":
        from .blender_applications.win32_blender_application import Win32BlenderApplication

        return Win32BlenderApplication(sys.argv)


parent_window = None


@bpy.app.handlers.persistent
def create_global_app():
    """
    runs after blender finished startup
    """
    global qapp

    qapp = instantiate_application()

    # save a reference to the C++ window in a global var, to prevent the parent being garbage collected
    # for some reason this works here, but not in the blender_applications init as a class attribute (self),
    # and saving it in a global in blender_applications.py causes blender to crash on startup
    global parent_window
    parent_window = qapp._blender_window.parent()


def register():
    """
    setup bqt, wrap blender in qt, register operators
    """

    # hacky way to check if we already are waiting on bqt setup, or bqt is already setup
    if QApplication.instance():
        logging.warning("bqt: QApplication already exists, skipping bqt registration")
        return

    if os.getenv("BQT_DISABLE_STARTUP", 0) == "1":
        logging.warning("bqt: BQT_DISABLE_STARTUP is set, skipping bqt registration")
        return

    # only start focus operator if blender is wrapped
    # if not os.getenv("BQT_DISABLE_WRAP", 0) == "1":
    #     # todo check if operator is already registered
    #     bpy.utils.register_class(bqt.focus.QFocusOperator)
    #     # append add_focus_handle before create_global_app, else it doesn't run on blender startup

    if not True:
        bpy.utils.register_class(bqt.focus.QFocusOperator)


    create_global_app()

    atexit.register(on_exit)


def unregister():
    """
    Unregister Blender Operator classes

    Returns: None

    """
    # todo, as long as blender is wrapped in qt, unregistering operator & callback will cause issues,
    #  for now we just return since unregister should not be called partially
    return

    if not os.getenv("BQT_DISABLE_WRAP", 0) == "1":
        bpy.utils.unregister_class(bqt.focus.QFocusOperator)
    atexit.unregister(on_exit)


def on_exit():
    """Close BlenderApplication instance on exit"""

    app = QApplication.instance()
    if app:
        app.store_window_geometry()
        app.quit()


