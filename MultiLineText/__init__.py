import bpy
from ..utils import PkgInstaller
from ..translation import ctxt

REGISTERED = [False]

REQUIREMENTS = ["imgui"]

QT_REG = [False]
QT_POS = [None]


def install():
    return PkgInstaller.try_install(*REQUIREMENTS)


def enable_multiline_text():
    if REGISTERED[0]:
        return True
    if not install():
        return False
    from .integration import multiline_register
    multiline_register()
    REGISTERED[0] = True
    return True


def disable_multiline_text():
    if not REGISTERED[0]:
        return
    from .integration import multiline_unregister
    multiline_unregister()
    REGISTERED[0] = False


from PySide2.QtCore import QTimer, QPoint, Qt
from PySide2.QtWidgets import QTextEdit, QVBoxLayout, QDialog, QApplication, QScrollArea, QCompleter
from PySide2.QtGui import QCursor, QStandardItemModel, QStandardItem, QTextCursor, QKeyEvent


def get_CF_active_node():
    for area in bpy.context.screen.areas:
        if area.type == "NODE_EDITOR":
            space = area.spaces.active
            if space.type == "NODE_EDITOR" and space.node_tree and space.node_tree.bl_idname == "CFNodeTree":
                if node := space.node_tree.nodes.active:
                    if node.bl_idname == "CLIPTextEncode":
                        return node


complete_list = [
    'hello', 'world', 'AIGODLIKE', 'Blender'
]


class TextEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self.model = QStandardItemModel()
        for word in complete_list:
            item = QStandardItem(word)
            self.model.appendRow(item)
        self.completer = QCompleter(self.model)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insertCompletion)
        self.setCompleter(self.completer)

    def insertCompletion(self, completion):
        if self.completer.widget() != self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.Left)
        tc.movePosition(QTextCursor.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def setCompleter(self, c):
        c.setWidget(self)
        c.setCompletionMode(QCompleter.PopupCompletion)
        c.setCaseSensitivity(Qt.CaseInsensitive)
        c.setFilterMode(Qt.MatchContains)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(tc.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab:
            completionPrefix = self.textUnderCursor()
            if completionPrefix != '':
                e.accept()
                self.completer.setCompletionPrefix(completionPrefix)
                popup = self.completer.popup()
                popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
                cr = self.cursorRect()
                cr.setWidth(self.completer.popup().sizeHintForColumn(
                    0) + self.completer.popup().verticalScrollBar().sizeHint().width())
                self.completer.complete(cr)
                return

        elif e.key() == Qt.Key_Return or e.key() == Qt.Key_Enter:
            if self.completer.popup().isVisible():
                e.ignore()
                return

        super().keyPressEvent(e)


class PromptEditorWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_node = None
        self.title = "Prompt 编辑器"

        self.timer = QTimer(self)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

        # stay on top
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Tool)
        # set title
        self.setWindowTitle(self.title)
        # disable maximize
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMaximizeButtonHint)
        # disable minimize
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowMinimizeButtonHint)

        self.textEdit = TextEdit()
        self.layout.addWidget(self.textEdit)

        self.timer.timeout.connect(self.check_node)
        self.timer.start(200)

        # move to mouse
        if QT_POS[0] is None:
            self.move(QCursor.pos())
        else:
            self.move(QT_POS[0])
        self.setFixedSize(200, 300)

    def closeEvent(self, event):
        self.timer.stop()
        QT_POS[0] = self.pos()
        super().closeEvent(event)

    def check_node(self):
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            node = get_CF_active_node()
            if node is None:
                if self.isVisible():
                    self.hide()

                return
            if not self.isVisible():
                # if not close, then show
                self.show()

            if node != self.active_node:
                self.active_node = node
                self.textEdit.setText(node.text)
                # self.textEdit.moveCursor(1)

            else:
                node.text = self.textEdit.toPlainText()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        self.check_node()


def launch_text_edit_window(pos=(0, 0)):
    main_window = QApplication.instance().blender_widget

    if QT_REG[0] is False:
        dlg = PromptEditorWindow(main_window)
        dlg.show()
        QT_REG[0] = dlg
    else:
        dlg = QT_REG[0]
        dlg.close()
        dlg.destroy()
        QT_REG[0] = False


class EnableMLT(bpy.types.Operator):
    bl_idname = "sdn.enable_mlt"
    bl_description = "Enable MLT"
    bl_label = "Enable MLT"
    bl_translation_context = ctxt

    def invoke(self, context, event):
        # if not enable_multiline_text():
        #     self.report({"ERROR"}, "MultiLineText Not Enabled")
        # bpy.ops.sdn.multiline_text("INVOKE_DEFAULT")
        # get context area top left corner position
        launch_text_edit_window()
        return {"FINISHED"}
