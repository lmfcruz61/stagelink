import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ChatMessage, LiveStream


class StreamChatConsumer(AsyncWebsocketConsumer):
    stream_viewers = {}

    async def connect(self):
        self.stream_id = self.scope['url_route']['kwargs']['stream_id']
        self.room_group_name = f'stream_{self.stream_id}_chat'

        # O acesso ao chat é validado no handshake do WebSocket.
        has_access = await self.user_has_access()
        if not has_access:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        self.stream_viewers.setdefault(self.stream_id, set()).add(self.channel_name)
        await self.broadcast_viewer_count()

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            viewers = self.stream_viewers.get(self.stream_id, set())
            viewers.discard(self.channel_name)
            if not viewers:
                self.stream_viewers.pop(self.stream_id, None)
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            await self.broadcast_viewer_count()

    async def receive(self, text_data):
        payload = json.loads(text_data)
        message = payload.get('message', '').strip()
        if not message:
            return

        saved = await self.save_message(message)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'username': saved['username'],
                'message': saved['message'],
                'timestamp': saved['timestamp'],
            },
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def viewer_count(self, event):
        await self.send(text_data=json.dumps(event))

    async def broadcast_viewer_count(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'viewer_count',
                'count': len(self.stream_viewers.get(self.stream_id, set())),
            },
        )

    @database_sync_to_async
    def user_has_access(self):
        user = self.scope['user']
        try:
            stream = LiveStream.objects.select_related('artist__user').get(pk=self.stream_id)
        except LiveStream.DoesNotExist:
            return False
        return stream.log_access_decision(user, 'websocket_connect')['allowed']

    @database_sync_to_async
    def save_message(self, message):
        chat_message = ChatMessage.objects.create(
            user=self.scope['user'],
            stream_id=self.stream_id,
            message=message[:600],
        )
        return {
            'username': chat_message.user.username,
            'message': chat_message.message,
            'timestamp': chat_message.timestamp.isoformat(),
        }
