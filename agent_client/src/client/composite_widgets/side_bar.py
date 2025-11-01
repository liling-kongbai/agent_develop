from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from .chat_history_page import ChatHistoryPage
from .set_page import SetPage


class Sidebar(QWidget):
    '''侧边栏'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.setObjectName('sidebar')
        self.setMinimumWidth(234)

        self._stack = QStackedWidget()  # 多页面容器控件

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._stack)

        chat_history_page = ChatHistoryPage(self)  # 对话历史页面
        set_page = SetPage(self)  # 设置页面

        self._stack.addWidget(chat_history_page)
        self._stack.addWidget(set_page)

    # 功能相关
    def set_page(self, index: int):
        '''设置页面'''

        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
