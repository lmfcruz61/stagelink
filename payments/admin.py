from django.contrib import admin

from .models import StreamTicketPurchase, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('fan', 'artist', 'tier', 'status', 'current_period_end', 'created_at')
    list_filter = ('tier', 'status', 'artist')
    search_fields = ('fan__display_name', 'fan__user__username', 'artist__name')


admin.site.register(StreamTicketPurchase)
