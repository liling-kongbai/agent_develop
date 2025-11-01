from textwrap import dedent

from markdown_it import MarkdownIt
from mdit_py_plugins.colon_fence import colon_fence_plugin
from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QPoint, QSize, Qt, Slot
from PySide6.QtGui import QAbstractTextDocumentLayout, QColor, QPainter, QPalette, QTextCursor, QTextDocument
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem

from ..models.chat_message_model import MessageRole

# colon_fence_plugin 插件，识别并渲染围栏式内容块，可配合 Pygments 实现语法高亮
# QPainter 画家，Qt 的 2D 图形系统的核心，提供了在绘图设备上进行绘制的各种 API
# QPainter.RenderHint.Antialiasing 抗锯齿
# QTextDocument 文本文档，Qt 富文本引擎的核心数据模型类，将复杂富文本文档组织成层次化的结构，表示和操作复杂富文本文档的底层结构
# QStyledItemDelegate 样式化项目委托，接管单个项目的绘制与编辑，并确保视觉表现与当前应用程序风格一致
# QStyleOptionViewItem 视图项目样式选项，数据结构类，封装了绘制视图项目所需的状态和显示参数，并被委托和样式用来确保项目渲染的正确性和一致性


# 配置全局 Markdown 解析器
md_parser = MarkdownIt('commonmark', {'html': True}).use(colon_fence_plugin)  # 全局 Markdown 解析器


class ChatBubbleDelegate(QStyledItemDelegate):
    '''对话气泡委托'''

    BUBBLE_PADDING_X = 10  # 气泡左右内边距
    BUBBLE_PADDING_Y = 6  # 气泡上下内边距
    BUBBLE_BORDER_RADIUS = 10  # 气泡圆角半径
    USER_BUBBLE_COLOR = QColor('#0078FF')  # User 气泡颜色
    AI_BUBBLE_COLOR = QColor('#E5E5EA')  # AI 气泡颜色
    USER_TEXT_COLOR = QColor(Qt.GlobalColor.white)  # User 文字颜色
    AI_TEXT_COLOR = QColor(Qt.GlobalColor.black)  # AI 文字颜色

    PYGMENTS_CSS = dedent(
        '''\
        .highlight pre { background-color: #2E2E2E; color: #F8F8F2; padding: 10px; border-radius: 5px; font-family: Consolas, Monaco, monospace; }
        .highlight .k { color: #66d9ef; font-weight: bold; }
        .highlight .s, .highlight .s1, .highlight .s2 { color: #e6db74; }
        .highlight .c, .highlight .c1 { color: #75715e; font-style: italic; }
        .highlight .kn { color: #f92672; }
        .highlight .mi { color: #ae81ff; }
        .highlight .o { color: #f92672; }
        .highlight .p { color: #f8f8f2; }
        .highlight .n, .highlight .nb { color: #A6E22E; }'''
    )  # Pygments 代码高亮样式，<AI 生成>

    def __init__(self, parent):
        super().__init__(parent)
        self._text_document_cache: dict[QPersistentModelIndex, QTextDocument] = {}  # QTextDocument 缓存

    # 辅助相关
    def _get_text_document(self, index: QModelIndex, option: QStyleOptionViewItem) -> QTextDocument:
        '''获取，创建，缓存 QTextDocument'''

        text_width = option.rect.width() - 4 * self.BUBBLE_PADDING_X
        persistent_index = QPersistentModelIndex(index)
        if persistent_index in self._text_document_cache:
            text_document = self._text_document_cache[persistent_index]
            if text_document.textWidth() != text_width:
                del self._text_document_cache[persistent_index]
            else:
                return text_document

        message = index.data(MessageRole)
        if not message:
            return None
        content = message.get('content', '')

        is_user = message['is_user']
        html = md_parser.render(content)
        css_color = self.USER_TEXT_COLOR.name() if is_user else self.AI_TEXT_COLOR.name()
        styled_html = f'<div style="color:{css_color};">{html}</div>'

        text_document = QTextDocument()
        text_document.setHtml(styled_html)
        text_document.setTextWidth(text_width)
        # text_document.setDefaultStyleSheet(self.PYGMENTS_CSS)

        self._text_document_cache[persistent_index] = text_document
        return text_document

    # 重写相关
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        '''绘制'''

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 设置渲染提示，指导渲染引擎控制绘制质量和效果
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        message = index.data(MessageRole)
        if not message:
            return
        text_document = self._get_text_document(index, option)
        if not text_document:
            return
        is_user = message['is_user']

        # 绘制气泡
        bubble_rect_size = option.rect.adjusted(
            self.BUBBLE_PADDING_X, self.BUBBLE_PADDING_Y, -self.BUBBLE_PADDING_X, -self.BUBBLE_PADDING_Y
        )
        bubble_color = self.USER_BUBBLE_COLOR if is_user else self.AI_BUBBLE_COLOR
        painter.setBrush(bubble_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bubble_rect_size, self.BUBBLE_BORDER_RADIUS, self.BUBBLE_BORDER_RADIUS)

        # 绘制文本
        painter.save()
        painter.translate(
            QPoint(bubble_rect_size.left() + self.BUBBLE_PADDING_X, bubble_rect_size.top() + self.BUBBLE_PADDING_Y)
        )

        # 绘制文本选区
        view = option.widget
        if view and view._check_index_is_selection_index(index):
            paint_context = QAbstractTextDocumentLayout.PaintContext()
            paint_context.palette = option.palette
            paint_context.palette.setColor(QPalette.ColorRole.Highlight, option.palette.highlight().color())
            paint_context.palette.setColor(
                QPalette.ColorRole.HighlightedText, option.palette.highlightedText().color()
            )

            selection = QAbstractTextDocumentLayout.Selection()
            if hasattr(view, '_selection_cursor'):
                selection.cursor = view._selection_cursor
            else:
                painter.restore()
                return
            paint_context.selections.append(selection)
            text_document.documentLayout().draw(painter, paint_context)
        else:
            text_document.drawContents(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        '''尺寸提示'''

        text_document = self._get_text_document(index, option)
        if not text_document:
            return QSize(0, 0)

        height = text_document.size().height() + self.BUBBLE_PADDING_Y * 4
        return QSize(option.rect.width(), int(height))

    # 功能相关
    def hit_test(self, index: QModelIndex, option: QStyleOptionViewItem, pos: QPoint) -> QTextCursor:
        '''命中测试，返回指定位置的文本光标'''

        text_document = self._get_text_document(index, option)
        if not text_document:
            return QTextCursor()

        pos = pos - QPoint(self.BUBBLE_PADDING_X * 2, self.BUBBLE_PADDING_Y * 2)
        char_pos = text_document.documentLayout().hitTest(pos, Qt.HitTestAccuracy.ExactHit)
        text_cursor = QTextCursor(text_document)
        if char_pos != -1:
            text_cursor.setPosition(char_pos)
        return text_cursor

    def anchor_at_url(self, index: QModelIndex, option: QStyleOptionViewItem, pos: QPoint) -> str:
        '''锚定 URL，判断并返回指定位置的 URL'''

        text_document = self._get_text_document(index, option)
        if not text_document:
            return ''
        return text_document.documentLayout().anchorAt(
            pos - QPoint(self.BUBBLE_PADDING_X * 2, self.BUBBLE_PADDING_Y * 2)
        )

    def get_selection_text(self, index: QModelIndex, option: QStyleOptionViewItem, selection: QTextCursor) -> str:
        '''获取选区文本'''

        text_document = self._get_text_document(index, option)
        if not text_document:
            return ''
        start_pos = selection.selectionStart()
        end_pos = selection.selectionEnd()

        text_cursor = QTextCursor(text_document)
        text_cursor.setPosition(start_pos)
        text_cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
        return text_cursor.selectedText()

    @Slot(QModelIndex, QModelIndex, list)
    def handle_date_changed(self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]):
        '''处理数据变化'''

        if Qt.ItemDataRole.DisplayRole in roles or MessageRole in roles:
            for row in range(top_left.row(), bottom_right.row() + 1):
                index = top_left.model().index(row, 0)
                persistent_index = QPersistentModelIndex(index)
                if persistent_index in self._text_document_cache:
                    del self._text_document_cache[persistent_index]

    @Slot()
    def clear_cache(self):
        '''清空缓存'''

        self._text_document_cache.clear()
