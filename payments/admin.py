from django.contrib import admin

from .models import PhotoGalleryPurchase, StreamTicketPurchase, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('fan', 'artist', 'tier', 'status', 'commission_percent', 'stripe_connected_account_id', 'current_period_end', 'created_at')
    list_filter = ('tier', 'status', 'artist')
    search_fields = ('fan__display_name', 'fan__user__username', 'artist__name', 'stripe_connected_account_id')


@admin.register(StreamTicketPurchase)
class StreamTicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ('fan', 'stream', 'amount', 'platform_fee_amount', 'artist_net_amount', 'paid', 'created_at')
    list_filter = ('paid', 'stream__artist')
    search_fields = ('fan__display_name', 'fan__user__username', 'stream__title', 'stripe_session_id', 'stripe_connected_account_id')


@admin.register(PhotoGalleryPurchase)
class PhotoGalleryPurchaseAdmin(admin.ModelAdmin):
    list_display = ('fan', 'gallery', 'amount', 'platform_fee_amount', 'artist_net_amount', 'paid', 'created_at')
    list_filter = ('paid', 'gallery__artist')
    search_fields = ('fan__display_name', 'fan__user__username', 'gallery__title', 'stripe_session_id', 'stripe_connected_account_id')
