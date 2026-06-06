from django.contrib import admin

from .models import ChatMessage, LiveStream, Tip


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = ('title', 'artist', 'event_type', 'scheduled_at', 'access_price', 'is_active')
    list_filter = ('event_type', 'is_active', 'scheduled_at')
    search_fields = ('title', 'artist__name', 'youtube_video_id')


admin.site.register(Tip)
admin.site.register(ChatMessage)
