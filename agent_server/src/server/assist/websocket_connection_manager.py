from logging import Logger
from traceback import format_exc

from fastapi import WebSocket


class WebSocketConnectionManager:
    '''WebSocket 连接管理器'''

    def __init__(self, logger: Logger | None = None):
        self._logger = logger
        self._notification_connections: dict[str, set[WebSocket]] = {}
        self._chat_connections: dict[str, set[WebSocket]] = {}

    # 功能相关
    def connect_chat(self, thread_id: str, websocket: WebSocket):
        if thread_id not in self._chat_connections:
            self._chat_connections[thread_id] = set()
        self._chat_connections[thread_id].add(websocket)

    def disconnect_chat(self, thread_id: str, websocket: WebSocket):
        if thread_id in self._chat_connections and websocket in self._chat_connections[thread_id]:
            self._chat_connections[thread_id].remove(websocket)
            if not self._chat_connections[thread_id]:
                del self._chat_connections[thread_id]

    def connect_notification(self, user_id: str, websocket: WebSocket):
        if user_id not in self._notification_connections:
            self._notification_connections[user_id] = set()
        self._notification_connections[user_id].add(websocket)

    def disconnect_notification(self, user_id: str, websocket: WebSocket):
        if user_id in self._notification_connections and websocket in self._notification_connections[user_id]:
            self._notification_connections[user_id].remove(websocket)
            if not self._notification_connections[user_id]:
                del self._notification_connections[user_id]

    async def broadcast_chat(self, thread_id: str, message: dict):
        '''广播对话'''

        if thread_id not in self._chat_connections:
            return

        for connection in list(self._chat_connections[thread_id]):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect_chat(thread_id, connection)
                if self._logger:
                    self._logger.critical(f'<broadcast> 广播对话报错！！！\n{format_exc()}')

    async def broadcast_notification(self, user_id: str, message: dict):
        '''广播通知'''

        if user_id not in self._notification_connections:
            return

        for connection in list(self._notification_connections[user_id]):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect_notification(user_id, connection)
                if self._logger:
                    self._logger.critical(f'<broadcast> 广播通知报错！！！\n{format_exc()}')
