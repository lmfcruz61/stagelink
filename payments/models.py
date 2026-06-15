from django.db import models
from django.utils import timezone
from decimal import Decimal


class Subscription(models.Model):
    ACTIVE = 'active'
    CANCELED = 'canceled'
    PAST_DUE = 'past_due'
    STATUS_CHOICES = (
        (ACTIVE, 'Ativa'),
        (CANCELED, 'Cancelada'),
        (PAST_DUE, 'Pagamento em atraso'),
    )
    SUBSCRIBER = 'subscriber'
    SUBSCRIBER_PRO = 'subscriber_pro'
    TIER_CHOICES = (
        (SUBSCRIBER, 'Subscritor'),
        (SUBSCRIBER_PRO, 'Subscritor Pro'),
    )
    TIER_PRICES = {
        SUBSCRIBER: Decimal('5.00'),
        SUBSCRIBER_PRO: Decimal('10.00'),
    }

    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='subscriptions')
    artist = models.ForeignKey('accounts.Artist', on_delete=models.CASCADE, related_name='subscriptions')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=SUBSCRIBER)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_connected_account_id = models.CharField(max_length=120, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=ACTIVE)
    current_period_end = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fan', 'artist')

    def __str__(self):
        return f'{self.fan} -> {self.artist} ({self.get_tier_display()}, {self.status})'

    @classmethod
    def price_for_tier(cls, tier):
        return cls.TIER_PRICES.get(tier, cls.TIER_PRICES[cls.SUBSCRIBER])

    @classmethod
    def label_for_tier(cls, tier):
        return dict(cls.TIER_CHOICES).get(tier, 'Subscritor')

    @property
    def is_current(self):
        return self.status == self.ACTIVE and self.current_period_end >= timezone.now()

    @property
    def is_pro(self):
        return self.tier == self.SUBSCRIBER_PRO


class StreamTicketPurchase(models.Model):
    fan = models.ForeignKey('accounts.Fan', on_delete=models.CASCADE, related_name='ticket_purchases')
    stream = models.ForeignKey('streams.LiveStream', on_delete=models.CASCADE, related_name='ticket_purchases')
    stripe_session_id = models.CharField(max_length=120, blank=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)
    stripe_connected_account_id = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    platform_fee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    artist_net_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('fan', 'stream')

    def __str__(self):
        return f'Bilhete {self.stream} - {self.fan}'
