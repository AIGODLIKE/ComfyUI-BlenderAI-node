import bpy
from PySide2.QtWidgets import QMessageBox
from PySide2.QtCore import Qt
import os
import bqt.ui


def shutdown_blender(*args):
    # By default changes to preferences are saved on exit, this can be toggled off in the preferences
    if bpy.context.preferences.use_preferences_save:
        bpy.ops.wm.save_userpref()

    bpy.ops.wm.quit_blender()


class WINDOW_OT_SaveFileFromQt(bpy.types.Operator):
    bl_idname = "wm.save_from_qt"
    bl_label = "Save_from_Qt"

    def execute(self, context):
        # TODO not sure what we are doing here, Friederman?
        if context.blend_data.is_saved:
            bpy.ops.wm.save_mainfile({"window": bpy.context.window_manager.windows[0]}, 'EXEC_AREA', check_existing=False)
        else:
            bpy.ops.wm.save_mainfile({"window": bpy.context.window_manager.windows[0]}, 'INVOKE_AREA', check_existing=False)
        # https://docs.blender.org/api/current/bpy.ops.html
        # EXEC_AREA - execute the operator in a certain context
        return {'FINISHED'}

# todo
#  when clicking the icon, the dialogue resets to center screen position
#  support dragging the dialogue around
#  add qshortcuts https://stackoverflow.com/questions/19845774/is-it-possible-to-use-an-underlined-letter-as-keyboard-shortcut-in-qt


class BlenderClosingDialog(QMessageBox):
    def __init__(self, parent):
        super().__init__(parent) #, Qt.WindowCloseButtonHint | Qt.WindowSystemMenuHint | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)

        # hide title bar
        self.setWindowFlag(Qt.FramelessWindowHint)

        filepath = bpy.data.filepath
        if not filepath:
            filepath = 'untitled.blend'
        filename = os.path.split(filepath)[1]

        question_icon = bqt.ui.get_question_pixmap()

        self.setText("Save changes before closing?\n\n" + filename)
        self.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        self.setDefaultButton(QMessageBox.Save)
        self.setIconPixmap(question_icon)

    def execute(self):
        if not bpy.data.is_dirty:
            shutdown_blender()
            return

        choice = super().exec_()
        if choice == QMessageBox.Save:
            bpy.utils.register_class(WINDOW_OT_SaveFileFromQt)
            bpy.app.handlers.save_post.append(shutdown_blender)
            bpy.ops.wm.save_from_qt()
        elif choice == QMessageBox.Discard:
            shutdown_blender()
        else:  # user clicked cancel
            pass
        return choice
