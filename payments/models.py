from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    ACTIVE = 'active'
    CANCELED = 'canceled'
    PAST_DUE = 'past_due'
    STATUS_CHOICES = (
        (ACTIVE, 'Ativa'),
        (CANCELED, 'Cancelada'),
        (PAST_DUE, 'Pagamento em atraso'),
    )

    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='subscriptions')
    artist = models.ForeignKey('accounts.Artist', on_delete=models.CASCADE, related_name='subscriptions')
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=ACTIVE)
    current_period_end = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fan', 'artist')

    def __str__(self):
        return f'{self.fan} -> {self.artist} ({self.status})'


class StreamTicketPurchase(models.Model):
    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='ticket_purchases')
    stream = models.ForeignKey('streams.LiveStream', on_delete=models.CASCADE, related_name='ticket_purchases')
    stripe_session_id = models.CharField(max_length=120, blank=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fan', 'stream')

    def __str__(self):
        return f'Bilhete {self.stream} - {self.fan}'
