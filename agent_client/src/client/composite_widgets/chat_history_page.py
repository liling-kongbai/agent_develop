from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from ..event_bus import event_bus


class ChatHistoryPage(QWidget):
    '''对话历史页面'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self._new_chat_button = QPushButton('新对话')
        self._chat_history_list = QListWidget()  # 显示可供选择的垂直项目列表

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._new_chat_button)
        layout.addWidget(self._chat_history_list, 1)

    def _connect_signal(self):
        self._new_chat_button.clicked.connect(event_bus.new_chat_requested.emit)  # 发送
        self._chat_history_list.itemClicked.connect(self._chat_selected)  # 行动

        event_bus.chat_history_loaded.connect(self._update_chat_history)  # 接收

    # 辅助相关
    @Slot(QListWidgetItem)
    def _chat_selected(self, item: QListWidgetItem):
        '''对话被选择'''

        thread_id = item.data(Qt.ItemDataRole.UserRole)
        event_bus.chat_selected.emit(thread_id)  # 发送

    @Slot(list)
    def _update_chat_history(self, chat_history: list):
        '''更新对话历史'''

        self._chat_history_list.clear()
        for chat in chat_history:
            title = chat['title'] or '无标题对话，请检查！！！'
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, chat['thread_id'])
            self._chat_history_list.addItem(item)
