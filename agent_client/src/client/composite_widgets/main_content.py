from PySide6.QtCore import Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..delegates.chat_bubble_delegate import ChatBubbleDelegate
from ..event_bus import event_bus
from ..models.chat_message_model import ChatMessageModel
from ..views.chat_list_view import ChatListView
from .function_bar import FunctionBar
from .input_bar import InputBar


class MainContent(QWidget):
    '''主内容区'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self.setMinimumWidth(234)

        # 对话相关，Model-View-Delegate 架构
        self._chat_list_view = ChatListView(self)
        self._chat_message_model = ChatMessageModel(self)
        self._chat_bubble_delegate = ChatBubbleDelegate(self._chat_list_view)
        self._chat_list_view.setModel(self._chat_message_model)
        self._chat_list_view.setItemDelegate(self._chat_bubble_delegate)

        self._function_bar = FunctionBar(self)  # 功能栏
        self._input_bar = InputBar(self)  # 输入栏

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._chat_list_view, 1)
        layout.addWidget(self._function_bar)
        layout.addWidget(self._input_bar)

    def _connect_signal(self):
        self._chat_message_model.dataChanged.connect(self._chat_bubble_delegate.handle_date_changed)
        self._chat_message_model.modelReset.connect(self._chat_bubble_delegate.clear_cache)

        event_bus.input_ready.connect(self._input_bar.activate_and_focus)  # 接收

        event_bus.chat_loaded.connect(self._load_chat)  # 接收

        event_bus.new_chat_requested.connect(self._handle_new_chat_request)  # 接收

        event_bus.input_submitted.connect(self._add_user_message)  # 接收
        event_bus.ai_message_chunk_received.connect(self._add_ai_message)  # 接收

    # 辅助相关
    @Slot(list)
    def _load_chat(self, chat: list):
        '''加载对话'''

        print(chat)

        messages = [{'is_user': message['is_user'], 'content': message['content']} for message in chat]
        self._chat_message_model.load_chat(messages)

    @Slot(bool)
    def _handle_new_chat_request(self):
        '''处理新对话请求'''

        self._chat_message_model.clear()

    @Slot(str)
    def _add_user_message(self, content: str):
        '''添加 User Message'''

        self._chat_message_model.add_message({'is_user': True, 'content': content})

    @Slot(str)
    def _add_ai_message(self, content: str):
        '''添加 AI Message'''

        self._chat_message_model.add_message({'is_user': False, 'content': content})
