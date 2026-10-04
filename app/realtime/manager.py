"""Realtime hub: employees stream GPS via WS; admins subscribe for live map."""
from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.admins: set[WebSocket] = set()
        self.last_pos: dict[int, dict] = {}  # user_id -> payload

    async def join_admin(self, ws: WebSocket):
        await ws.accept()
        self.admins.add(ws)

    def leave_admin(self, ws: WebSocket):
        self.admins.discard(ws)

    async def broadcast(self, payload: dict):
        uid = payload.get("user_id")
        if uid is not None:
            self.last_pos[int(uid)] = payload
        dead = []
        for ws in list(self.admins):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.admins.discard(ws)


hub = Hub()
