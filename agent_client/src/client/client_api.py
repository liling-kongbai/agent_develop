import json
from functools import partial
from traceback import format_exc
from uuid import uuid4

from PySide6.QtCore import QByteArray, QObject, QUrl, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWebSockets import QWebSocket

from .event_bus import event_bus


class ClientAPI(QObject):
    '''客户端 API，与服务器进行网络通信'''

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_url = r'http://127.0.0.1:8000'
        self._current_thread_id = None
        self._llm_activated = False

        self._access_manager = QNetworkAccessManager(self)  # 发送 HTTP 请求并处理响应
        self._websocket = QWebSocket(parent=self)  # 建立和管理 WebSocket 通信

        self._connect_signal()
        self._connect_websocket()

    def _connect_signal(self):
        event_bus.llm_changed.connect(self._request_activate_llm)  # 接收
        event_bus.mcp_client_toggled.connect(self._request_activate_mcp_client)  # 接收
        event_bus.gpt_sovits_toggled.connect(self._request_activate_gpt_sovits)  # 接收

        event_bus.chat_history_load_requested.connect(self._request_load_chat_history)  # 接收
        event_bus.chat_selected.connect(self._request_load_chat)  # 接收

        event_bus.new_chat_requested.connect(self._handle_new_chat_request)  # 接收

    def _connect_websocket(self):
        self._websocket.disconnected.connect(self._websocket_disconnected)  # 行动
        self._websocket.errorOccurred.connect(self._websocket_occur_error)  # 行动

        self._websocket.textMessageReceived.connect(self._websocket_communication)  # 行动

        event_bus.input_submitted.connect(self._submit_user_content)  # 接收

    # 辅助相关
    @Slot()
    def _handle_new_chat_request(self):
        '''处理新对话请求'''

        if not self._llm_activated:
            event_bus.occur_error.emit('请选择一个 LLM ！！！')
            return

        self._close_websocket()
        self._connect_chat_websocket(str(uuid4()))

    def _send_request(self, route: str, payload: dict | None = None) -> QNetworkReply:  # 网络回复，封装网络操作的回复
        '''发送请求'''

        request = QNetworkRequest(QUrl(self._base_url + route))
        # 网络请求，数据容器，结构化地封装和描述网络请求
        # 统一资源定位符，表示，解析，操作 URL
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json'
        )  # 内容类型请求头，设置 HTTP 请求的 Content-Type 头部，声明请求体中的数据媒体类型
        json_payload = (
            QByteArray(json.dumps(payload).encode()) if payload else QByteArray()
        )  # 字节数组，存储和操作字节序列，数据序列化操作的基础
        return self._access_manager.post(request, json_payload)

    def _llm_activate_finished(self, reply: QNetworkReply):
        '''LLM 激活完成'''

        if reply.error() != QNetworkReply.NetworkError.NoError:
            e = f'<_llm_activate_finished> LLM 激活完成失败！！！\n{reply.errorString()}'
            event_bus.occur_error.emit(e)  # 发送
            print(e)
            self._llm_activated = False
        else:
            self._llm_activated = True
            if not self._current_thread_id:
                self._handle_new_chat_request()
        reply.deleteLater()

    def _chat_history_loaded(self, reply: QNetworkReply):
        '''对话历史加载'''

        if reply.error() != QNetworkReply.NetworkError.NoError:
            e = f'<_chat_history_loaded> 加载对话历史失败！！！\n{reply.errorString()}'
            event_bus.occur_error.emit(e)  # 发送
            print(e)
        else:
            try:
                chat_history = json.loads(reply.readAll().data().decode()).get('chat_history', [])
                event_bus.chat_history_loaded.emit(chat_history)
            except Exception:
                e = f'<_chat_history_loaded> 解析对话历史失败！！！\n{format_exc()}'
                event_bus.occur_error.emit(e)
                print(e)
        reply.deleteLater()

    def _chat_loaded(self, reply: QNetworkReply, thread_id: str):
        '''对话被加载'''

        if reply.error() != QNetworkReply.NetworkError.NoError:
            e = f'<_chat_loaded> 加载对话失败！！！\n{reply.errorString()}'
            event_bus.occur_error.emit(e)
            print(e)
        else:
            try:
                self._close_websocket()
                chat = json.loads(reply.readAll().data().decode()).get('chat', [])
                event_bus.chat_loaded.emit(chat)
                self._connect_chat_websocket(thread_id)
            except Exception:
                e = f'<_chat_loaded> 解析对话失败！！！\n{format_exc()}'
                event_bus.occur_error.emit(e)
                print(e)
        reply.deleteLater()

    # HTTP 请求
    @Slot(str, str)
    def _request_activate_llm(self, platform: str, llm: str):
        '''请求激活 LLM'''

        if not platform or not llm:
            self._llm_activated = False
            event_bus.input_ready.emit(False)
        elif platform and llm:
            self._llm_activated = True

        payload = {'platform': platform, 'llm': llm}
        reply = self._send_request(r'/activate_llm', payload)
        reply.finished.connect(partial(self._llm_activate_finished, reply))

    @Slot(bool)
    def _request_activate_mcp_client(self, activation: bool):
        '''请求激活 MCP 客户端'''

        payload = {'activation': activation}
        self._send_request(r'/activate_mcp_client', payload)

    @Slot(bool)
    def _request_activate_gpt_sovits(self, activation: bool):
        '''请求激活 GPT_SoVITS'''

        payload = {'activation': activation}
        self._send_request(r'/activate_gpt_sovits', payload)

    @Slot()
    def _request_load_chat_history(self):
        '''请求加载对话历史'''

        reply = self._send_request(r'/load_chat_history')
        reply.finished.connect(partial(self._chat_history_loaded, reply))

    @Slot(str)
    def _request_load_chat(self, thread_id: str):
        '''请求加载对话'''

        if thread_id == self._current_thread_id:
            return

        reply = self._send_request(f'/load_chat/{thread_id}')
        reply.finished.connect(partial(self._chat_loaded, reply, thread_id))

    # WebSocket 相关
    @Slot(str)
    def _connect_chat_websocket(self, current_thread_id: str):
        '''连接 WebSocket'''

        self._current_thread_id = current_thread_id

        if self._websocket.isValid():
            self._websocket.close()

        self._websocket.open(QUrl(f'ws://{self._base_url.split('//')[1]}/ws/chat/{current_thread_id}'))

    @Slot()
    def _close_websocket(self):
        '''关闭 WebSocket'''

        event_bus.input_ready.emit(False)

        self._current_thread_id = None

        if self._websocket.isValid():
            self._websocket.close()

    @Slot()
    def _websocket_disconnected(self):
        '''WebSocket 断开连接'''

        event_bus.input_ready.emit(False)

        self._current_thread_id = None

    @Slot()
    def _websocket_occur_error(self):
        '''WebSocket 报错'''

        e = f'<_websocket_occur_error> WebSocket 报错！！！\n{self._websocket.errorString()}'
        event_bus.occur_error.emit(e)

    @Slot(str)
    def _submit_user_content(self, content: str):
        '''发送用户输入'''

        if self._websocket.isValid() and self._current_thread_id:
            self._websocket.sendTextMessage(content)
            event_bus.input_ready.emit(False)
        else:
            event_bus.occur_error.emit(
                '<send_user_content> 无法发送用户输入，WebSocket 连接无效 或 当前 thread_id 不存在！！！'
            )

    @Slot(str)
    def _websocket_communication(self, reply: str):
        '''WebSocket 通信'''

        print(f"--- CLIENT RECEIVED MESSAGE: {reply} ---")

        try:
            reply = json.loads(reply)
            reply_type = reply['type']
            payload = reply['payload']

            match reply_type:
                case 'ai_message_chunk':
                    event_bus.ai_message_chunk_received.emit(payload)
                case 'graph_operate_log':
                    event_bus.graph_operate_logged.emit(payload)
                case 'input_ready':
                    event_bus.input_ready.emit(payload)
                case 'occur_error':
                    event_bus.occur_error.emit(payload)
                case 'chat_title_generated':
                    event_bus.chat_history_load_requested.emit()
                case _:
                    event_bus.occur_error.emit('<_websocket_communication> WebSocket 通信收到未知信息！')
        except Exception:
            e = f'<_websocket_communication> WebSocket 通信报错！！！\n{format_exc()}'
            event_bus.occur_error.emit(e)
