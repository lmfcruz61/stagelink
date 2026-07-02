import re

from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import Artist

from .cloudflare import (
    CloudflareStreamError,
    delete_stream_live_input,
    delete_stream_video,
    get_stream_live_input,
    get_stream_video,
    list_stream_live_inputs,
    list_stream_videos,
)
from .models import ChatMessage, LiveStream, MediaDeletionLog, PhotoGallery, PhotoGalleryImage, Tip

admin.site.index_template = 'admin/stagehub_index.html'


VALID_CLOUDFLARE_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def cloudflare_thumbnail_url(cloudflare_id):
    return f'https://videodelivery.net/{cloudflare_id}/thumbnails/thumbnail.jpg?time=1s&height=120'


def item_matches_query(item, query):
    if not query:
        return True
    haystack = ' '.join(str(item.get(key, '')) for key in ('name', 'owner', 'event', 'cloudflare_id'))
    return query.lower() in haystack.lower()


def item_matches_filters(item, media_type, user_id, event_id, date_from=None, date_to=None):
    if media_type and item['media_type'] != media_type:
        return False
    if user_id and str(item.get('user_id') or '') != str(user_id):
        return False
    if event_id and str(item.get('event_id') or '') != str(event_id):
        return False
    item_date = item.get('date_for_filter')
    if date_from and item_date and item_date.date() < date_from:
        return False
    if date_to and item_date and item_date.date() > date_to:
        return False
    return True


def remote_video_details(cloudflare_id):
    try:
        return get_stream_video(cloudflare_id), ''
    except CloudflareStreamError as error:
        return {}, str(error)


def remote_live_input_details(cloudflare_id):
    try:
        return get_stream_live_input(cloudflare_id), ''
    except CloudflareStreamError as error:
        return {}, str(error)


def build_cloudflare_media_items(include_remote_details=False):
    items = []
    seen = set()

    def add_item(item):
        key = (item['media_type'], item['cloudflare_id'], item.get('source'))
        if not item['cloudflare_id'] or key in seen:
            return
        seen.add(key)
        items.append(item)

    streams = LiveStream.objects.select_related('artist__user').exclude(cloudflare_video_uid='').order_by('-scheduled_at')
    for stream in streams:
        details, error = ({}, '')
        if include_remote_details:
            details, error = remote_video_details(stream.cloudflare_video_uid)
        add_item({
            'key': f'video:stream:{stream.id}:{stream.cloudflare_video_uid}',
            'media_type': 'video',
            'type_label': 'Video',
            'name': stream.title,
            'owner': stream.artist.name,
            'user_id': stream.artist.user_id,
            'event': stream.title,
            'event_id': stream.id,
            'url': stream.cloudflare_embed_url,
            'cloudflare_id': stream.cloudflare_video_uid,
            'source': 'stream_video',
            'object_id': stream.id,
            'thumbnail_url': cloudflare_thumbnail_url(stream.cloudflare_video_uid),
            'size': details.get('size') or details.get('sizeBytes') or '',
            'uploaded_at': details.get('created') or details.get('uploaded') or stream.uploaded_at or '',
            'date_for_filter': stream.uploaded_at or stream.scheduled_at,
            'remote_error': error,
        })

    live_streams = LiveStream.objects.select_related('artist__user').exclude(cloudflare_live_input_uid='').order_by('-scheduled_at')
    for stream in live_streams:
        live_input_id = LiveStream.extract_cloudflare_identifier(stream.cloudflare_live_input_uid)
        details, error = ({}, '')
        if include_remote_details:
            details, error = remote_live_input_details(live_input_id)
        add_item({
            'key': f'live_input:stream:{stream.id}:{live_input_id}',
            'media_type': 'live_input',
            'type_label': 'Canal ao vivo',
            'name': f'Canal ao vivo - {stream.title}',
            'owner': stream.artist.name,
            'user_id': stream.artist.user_id,
            'event': stream.title,
            'event_id': stream.id,
            'url': stream.cloudflare_embed_url,
            'cloudflare_id': live_input_id,
            'source': 'stream_live_input',
            'object_id': stream.id,
            'thumbnail_url': '',
            'size': '',
            'uploaded_at': details.get('created') or '',
            'date_for_filter': stream.scheduled_at,
            'remote_error': error,
        })

    artists = Artist.objects.select_related('user').exclude(cloudflare_live_input_uid='').order_by('name')
    for artist in artists:
        live_input_id = LiveStream.extract_cloudflare_identifier(artist.cloudflare_live_input_uid)
        details, error = ({}, '')
        if include_remote_details:
            details, error = remote_live_input_details(live_input_id)
        add_item({
            'key': f'live_input:artist:{artist.id}:{live_input_id}',
            'media_type': 'live_input',
            'type_label': 'Canal ao vivo',
            'name': f'Canal ao vivo - {artist.name}',
            'owner': artist.name,
            'user_id': artist.user_id,
            'event': '',
            'event_id': '',
            'url': '',
            'cloudflare_id': live_input_id,
            'source': 'artist_live_input',
            'object_id': artist.id,
            'thumbnail_url': '',
            'size': '',
            'uploaded_at': details.get('created') or '',
            'date_for_filter': None,
            'remote_error': error,
        })

    return items


def log_media_deletion(admin_user, item, action, status, details=''):
    MediaDeletionLog.objects.create(
        admin_user=admin_user,
        file_name=item.get('name', ''),
        cloudflare_id=item.get('cloudflare_id', ''),
        action=action,
        status=status,
        details=details,
    )


def clear_cloudflare_references(item):
    cloudflare_id = item['cloudflare_id']
    source = item.get('source')
    if source == 'stream_video':
        LiveStream.objects.filter(pk=item['object_id']).update(
            cloudflare_video_uid='',
            cloudflare_upload_url='',
            cloudflare_upload_status=LiveStream.UPLOAD_NOT_REQUESTED,
            uploaded_at=None,
        )
    elif source == 'stream_live_input':
        LiveStream.objects.filter(pk=item['object_id']).update(cloudflare_live_input_uid='')
    elif source == 'artist_live_input':
        Artist.objects.filter(pk=item['object_id']).update(
            cloudflare_live_input_uid='',
            cloudflare_rtmps_url='',
            cloudflare_stream_key='',
        )
    LiveStream.objects.filter(cloudflare_playback_url__icontains=cloudflare_id).update(cloudflare_playback_url='')


def delete_cloudflare_item(admin_user, item, action=MediaDeletionLog.ACTION_DELETE_ONE):
    if not VALID_CLOUDFLARE_ID_RE.match(item.get('cloudflare_id', '')):
        log_media_deletion(admin_user, item, action, MediaDeletionLog.STATUS_FAILED, 'ID Cloudflare invalido.')
        return False, 'ID Cloudflare invalido.'

    try:
        if item['media_type'] == 'video':
            delete_stream_video(item['cloudflare_id'])
        elif item['media_type'] == 'live_input':
            delete_stream_live_input(item['cloudflare_id'])
        else:
            raise CloudflareStreamError('Tipo de media Cloudflare nao suportado.')
    except CloudflareStreamError as error:
        log_media_deletion(admin_user, item, action, MediaDeletionLog.STATUS_FAILED, str(error))
        return False, str(error)

    clear_cloudflare_references(item)
    log_media_deletion(admin_user, item, action, MediaDeletionLog.STATUS_SUCCESS)
    return True, ''


def cloudflare_media_admin_view(request):
    query = request.GET.get('q', '').strip()
    media_type = request.GET.get('type', '').strip()
    user_id = request.GET.get('user', '').strip()
    event_id = request.GET.get('event', '').strip()
    date_from = parse_date(request.GET.get('date_from', '').strip())
    date_to = parse_date(request.GET.get('date_to', '').strip())
    include_remote_details = request.GET.get('remote') == '1'

    items = build_cloudflare_media_items(include_remote_details=include_remote_details)
    item_map = {item['key']: item for item in items}

    if request.method == 'POST':
        action = request.POST.get('action')
        delete_one_key = request.POST.get('delete_one_key', '')
        if delete_one_key:
            action = 'delete_one'
        confirm = request.POST.get('confirm') == 'APAGAR'
        if not confirm:
            messages.error(request, 'Escreve APAGAR para confirmar a eliminacao.')
        elif action == 'delete_one':
            item = item_map.get(delete_one_key)
            if item and delete_cloudflare_item(request.user, item, MediaDeletionLog.ACTION_DELETE_ONE)[0]:
                messages.success(request, 'Ficheiro apagado da Cloudflare.')
            else:
                messages.error(request, 'Nao foi possivel apagar o ficheiro selecionado.')
        elif action == 'delete_selected':
            selected_keys = request.POST.getlist('selected')
            deleted = 0
            for key in selected_keys:
                item = item_map.get(key)
                if item and delete_cloudflare_item(request.user, item, MediaDeletionLog.ACTION_DELETE_SELECTED)[0]:
                    deleted += 1
            messages.success(request, f'{deleted} ficheiro(s) apagado(s) da Cloudflare.')
        elif action == 'delete_user':
            target_user = request.POST.get('target_user', '').strip()
            deleted = 0
            if not target_user:
                messages.error(request, 'Escolhe um utilizador antes de apagar ficheiros por utilizador.')
            else:
                for item in items:
                    if str(item.get('user_id') or '') == target_user and delete_cloudflare_item(request.user, item, MediaDeletionLog.ACTION_DELETE_USER)[0]:
                        deleted += 1
                messages.success(request, f'{deleted} ficheiro(s) do utilizador apagado(s).')
        elif action == 'delete_event':
            target_event = request.POST.get('target_event', '').strip()
            deleted = 0
            if not target_event:
                messages.error(request, 'Escolhe um evento antes de apagar ficheiros por evento.')
            else:
                for item in items:
                    if str(item.get('event_id') or '') == target_event and delete_cloudflare_item(request.user, item, MediaDeletionLog.ACTION_DELETE_EVENT)[0]:
                        deleted += 1
                messages.success(request, f'{deleted} ficheiro(s) do evento apagado(s).')
        elif action == 'delete_orphans':
            referenced_video_ids = {item['cloudflare_id'] for item in items if item['media_type'] == 'video'}
            referenced_live_input_ids = {item['cloudflare_id'] for item in items if item['media_type'] == 'live_input'}
            deleted = 0
            try:
                remote_videos = list_stream_videos()
                remote_live_inputs = list_stream_live_inputs()
            except CloudflareStreamError as error:
                messages.error(request, str(error))
            else:
                for remote_video in remote_videos:
                    remote_id = remote_video.get('uid') or remote_video.get('id')
                    if remote_id and remote_id not in referenced_video_ids:
                        orphan_item = {
                            'name': remote_video.get('meta', {}).get('name') or remote_video.get('filename') or 'Video orfao',
                            'media_type': 'video',
                            'cloudflare_id': remote_id,
                            'source': 'orphan_video',
                        }
                        if delete_cloudflare_item(request.user, orphan_item, MediaDeletionLog.ACTION_DELETE_ORPHAN)[0]:
                            deleted += 1
                for remote_live_input in remote_live_inputs:
                    remote_id = remote_live_input.get('uid') or remote_live_input.get('id')
                    if remote_id and remote_id not in referenced_live_input_ids:
                        orphan_item = {
                            'name': remote_live_input.get('meta', {}).get('name') or 'Canal ao vivo orfao',
                            'media_type': 'live_input',
                            'cloudflare_id': remote_id,
                            'source': 'orphan_live_input',
                        }
                        if delete_cloudflare_item(request.user, orphan_item, MediaDeletionLog.ACTION_DELETE_ORPHAN)[0]:
                            deleted += 1
                messages.success(request, f'{deleted} ficheiro(s) orfao(s) apagado(s).')
        elif action == 'delete_removed':
            removed_event_ids = set(
                LiveStream.objects.filter(is_active=False).values_list('id', flat=True)
            )
            deleted = 0
            for item in items:
                if item.get('event_id') in removed_event_ids and delete_cloudflare_item(request.user, item, MediaDeletionLog.ACTION_DELETE_REMOVED)[0]:
                    deleted += 1
            messages.success(request, f'{deleted} ficheiro(s) de eventos inativos/removidos apagado(s).')
        else:
            messages.error(request, 'Acao desconhecida.')
        return HttpResponseRedirect(request.get_full_path())

    filtered_items = [
        item for item in items
        if item_matches_query(item, query) and item_matches_filters(item, media_type, user_id, event_id, date_from, date_to)
    ]

    context = {
        **admin.site.each_context(request),
        'title': 'Media Cloudflare',
        'items': filtered_items,
        'query': query,
        'media_type': media_type,
        'user_id': user_id,
        'event_id': event_id,
        'date_from': request.GET.get('date_from', '').strip(),
        'date_to': request.GET.get('date_to', '').strip(),
        'include_remote_details': include_remote_details,
        'users': Artist.objects.exclude(user=None).select_related('user').order_by('name'),
        'events': LiveStream.objects.select_related('artist').order_by('-scheduled_at')[:200],
        'service_summary': 'Este projeto usa Cloudflare Stream para videos e canais ao vivo. As fotos estao no storage local da StageHub/Fly.',
        'deletion_logs_url': reverse('admin:streams_mediadeletionlog_changelist'),
    }
    return TemplateResponse(request, 'admin/cloudflare_media.html', context)


original_admin_get_urls = admin.site.get_urls


def stagehub_admin_get_urls():
    urls = original_admin_get_urls()
    custom_urls = [
        path('media-cloudflare/', admin.site.admin_view(cloudflare_media_admin_view), name='cloudflare_media'),
    ]
    return custom_urls + urls


admin.site.get_urls = stagehub_admin_get_urls


@admin.register(LiveStream)
class LiveStreamAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'artist',
        'video_provider',
        'event_type',
        'access_type',
        'cloudflare_upload_status',
        'scheduled_at',
        'access_price',
        'is_active',
    )
    list_filter = ('access_type', 'video_provider', 'event_type', 'cloudflare_upload_status', 'is_active', 'scheduled_at')
    search_fields = ('title', 'artist__name', 'cloudflare_video_uid', 'cloudflare_live_input_uid', 'youtube_video_id')


@admin.register(Tip)
class TipAdmin(admin.ModelAdmin):
    list_display = ('fan', 'artist', 'stream', 'amount', 'platform_fee_amount', 'artist_net_amount', 'stripe_livemode', 'created_at')
    list_filter = ('artist', 'stream', 'stripe_livemode')
    search_fields = ('fan__display_name', 'fan__user__username', 'artist__name', 'stream__title', 'stripe_payment_intent')


@admin.register(MediaDeletionLog)
class MediaDeletionLogAdmin(admin.ModelAdmin):
    list_display = ('cloudflare_id', 'file_name', 'action', 'status', 'admin_user', 'created_at')
    list_filter = ('action', 'status', 'created_at')
    search_fields = ('cloudflare_id', 'file_name', 'details', 'admin_user__username')
    readonly_fields = ('admin_user', 'file_name', 'cloudflare_id', 'action', 'status', 'details', 'created_at')
    ordering = ('-created_at',)


admin.site.register(ChatMessage)


class PhotoGalleryImageInline(admin.TabularInline):
    model = PhotoGalleryImage
    extra = 0


@admin.register(PhotoGallery)
class PhotoGalleryAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'artist',
        'access_type',
        'access_price',
        'image_total',
        'moderation_status',
        'is_sensitive',
        'is_active',
        'created_at',
    )
    list_filter = ('access_type', 'moderation_status', 'is_sensitive', 'is_active', 'created_at')
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
