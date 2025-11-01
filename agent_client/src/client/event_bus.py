from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget


class _EventBus(QObject):
    '''事件总线'''

    # 客户端 API 发送 ----------

    # 主窗口接收
    occur_error = Signal(str)  # 报错

    # 主窗口发送，主窗口接收
    long_operate_started = Signal(str)  # 长时运行开始
    long_operate_finished = Signal()  # 长时运行结束

    # 对话历史页面接收
    chat_history_loaded = Signal(list)  # 对话历史加载

    # 主内容区接收
    input_ready = Signal(bool)  # 输入准备
    chat_loaded = Signal(list)  # 对话加载
    ai_message_chunk_received = Signal(str)  # AI Message Chunk 到达

    # 面板区接收
    graph_operate_logged = Signal(str)  # 图运行日志

    # 客户端 API 接收 ----------

    # 设置页面发送
    llm_changed = Signal(str, str)  # LLM 改变
    mcp_client_toggled = Signal(bool)  # MCP 客户端开关切换
    gpt_sovits_toggled = Signal(bool)  # GPT_SoVITS 开关切换

    # 对话历史页面发送
    chat_history_load_requested = Signal()  # 对话历史请求
    chat_selected = Signal(str)  # 对话历史选择

    # 输入栏发送，客户端 API 接收，主内容区接收
    input_submitted = Signal(str)

    # 对话历史页面发送，客户端 API 接收，面板区接收
    new_chat_requested = Signal()  # 新建对话请求

    # 分隔器相关 -----------

    # 活动栏发送，分隔器接收
    activity_bar_button_changed = Signal(int, bool)  # 活动栏按钮变换

    # 功能栏发送，分隔器接收
    panel_slide_switch_toggled = Signal(bool)  # 面板区滑动开关切换

    # 分隔器发送，活动栏接收，功能栏接收
    widget_visibility_changed = Signal(str, bool)  # 控件可见性变换

    # 输入栏相关 ----------

    # 文本编辑框发送，输入栏接收
    text_submited = Signal()  # 文本提交

    def __init__(self):
        super().__init__()


event_bus = _EventBus()  # 全局事件总线实例
