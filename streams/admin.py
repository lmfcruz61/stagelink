from django.contrib import admin

from .models import ChatMessage, LiveStream, Tip


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'artist',
        'video_provider',
        'event_type',
        'cloudflare_upload_status',
        'scheduled_at',
        'access_price',
        'is_active',
    )
    list_filter = ('video_provider', 'event_type', 'cloudflare_upload_status', 'is_active', 'scheduled_at')
    search_fields = ('title', 'artist__name', 'cloudflare_video_uid', 'cloudflare_live_input_uid', 'youtube_video_id')


@admin.register(Tip)
class TipAdmin(admin.ModelAdmin):
    list_display = ('fan', 'artist', 'stream', 'amount', 'platform_fee_amount', 'artist_net_amount', 'created_at')
    list_filter = ('artist', 'stream')
    search_fields = ('fan__display_name', 'fan__user__username', 'artist__name', 'stream__title', 'stripe_payment_intent')


admin.site.register(ChatMessage)
