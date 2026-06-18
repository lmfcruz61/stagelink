from datetime import timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Artist, Fan
from payments.models import PhotoGalleryPurchase, StreamTicketPurchase, Subscription

from .admin import PhotoGalleryAdmin
from .forms import LiveStreamForm, PhotoGalleryForm, PhotoGalleryImageUploadForm
from .cloudflare import create_direct_upload_for_stream
from .models import LiveStream, PhotoGallery, PhotoGalleryImage, Tip


class LegalPageTests(TestCase):
    def test_legal_pages_are_public(self):
        cases = (
            ('streams:privacy_policy', 'Politica de Privacidade'),
            ('streams:cookie_policy', 'Politica de Cookies'),
            ('streams:terms_conditions', 'Termos e Condicoes'),
        )

        for url_name, expected_text in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_text)

    def test_footer_links_to_legal_pages_and_cookie_settings(self):
        response = self.client.get(reverse('streams:home'))

        self.assertContains(response, reverse('streams:privacy_policy'))
        self.assertContains(response, reverse('streams:cookie_policy'))
        self.assertContains(response, reverse('streams:terms_conditions'))
        self.assertContains(response, 'Gerir cookies')


class DashboardPaymentPanelTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='artist', password='pass12345')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista')
        self.fan_user = User.objects.create_user(username='fan', password='pass12345')
        self.fan = Fan.objects.create(user=self.fan_user, display_name='Fa')

    def test_dashboard_guides_artist_before_stripe_connection(self):
        self.client.login(username='artist', password='pass12345')

        response = self.client.get(reverse('streams:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pagamentos ainda nao ligados')
        self.assertContains(response, 'Ligar Stripe')
        self.assertContains(response, 'Checklist para ativar pagamentos')
        self.assertContains(response, '0,00 EUR')

    def test_dashboard_shows_payment_summary_when_stripe_is_ready(self):
        self.artist.stripe_account_id = 'acct_artist'
        self.artist.stripe_details_submitted = True
        self.artist.stripe_charges_enabled = True
        self.artist.stripe_payouts_enabled = True
        self.artist.save(update_fields=[
            'stripe_account_id',
            'stripe_details_submitted',
            'stripe_charges_enabled',
            'stripe_payouts_enabled',
        ])
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Evento',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            event_type=LiveStream.LIVE,
            access_price=Decimal('10.00'),
            scheduled_at=timezone.now(),
        )
        gallery = PhotoGallery.objects.create(
            artist=self.artist,
            title='Galeria',
            public_cover=SimpleUploadedFile('cover.jpg', b'cover', content_type='image/jpeg'),
            access_price=Decimal('5.00'),
            is_active=True,
            moderation_status=PhotoGallery.APPROVED,
        )
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_live_ticket',
            stripe_livemode=True,
            amount=Decimal('10.00'),
            platform_fee_amount=Decimal('2.00'),
            artist_net_amount=Decimal('8.00'),
            paid=True,
        )
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            stripe_session_id='cs_live_gallery',
            stripe_livemode=True,
            amount=Decimal('5.00'),
            platform_fee_amount=Decimal('1.00'),
            artist_net_amount=Decimal('4.00'),
            paid=True,
        )
        Tip.objects.create(
            fan=self.fan,
            artist=self.artist,
            stream=stream,
            amount=Decimal('3.00'),
            platform_fee_amount=Decimal('0.60'),
            artist_net_amount=Decimal('2.40'),
            stripe_livemode=True,
        )
        Subscription.objects.create(
            fan=self.fan,
            artist=self.artist,
            tier=Subscription.SUBSCRIBER,
            status=Subscription.ACTIVE,
            stripe_livemode=True,
            current_period_end=timezone.now() + timedelta(days=30),
        )
        self.client.login(username='artist', password='pass12345')

        response = self.client.get(reverse('streams:dashboard'))

        self.assertContains(response, 'Pagamentos ativos')
        self.assertContains(response, '23,00 EUR')
        self.assertContains(response, '4,60 EUR')
        self.assertContains(response, '18,40 EUR')
        self.assertContains(response, '1 vendas')
        self.assertContains(response, '1 recebidas')

    def test_dashboard_excludes_test_mode_payments_from_summary(self):
        self.artist.stripe_account_id = 'acct_artist'
        self.artist.stripe_details_submitted = True
        self.artist.stripe_charges_enabled = True
        self.artist.stripe_payouts_enabled = True
        self.artist.save(update_fields=[
            'stripe_account_id',
            'stripe_details_submitted',
            'stripe_charges_enabled',
            'stripe_payouts_enabled',
        ])
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Evento',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            event_type=LiveStream.LIVE,
            access_price=Decimal('10.00'),
            scheduled_at=timezone.now(),
        )
        gallery = PhotoGallery.objects.create(
            artist=self.artist,
            title='Galeria',
            public_cover=SimpleUploadedFile('cover.jpg', b'cover', content_type='image/jpeg'),
            access_price=Decimal('2.00'),
            is_active=True,
            moderation_status=PhotoGallery.APPROVED,
        )
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_test_ticket',
            stripe_livemode=False,
            amount=Decimal('10.00'),
            platform_fee_amount=Decimal('2.00'),
            artist_net_amount=Decimal('8.00'),
            paid=True,
        )
        Tip.objects.create(
            fan=self.fan,
            artist=self.artist,
            stream=stream,
            amount=Decimal('10.00'),
            platform_fee_amount=Decimal('2.00'),
            artist_net_amount=Decimal('8.00'),
            stripe_livemode=False,
        )
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            stripe_session_id='cs_live_gallery',
            stripe_livemode=True,
            amount=Decimal('2.00'),
            platform_fee_amount=Decimal('0.40'),
            artist_net_amount=Decimal('1.60'),
            paid=True,
        )
        self.client.login(username='artist', password='pass12345')

        response = self.client.get(reverse('streams:dashboard'))

        self.assertContains(response, '2,00 EUR')
        self.assertContains(response, '0,40 EUR')
        self.assertContains(response, '1,60 EUR')
        self.assertContains(response, '0 recebidas')
        self.assertNotContains(response, '12,00 EUR')


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

    def test_recorded_cloudflare_video_rejects_duration_over_one_hour(self):
        scheduled_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Video longo',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': '',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.RECORDED,
                'access_price': '5.00',
                'scheduled_at': scheduled_at,
                'duration_minutes': '61',
                'create_upload_url': 'on',
            },
            artist=self.artist,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('duration_minutes', form.errors)

    def test_recorded_cloudflare_video_rejects_duration_over_one_hour_on_edit(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video existente',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-stagehub-123',
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now(),
            duration_minutes=45,
        )
        scheduled_at = timezone.localtime(stream.scheduled_at).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': stream.title,
                'description': stream.description,
                'video_provider': stream.video_provider,
                'cloudflare_stream_id': stream.cloudflare_video_uid,
                'cloudflare_playback_url': stream.cloudflare_playback_url,
                'youtube_video_id': stream.youtube_video_id,
                'event_type': stream.event_type,
                'access_price': str(stream.access_price),
                'scheduled_at': scheduled_at,
                'duration_minutes': '61',
                'create_upload_url': '',
            },
            instance=stream,
            artist=self.artist,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('duration_minutes', form.errors)

    def test_events_below_minimum_price_are_rejected(self):
        scheduled_at = timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Evento barato',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': 'video-stagehub-123',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.RECORDED,
                'access_price': '1.99',
                'scheduled_at': scheduled_at,
                'duration_minutes': '30',
                'create_upload_url': '',
            },
            artist=self.artist,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('access_price', form.errors)


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


class PhotoGalleryAccessTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='gallery_artist')
        self.artist = Artist.objects.create(user=self.artist_user, name='Fotografo')
        self.fan_user = User.objects.create_user(username='gallery_fan')
        self.fan = Fan.objects.create(user=self.fan_user, display_name='Publico Galeria')

    def create_gallery(self, **kwargs):
        defaults = {
            'artist': self.artist,
            'title': 'Galeria exclusiva',
            'description': 'Fotos protegidas',
            'public_cover': 'covers/capa.jpg',
            'access_price': Decimal('5.00'),
            'is_active': True,
            'moderation_status': PhotoGallery.APPROVED,
        }
        defaults.update(kwargs)
        return PhotoGallery.objects.create(**defaults)

    def test_photo_gallery_form_rejects_price_below_minimum(self):
        form = PhotoGalleryForm(data={
            'title': 'Galeria barata',
            'description': '',
            'public_cover': 'covers/capa.jpg',
            'access_price': '1.99',
            'is_sensitive': '',
            'is_active': 'on',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('access_price', form.errors)

    def test_photo_gallery_upload_rejects_images_over_three_mb(self):
        gallery = self.create_gallery()
        image = SimpleUploadedFile(
            'foto.jpg',
            b'x' * ((3 * 1024 * 1024) + 1),
            content_type='image/jpeg',
        )
        form = PhotoGalleryImageUploadForm(
            files={'images': image},
            gallery=gallery,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Cada foto pode ter no maximo 3 MB.', form.errors['images'])

    def test_photo_gallery_upload_rejects_more_than_ten_images_per_upload(self):
        gallery = self.create_gallery()
        images = [
            SimpleUploadedFile(f'foto-{index}.jpg', b'x', content_type='image/jpeg')
            for index in range(11)
        ]
        form = PhotoGalleryImageUploadForm(
            files={'images': images},
            gallery=gallery,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Envia no maximo 10 fotos de cada vez.', form.errors['images'])

    def test_photo_gallery_upload_rejects_total_over_thirty_mb(self):
        gallery = self.create_gallery()
        images = [
            SimpleUploadedFile(f'foto-{index}.jpg', b'x' * ((3 * 1024 * 1024) + 1), content_type='image/jpeg')
            for index in range(10)
        ]
        form = PhotoGalleryImageUploadForm(
            files={'images': images},
            gallery=gallery,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Cada envio pode ter no maximo 30 MB no total.', form.errors['images'])

    def test_photo_gallery_form_shows_safer_upload_limits(self):
        gallery = self.create_gallery()
        self.client.force_login(self.artist_user)

        response = self.client.get(f'/dashboard/galerias/{gallery.id}/editar/')

        self.assertContains(response, '10 fotos por envio')
        self.assertContains(response, '3 MB por foto')
        self.assertContains(response, '30 MB por envio')

    def test_home_shows_active_approved_photo_gallery(self):
        self.create_gallery(title='Galeria na entrada')

        response = self.client.get(reverse('streams:home'))

        self.assertContains(response, 'Galeria na entrada')
        self.assertContains(response, 'Galerias de fotos')

    def test_admin_approval_publishes_photo_gallery(self):
        admin_user = User.objects.create_user(username='admin_gallery', is_staff=True, is_superuser=True)
        gallery = self.create_gallery(
            title='Galeria pendente',
            is_active=False,
            moderation_status=PhotoGallery.PENDING,
        )
        request = RequestFactory().post('/admin/streams/photogallery/')
        request.user = admin_user
        gallery_admin = PhotoGalleryAdmin(PhotoGallery, AdminSite())

        gallery_admin.approve_galleries(request, PhotoGallery.objects.filter(pk=gallery.pk))
        gallery.refresh_from_db()

        self.assertEqual(gallery.moderation_status, PhotoGallery.APPROVED)
        self.assertTrue(gallery.is_active)
        self.assertEqual(gallery.reviewed_by, admin_user)

    def test_pending_gallery_does_not_show_to_public_on_artist_page(self):
        self.create_gallery(moderation_status=PhotoGallery.PENDING)

        response = self.client.get(f'/artistas/{self.artist.id}/')

        self.assertNotContains(response, 'Galeria exclusiva')

    def test_approved_gallery_shows_public_cover_but_not_private_images_to_non_buyer(self):
        gallery = self.create_gallery()
        PhotoGalleryImage.objects.create(gallery=gallery, image='private/foto-secreta.jpg')

        response = self.client.get(f'/galerias/{gallery.id}/')

        self.assertContains(response, 'Galeria exclusiva')
        self.assertContains(response, 'covers/capa.jpg')
        self.assertNotContains(response, 'private/foto-secreta.jpg')
        self.assertContains(response, 'Fotos privadas')

    def test_paid_buyer_can_view_private_gallery_images(self):
        gallery = self.create_gallery()
        PhotoGalleryImage.objects.create(gallery=gallery, image='private/foto-secreta.jpg')
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            amount=Decimal('5.00'),
            paid=True,
        )

        self.client.force_login(self.fan_user)
        response = self.client.get(f'/galerias/{gallery.id}/')

        self.assertContains(response, 'private/foto-secreta.jpg')


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
        self.assertEqual(upload['expires'], '2026-06-14T20:00:00Z')

    @override_settings(CLOUDFLARE_ACCOUNT_ID='account', CLOUDFLARE_API_TOKEN='token')
    @patch('streams.cloudflare.urlopen')
    def test_create_direct_upload_caps_max_duration_at_one_hour(self, mock_urlopen):
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

        self.stream.duration_minutes = 90
        mock_urlopen.return_value = FakeResponse()

        create_direct_upload_for_stream(self.stream)

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload['maxDurationSeconds'], 3600)
