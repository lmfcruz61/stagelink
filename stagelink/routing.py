from django.urls import path

from streams.consumers import StreamChatConsumer

websocket_urlpatterns = [
    path('ws/streams/<int:stream_id>/chat/', StreamChatConsumer.as_asgi()),
]
