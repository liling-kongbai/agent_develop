from PySide6.QtCore import QModelIndex, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent, QKeySequence, QMouseEvent, QTextCursor
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyleOptionViewItem


class ChatListView(QListView):
    '''对话列表视图'''

    SCROLL_AT_BOTTOM_THRESHOLD = 5  # 滚动到底部阈值

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

        self._is_at_bottom = True

        self._mouse_pressed = False
        self._selection_index = QModelIndex()
        self._selection_cursor = QTextCursor()
        self._hovered_link = ''  # 悬停链接

    def _init_ui(self):
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # 垂直滚动条策略，按需显示
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)  # 垂直滚动模式，按像素滚动
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # 水平滚动条策略，始终关闭
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)  # 选择模式，非选择
        self.setResizeMode(QListView.ResizeMode.Adjust)  # 尺寸调整模式，调整
        self.setWordWrap(True)  # 文字换行
        self.setStyleSheet('QListView {border: 1px solid #E1E1E1;}')  # 样式表
        self.setMouseTracking(True)  # 鼠标跟踪

    def _connect_signal(self):
        self.verticalScrollBar().valueChanged.connect(self._update_scroll_bar_state)
        self.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)

    # 辅助相关
    @Slot(int)
    def _update_scroll_bar_state(self, value: int):
        '''更新滚动条状态'''

        scroll_bar = self.verticalScrollBar()
        if scroll_bar.isVisible():
            self._is_at_bottom = value >= (scroll_bar.maximum() - self.SCROLL_AT_BOTTOM_THRESHOLD)
        else:
            self._is_at_bottom = True

    @Slot()
    def _scroll_to_bottom(self):
        '''滚动到底部'''

        if self._is_at_bottom:
            self.scrollToBottom()

    def _get_option_for_index(self, index: QModelIndex) -> QStyleOptionViewItem:
        '''根据数据模型索引获取项样式选项'''

        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = self.visualRect(index)
        option.index = index
        return option

    def _check_index_is_selection_index(self, index: QModelIndex) -> bool:
        '''检查数据模型索引是否是选区数据模型索引，选区文本光标是否存在选区'''

        return index == self._selection_index and self._selection_cursor.hasSelection()

    # 事件相关
    def mousePressEvent(self, event: QMouseEvent):
        '''鼠标按压事件，处理文本选区'''

        if event.button() == Qt.MouseButton.LeftButton:
            index = self.indexAt(event.pos())
            if not index.isValid():  # 是否点击了空白区域，清空选区
                if self._selection_index.isValid():
                    self.viewport().update(self.visualRect(self._selection_index))

                    self._selection_index = QModelIndex()
                    self._selection_cursor.clearSelection()
                    return

            self._mouse_pressed = True

            if index != self._selection_index:  # 是否点击了其他索引的数据模型
                if self._selection_index.isValid():
                    self.viewport().update(self.visualRect(self._selection_index))
                self._selection_index = index
                self._selection_cursor.clearSelection()

            item_rect = self.visualRect(index)
            delegate = self.itemDelegateForIndex(index)
            self._selection_cursor = delegate.hit_test(
                index, self._get_option_for_index(index), event.pos() - item_rect.topLeft()
            )
            self.viewport().update(item_rect)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        '''鼠标移动事件，更新光标，文本选区'''

        index = self.indexAt(event.pos())
        if not index.isValid():
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            self._hovered_link = ''
            super().mouseMoveEvent(event)
            return

        item_rect = self.visualRect(index)
        cursor_in_item_pos = event.pos() - item_rect.topLeft()
        delegate = self.itemDelegateForIndex(index)

        link = delegate.anchor_at_url(index, self._get_option_for_index(index), cursor_in_item_pos)
        if link:
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
            self._hovered_link = link
        else:
            self.viewport().setCursor(Qt.CursorShape.IBeamCursor)
            self._hovered_link = ''

        if self._mouse_pressed and self._selection_index.isValid():
            cursor_end = delegate.hit_test(
                self._selection_index, self._get_option_for_index(self._selection_index), cursor_in_item_pos
            )
            self._selection_cursor.setPosition(cursor_end.position(), QTextCursor.MoveMode.KeepAnchor)
            self.viewport().update(self.visualRect(self._selection_index))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        '''鼠标释放事件，完成文本选区，处理 URL 点击'''

        self._mouse_pressed = False

        if event.button() == Qt.MouseButton.LeftButton and self._hovered_link:
            QDesktopServices.openUrl(QUrl(self._hovered_link))

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        '''键盘按压事件，增加复制操作'''

        if event.matches(QKeySequence.StandardKey.Copy):
            if self._check_index_is_selection_index(self._selection_index):
                delegate = self.itemDelegateForIndex(self._selection_index)
                selected_text = delegate.get_selection_text(
                    self._selection_index,
                    self._get_option_for_index(self._selection_index),
                    self._selection_cursor,
                )
                if selected_text:
                    QGuiApplication.clipboard().setText(selected_text)
        else:
            super().keyPressEvent(event)
