"""
when alt tabbing in and out of blender, a bug happens when blender is wrapped in qt.
some keys stay stuck, e.g. alt or control, resulting in the user
not being able to use blender on refocus

this module fixes the bug by sending a key release event to the window
"""

import ctypes
import bpy


class QFocusOperator(bpy.types.Operator):
    bl_idname = "bqt.return_focus"  # access from bpy.ops.bqt.return_focus
    bl_label = "Fix bug related to bqt focus"
    bl_description = "Fix bug related to bqt focus"
    bl_options = {"INTERNAL"}

    def __init__(self):
        super().__init__()

    def __del__(self):
        """called when the operator finishes"""
        pass

    def invoke(self, context, event):
        """
        simulate key release to prevent blender from ignoring mouse input, after refocusing blender
        """
        self._detect_keyboard()
        return {"FINISHED"}

    @staticmethod
    def _detect_keyboard():
        """
        force a release of 'stuck' keys
        """

        # key codes from https://itecnote.com/tecnote/python-simulate-keydown/
        keycodes = [
            ("_ALT", 0x12),
            ("_CTRL", 0x11),
            ("_SHIFT", 0x10),
            ("VK_LWIN", 0x5B),
            ("VK_RWIN", 0x5C),
            ("OSKEY", 0x5B),  # dupe oskey, blender names it this
        ]

        # print("event.type", event.type, type(event.type))
        for name, code in keycodes:

            # todo this bug fix is not perfect yet, blender works better without this atm
            # # if the first key pressed is one of the following,
            # # don't simulate a key release, since it causes this bug:
            # # the first keypress on re-focus blender will be ignored, e.g. ctrl + v will just be v
            # if name in event.type:
            #     print("skipping:", name)
            #     continue

            # safely release all other keys that might be stuck down
            ctypes.windll.user32.keybd_event(code, 0, 2, 0)  # release key
            # print("released key", name, code)

        # todo, fix: blender occasionally still frozen input, despite having run the above code
        # but when we click the mouse, it starts working again
        # simulate a right mouse click did not work ...
        # ctypes.windll.user32.mouse_event(0x0008, 0, 0, 0, 0)  # right mouse click
