from textwrap import dedent

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel

from ..event_bus import event_bus


class StatusBar(QFrame):
    '''状态栏'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self.setFixedHeight(21)
        self.setStyleSheet(
            dedent(
                '''\
                StatusBar { border-top: 1px solid #E1E1E1; }
                '''
            )
        )

        self._status_label = QLabel('状态栏工作中···', self)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.addWidget(self._status_label)
        layout.addStretch()

    def _connect_signal(self):
        event_bus.long_operate_started.connect(self._long_operate_start)  # 接收
        event_bus.long_operate_finished.connect(self._long_operate_finish)  # 接收

    # 辅助相关
    def _set_status(self, status: str | None = None):
        '''设置状态'''

        if status:
            self._status_label.setText(status)

    def _clear_status(self):
        '''清空状态，恢复默认'''

        self._status_label.setText('状态栏工作中···')

    @Slot(str)
    def _long_operate_start(self, status: str | None = None):
        '''长时运行开始'''

        self._set_status(status)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

    @Slot()
    def _long_operate_finish(self):
        '''长时运行结束'''

        self._clear_status()
        QApplication.restoreOverrideCursor()
