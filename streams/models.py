import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from urllib.parse import parse_qs, urlparse

from accounts.models import Artist, OrganizationMember

logger = logging.getLogger(__name__)


class LiveStream(models.Model):
    VIDEO_PROVIDER_CLOUDFLARE = 'cloudflare_stream'
    VIDEO_PROVIDER_CLOUDFLARE_WEBRTC = 'cloudflare_webrtc'
    VIDEO_PROVIDER_YOUTUBE = 'youtube'
    VIDEO_PROVIDER_CHOICES = (
        (VIDEO_PROVIDER_CLOUDFLARE, 'Video StageHub'),
        (VIDEO_PROVIDER_CLOUDFLARE_WEBRTC, 'Direto StageHub experimental'),
    )

    LIVE = 'live'
    PREMIERE = 'premiere'
    RECORDED = 'recorded'
    REPLAY = 'replay'
    EVENT_TYPE_CHOICES = (
        (LIVE, 'Ao vivo'),
        (PREMIERE, 'Estreia'),
        (RECORDED, 'Vídeo gravado'),
        (REPLAY, 'Replay'),
    )
    UPLOAD_NOT_REQUESTED = 'not_requested'
    UPLOAD_PENDING = 'pending'
    UPLOAD_UPLOADED = 'uploaded'
    UPLOAD_STATUS_CHOICES = (
        (UPLOAD_NOT_REQUESTED, 'Sem upload direto'),
        (UPLOAD_PENDING, 'Upload pendente'),
        (UPLOAD_UPLOADED, 'Upload enviado'),
    )

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='streams')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='streams/covers/', blank=True, null=True)
    video_provider = models.CharField(max_length=30, choices=VIDEO_PROVIDER_CHOICES, default=VIDEO_PROVIDER_CLOUDFLARE)
    cloudflare_video_uid = models.CharField(max_length=120, blank=True)
    cloudflare_live_input_uid = models.CharField(max_length=120, blank=True)
    cloudflare_playback_url = models.URLField(blank=True)
    cloudflare_upload_url = models.URLField(max_length=1000, blank=True)
    cloudflare_upload_expires_at = models.DateTimeField(blank=True, null=True)
    cloudflare_upload_status = models.CharField(
        max_length=20,
        choices=UPLOAD_STATUS_CHOICES,
        default=UPLOAD_NOT_REQUESTED,
    )
    uploaded_at = models.DateTimeField(blank=True, null=True)
    youtube_video_id = models.CharField(max_length=200, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default=LIVE)
    access_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Duração estimada em minutos (opcional)',
    )
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f'{self.title} - {self.artist.name}'

    @property
    def is_past(self):
        return self.scheduled_at < timezone.now()

    @property
    def is_publicly_available(self):
        return self.is_active or self.scheduled_at >= timezone.now()

    @property
    def visual_state(self):
        return self.display_status['code']

    @property
    def post_start_visual_state(self):
        return self.post_start_display_status['code']

    @property
    def visual_label(self):
        return self.display_status['label']

    @property
    def post_start_visual_label(self):
        return self.post_start_display_status['label']

    @property
    def visual_icon(self):
        return self.display_status['icon']

    @property
    def post_start_visual_icon(self):
        return self.post_start_display_status['icon']

    @property
    def display_status(self):
        if self.scheduled_at > timezone.now():
            return self._status_payload('scheduled')
        return self.post_start_display_status

    @property
    def post_start_display_status(self):
        if self.event_type == self.LIVE:
            if self.is_active:
                return self._status_payload('live')
            return self._status_payload('replay')
        if self.event_type == self.PREMIERE and self.is_active:
            return self._status_payload('live')
        if self.event_type == self.PREMIERE:
            return self._status_payload('premiere')
        if self.event_type == self.RECORDED:
            return self._status_payload('recorded')
        return self._status_payload('replay')

    def _status_payload(self, code):
        labels = {
            'scheduled': 'Agendado',
            'live': 'Ao vivo',
            'premiere': 'Estreia',
            'recorded': 'Vídeo gravado',
            'replay': 'Replay disponível',
        }
        icons = {
            'scheduled': '📅',
            'live': '🔴',
            'premiere': '▶',
            'recorded': '🎬',
            'replay': '📼',
        }
        return {
            'code': code,
            'icon': icons[code],
            'label': labels[code],
            'text': f'{icons[code]} {labels[code]}',
        }

    @property
    def youtube_embed_id(self):
        value = self.youtube_video_id.strip()
        parsed = urlparse(value)
        if parsed.netloc:
            if parsed.hostname and 'youtu.be' in parsed.hostname:
                return parsed.path.strip('/').split('/')[0]
            query_id = parse_qs(parsed.query).get('v')
            if query_id:
                return query_id[0]
            parts = [part for part in parsed.path.split('/') if part]
            for marker in ('embed', 'live', 'shorts'):
                if marker in parts:
                    index = parts.index(marker)
                    if len(parts) > index + 1:
                        return parts[index + 1]
        return value

    @property
    def uses_youtube(self):
        return self.video_provider == self.VIDEO_PROVIDER_YOUTUBE

    @property
    def uses_cloudflare(self):
        return self.video_provider in {
            self.VIDEO_PROVIDER_CLOUDFLARE,
            self.VIDEO_PROVIDER_CLOUDFLARE_WEBRTC,
        }

    @property
    def is_recorded_video(self):
        return self.event_type == self.RECORDED

    @property
    def has_pending_direct_upload(self):
        return (
            self.is_recorded_video
            and self.cloudflare_upload_status == self.UPLOAD_PENDING
            and bool(self.cloudflare_upload_url)
        )

    @property
    def cloudflare_identifier(self):
        if self.event_type in {self.LIVE, self.PREMIERE}:
            value = self.cloudflare_live_input_uid or self.cloudflare_video_uid
        else:
            value = self.cloudflare_video_uid or self.cloudflare_live_input_uid
        return self.extract_cloudflare_identifier(value)

    @property
    def cloudflare_embed_url(self):
        params = 'autoplay=true&lowLatency=true&preload=true'
        if self.cloudflare_playback_url:
            normalized_url = self.normalize_cloudflare_embed_url(self.cloudflare_playback_url, params)
            if normalized_url:
                return normalized_url
            return self.add_cloudflare_player_params(self.cloudflare_playback_url, params)
        host = self.cloudflare_stream_host
        identifier = self.cloudflare_identifier
        if not host or not identifier:
            return ''
        return f'https://{host}/{identifier}/iframe?{params}'

    @classmethod
    def extract_cloudflare_identifier(cls, value):
        value = (value or '').strip()
        if not value:
            return ''
        parsed = urlparse(value if '://' in value else f'https://{value}')
        if parsed.scheme in {'rtmp', 'rtmps'}:
            return ''
        parts = [part for part in parsed.path.split('/') if part]
        if parsed.netloc and parts:
            return parts[0]
        return value

    @classmethod
    def add_cloudflare_player_params(cls, url, params):
        base = (url or '').strip().rstrip('?&')
        separator = '&' if '?' in base else '?'
        return f'{base}{separator}{params}'

    @classmethod
    def normalize_cloudflare_embed_url(cls, value, params):
        value = (value or '').strip()
        if not value:
            return ''
        parsed = urlparse(value if '://' in value else f'https://{value}')
        host = (parsed.netloc or '').strip()
        if not host or 'cloudflarestream.com' not in host:
            return ''
        identifier = cls.extract_cloudflare_identifier(value)
        if not identifier:
            return ''
        return f'https://{host}/{identifier}/iframe?{params}'

    @property
    def cloudflare_stream_host(self):
        value = getattr(settings, 'CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN', '').strip().strip('/')
        if not value:
            return ''
        parsed = urlparse(value if '://' in value else f'https://{value}')
        host = (parsed.netloc or parsed.path).split('/')[0].strip()
        if not host:
            return ''
        if host.endswith('.cloudflarestream.com'):
            return host
        return f'{host}.cloudflarestream.com'

    @property
    def is_recent_recorded_content(self):
        archive_start = timezone.now() - timedelta(days=30)
        return (
            self.event_type in {self.PREMIERE, self.RECORDED, self.REPLAY}
            and self.scheduled_at <= timezone.now()
            and self.scheduled_at >= archive_start
        )

    def active_subscription_for_user(self, user):
        if not user.is_authenticated:
            return None
        from payments.models import Subscription

        return Subscription.objects.filter(
            fan__user=user,
            artist=self.artist,
            status=Subscription.ACTIVE,
            current_period_end__gte=timezone.now(),
        ).first()

    def user_can_chat(self, user):
        decision = self.access_decision(user)
        if decision['allowed']:
            return True
        subscription = self.active_subscription_for_user(user)
        return bool(subscription and self.event_type == self.LIVE and self.is_active)

    def access_decision(self, user):
        # Centraliza a regra de acesso usada pelas views e pelo WebSocket.
        base = {
            'user_id': getattr(user, 'id', None),
            'stream_id': self.id,
            'access_price': str(self.access_price),
        }
        if not user.is_authenticated:
            return {**base, 'allowed': False, 'reason': 'anonymous'}
        if user.is_staff or user.is_superuser:
            return {**base, 'allowed': True, 'reason': 'staff_or_superuser'}
        if self.artist.user_id == user.id:
            return {**base, 'allowed': True, 'reason': 'artist_owner'}
        if self.artist.organization_id:
            from accounts.models import OrganizationMember

            if OrganizationMember.objects.filter(
                organization=self.artist.organization,
                user=user,
                role__in=OrganizationMember.EDIT_ROLES,
            ).exists():
                return {**base, 'allowed': True, 'reason': 'organization_manager'}

        if self.access_price <= 0:
            return {**base, 'allowed': False, 'reason': 'free_events_disabled'}

        from payments.models import StreamTicketPurchase

        active_subscription = self.active_subscription_for_user(user)

        has_paid_ticket = StreamTicketPurchase.objects.filter(
            fan__user=user,
            stream=self,
            paid=True,
        ).exclude(stripe_session_id='').exists()
        if has_paid_ticket:
            return {**base, 'allowed': True, 'reason': 'paid_ticket'}

        if active_subscription and self.is_recent_recorded_content:
            return {**base, 'allowed': True, 'reason': 'subscription_recent_archive'}

        if active_subscription and self.event_type == self.LIVE and self.is_active:
            return {**base, 'allowed': False, 'reason': 'subscription_chat_only_live'}

        has_stale_free_ticket = StreamTicketPurchase.objects.filter(
            fan__user=user,
            stream=self,
            paid=True,
            stripe_session_id='',
        ).exists()
        if has_stale_free_ticket:
            return {**base, 'allowed': False, 'reason': 'stale_free_ticket_on_paid_event'}

        return {**base, 'allowed': False, 'reason': 'missing_paid_access'}

    def log_access_decision(self, user, source):
        decision = self.access_decision(user)
        logger.info(
            'StageLink access check source=%s user_id=%s stream_id=%s access_price=%s allowed=%s reason=%s',
            source,
            decision['user_id'],
            decision['stream_id'],
            decision['access_price'],
            decision['allowed'],
            decision['reason'],
        )
        return decision

    def user_has_access(self, user):
        return self.access_decision(user)['allowed']


class PhotoGallery(models.Model):
    DRAFT = 'draft'
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    SUSPENDED = 'suspended'
    MODERATION_CHOICES = (
        (DRAFT, 'Rascunho'),
        (PENDING, 'Pendente de validacao'),
        (APPROVED, 'Aprovada'),
        (REJECTED, 'Rejeitada'),
        (SUSPENDED, 'Suspensa'),
    )
    MIN_PRICE = Decimal('2.00')
    MAX_IMAGES = 30

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='photo_galleries')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    public_cover = models.ImageField(upload_to='photo_galleries/covers/')
    access_price = models.DecimalField(max_digits=8, decimal_places=2, default=MIN_PRICE)
    is_active = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)
    moderation_status = models.CharField(max_length=20, choices=MODERATION_CHOICES, default=DRAFT)
    rejection_reason = models.TextField(blank=True)
    internal_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_photo_galleries',
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} - {self.artist.name}'

    @property
    def is_publicly_available(self):
        return self.is_active and self.moderation_status == self.APPROVED and self.access_price >= self.MIN_PRICE

    @property
    def image_count(self):
        return self.images.count()

    def user_has_access(self, user):
        if not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if self.artist.user_id == user.id:
            return True
        if self.artist.organization_id:
            if self.artist.organization.members.filter(user=user, role__in=OrganizationMember.EDIT_ROLES).exists():
                return True
        fan = getattr(user, 'fan_profile', None)
        if not fan:
            return False
        return self.purchases.filter(fan=fan, paid=True).exists()


class PhotoGalleryImage(models.Model):
    gallery = models.ForeignKey(PhotoGallery, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='photo_galleries/private/')
    caption = models.CharField(max_length=140, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'id']

    def __str__(self):
        return f'Foto de {self.gallery.title}'


class Tip(models.Model):
    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='tips')
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='tips')
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name='tips')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    platform_fee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    artist_net_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    message = models.CharField(max_length=240, blank=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)
    stripe_connected_account_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.amount} EUR para {self.artist.name}'


class ChatMessage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name='chat_messages')
    message = models.TextField(max_length=600)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'{self.user.username}: {self.message[:40]}'
