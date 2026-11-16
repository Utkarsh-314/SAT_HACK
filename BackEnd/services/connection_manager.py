
import asyncio


class ConnectionManager:

    def __init__(self):
        self.rooms = {}
        self.lock = asyncio.Lock()

    async def connect(self, meeting_code, user_id, websocket):

        async with self.lock:

            room = self.rooms.setdefault(meeting_code, {})

            if user_id in room:
                return False, []

            if len(room) >= 2:
                return False, []

            existing_connections = list(room.values())

            room[user_id] = websocket

            return True, existing_connections

    async def disconnect(self, meeting_code, user_id):

        async with self.lock:

            room = self.rooms.get(meeting_code)

            if not room:
                return []

            room.pop(user_id, None)

            remaining = list(room.values())

            if not room:
                self.rooms.pop(meeting_code, None)

            return remaining

    async def send_to_connection(self, websocket, message):

        try:
            await websocket.send_json(message)
        except Exception:
            pass

    async def broadcast_except(
        self,
        meeting_code,
        sender_id,
        message
    ):

        async with self.lock:

            room = self.rooms.get(meeting_code, {})

            recipients = [
                connection
                for user_id, connection in room.items()
                if user_id != sender_id
            ]

        for connection in recipients:

            await self.send_to_connection(
                connection,
                message
            )


manager = ConnectionManager()
