from logging import Logger
from traceback import format_exc

from fastapi import WebSocket


class WebSocketConnectionManager:
    '''WebSocket 连接管理器'''

    def __init__(self, logger: Logger):
        self._logger = logger
        self._active_connections: list[WebSocket] = []  # 活跃的连接，实际仅有一个连接

    # 功能相关
    def connect(self, websocket: WebSocket):
        self._active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        '''广播'''

        for connection in self._active_connections[:]:
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)
                self._logger.critical(f'<broadcast> 广播报错！！！\n{format_exc()}')
