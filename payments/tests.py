from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Artist, Fan
from streams.models import LiveStream

from .models import Subscription
from .pricing import ticket_checkout_pricing


class SubscriptionTierRulesTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='artist')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista Teste')
        self.fan_user = User.objects.create_user(username='fan')
        self.fan = Fan.objects.create(user=self.fan_user, display_name='Publico Teste')

    def create_subscription(self, tier):
        return Subscription.objects.create(
            fan=self.fan,
            artist=self.artist,
            tier=tier,
            status=Subscription.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=20),
        )

    def create_stream(self, **kwargs):
        defaults = {
            'artist': self.artist,
            'title': 'Evento Teste',
            'event_type': LiveStream.LIVE,
            'access_price': Decimal('20.00'),
            'scheduled_at': timezone.now() - timedelta(hours=1),
            'is_active': True,
        }
        defaults.update(kwargs)
        return LiveStream.objects.create(**defaults)

    def test_subscriber_pro_gets_half_price_on_paid_live_ticket(self):
        self.create_subscription(Subscription.SUBSCRIBER_PRO)
        stream = self.create_stream(access_price=Decimal('20.00'), event_type=LiveStream.LIVE)

        pricing = ticket_checkout_pricing(stream, self.fan)

        self.assertEqual(pricing['original_price'], Decimal('20.00'))
        self.assertEqual(pricing['final_price'], Decimal('10.00'))
        self.assertEqual(pricing['discount_percent'], 50)
        self.assertTrue(pricing['has_discount'])

    def test_regular_subscriber_does_not_get_live_ticket_discount(self):
        self.create_subscription(Subscription.SUBSCRIBER)
        stream = self.create_stream(access_price=Decimal('20.00'), event_type=LiveStream.LIVE)

        pricing = ticket_checkout_pricing(stream, self.fan)

        self.assertEqual(pricing['final_price'], Decimal('20.00'))
        self.assertEqual(pricing['discount_percent'], 0)
        self.assertFalse(pricing['has_discount'])

    def test_subscription_allows_recent_recorded_archive(self):
        self.create_subscription(Subscription.SUBSCRIBER)
        stream = self.create_stream(
            event_type=LiveStream.RECORDED,
            scheduled_at=timezone.now() - timedelta(days=10),
        )

        decision = stream.access_decision(self.fan_user)

        self.assertTrue(decision['allowed'])
        self.assertEqual(decision['reason'], 'subscription_recent_archive')

    def test_subscription_does_not_allow_old_recorded_archive(self):
        self.create_subscription(Subscription.SUBSCRIBER_PRO)
        stream = self.create_stream(
            event_type=LiveStream.RECORDED,
            scheduled_at=timezone.now() - timedelta(days=31),
        )

        decision = stream.access_decision(self.fan_user)

        self.assertFalse(decision['allowed'])
        self.assertEqual(decision['reason'], 'missing_paid_access')

    def test_subscription_does_not_grant_paid_live_video_access(self):
        self.create_subscription(Subscription.SUBSCRIBER_PRO)
        stream = self.create_stream(event_type=LiveStream.LIVE, access_price=Decimal('20.00'))

        decision = stream.access_decision(self.fan_user)

        self.assertFalse(decision['allowed'])
        self.assertEqual(decision['reason'], 'subscription_chat_only_live')
        self.assertTrue(stream.user_can_chat(self.fan_user))
