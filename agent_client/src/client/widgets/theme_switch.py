from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Slot
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton


class ThemeSwitch(QAbstractButton):
    '''主题切换按钮'''

    track_color_off = QColor('#D0D0D0')
    track_color_on = QColor('#0078D3')
    knob_color = QColor('#F0F0F0')

    def __init__(self, parent=None):
        super().__init__(parent)

        self._knob_position = 0.0

    def _init_ui(self):
        self.setCheckable(True)
        self.setChecked(False)

        self.animation = QPropertyAnimation()
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _connect_signal(self):
        self.toggled.connect(self._handle_toggled)

    # 重写相关
    def paintEvent(self, e: QPaintEvent):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        return super().paintEvent(e)

    @Slot(bool)
    def _handle_toggled(self, toggle: bool):

        self.animation.setStartValue()
        self.animation.setEndValue(1.0 if toggle else 0.0)
        self.animation.start()
