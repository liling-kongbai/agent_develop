from PySide6.QtCore import Slot
from PySide6.QtWidgets import QHBoxLayout, QWidget

from ..event_bus import event_bus
from ..widgets.SlideSwitch import SlideSwitch


class FunctionBar(QWidget):
    '''功能栏'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signal()

    def _init_ui(self):
        self.setFixedHeight(46)  # 69

        self._panel_slide_switch = SlideSwitch(self)  # 面板区滑动按钮
        self._panel_slide_switch.setFixedSize(40, 20)
        self._panel_slide_switch.setChecked(True)

        layout = QHBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self._panel_slide_switch)

    def _connect_signal(self):
        self._panel_slide_switch.toggled.connect(event_bus.panel_slide_switch_toggled.emit)  # 发送

        event_bus.widget_visibility_changed.connect(self._change_panel_slide_switch_state)  # 接收

    # 辅助相关
    @Slot(str, bool)
    def _change_panel_slide_switch_state(self, widget_object_name: str, state: bool):
        '''改变面板区滑动开关状态'''

        if widget_object_name == 'panel':
            self._panel_slide_switch.blockSignals(True)
            self._panel_slide_switch.setChecked(state)
            self._panel_slide_switch.knob_position = 1.0 if state else 0.0
            self._panel_slide_switch.blockSignals(False)
