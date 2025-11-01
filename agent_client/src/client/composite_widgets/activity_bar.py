from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from ..event_bus import event_bus


class ActivityBar(QWidget):
    '''活动栏'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_index = -1

        self._init_ui()
        self._connect_signal()

        self._buttons = [self._chat_history_button, self._set_button]

        self._init_button_check_state(0)

    def _init_ui(self):
        self.setFixedWidth(46)  # 69

        self._chat_history_button = QPushButton('Chat')
        self._chat_history_button.setCheckable(True)
        self._set_button = QPushButton('Set')
        self._set_button.setCheckable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._chat_history_button)
        layout.addWidget(self._set_button)

    def _connect_signal(self):
        self._chat_history_button.clicked.connect(lambda: self._emit_button_check_state(0))  # 行动
        self._set_button.clicked.connect(lambda: self._emit_button_check_state(1))  # 行动

        event_bus.widget_visibility_changed.connect(self._change_button_check_state)  # 接收

    # 辅助相关
    def _set_button_check_state(self, visibility: bool):
        '''设置按钮选中状态'''

        for i, button in enumerate(self._buttons):
            button.setChecked(visibility and i == self._current_index)

    def _init_button_check_state(self, index: int):
        '''初始化按钮选中状态'''

        self._current_index = index
        self._set_button_check_state(True)

    @Slot(int)
    def _emit_button_check_state(self, index: int):
        '''发送按钮选中状态'''

        toggle = index == self._current_index
        if toggle:
            self._set_button_check_state(False)
        else:
            self._current_index = index
            self._set_button_check_state(True)
        event_bus.activity_bar_button_changed.emit(index, toggle)  # 发送

    @Slot(str, bool)
    def _change_button_check_state(self, widget_object_name: str, visibility: bool):
        '''改变按钮选中状态'''

        if widget_object_name == 'sidebar':
            if visibility:
                self._set_button_check_state(True)
            else:
                self._set_button_check_state(False)
