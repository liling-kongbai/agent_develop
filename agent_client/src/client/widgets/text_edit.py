from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QTextEdit

from ..event_bus import event_bus


class TextEdit(QTextEdit):  # 支持富文本的多行文本编辑控件
    '''支持富文本的多行文本编辑控件，增加判断回车 + Shift 组合键'''

    # 事件相关
    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Return and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            event_bus.text_submited.emit()  # 发送
        else:
            super().keyPressEvent(e)
