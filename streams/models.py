from django.conf import settings
from django.db import models
from django.utils import timezone
from urllib.parse import parse_qs, urlparse

from accounts.models import Artist


class LiveStream(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='streams')
    title = models.CharField(max_length=180)
    cover_image = models.ImageField(upload_to='streams/covers/', blank=True, null=True)
    youtube_video_id = models.CharField(max_length=200)
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

    def user_has_access(self, user):
        # Centraliza a regra de acesso usada pelas views e pelo WebSocket.
        if not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        if self.artist.user_id == user.id:
            return True
        if self.artist.organization_id:
            from accounts.models import OrganizationMember

            if OrganizationMember.objects.filter(
                organization=self.artist.organization,
                user=user,
                role__in=OrganizationMember.EDIT_ROLES,
            ).exists():
                return True

        from payments.models import StreamTicketPurchase, Subscription

        has_subscription = Subscription.objects.filter(
            fan__user=user,
            artist=self.artist,
            status=Subscription.ACTIVE,
            current_period_end__gte=timezone.now(),
        ).exists()
        has_ticket = StreamTicketPurchase.objects.filter(
            fan__user=user,
            stream=self,
            paid=True,
        ).exists()
        return has_subscription or has_ticket


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
