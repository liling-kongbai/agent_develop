from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QWidget

from ..event_bus import event_bus
from .splitter_handle import SplitterHandle


class Splitter(QSplitter):
    '''分隔器，增加边缘吸附功能'''

    def __init__(self, orientation: Qt.Orientation, parent: QWidget):
        super().__init__(orientation, parent)
        self._border_adsorb_thresholds = {}  # 边缘吸附阈值
        self._widget_was_visible = {}  # 控件过去可见性
        self._last_sidebar_width = 234
        self._last_panel_width = 234

        self._init_ui()
        self._connect_signal()

        self._check_widget_visibility()

    # 重写相关
    def createHandle(self) -> QSplitterHandle:
        return SplitterHandle(self.orientation(), self)

    def _init_ui(self):
        self.setHandleWidth(3)

    def _connect_signal(self):
        self.splitterMoved.connect(self._border_adsorb)  # 行动
        self.splitterMoved.connect(self._check_widget_visibility)  # 行动

        event_bus.activity_bar_button_changed.connect(self._handle_activity_bar_button_changed)  # 接收
        event_bus.panel_slide_switch_toggled.connect(self._handle_panel_slide_switch_toggled)  # 接收

    # 辅助相关
    def _check_widget_visibility(self):
        '''检查控件可见性'''

        sizes = self.sizes()
        for i in range(self.count()):
            widget = self.widget(i)
            widget_is_visible = sizes[i] > 0
            widget_was_visible = self._widget_was_visible.get(widget)
            if widget_is_visible != widget_was_visible:
                event_bus.widget_visibility_changed.emit(widget.objectName(), widget_is_visible)  # 发送
                self._widget_was_visible[widget] = widget_is_visible

    # 重写相关，辅助相关
    def setSizes(self, list):
        '''设置大小并检查'''

        super().setSizes(list)
        self._check_widget_visibility()

    # 辅助相关
    @Slot(int, int)
    def _border_adsorb(self, pos: int, index: int):
        '''边缘吸附'''

        if index <= 0 or index >= self.count():
            return

        sizes = self.sizes()
        left_widget_threshold = self._border_adsorb_thresholds.get(self.widget(index - 1))
        if left_widget_threshold and left_widget_threshold > 0 and sizes[index - 1] < left_widget_threshold:
            sizes[index - 1] = 0
            sizes[index] += sizes[index - 1]
            self.setSizes(sizes)
            return
        right_widget_threshold = self._border_adsorb_thresholds.get(self.widget(index))
        if right_widget_threshold and right_widget_threshold > 0 and sizes[index] < right_widget_threshold:
            sizes[index] = 0
            sizes[index - 1] += sizes[index]
            self.setSizes(sizes)

    # 辅助相关
    @Slot(int, bool)
    def _handle_activity_bar_button_changed(self, index: int, toggle: bool):
        '''处理活动栏按钮变换，改变侧边栏状态'''

        sizes = self.sizes()
        side_bar = self.widget(0)
        side_bar_width = sizes[0]
        side_bar_visibility = side_bar_width > 0

        if toggle:
            if side_bar_visibility:
                self.setSizes(
                    [
                        0,
                        sizes[1] + self._last_sidebar_width,
                        sizes[2],
                    ]
                )
                self._last_sidebar_width = side_bar_width
            else:
                self.setSizes(
                    [
                        self._last_sidebar_width,
                        sizes[1] - self._last_sidebar_width,
                        sizes[2],
                    ]
                )
        else:
            side_bar.set_page(index)
            if not side_bar_visibility:
                self.setSizes(
                    [
                        self._last_sidebar_width,
                        sizes[1] - self._last_sidebar_width,
                        sizes[2],
                    ]
                )

    @Slot(bool)
    def _handle_panel_slide_switch_toggled(self, toggle: bool):
        '''处理面板区滑动开关切换'''

        sizes = self.sizes()
        panel_visibility = sizes[2] > 0

        if toggle and not panel_visibility:
            self.setSizes([sizes[0], sizes[1] - self._last_panel_width, self._last_panel_width])
        elif not toggle and panel_visibility:
            self.setSizes([sizes[0], sizes[1] + sizes[2], 0])
            self._last_panel_width = sizes[2]

    # 重写相关，功能相关
    def addWidget(self, widget: QWidget, threshold: int):
        '''添加子控件，边缘吸附阈值，可见性状态'''

        super().addWidget(widget)
        self._border_adsorb_thresholds[widget] = threshold
        self._widget_was_visible[widget] = True
