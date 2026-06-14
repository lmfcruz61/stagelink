from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone

from accounts.models import Artist, Fan
from payments.models import StreamTicketPurchase

from .forms import LiveStreamForm
from .models import LiveStream


class LiveStreamFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='artist')
        self.artist = Artist.objects.create(user=self.user, name='Artista')

    def test_datetime_local_value_uses_browser_format(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Evento',
            video_provider=LiveStream.VIDEO_PROVIDER_YOUTUBE,
            youtube_video_id='abcdefghijk',
            event_type=LiveStream.RECORDED,
            access_price=Decimal('0.00'),
            scheduled_at=timezone.now() + timedelta(days=1),
        )

        form = LiveStreamForm(instance=stream, artist=self.artist)

        self.assertIn('T', str(form['scheduled_at']))

    def test_title_only_edit_does_not_fail_on_legacy_video_rules(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Nome antigo',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('0.00'),
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        scheduled_at = timezone.localtime(stream.scheduled_at).strftime('%Y-%m-%dT%H:%M')

        form = LiveStreamForm(
            data={
                'title': 'Nome novo',
                'description': stream.description,
                'video_provider': stream.video_provider,
                'cloudflare_stream_id': stream.cloudflare_live_input_uid,
                'cloudflare_playback_url': stream.cloudflare_playback_url,
                'youtube_video_id': stream.youtube_video_id,
                'event_type': stream.event_type,
                'access_price': str(stream.access_price),
                'scheduled_at': scheduled_at,
                'duration_minutes': '',
            },
            instance=stream,
            artist=self.artist,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.title, 'Nome novo')


class LiveStreamAccessAndEmbedTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='artist2')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista 2')
        self.fan_user = User.objects.create_user(username='fan2')
        self.fan = Fan.objects.create(user=self.fan_user, display_name='Publico 2')

    def create_paid_stream(self):
        return LiveStream.objects.create(
            artist=self.artist,
            title='Live paga',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('10.00'),
            scheduled_at=timezone.now() - timedelta(hours=1),
            is_active=True,
        )

    @override_settings(CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN='customer-test.cloudflarestream.com')
    def test_cloudflare_embed_url_does_not_duplicate_full_host(self):
        stream = self.create_paid_stream()

        self.assertEqual(
            stream.cloudflare_embed_url,
            'https://customer-test.cloudflarestream.com/live-input-123/iframe?autoplay=true&lowLatency=true&preload=true',
        )

    @override_settings(CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN='customer-test')
    def test_cloudflare_embed_url_accepts_short_customer_subdomain(self):
        stream = self.create_paid_stream()

        self.assertEqual(
            stream.cloudflare_embed_url,
            'https://customer-test.cloudflarestream.com/live-input-123/iframe?autoplay=true&lowLatency=true&preload=true',
        )

    @override_settings(CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN='customer-test')
    def test_live_cloudflare_embed_prefers_live_input_uid(self):
        stream = self.create_paid_stream()
        stream.cloudflare_video_uid = 'old-video-uid'
        stream.cloudflare_live_input_uid = 'current-live-input'

        self.assertEqual(
            stream.cloudflare_embed_url,
            'https://customer-test.cloudflarestream.com/current-live-input/iframe?autoplay=true&lowLatency=true&preload=true',
        )

    def test_active_premiere_after_start_is_shown_as_live(self):
        stream = self.create_paid_stream()
        stream.event_type = LiveStream.PREMIERE
        stream.is_active = True

        self.assertEqual(stream.display_status['code'], 'live')

    def test_paid_ticket_allows_entry_after_scheduled_time(self):
        stream = self.create_paid_stream()
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_test_paid',
            paid=True,
        )

        decision = stream.access_decision(self.fan_user)

        self.assertTrue(decision['allowed'])
        self.assertEqual(decision['reason'], 'paid_ticket')
