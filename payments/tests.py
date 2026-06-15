from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings, TestCase
from django.utils import timezone

from accounts.models import Artist, Fan
from streams.models import LiveStream

from .models import Subscription
from .pricing import split_platform_fee, stagehub_commission_percent, ticket_checkout_pricing


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

    def mark_artist_stripe_ready(self):
        self.artist.stripe_account_id = 'acct_test_artist'
        self.artist.stripe_details_submitted = True
        self.artist.stripe_charges_enabled = True
        self.artist.stripe_payouts_enabled = True
        self.artist.save(update_fields=[
            'stripe_account_id',
            'stripe_details_submitted',
            'stripe_charges_enabled',
            'stripe_payouts_enabled',
        ])

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

    @override_settings(STAGEHUB_COMMISSION_PERCENT='20.00')
    def test_split_platform_fee_uses_configured_commission(self):
        split = split_platform_fee(Decimal('10.00'))

        self.assertEqual(stagehub_commission_percent(), Decimal('20.00'))
        self.assertEqual(split['platform_fee_amount'], Decimal('2.00'))
        self.assertEqual(split['artist_net_amount'], Decimal('8.00'))

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx', STAGEHUB_COMMISSION_PERCENT='20.00')
    @patch('payments.views.stripe.checkout.Session.create')
    @patch('payments.views.stripe.Account.retrieve')
    def test_paid_ticket_checkout_uses_connect_destination_charge(self, mock_retrieve, mock_session_create):
        self.mark_artist_stripe_ready()
        stream = self.create_stream(access_price=Decimal('10.00'))
        mock_retrieve.return_value = {
            'details_submitted': True,
            'charges_enabled': True,
            'payouts_enabled': True,
        }
        mock_session_create.return_value = SimpleNamespace(id='cs_test_ticket', url='https://stripe.test/checkout')

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/pagamentos/streams/{stream.id}/bilhete/')

        self.assertEqual(response.status_code, 302)
        kwargs = mock_session_create.call_args.kwargs
        self.assertEqual(kwargs['payment_intent_data']['application_fee_amount'], 200)
        self.assertEqual(kwargs['payment_intent_data']['transfer_data']['destination'], 'acct_test_artist')
        self.assertEqual(kwargs['metadata']['platform_fee_amount'], '2.00')
        self.assertEqual(kwargs['metadata']['artist_net_amount'], '8.00')

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx')
    @patch('payments.views.stripe.Account.retrieve')
    def test_paid_ticket_blocks_artist_without_completed_connect(self, mock_retrieve):
        self.artist.stripe_account_id = 'acct_test_artist'
        self.artist.save(update_fields=['stripe_account_id'])
        stream = self.create_stream(access_price=Decimal('10.00'))
        mock_retrieve.return_value = {
            'details_submitted': False,
            'charges_enabled': False,
            'payouts_enabled': False,
        }

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/pagamentos/streams/{stream.id}/bilhete/')

        self.assertRedirects(response, f'/eventos/{stream.id}/')
