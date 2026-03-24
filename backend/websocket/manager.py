import json
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = {}
        # {table_id: {session_id: websocket}}

    async def connect(self, table_id: str, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if table_id not in self._connections:
            self._connections[table_id] = {}
        self._connections[table_id][session_id] = websocket

    def disconnect(self, table_id: str, session_id: str) -> None:
        if table_id in self._connections:
            self._connections[table_id].pop(session_id, None)
            if not self._connections[table_id]:
                del self._connections[table_id]

    async def broadcast(self, table_id: str, message: dict) -> None:
        if table_id not in self._connections:
            return
        data = json.dumps(message)
        dead: list[str] = []
        for session_id, ws in self._connections[table_id].items():
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(session_id)
        for s in dead:
            self.disconnect(table_id, s)

    async def send_personal(self, table_id: str, session_id: str, message: dict) -> None:
        ws = self._connections.get(table_id, {}).get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(table_id, session_id)

    def get_connected_sessions(self, table_id: str) -> list[str]:
        return list(self._connections.get(table_id, {}).keys())

    def is_connected(self, table_id: str, session_id: str) -> bool:
        return session_id in self._connections.get(table_id, {})


manager = ConnectionManager()
