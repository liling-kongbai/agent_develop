from PySide6.QtCore import Slot
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from ..event_bus import event_bus


class Panel(QWidget):
    '''面板区'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self.setObjectName('panel')
        self.setMinimumWidth(234)

        self._graph_state_plain_text_edit = QPlainTextEdit()
        self._graph_state_plain_text_edit.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._graph_state_plain_text_edit)

    def _connect_signal(self):
        event_bus.graph_operate_logged.connect(self._add_graph_operate_log)  # 接收
        event_bus.new_chat_requested.connect(self._clear_graph_operate_log)  # 接收

    # 辅助相关
    @Slot(str)
    def _add_graph_operate_log(self, log):
        '''添加图运行日志'''

        self._graph_state_plain_text_edit.appendPlainText(log)
        self._graph_state_plain_text_edit.verticalScrollBar().setValue(
            self._graph_state_plain_text_edit.verticalScrollBar().maximum()
        )

    @Slot()
    def _clear_graph_operate_log(self):
        '''清空图运行日志'''

        self._graph_state_plain_text_edit.clear()
