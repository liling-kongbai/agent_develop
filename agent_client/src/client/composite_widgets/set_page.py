from PySide6.QtCore import Slot
from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QLabel, QWidget

from ..event_bus import event_bus


class SetPage(QWidget):
    '''设置页面'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._PLACEHOLDER_TEXT = '请选择模型'
        self.llm_options = {
            'ollama': ['qwen2.5:3b', 'qwen2.5:7b', 'qwen3:1.7b', 'qwen3:4b', 'qwen3:latest'],
            'deepseek': ['deepseek-chat', 'deepseek-reasoner'],
        }

        self._init_ui()
        self._connect_signal()

        self._update_llm_combo(self._llm_platform_combo.currentText())

    def _init_ui(self):
        llm_platform_label = QLabel('LLM 平台')
        self._llm_platform_combo = QComboBox(editable=False)  # 下拉列表控件
        self._llm_platform_combo.addItems(self.llm_options.keys())
        llm_label = QLabel('LLM')
        self._llm_combo = QComboBox(editable=False)
        self._gpt_sovits_check = QCheckBox('GPT_SoVITS')  # 带文本标签的复选框控件
        self._gpt_sovits_check.setChecked(False)
        self._mcp_client_check = QCheckBox('MCP_Client')
        self._mcp_client_check.setChecked(False)

        layout = QGridLayout(self)
        layout.addWidget(llm_platform_label, 0, 0)
        layout.addWidget(self._llm_platform_combo, 1, 0)
        layout.addWidget(llm_label, 0, 1)
        layout.addWidget(self._llm_combo, 1, 1)
        layout.addWidget(self._gpt_sovits_check, 2, 0)
        layout.addWidget(self._mcp_client_check, 2, 1)

    def _connect_signal(self):
        self._llm_platform_combo.currentTextChanged.connect(self._update_llm_combo)  # 行动
        self._llm_combo.currentIndexChanged.connect(self._llm_changed)  # 行动
        self._gpt_sovits_check.toggled.connect(event_bus.gpt_sovits_toggled.emit)  # 发送
        self._mcp_client_check.toggled.connect(event_bus.mcp_client_toggled.emit)  # 发送

    # 辅助相关
    @Slot(str)
    def _update_llm_combo(self, llm_platform: str):
        '''更新 LLM 下拉列表'''

        try:
            self._llm_combo.blockSignals(True)
            self._llm_combo.clear()
            self._llm_combo.addItem(self._PLACEHOLDER_TEXT)
            self._llm_combo.addItems(self.llm_options.get(llm_platform, []))
            self._llm_combo.setCurrentIndex(0)
        finally:
            self._llm_combo.blockSignals(False)

    @Slot(int)
    def _llm_changed(self, index: int):
        '''LLM 改变了'''

        if index == 0:
            event_bus.llm_changed.emit('', '')
            return
        event_bus.llm_changed.emit(self._llm_platform_combo.currentText(), self._llm_combo.currentText())  # 发送
