from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from .client_api import ClientAPI
from .composite_widgets import ActivityBar, MainContent, Panel, Sidebar, StatusBar
from .event_bus import event_bus
from .widgets import Splitter


class MainWindow(QWidget):
    '''主窗口'''

    def __init__(self):
        super().__init__()
        self._is_first_show = True

        self._init_client_api()
        self._init_ui()
        self._connect_signal()

        QTimer.singleShot(1000, self._init_app)

    def _init_client_api(self):
        '''初始化客户端 API'''

        self._client_api = ClientAPI(self)

    def _init_ui(self):
        self.setWindowTitle('Agent-Client')
        self.resize(1400, 700)  # 2100，1050

        self._activity_bar = ActivityBar(self)  # 活动栏

        self._sidebar = Sidebar(self)  # 侧边栏
        self._main_content = MainContent(self)  # 主内容区
        self._panel = Panel(self)  # 面板区

        self._splitter = Splitter(Qt.Orientation.Horizontal, self)  # 分隔器
        self._splitter.addWidget(self._sidebar, 234)
        self._splitter.addWidget(self._main_content, -1)
        self._splitter.addWidget(self._panel, 234)
        self._splitter.setCollapsible(0, True)
        self._splitter.setCollapsible(1, False)
        self._splitter.setCollapsible(2, True)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)

        center_widget = QWidget(self)
        center_layout = QHBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self._activity_bar)
        center_layout.addWidget(self._splitter)

        self._status_bar = StatusBar(self)  # 状态栏

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(center_widget)
        layout.addWidget(self._status_bar)

    def _connect_signal(self):
        event_bus.occur_error.connect(self._occur_error)  # 接收

    # 辅助相关
    def _init_app(self):
        '''初始化 APP'''

        event_bus.long_operate_started.emit('APP 启动中···')  # 发送
        event_bus.chat_history_load_requested.emit()  # 发送
        event_bus.long_operate_finished.emit()  # 发送

    @Slot(str)
    def _occur_error(self, e: str):
        '''报错'''

        QMessageBox.warning(self, '报错', e)

    def _display_window_on_screen_center(self):
        '''显示窗口到屏幕中间'''

        screen_geometry = self.screen().geometry()
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        self.move(window_geometry.topLeft())

    # 重写相关
    def showEvent(self, e: QShowEvent):
        super().showEvent(e)
        if self._is_first_show:
            QTimer.singleShot(0, self._display_window_on_screen_center)
            self._is_first_show = False
