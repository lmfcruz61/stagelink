from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import override_settings, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Artist, Fan
from streams.models import LiveStream, PhotoGallery

from .models import PhotoGalleryPurchase, Subscription
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

    def test_subscription_only_allows_recorded_content_for_active_subscriber(self):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_ONLY
        self.artist.save(update_fields=['monetization_mode'])
        self.create_subscription(Subscription.SUBSCRIBER)
        stream = self.create_stream(
            event_type=LiveStream.RECORDED,
            scheduled_at=timezone.now() - timedelta(days=10),
        )

        decision = stream.access_decision(self.fan_user)

        self.assertTrue(decision['allowed'])
        self.assertEqual(decision['reason'], 'subscription_included_content')

    def test_subscription_only_allows_old_recorded_content_for_active_subscriber(self):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_ONLY
        self.artist.save(update_fields=['monetization_mode'])
        self.create_subscription(Subscription.SUBSCRIBER_PRO)
        stream = self.create_stream(
            event_type=LiveStream.RECORDED,
            scheduled_at=timezone.now() - timedelta(days=31),
        )

        decision = stream.access_decision(self.fan_user)

        self.assertTrue(decision['allowed'])
        self.assertEqual(decision['reason'], 'subscription_included_content')

    def test_subscription_does_not_grant_paid_live_video_access(self):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_AND_PAID_EXCLUSIVE
        self.artist.save(update_fields=['monetization_mode'])
        self.create_subscription(Subscription.SUBSCRIBER_PRO)
        stream = self.create_stream(event_type=LiveStream.LIVE, access_price=Decimal('20.00'))

        decision = stream.access_decision(self.fan_user)

        self.assertFalse(decision['allowed'])
        self.assertEqual(decision['reason'], 'subscription_chat_only_live')
        self.assertTrue(stream.user_can_chat(self.fan_user))

    def test_paid_content_only_does_not_allow_new_subscriptions(self):
        self.artist.monetization_mode = Artist.PAID_CONTENT_ONLY
        self.artist.save(update_fields=['monetization_mode'])
        self.client.force_login(self.fan_user)

        response = self.client.get(reverse('payments:subscribe_artist', args=[self.artist.id]))

        self.assertRedirects(response, reverse('streams:artist_detail', args=[self.artist.id]))

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx')
    @patch('payments.views.stripe.checkout.Session.create')
    @patch('payments.views.stripe.Account.retrieve')
    def test_subscription_exclusive_ticket_requires_active_subscription(self, mock_retrieve, mock_session_create):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_AND_PAID_EXCLUSIVE
        self.artist.save(update_fields=['monetization_mode'])
        self.mark_artist_stripe_ready()
        stream = self.create_stream(access_price=Decimal('10.00'))
        mock_retrieve.return_value = {
            'details_submitted': True,
            'charges_enabled': True,
            'payouts_enabled': True,
        }

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/pagamentos/streams/{stream.id}/bilhete/')

        self.assertRedirects(response, reverse('streams:artist_detail', args=[self.artist.id]))
        mock_session_create.assert_not_called()

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx')
    @patch('payments.views.stripe.checkout.Session.create')
    @patch('payments.views.stripe.Account.retrieve')
    def test_subscription_exclusive_ticket_allows_active_subscriber(self, mock_retrieve, mock_session_create):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_AND_PAID_EXCLUSIVE
        self.artist.save(update_fields=['monetization_mode'])
        self.create_subscription(Subscription.SUBSCRIBER)
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
        self.assertEqual(response.url, 'https://stripe.test/checkout')
        mock_session_create.assert_called_once()

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx')
    @patch('payments.views.stripe.checkout.Session.create')
    @patch('payments.views.stripe.Account.retrieve')
    def test_subscription_only_blocks_ticket_purchase(self, mock_retrieve, mock_session_create):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_ONLY
        self.artist.save(update_fields=['monetization_mode'])
        self.mark_artist_stripe_ready()
        stream = self.create_stream(access_price=Decimal('10.00'))

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/pagamentos/streams/{stream.id}/bilhete/')

        self.assertRedirects(response, reverse('streams:event_detail', args=[stream.id]))
        mock_retrieve.assert_not_called()
        mock_session_create.assert_not_called()

    @override_settings(STAGEHUB_COMMISSION_PERCENT='20.00')
    def test_split_platform_fee_uses_configured_commission(self):
        split = split_platform_fee(Decimal('10.00'))

        self.assertEqual(stagehub_commission_percent(), Decimal('20.00'))
        self.assertEqual(split['platform_fee_amount'], Decimal('2.00'))
        self.assertEqual(split['artist_net_amount'], Decimal('8.00'))

    def test_split_platform_fee_uses_default_artist_commission(self):
        split = split_platform_fee(Decimal('10.00'), artist=self.artist)

        self.assertEqual(stagehub_commission_percent(self.artist), Decimal('20.00'))
        self.assertEqual(split['commission_percent'], Decimal('20.00'))
        self.assertEqual(split['platform_fee_amount'], Decimal('2.00'))
        self.assertEqual(split['artist_net_amount'], Decimal('8.00'))

    def test_split_platform_fee_uses_reduced_artist_commission(self):
        self.artist.commission_rate = Decimal('10.00')
        self.artist.save(update_fields=['commission_rate'])

        split = split_platform_fee(Decimal('10.00'), artist=self.artist)

        self.assertEqual(split['commission_percent'], Decimal('10.00'))
        self.assertEqual(split['platform_fee_amount'], Decimal('1.00'))
        self.assertEqual(split['artist_net_amount'], Decimal('9.00'))

    def test_split_platform_fee_allows_zero_artist_commission(self):
        self.artist.commission_rate = Decimal('0.00')
        self.artist.save(update_fields=['commission_rate'])

        split = split_platform_fee(Decimal('10.00'), artist=self.artist)

        self.assertEqual(split['commission_percent'], Decimal('0.00'))
        self.assertEqual(split['platform_fee_amount'], Decimal('0.00'))
        self.assertEqual(split['artist_net_amount'], Decimal('10.00'))

    def test_artist_commission_rate_must_be_between_zero_and_one_hundred(self):
        self.artist.commission_rate = Decimal('-1.00')
        with self.assertRaises(ValidationError):
            self.artist.full_clean()

        self.artist.commission_rate = Decimal('100.01')
        with self.assertRaises(ValidationError):
            self.artist.full_clean()

    def test_artist_with_active_subscriptions_cannot_switch_to_paid_content_only(self):
        self.artist.monetization_mode = Artist.SUBSCRIPTION_ONLY
        self.artist.save(update_fields=['monetization_mode'])
        self.create_subscription(Subscription.SUBSCRIBER)

        self.artist.monetization_mode = Artist.PAID_CONTENT_ONLY

        with self.assertRaises(ValidationError):
            self.artist.full_clean()

    @override_settings(STRIPE_SECRET_KEY='sk_live_xxx')
    @patch('payments.views.stripe.AccountLink.create')
    @patch('payments.views.stripe.Account.create_login_link')
    def test_ready_connect_account_opens_express_dashboard(self, mock_login_link, mock_account_link):
        self.mark_artist_stripe_ready()
        mock_login_link.return_value = SimpleNamespace(url='https://connect.stripe.com/express/dashboard')
        self.client.force_login(self.artist_user)

        response = self.client.get(reverse('payments:stripe_connect_start', args=[self.artist.id]))

        self.assertRedirects(
            response,
            'https://connect.stripe.com/express/dashboard',
            fetch_redirect_response=False,
        )
        mock_login_link.assert_called_once_with('acct_test_artist')
        mock_account_link.assert_not_called()

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

    @override_settings(STRIPE_SECRET_KEY='sk_test_xxx', STAGEHUB_COMMISSION_PERCENT='20.00')
    @patch('payments.views.stripe.checkout.Session.create')
    @patch('payments.views.stripe.Account.retrieve')
    def test_photo_gallery_checkout_uses_connect_destination_charge(self, mock_retrieve, mock_session_create):
        self.mark_artist_stripe_ready()
        gallery = PhotoGallery.objects.create(
            artist=self.artist,
            title='Galeria paga',
            public_cover='covers/capa.jpg',
            access_price=Decimal('10.00'),
            is_active=True,
            moderation_status=PhotoGallery.APPROVED,
        )
        mock_retrieve.return_value = {
            'details_submitted': True,
            'charges_enabled': True,
            'payouts_enabled': True,
        }
        mock_session_create.return_value = SimpleNamespace(id='cs_test_gallery', url='https://stripe.test/gallery')

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/pagamentos/galerias/{gallery.id}/comprar/')

        self.assertEqual(response.status_code, 302)
        kwargs = mock_session_create.call_args.kwargs
        self.assertEqual(kwargs['payment_intent_data']['application_fee_amount'], 200)
        self.assertEqual(kwargs['payment_intent_data']['transfer_data']['destination'], 'acct_test_artist')
        self.assertEqual(kwargs['metadata']['type'], 'photo_gallery')
        self.assertEqual(kwargs['metadata']['platform_fee_amount'], '2.00')
        self.assertEqual(kwargs['metadata']['artist_net_amount'], '8.00')
        purchase = PhotoGalleryPurchase.objects.get(fan=self.fan, gallery=gallery)
        self.assertFalse(purchase.paid)
        self.assertEqual(purchase.stripe_session_id, 'cs_test_gallery')


class StripeConnectWebhookTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='connect_artist')
        self.artist = Artist.objects.create(
            user=self.artist_user,
            name='Artista Connect',
            stripe_account_id='acct_connect_artist',
        )

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    @patch('payments.views.stripe.Webhook.construct_event')
    def test_account_updated_webhook_marks_artist_stripe_ready(self, mock_construct_event):
        mock_construct_event.return_value = {
            'type': 'account.updated',
            'data': {
                'object': {
                    'id': 'acct_connect_artist',
                    'details_submitted': True,
                    'charges_enabled': True,
                    'payouts_enabled': True,
                },
            },
        }

        response = self.client.post(
            reverse('payments:stripe_webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='sig_test',
        )

        self.assertEqual(response.status_code, 200)
        self.artist.refresh_from_db()
        self.assertTrue(self.artist.stripe_details_submitted)
        self.assertTrue(self.artist.stripe_charges_enabled)
        self.assertTrue(self.artist.stripe_payouts_enabled)
        self.assertTrue(self.artist.stripe_connect_ready)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    @patch('payments.views.stripe.Webhook.construct_event')
    def test_account_updated_webhook_ignores_unknown_account(self, mock_construct_event):
        mock_construct_event.return_value = {
            'type': 'account.updated',
            'data': {
                'object': {
                    'id': 'acct_unknown',
                    'details_submitted': True,
                    'charges_enabled': True,
                    'payouts_enabled': True,
                },
            },
        }

        response = self.client.post(
            reverse('payments:stripe_webhook'),
            data=b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='sig_test',
        )

        self.assertEqual(response.status_code, 200)
        self.artist.refresh_from_db()
        self.assertFalse(self.artist.stripe_connect_ready)
