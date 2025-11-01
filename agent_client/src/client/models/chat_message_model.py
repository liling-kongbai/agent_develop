from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QTimer, Slot

MessageRole = Qt.ItemDataRole.UserRole + 1


class ChatMessageModel(QAbstractListModel):  # 列表数据模型抽象类，为视图控件提供数据
    '''对话 Message 数据模型'''

    def __init__(self, parent):
        super().__init__(parent)

        # 节流防抖
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)
        self._update_timer.timeout.connect(self._handle_pending_updates)

        self._pending_updates = set()

        self._messages: list[dict[bool, str]] = []

    # 重写相关
    def rowCount(self, parent: QModelIndex) -> int:  # 数据模型索引，指向数据模型内部数据项的临时坐标式引用
        '''行总数'''

        return len(self._messages)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # 可见文本角色
        '''根据数据模型索引和项数据角色返回数据'''

        if not index.isValid() or not 0 <= index.row() < self.rowCount(QModelIndex()):
            return None

        message = self._messages[index.row()]
        if role == MessageRole:
            return message
        elif role == Qt.ItemDataRole.DisplayRole:
            return message.get('content', '')
        else:
            return None

    # 辅助相关
    def _add_new_message(self, message: dict[bool, str]):
        '''添加新的 Message'''

        self.beginInsertRows(QModelIndex(), self.rowCount(QModelIndex()), self.rowCount(QModelIndex()))
        self._messages.append(message)
        self.endInsertRows()

    def _add_chunk_to_last_message(self, chunk: str):
        '''添加 Chunk 到最后一个 Message'''

        last_message_index_row = self.rowCount(QModelIndex()) - 1
        self._messages[last_message_index_row]['content'] += chunk

        self._pending_updates.add(last_message_index_row)
        if not self._update_timer.isActive():
            self._update_timer.start()

    @Slot()
    def _handle_pending_updates(self):
        '''处理待办更新'''

        if not self._pending_updates:
            return

        for row in self._pending_updates:
            index = self.index(row)
            self.dataChanged.emit(index, index, [MessageRole, Qt.ItemDataRole.DisplayRole])

        self._pending_updates.clear()

    # 功能相关
    def add_message(self, message: dict[bool, str]):
        '''添加 Message'''

        is_user = message['is_user']
        if is_user:
            self._add_new_message(message)
        else:
            if self._messages[-1]['is_user']:
                self._add_new_message(message)
            else:
                content = message.get('content', '')
                self._add_chunk_to_last_message(content)

    def clear(self):
        '''清空'''

        if not self._messages:
            return
        self._messages.clear()
        self.modelReset.emit()

    def load_chat(self, chat: list[dict[bool, str]]):
        '''加载对话'''

        self.beginResetModel()
        self._messages = chat
        self.endResetModel()
