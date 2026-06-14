from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import override_settings
from django.test import TestCase
from django.utils import timezone

from accounts.models import Artist, Fan
from payments.models import StreamTicketPurchase

from .forms import LiveStreamForm
from .cloudflare import create_direct_upload_for_stream
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

    def test_recorded_cloudflare_direct_upload_does_not_require_video_uid(self):
        scheduled_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Video gravado',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': '',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.RECORDED,
                'access_price': '5.00',
                'scheduled_at': scheduled_at,
                'duration_minutes': '60',
                'create_upload_url': 'on',
            },
            artist=self.artist,
        )

        self.assertTrue(form.is_valid(), form.errors)


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

    @override_settings(CLOUDFLARE_STREAM_CUSTOMER_SUBDOMAIN='customer-test')
    def test_cloudflare_embed_url_extracts_uid_from_manifest_url(self):
        stream = self.create_paid_stream()
        stream.cloudflare_live_input_uid = 'https://customer-test.cloudflarestream.com/live-input-123/manifest/video.m3u8'

        self.assertEqual(
            stream.cloudflare_embed_url,
            'https://customer-test.cloudflarestream.com/live-input-123/iframe?autoplay=true&lowLatency=true&preload=true',
        )

    def test_cloudflare_embed_url_normalizes_advanced_iframe_url(self):
        stream = self.create_paid_stream()
        stream.cloudflare_playback_url = 'https://customer-test.cloudflarestream.com/live-input-123/iframe'

        self.assertEqual(
            stream.cloudflare_embed_url,
            'https://customer-test.cloudflarestream.com/live-input-123/iframe?autoplay=true&lowLatency=true&preload=true',
        )

    def test_cloudflare_stream_id_rejects_rtmps_url(self):
        scheduled_at = timezone.localtime(timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Live paga',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': 'rtmps://live.cloudflare.com/live/',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.LIVE,
                'access_price': '5.00',
                'scheduled_at': scheduled_at,
                'duration_minutes': '',
            },
            artist=self.artist,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('cloudflare_stream_id', form.errors)

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

    def test_home_shows_purchased_past_inactive_event_to_buyer(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Evento comprado passado',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() - timedelta(minutes=10),
            duration_minutes=5,
            is_active=False,
        )
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_test_paid_past',
            paid=True,
        )

        self.client.force_login(self.fan_user)
        response = self.client.get('/')

        self.assertContains(response, 'Evento comprado passado')
        self.assertContains(response, 'Entrar na sala')

    def test_pending_direct_upload_requires_recorded_video_and_upload_url(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video por enviar',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-uid-123',
            cloudflare_upload_url='https://upload.videodelivery.net/tus/abc',
            cloudflare_upload_status=LiveStream.UPLOAD_PENDING,
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now(),
        )

        self.assertTrue(stream.has_pending_direct_upload)


class CloudflareDirectUploadTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='artist3')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista 3')
        self.stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video novo',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now(),
            duration_minutes=45,
        )

    @override_settings(CLOUDFLARE_ACCOUNT_ID='account', CLOUDFLARE_API_TOKEN='token')
    @patch('streams.cloudflare.urlopen')
    def test_create_direct_upload_for_stream_returns_uid_and_upload_url(self, mock_urlopen):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({
                    'success': True,
                    'result': {
                        'uid': 'video-uid',
                        'uploadURL': 'https://upload.videodelivery.net/tus/upload',
                        'expires': '2026-06-14T20:00:00Z',
                    },
                }).encode('utf-8')

        mock_urlopen.return_value = FakeResponse()

        upload = create_direct_upload_for_stream(self.stream)

        self.assertEqual(upload['uid'], 'video-uid')
        self.assertEqual(upload['upload_url'], 'https://upload.videodelivery.net/tus/upload')
