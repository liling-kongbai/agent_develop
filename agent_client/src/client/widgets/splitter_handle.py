from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPalette
from PySide6.QtWidgets import QSplitter, QSplitterHandle


class SplitterHandle(QSplitterHandle):
    '''分隔条，增加根据鼠标行为的颜色变化'''

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter):
        super().__init__(orientation, parent)
        self._hover_color = QColor('#D6EAF8')
        self._pressed_color = QColor("#AED6F1")

        self._init_ui()

    def _init_ui(self):
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)

        self._change_palette_window_color(Qt.GlobalColor.transparent)

    # 辅助相关
    def _change_palette_window_color(self, color):
        '''改变调色板背景颜色'''

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        self.setPalette(palette)

    # 重写相关
    def enterEvent(self, e: QEnterEvent):
        self._change_palette_window_color(self._hover_color)
        super().enterEvent(e)

    def leaveEvent(self, e: QEnterEvent):
        self._change_palette_window_color(Qt.GlobalColor.transparent)
        super().leaveEvent(e)

    def mousePressEvent(self, e: QMouseEvent):
        self._change_palette_window_color(self._pressed_color)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._change_palette_window_color(self._hover_color)
        super().mouseReleaseEvent(e)
