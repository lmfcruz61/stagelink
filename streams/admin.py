from django.contrib import admin

from .models import ChatMessage, LiveStream, Tip

admin.site.register(LiveStream)
admin.site.register(Tip)
admin.site.register(ChatMessage)
