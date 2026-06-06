import logging

from django.conf import settings
from django.db import models
from django.utils import timezone
from urllib.parse import parse_qs, urlparse

from accounts.models import Artist

logger = logging.getLogger(__name__)


class LiveStream(models.Model):
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

    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='streams')
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to='streams/covers/', blank=True, null=True)
    youtube_video_id = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default=LIVE)
    access_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    scheduled_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f'{self.title} - {self.artist.name}'

    @property
    def is_past(self):
        return self.scheduled_at < timezone.now()

    @property
    def visual_state(self):
        now = timezone.now()
        if self.scheduled_at > now:
            return 'scheduled'
        return self.post_start_visual_state

    @property
    def post_start_visual_state(self):
        if self.event_type == self.REPLAY:
            return 'replay'
        if self.event_type == self.RECORDED:
            return 'recorded'
        if self.event_type == self.PREMIERE:
            return 'premiere'
        if self.event_type == self.LIVE and self.is_active:
            return 'live'
        return 'replay'

    @property
    def visual_label(self):
        labels = {
            'scheduled': 'Agendado',
            'live': 'Ao vivo',
            'premiere': 'Estreia',
            'recorded': 'Vídeo gravado',
            'replay': 'Replay disponível',
        }
        return labels[self.visual_state]

    @property
    def post_start_visual_label(self):
        labels = {
            'live': 'Ao vivo',
            'premiere': 'Estreia',
            'recorded': 'Vídeo gravado',
            'replay': 'Replay disponível',
        }
        return labels[self.post_start_visual_state]

    @property
    def visual_icon(self):
        icons = {
            'scheduled': '📅',
            'live': '🔴',
            'premiere': '▶',
            'recorded': '🎬',
            'replay': '📼',
        }
        return icons[self.visual_state]

    @property
    def post_start_visual_icon(self):
        icons = {
            'live': '🔴',
            'premiere': '▶',
            'recorded': '🎬',
            'replay': '📼',
        }
        return icons[self.post_start_visual_state]

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
            return {**base, 'allowed': True, 'reason': 'free_event'}

        from payments.models import StreamTicketPurchase, Subscription

        has_subscription = Subscription.objects.filter(
            fan__user=user,
            artist=self.artist,
            status=Subscription.ACTIVE,
            current_period_end__gte=timezone.now(),
        ).exists()
        if has_subscription:
            return {**base, 'allowed': True, 'reason': 'active_subscription'}

        has_paid_ticket = StreamTicketPurchase.objects.filter(
            fan__user=user,
            stream=self,
            paid=True,
        ).exclude(stripe_session_id='').exists()
        if has_paid_ticket:
            return {**base, 'allowed': True, 'reason': 'paid_ticket'}

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


class Tip(models.Model):
    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='tips')
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='tips')
    stream = models.ForeignKey(LiveStream, on_delete=models.CASCADE, related_name='tips')
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    message = models.CharField(max_length=240, blank=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)
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
