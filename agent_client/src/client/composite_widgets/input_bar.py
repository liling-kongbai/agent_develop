from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..event_bus import event_bus
from ..widgets.text_edit import TextEdit


class InputBar(QWidget):
    '''输入栏'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self._text_edit = TextEdit()
        self._text_edit.setFixedHeight(60)  # 90
        self._text_edit.setEnabled(False)
        self._send_button = QPushButton('发送')
        self._send_button.setEnabled(False)

        layout = QHBoxLayout(self)
        layout.addWidget(self._text_edit)
        layout.addWidget(self._send_button)

    def _connect_signal(self):
        self._send_button.clicked.connect(self._submit_and_clear)  # 行动

        event_bus.text_submited.connect(self._submit_and_clear)  # 接收

    # 辅助相关
    @Slot()
    def _submit_and_clear(self):
        '''提交与清理，获取文本并提交，清空文本编辑框'''

        text = self._text_edit.toPlainText().strip()
        if text:
            event_bus.input_submitted.emit(text)  # 发送
            self._text_edit.clear()

    def _set_activation(self, activation: bool):
        '''设置激活状态'''

        self._text_edit.setEnabled(activation)
        self._send_button.setEnabled(activation)

    def _focus_text_edit(self):
        '''聚焦文本编辑框'''

        self._text_edit.setFocus()

    # 功能相关
    @Slot(bool)
    def activate_and_focus(self, activation: bool):
        '''激活与聚焦'''

        self._set_activation(activation)
        if activation:
            self._focus_text_edit()
