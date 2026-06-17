from django.contrib import admin
from django.utils import timezone

from .models import ChatMessage, LiveStream, PhotoGallery, PhotoGalleryImage, Tip


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


class PhotoGalleryImageInline(admin.TabularInline):
    model = PhotoGalleryImage
    extra = 0


@admin.register(PhotoGallery)
class PhotoGalleryAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'artist',
        'access_price',
        'moderation_status',
        'is_sensitive',
        'is_active',
        'created_at',
    )
    list_filter = ('moderation_status', 'is_sensitive', 'is_active', 'created_at')
    search_fields = ('title', 'artist__name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')
    inlines = (PhotoGalleryImageInline,)
    actions = ('approve_galleries', 'reject_galleries', 'suspend_galleries')

    @admin.action(description='Aprovar galerias selecionadas')
    def approve_galleries(self, request, queryset):
        queryset.update(moderation_status=PhotoGallery.APPROVED, reviewed_by_id=request.user.id, reviewed_at=timezone.now())

    @admin.action(description='Rejeitar galerias selecionadas')
    def reject_galleries(self, request, queryset):
        queryset.update(moderation_status=PhotoGallery.REJECTED, reviewed_by_id=request.user.id, reviewed_at=timezone.now())

    @admin.action(description='Suspender galerias selecionadas')
    def suspend_galleries(self, request, queryset):
        queryset.update(moderation_status=PhotoGallery.SUSPENDED, reviewed_by_id=request.user.id, reviewed_at=timezone.now())
