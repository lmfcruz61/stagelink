from django.contrib import admin
from django.db.models import Count
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
    list_display = ('fan', 'artist', 'stream', 'amount', 'platform_fee_amount', 'artist_net_amount', 'stripe_livemode', 'created_at')
    list_filter = ('artist', 'stream', 'stripe_livemode')
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
        'image_total',
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

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(image_total_count=Count('images'))

    @admin.display(description='Fotos', ordering='image_total_count')
    def image_total(self, obj):
        return obj.image_total_count

    def changelist_view(self, request, extra_context=None):
        pending_count = self.model.objects.filter(moderation_status=PhotoGallery.PENDING).count()
        extra_context = extra_context or {}
        extra_context['title'] = f'Galerias de fotos - {pending_count} pendente(s) de validacao'
        return super().changelist_view(request, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        if obj.moderation_status == PhotoGallery.APPROVED:
            obj.is_active = True
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        elif obj.moderation_status in {PhotoGallery.REJECTED, PhotoGallery.SUSPENDED}:
            obj.is_active = False
            obj.reviewed_by = request.user
            obj.reviewed_at = timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description='Aprovar galerias selecionadas')
    def approve_galleries(self, request, queryset):
        queryset.update(
            moderation_status=PhotoGallery.APPROVED,
            is_active=True,
            reviewed_by_id=request.user.id,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Rejeitar galerias selecionadas')
    def reject_galleries(self, request, queryset):
        queryset.update(
            moderation_status=PhotoGallery.REJECTED,
            is_active=False,
            reviewed_by_id=request.user.id,
            reviewed_at=timezone.now(),
        )

    @admin.action(description='Suspender galerias selecionadas')
    def suspend_galleries(self, request, queryset):
        queryset.update(
            moderation_status=PhotoGallery.SUSPENDED,
            is_active=False,
            reviewed_by_id=request.user.id,
            reviewed_at=timezone.now(),
        )
