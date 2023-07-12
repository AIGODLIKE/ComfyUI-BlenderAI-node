"""
This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from abc import abstractmethod, abstractstaticmethod, ABCMeta
from pathlib import Path
import os
from PySide2.QtWidgets import QApplication, QWidget, QSplashScreen
from PySide2.QtGui import QCloseEvent, QIcon, QImage, QPixmap, QWindow
from PySide2.QtCore import QEvent, QObject, QRect, QSettings, QTimer
from bqt.ui.quit_dialogue import BlenderClosingDialog
import bpy

from enum import Enum
from qfluentwidgets import StyleSheetBase, Theme, isDarkTheme, qconfig, setTheme


class BlenderApplication(QApplication):
    """
    Base Implementation for QT Blender Window Container
    """

    def __init__(self, *args, **kwargs):
        __metaclass__ = ABCMeta
        super().__init__(*args, **kwargs)
        self._stylesheet_filepath = Path(__file__).parents[1] / "blender_stylesheet.qss"
        # self._stylesheet_filepath = Path(__file__).parents[1] / "dark.qss"
        self._settings_key_geometry = "Geometry"
        self._settings_key_maximized = "IsMaximized"
        self._settings_key_full_screen = "IsFullScreen"
        self._settings_key_window_group_name = "MainWindow"

        # QApplication
        if self._stylesheet_filepath.exists():
            self.setStyleSheet(self._stylesheet_filepath.read_text())

        QApplication.setWindowIcon(self._get_application_icon())

        # Blender Window
        self._hwnd = self._get_application_hwnd()
        failed_to_get_handle = self._hwnd is None

        if True:
            self._blender_window = QWindow()
            self.blender_widget = QWidget.createWindowContainer(self._blender_window)

        # if os.getenv("BQT_DISABLE_WRAP") == "1" or failed_to_get_handle:
        #     self._blender_window = QWindow()
        #     self.blender_widget = QWidget.createWindowContainer(self._blender_window)
        else:
            self._blender_window = QWindow.fromWinId(self._hwnd)
            self.blender_widget = QWidget.createWindowContainer(self._blender_window)
            self._set_window_geometry()
            self.focusObjectChanged.connect(self._on_focus_object_changed)

    @abstractstaticmethod
    def _get_application_hwnd() -> int:
        """
        This finds the blender application window and collects the
        handler window ID

        Returns int: Handler Window ID
        """

        return -1

    @staticmethod
    def _get_application_icon() -> QIcon:
        """
        This finds the running blender process, extracts the blender icon from the blender.exe file on disk and saves it to the user's temp folder.
        It then creates a QIcon with that data and returns it.

        Returns QIcon: Application Icon
        """

        icon_filepath = Path(__file__).parents[1] / "images" / "blender_icon_16_backup.png"
        icon = QIcon()

        if icon_filepath.exists():
            image = QImage(str(icon_filepath))
            if not image.isNull():
                icon = QIcon(QPixmap().fromImage(image))

        return icon

    @abstractmethod
    def _on_focus_object_changed(self, focus_object: QObject):
        """
        Args:
            focus_object: Object to track focus event
        """

        pass

    def _set_window_geometry(self):
        """
        Loads stored window geometry preferences and applies them to the QWindow.
        .setGeometry() sets the size of the window minus the window frame.
        For this reason it should be set on self.blender_widget.
        """

        settings = QSettings("Tech-Artists.org", "Blender Qt Wrapper")
        settings.beginGroup(self._settings_key_window_group_name)

        if settings.value(self._settings_key_full_screen, "false").lower() == "true":
            self.blender_widget.showFullScreen()
            return

        if settings.value(self._settings_key_maximized, "false").lower() == "true":
            self.blender_widget.showMaximized()
            return

        self.blender_widget.setGeometry(settings.value(self._settings_key_geometry, QRect(0, 0, 640, 480)))
        self.blender_widget.show()

        settings.endGroup()
        return

    def notify(self, receiver: QObject, event: QEvent) -> bool:
        """
        Args:
            receiver: Object to recieve event
            event: Event

        Returns: bool
        """

        if isinstance(event, QCloseEvent) and receiver in (self.blender_widget, self._blender_window):
            # catch the close event when clicking close on the qt window,
            # ignore the event, and ask user if they want to close blender if unsaved changes.
            # if this is successful, blender will trigger bqt.on_exit()
            event.ignore()

            if os.getenv("BQT_DISABLE_CLOSE_DIALOGUE") == "1":
                # this triggers the default blender close event, showing the save dialog if needed
                bpy.ops.wm.quit_blender({"window": bpy.context.window_manager.windows[0]}, "INVOKE_DEFAULT")
            else:
                closing_dialog = BlenderClosingDialog(self.blender_widget)
                closing_dialog.execute()

            return False

        return super().notify(receiver, event)

    def store_window_geometry(self):
        """
        Stores the current window geometry for the QWindow
        The .geometry() method on QWindow includes the size of the application minus the window frame.
        For that reason the _blender_widget should be used.
        """

        settings = QSettings("Tech-Artists.org", "Blender Qt Wrapper")
        settings.beginGroup(self._settings_key_window_group_name)
        settings.setValue(self._settings_key_geometry, self.blender_widget.geometry())
        settings.setValue(self._settings_key_maximized, self.blender_widget.isMaximized())
        settings.setValue(self._settings_key_full_screen, self.blender_widget.isFullScreen())
        settings.endGroup()
