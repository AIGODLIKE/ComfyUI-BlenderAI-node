from pathlib import Path
from PySide2.QtGui import QCloseEvent, QIcon, QImage, QPixmap, QWindow
import PySide2.QtCore as QtCore


def get_question_pixmap():
    icon_filepath = Path(__file__).parents[1] / "images" / "question.svg"
    pixmap = QPixmap()
    if icon_filepath.exists():
        image = QImage(str(icon_filepath))
        if not image.isNull():
            pixmap = pixmap.fromImage(image)
            pixmap = pixmap.scaledToWidth(64, QtCore.Qt.SmoothTransformation)
    return pixmap