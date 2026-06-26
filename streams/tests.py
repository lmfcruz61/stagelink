from datetime import datetime, timedelta
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings, RequestFactory
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.forms import ArtistGalleryUploadForm
from accounts.models import Artist, ArtistPhoto, ContactMessage, Fan
from payments.models import PhotoGalleryPurchase, StreamTicketPurchase, Subscription

from .admin import PhotoGalleryAdmin
from .forms import LiveStreamForm, PhotoGalleryForm, PhotoGalleryImageUploadForm
from .cloudflare import CloudflareStreamError, create_direct_upload_for_stream
from .models import LiveStream, MediaDeletionLog, PhotoGallery, PhotoGalleryImage, Tip


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
        self.assertContains(response, reverse('streams:contact'))
        self.assertContains(response, 'Gerir cookies')

    @override_settings(ALLOWED_HOSTS=['stagehub.pt'])
    def test_homepage_has_institutional_social_metadata(self):
        artist_user = User.objects.create_user(username='artist_meta')
        Artist.objects.create(
            user=artist_user,
            name='Artista Meta',
            bio='Biografia do artista que nao deve aparecer nos metadados da homepage.',
            headline='Frase do artista',
        )

        response = self.client.get(reverse('streams:home'), secure=True, HTTP_HOST='stagehub.pt')

        expected_title = 'StageHub – Centro de Artistas e Eventos'
        expected_description = (
            'Crie. Partilhe. Atue. Ensine. Inspire. O StageHub reúne artistas, formadores e criadores '
            'numa única plataforma para realizar eventos ao vivo, workshops, espetáculos, aulas, conteúdos '
            'exclusivos e construir comunidades verdadeiras. Descubra novos talentos, apoie os seus artistas '
            'favoritos e viva experiências únicas, interativas e memoráveis.'
        )
        head_html = response.content.decode().split('</head>', 1)[0]
        self.assertIn(f'<title>{expected_title}</title>', head_html)
        self.assertIn(f'<meta name="description" content="{expected_description}">', head_html)
        self.assertIn(f'<meta property="og:title" content="{expected_title}">', head_html)
        self.assertIn(f'<meta property="og:description" content="{expected_description}">', head_html)
        self.assertIn('<meta property="og:url" content="https://stagehub.pt/">', head_html)
        self.assertIn('<meta property="og:type" content="website">', head_html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', head_html)
        self.assertIn(f'<meta name="twitter:title" content="{expected_title}">', head_html)
        self.assertIn(f'<meta name="twitter:description" content="{expected_description}">', head_html)
        self.assertIn('<meta property="og:image" content="https://stagehub.pt/static/img/stagehub-og-placeholder.svg">', head_html)
        self.assertIn('<meta name="twitter:image" content="https://stagehub.pt/static/img/stagehub-og-placeholder.svg">', head_html)
        self.assertNotIn('Biografia do artista que nao deve aparecer nos metadados da homepage.', head_html)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ContactPageTests(TestCase):
    def test_contact_page_is_public(self):
        response = self.client.get(reverse('streams:contact'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Contactar-nos')
        self.assertContains(response, 'Geral')
        self.assertContains(response, 'Financeiro')
        self.assertContains(response, 'Tecnico')

    def test_contact_form_saves_message_and_sends_categorized_email(self):
        response = self.client.post(
            reverse('streams:contact'),
            {
                'name': 'Luis Cruz',
                'email': 'luis@example.com',
                'contact_type': ContactMessage.FINANCE,
                'subject': 'Duvida sobre faturacao',
                'message': 'Gostava de esclarecer uma duvida sobre uma compra feita na plataforma.',
            },
            HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1',
            HTTP_USER_AGENT='StageHub Test Browser',
        )

        self.assertRedirects(response, reverse('streams:contact'))
        contact_message = ContactMessage.objects.get()
        self.assertEqual(contact_message.name, 'Luis Cruz')
        self.assertEqual(contact_message.email, 'luis@example.com')
        self.assertEqual(contact_message.contact_type, ContactMessage.FINANCE)
        self.assertEqual(contact_message.status, ContactMessage.NEW)
        self.assertEqual(contact_message.ip_address, '203.0.113.10')
        self.assertEqual(contact_message.user_agent, 'StageHub Test Browser')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['stagehub.platform@gmail.com'])
        self.assertEqual(mail.outbox[0].reply_to, ['luis@example.com'])
        self.assertEqual(mail.outbox[0].subject, '[STAGEHUB - FINANCEIRO] Duvida sobre faturacao')
        self.assertIn('Nome:\nLuis Cruz', mail.outbox[0].body)
        self.assertIn('IP:\n203.0.113.10', mail.outbox[0].body)

    def test_contact_form_blocks_honeypot_spam(self):
        response = self.client.post(reverse('streams:contact'), {
            'name': 'Spam',
            'email': 'spam@example.com',
            'contact_type': ContactMessage.GENERAL,
            'subject': 'Spam',
            'message': 'Esta mensagem tem tamanho suficiente.',
            'website': 'https://spam.example.com',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_technical_contact_email_uses_expected_subject_prefix(self):
        self.client.post(reverse('streams:contact'), {
            'name': 'Ana',
            'email': 'ana@example.com',
            'contact_type': ContactMessage.TECHNICAL,
            'subject': 'Erro ao carregar imagem',
            'message': 'Tenho um erro ao carregar uma imagem na galeria.',
        })

        self.assertEqual(mail.outbox[0].subject, '[STAGEHUB - TÉCNICO] Erro ao carregar imagem')


class CloudflareMediaAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_media',
            email='admin@example.com',
            password='pass12345',
        )
        self.artist_user = User.objects.create_user(username='artist_media', password='pass12345')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista Media')
        self.stream = LiveStream.objects.create(
            artist=self.artist,
            title='Evento com video',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            event_type=LiveStream.RECORDED,
            cloudflare_video_uid='video-cloudflare-123',
            access_price=Decimal('2.00'),
            scheduled_at=timezone.now(),
        )

    def test_cloudflare_media_admin_lists_referenced_video(self):
        self.client.login(username='admin_media', password='pass12345')

        response = self.client.get(reverse('admin:cloudflare_media'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Media Cloudflare')
        self.assertContains(response, 'Evento com video')
        self.assertContains(response, 'video-cloudflare-123')

    @patch('streams.admin.delete_stream_video')
    def test_cloudflare_media_admin_deletes_selected_video_and_logs(self, delete_stream_video):
        self.client.login(username='admin_media', password='pass12345')
        key = f'video:stream:{self.stream.id}:video-cloudflare-123'

        response = self.client.post(reverse('admin:cloudflare_media'), {
            'action': 'delete_selected',
            'confirm': 'APAGAR',
            'selected': [key],
        })

        self.assertEqual(response.status_code, 302)
        delete_stream_video.assert_called_once_with('video-cloudflare-123')
        self.stream.refresh_from_db()
        self.assertEqual(self.stream.cloudflare_video_uid, '')
        self.assertEqual(self.stream.cloudflare_upload_status, LiveStream.UPLOAD_NOT_REQUESTED)
        log = MediaDeletionLog.objects.get()
        self.assertEqual(log.admin_user, self.admin_user)
        self.assertEqual(log.cloudflare_id, 'video-cloudflare-123')
        self.assertEqual(log.status, MediaDeletionLog.STATUS_SUCCESS)


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
        self.assertContains(response, 'Abrir painel Stripe')
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

    def test_datetime_local_value_uses_current_timezone_on_edit(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Live com data',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.make_aware(datetime(2026, 6, 24, 20, 30)),
        )

        with timezone.override('Europe/Lisbon'):
            form = LiveStreamForm(instance=stream, artist=self.artist)

        self.assertIn('2026-06-24T20:30', str(form['scheduled_at']))

    def test_title_only_edit_does_not_fail_on_legacy_video_rules(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Nome antigo',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('2.00'),
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

    def test_stream_edit_without_new_cover_keeps_existing_cover(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video com capa',
            description='Descricao antiga',
            cover_image='streams/covers/capa-existente.jpg',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-stagehub-123',
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        scheduled_at = timezone.localtime(stream.scheduled_at).strftime('%Y-%m-%dT%H:%M')
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')

        response = self.client.post(reverse('streams:stream_update', args=[stream.id]), {
            'title': 'Video com capa editado',
            'description': stream.description,
            'video_provider': stream.video_provider,
            'cloudflare_stream_id': stream.cloudflare_video_uid,
            'cloudflare_playback_url': stream.cloudflare_playback_url,
            'youtube_video_id': stream.youtube_video_id,
            'event_type': stream.event_type,
            'access_price': '5.00',
            'scheduled_at': scheduled_at,
            'duration_minutes': '',
            'create_upload_url': '',
        })
        stream.refresh_from_db()

        self.assertRedirects(response, f"{reverse('streams:dashboard')}?artist={self.artist.id}")
        self.assertEqual(stream.cover_image.name, 'streams/covers/capa-existente.jpg')

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

    def test_live_cloudflare_does_not_require_manual_video_uid(self):
        scheduled_at = timezone.localtime(timezone.now() + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Live nova',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': '',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.LIVE,
                'access_price': '5.00',
                'scheduled_at': scheduled_at,
                'duration_minutes': '',
                'create_upload_url': '',
            },
            artist=self.artist,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_new_live_form_defaults_to_minimum_ticket_price(self):
        form = LiveStreamForm(
            artist=self.artist,
            initial={'event_type': LiveStream.LIVE},
        )

        self.assertEqual(form.initial['access_price'], '2.00')
        self.assertIn('min="2"', str(form['access_price']))

    def test_live_below_minimum_price_is_rejected(self):
        scheduled_at = timezone.localtime(timezone.now() + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M')
        form = LiveStreamForm(
            data={
                'title': 'Live barata',
                'description': '',
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'cloudflare_stream_id': '',
                'cloudflare_playback_url': '',
                'youtube_video_id': '',
                'event_type': LiveStream.LIVE,
                'access_price': '1.99',
                'scheduled_at': scheduled_at,
                'duration_minutes': '',
                'create_upload_url': '',
            },
            artist=self.artist,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('access_price', form.errors)

    def test_legacy_live_below_minimum_price_is_rejected_on_simple_edit(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Live antiga',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('0.00'),
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        scheduled_at = timezone.localtime(stream.scheduled_at).strftime('%Y-%m-%dT%H:%M')

        form = LiveStreamForm(
            data={
                'title': 'Live antiga editada',
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

        self.assertFalse(form.is_valid())
        self.assertIn('access_price', form.errors)

    @patch('streams.views.create_live_input_for_artist')
    def test_dashboard_creates_live_and_prepares_obs_data(self, create_live_input):
        create_live_input.return_value = {
            'uid': 'live-input-new',
            'rtmps_url': 'rtmps://live.cloudflare.com/live/',
            'stream_key': 'secret-key',
        }
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')
        scheduled_at = timezone.localtime(timezone.now() + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M')

        response = self.client.post(reverse('streams:stream_create'), {
            'artist': self.artist.id,
            'title': 'Live preparada',
            'description': '',
            'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            'cloudflare_stream_id': '',
            'cloudflare_playback_url': '',
            'youtube_video_id': '',
            'event_type': LiveStream.LIVE,
            'access_price': '5.00',
            'scheduled_at': scheduled_at,
            'duration_minutes': '',
            'create_upload_url': '',
        })

        stream = LiveStream.objects.get(title='Live preparada')
        self.assertRedirects(response, reverse('streams:stream_update', args=[stream.id]))
        self.artist.refresh_from_db()
        self.assertEqual(self.artist.cloudflare_live_input_uid, 'live-input-new')
        self.assertEqual(self.artist.cloudflare_rtmps_url, 'rtmps://live.cloudflare.com/live/')
        self.assertEqual(self.artist.cloudflare_stream_key, 'secret-key')
        self.assertEqual(stream.cloudflare_live_input_uid, 'live-input-new')
        self.assertEqual(stream.cloudflare_video_uid, '')

    def test_live_edit_page_shows_obs_recommendations(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Live com OBS',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-123',
            event_type=LiveStream.LIVE,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() + timedelta(minutes=10),
        )
        self.artist.cloudflare_live_input_uid = 'live-input-123'
        self.artist.cloudflare_rtmps_url = 'rtmps://live.cloudflare.com/live/'
        self.artist.cloudflare_stream_key = 'secret-key'
        self.artist.save(update_fields=[
            'cloudflare_live_input_uid',
            'cloudflare_rtmps_url',
            'cloudflare_stream_key',
        ])
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')

        response = self.client.get(reverse('streams:stream_update', args=[stream.id]))

        self.assertContains(response, 'Configuracao OBS recomendada')
        self.assertContains(response, 'Ativar live')
        self.assertContains(response, 'Live inativa')
        self.assertContains(response, 'Canal StageHub ao vivo')
        self.assertContains(response, 'live-input-123')
        self.assertContains(response, '1280x720')
        self.assertContains(response, '4000-6000 kbps')

    def test_stream_edit_page_does_not_offer_accidental_cover_clear(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video com capa',
            cover_image='streams/covers/capa-existente.jpg',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-stagehub-123',
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')

        response = self.client.get(reverse('streams:stream_update', args=[stream.id]))

        self.assertContains(response, 'Capa atual')
        self.assertNotContains(response, 'Limpar')

    @patch('streams.views.create_live_input_for_artist')
    def test_live_edit_page_can_prepare_missing_obs_data(self, create_live_input):
        create_live_input.return_value = {
            'uid': 'live-input-prepared',
            'rtmps_url': 'rtmps://live.cloudflare.com/live/',
            'stream_key': 'secret-key',
        }
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Live sem OBS',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            event_type=LiveStream.LIVE,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() + timedelta(minutes=10),
        )
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')

        response = self.client.post(reverse('streams:stream_update', args=[stream.id]), {
            'action': 'prepare_obs',
        })

        self.assertRedirects(response, reverse('streams:stream_update', args=[stream.id]))
        self.artist.refresh_from_db()
        stream.refresh_from_db()
        self.assertEqual(self.artist.cloudflare_live_input_uid, 'live-input-prepared')
        self.assertEqual(stream.cloudflare_live_input_uid, 'live-input-prepared')
        self.assertEqual(stream.cloudflare_video_uid, '')

    @patch('streams.views.create_live_input_for_artist')
    def test_live_creation_is_kept_when_obs_setup_fails(self, create_live_input):
        create_live_input.side_effect = CloudflareStreamError('Cloudflare indisponivel')
        scheduled_at = timezone.localtime(timezone.now() + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M')
        self.user.set_password('pass12345')
        self.user.save()
        self.client.login(username='artist', password='pass12345')

        response = self.client.post(reverse('streams:stream_create'), {
            'artist': self.artist.id,
            'title': 'Live guardada sem OBS',
            'description': 'Mesmo com falha OBS, a live fica criada.',
            'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            'cloudflare_stream_id': '',
            'cloudflare_playback_url': '',
            'youtube_video_id': '',
            'event_type': LiveStream.LIVE,
            'access_price': '2.00',
            'scheduled_at': scheduled_at,
            'duration_minutes': '',
            'create_upload_url': '',
        })

        stream = LiveStream.objects.get(title='Live guardada sem OBS')
        self.assertRedirects(response, reverse('streams:stream_update', args=[stream.id]))
        self.assertEqual(stream.artist, self.artist)
        self.assertEqual(stream.event_type, LiveStream.LIVE)
        self.assertEqual(stream.access_price, Decimal('2.00'))
        self.assertEqual(stream.cloudflare_upload_status, LiveStream.UPLOAD_NOT_REQUESTED)
        self.assertEqual(stream.cloudflare_video_uid, '')
        self.assertEqual(stream.cloudflare_live_input_uid, '')

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

    def test_artist_page_marks_current_live_with_red_badge(self):
        self.create_paid_stream()

        response = self.client.get(reverse('streams:artist_detail', args=[self.artist.id]))

        self.assertContains(response, 'Ao vivo')
        self.assertContains(response, 'sl-live-badge')

    def test_artist_page_shows_scheduled_inactive_paid_live(self):
        LiveStream.objects.create(
            artist=self.artist,
            title='Live futura paga',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-future',
            event_type=LiveStream.LIVE,
            access_price=LiveStream.MIN_PRICE,
            scheduled_at=timezone.now() + timedelta(hours=2),
            is_active=False,
        )

        response = self.client.get(reverse('streams:artist_detail', args=[self.artist.id]))

        self.assertContains(response, 'Live futura paga')

    def test_artist_page_hides_live_below_minimum_price_from_public(self):
        LiveStream.objects.create(
            artist=self.artist,
            title='Live barata escondida',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_live_input_uid='live-input-cheap',
            event_type=LiveStream.LIVE,
            access_price=Decimal('1.00'),
            scheduled_at=timezone.now() + timedelta(hours=2),
            is_active=False,
        )

        response = self.client.get(reverse('streams:artist_detail', args=[self.artist.id]))

        self.assertNotContains(response, 'Live barata escondida')

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

    def test_paid_event_is_archived_instead_of_deleted(self):
        stream = self.create_paid_stream()
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_test_paid_delete',
            paid=True,
        )
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/streams/{stream.id}/apagar/')
        stream.refresh_from_db()

        self.assertRedirects(response, f'/dashboard/?artist={self.artist.id}')
        self.assertFalse(stream.is_active)
        self.assertTrue(LiveStream.objects.filter(pk=stream.pk).exists())

    def test_unpaid_event_can_be_deleted(self):
        stream = self.create_paid_stream()
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/streams/{stream.id}/apagar/')

        self.assertRedirects(response, f'/dashboard/?artist={self.artist.id}')
        self.assertFalse(LiveStream.objects.filter(pk=stream.pk).exists())

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

    def test_room_explains_recorded_video_pending_upload(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video pendente na sala',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-pending-123',
            cloudflare_upload_url='https://upload.videodelivery.net/tus/abc',
            cloudflare_upload_status=LiveStream.UPLOAD_PENDING,
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now() - timedelta(minutes=5),
            is_active=True,
        )
        StreamTicketPurchase.objects.create(
            fan=self.fan,
            stream=stream,
            stripe_session_id='cs_test_pending_room',
            paid=True,
        )
        self.client.force_login(self.fan_user)

        response = self.client.get(reverse('streams:room', args=[stream.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "const cloudflareUploadStatus = 'pending'")
        self.assertContains(response, 'Este video ainda nao foi enviado')

    @patch('streams.views.prepare_cloudflare_direct_upload')
    def test_artist_can_renew_recorded_video_upload_link(self, prepare_upload):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video com link expirado',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-expired-123',
            cloudflare_upload_url='https://upload.videodelivery.net/tus/old',
            cloudflare_upload_status=LiveStream.UPLOAD_PENDING,
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now(),
        )
        self.client.force_login(self.artist_user)

        response = self.client.post(reverse('streams:stream_update', args=[stream.id]), {
            'action': 'renew_upload',
        })

        self.assertRedirects(response, reverse('streams:stream_update', args=[stream.id]))
        prepare_upload.assert_called_once_with(stream)

    def test_recorded_video_upload_uses_cloudflare_direct_upload_endpoint_without_resume(self):
        stream = LiveStream.objects.create(
            artist=self.artist,
            title='Video com upload direto',
            video_provider=LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
            cloudflare_video_uid='video-upload-123',
            cloudflare_upload_url='https://upload.cloudflarestream.com/video-upload-123',
            cloudflare_upload_status=LiveStream.UPLOAD_PENDING,
            event_type=LiveStream.RECORDED,
            access_price=Decimal('5.00'),
            scheduled_at=timezone.now(),
        )
        self.client.force_login(self.artist_user)

        response = self.client.get(reverse('streams:stream_update', args=[stream.id]))

        self.assertContains(response, 'endpoint:')
        self.assertContains(response, 'https://upload.cloudflarestream.com/video')
        self.assertContains(response, 'storeFingerprintForResuming: false')
        self.assertNotContains(response, 'uploadUrl:')
        self.assertNotContains(response, 'metadata:')


class ArtistProfilePhotoUploadTests(TestCase):
    def setUp(self):
        self.artist_user = User.objects.create_user(username='profile_artist', password='pass12345')
        self.artist = Artist.objects.create(user=self.artist_user, name='Artista Perfil')

    def test_artist_profile_photo_upload_adds_gallery_photo(self):
        self.client.force_login(self.artist_user)
        image = SimpleUploadedFile('foto.jpg', b'foto-valida', content_type='image/jpeg')

        response = self.client.post(
            f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}",
            {
                'action': 'add_photo',
                'caption': 'Foto do perfil',
                'images': image,
            },
        )

        self.assertRedirects(response, f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}")
        photo = ArtistPhoto.objects.get(artist=self.artist)
        self.assertEqual(photo.caption, 'Foto do perfil')

    def test_artist_profile_photo_form_rejects_too_many_images(self):
        images = [
            SimpleUploadedFile(f'foto-{index}.jpg', b'foto', content_type='image/jpeg')
            for index in range(11)
        ]

        form = ArtistGalleryUploadForm(files={'images': images})

        self.assertFalse(form.is_valid())
        self.assertIn('images', form.errors)

    def test_artist_profile_photo_form_rejects_large_image(self):
        image = SimpleUploadedFile(
            'foto-grande.jpg',
            b'x' * ((5 * 1024 * 1024) + 1),
            content_type='image/jpeg',
        )

        form = ArtistGalleryUploadForm(files={'images': image})

        self.assertFalse(form.is_valid())
        self.assertIn('images', form.errors)

    def test_artist_profile_page_shows_photo_upload_limits(self):
        self.client.force_login(self.artist_user)

        response = self.client.get(f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}")

        self.assertContains(response, '10 fotos por envio')
        self.assertContains(response, '5 MB por foto')
        self.assertContains(response, '30 MB no total')

    def test_artist_profile_edit_without_new_images_keeps_existing_images(self):
        self.artist.photo = 'artists/foto-existente.jpg'
        self.artist.hero_image = 'artists/heroes/capa-existente.jpg'
        self.artist.save(update_fields=['photo', 'hero_image'])
        self.client.force_login(self.artist_user)

        response = self.client.post(f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}", {
            'action': 'save_profile',
            'name': 'Artista Perfil Editado',
            'headline': '',
            'monetization_mode': self.artist.monetization_mode,
            'location': '',
            'bio': '',
            'contact_email': '',
            'contact_phone': '',
            'youtube_link': '',
            'instagram_link': '',
            'spotify_link': '',
            'website_link': '',
        })
        self.artist.refresh_from_db()

        self.assertRedirects(response, f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}")
        self.assertEqual(self.artist.photo.name, 'artists/foto-existente.jpg')
        self.assertEqual(self.artist.hero_image.name, 'artists/heroes/capa-existente.jpg')

    def test_artist_profile_page_does_not_offer_accidental_image_clear(self):
        self.artist.photo = 'artists/foto-existente.jpg'
        self.artist.hero_image = 'artists/heroes/capa-existente.jpg'
        self.artist.save(update_fields=['photo', 'hero_image'])
        self.client.force_login(self.artist_user)

        response = self.client.get(f"{reverse('streams:artist_profile_edit')}?artist={self.artist.id}")

        self.assertNotContains(response, 'Limpar')


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

    def test_admin_home_shows_pending_photo_gallery_notification(self):
        User.objects.create_user(
            username='admin_pending',
            password='pass12345',
            is_staff=True,
            is_superuser=True,
        )
        self.create_gallery(
            title='Galeria por aprovar',
            is_active=False,
            moderation_status=PhotoGallery.PENDING,
        )
        self.client.login(username='admin_pending', password='pass12345')

        response = self.client.get('/admin/')

        self.assertContains(response, 'Aprovacoes pendentes')
        self.assertContains(response, 'Abrir galerias pendentes')

    def test_submit_gallery_for_review_redirects_to_artist_dashboard(self):
        gallery = self.create_gallery(
            is_active=False,
            moderation_status=PhotoGallery.DRAFT,
        )
        PhotoGalleryImage.objects.create(gallery=gallery, image='private/foto-secreta.jpg')
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/{gallery.id}/editar/', {
            'action': 'submit_review',
        })
        gallery.refresh_from_db()

        self.assertRedirects(response, f'/dashboard/?artist={self.artist.id}')
        self.assertEqual(gallery.moderation_status, PhotoGallery.PENDING)
        self.assertFalse(gallery.is_active)

    def test_approved_gallery_edit_page_does_not_show_submit_review_button(self):
        gallery = self.create_gallery()
        self.client.force_login(self.artist_user)

        response = self.client.get(f'/dashboard/galerias/{gallery.id}/editar/')

        self.assertContains(response, 'Galeria aprovada')
        self.assertNotContains(response, 'Enviar para validacao')

    def test_changing_approved_gallery_moves_it_back_to_draft(self):
        gallery = self.create_gallery()
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/{gallery.id}/editar/', {
            'action': 'save_gallery',
            'title': gallery.title,
            'description': 'Descricao alterada',
            'access_price': '5.00',
            'is_active': 'on',
        })
        gallery.refresh_from_db()

        self.assertRedirects(response, f'/dashboard/galerias/{gallery.id}/editar/')
        self.assertEqual(gallery.moderation_status, PhotoGallery.DRAFT)
        self.assertFalse(gallery.is_active)

    def test_gallery_edit_without_new_cover_keeps_existing_cover(self):
        gallery = self.create_gallery(public_cover='photo_galleries/covers/capa-existente.jpg')
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/{gallery.id}/editar/', {
            'action': 'save_gallery',
            'title': 'Galeria renomeada',
            'description': gallery.description,
            'access_price': '5.00',
            'is_active': 'on',
        })
        gallery.refresh_from_db()

        self.assertRedirects(response, f'/dashboard/galerias/{gallery.id}/editar/')
        self.assertEqual(gallery.public_cover.name, 'photo_galleries/covers/capa-existente.jpg')

    def test_gallery_edit_page_does_not_offer_accidental_cover_clear(self):
        gallery = self.create_gallery(public_cover='photo_galleries/covers/capa-existente.jpg')
        self.client.force_login(self.artist_user)

        response = self.client.get(f'/dashboard/galerias/{gallery.id}/editar/')

        self.assertContains(response, 'Capa publica')
        self.assertNotContains(response, 'Limpar')

    def test_deleting_gallery_removes_it_from_public_pages(self):
        gallery = self.create_gallery(title='Galeria para apagar')
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/{gallery.id}/apagar/')

        self.assertRedirects(response, f'/dashboard/?artist={self.artist.id}')
        self.assertFalse(PhotoGallery.objects.filter(pk=gallery.pk).exists())
        response = self.client.get(reverse('streams:home'))
        self.assertNotContains(response, 'Galeria para apagar')

    def test_paid_gallery_is_retired_instead_of_deleted(self):
        gallery = self.create_gallery(title='Galeria comprada')
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            amount=Decimal('5.00'),
            paid=True,
        )
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/{gallery.id}/apagar/')
        gallery.refresh_from_db()

        self.assertRedirects(response, f'/dashboard/?artist={self.artist.id}')
        self.assertFalse(gallery.is_active)
        self.assertTrue(PhotoGallery.objects.filter(pk=gallery.pk).exists())

    def test_paid_gallery_image_cannot_be_removed(self):
        gallery = self.create_gallery()
        image = PhotoGalleryImage.objects.create(gallery=gallery, image='private/foto-secreta.jpg')
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            amount=Decimal('5.00'),
            paid=True,
        )
        self.client.force_login(self.artist_user)

        response = self.client.post(f'/dashboard/galerias/fotos/{image.id}/remover/')

        self.assertRedirects(response, f'/dashboard/galerias/{gallery.id}/editar/')
        self.assertTrue(PhotoGalleryImage.objects.filter(pk=image.pk).exists())

    def test_purchased_retired_gallery_remains_visible_to_buyer_home(self):
        gallery = self.create_gallery(title='Galeria comprada retirada', is_active=False)
        PhotoGalleryPurchase.objects.create(
            fan=self.fan,
            gallery=gallery,
            amount=Decimal('5.00'),
            paid=True,
        )
        self.client.force_login(self.fan_user)

        response = self.client.get(reverse('streams:home'))

        self.assertContains(response, 'Galeria comprada retirada')

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
        self.assertContains(response, 'Foto protegida')
        self.assertContains(response, 'Disponivel apos compra')
        self.assertContains(response, 'Fotos privadas')

    def test_sensitive_gallery_requires_age_confirmation_before_public_view(self):
        gallery = self.create_gallery(is_sensitive=True)

        response = self.client.get(f'/galerias/{gallery.id}/')

        self.assertContains(response, 'Confirma antes de continuar')
        self.assertContains(response, 'Tenho 18+ e quero continuar')
        self.assertNotContains(response, 'covers/capa.jpg')

    def test_sensitive_gallery_confirmation_allows_public_view(self):
        gallery = self.create_gallery(is_sensitive=True)

        response = self.client.post(
            f'/galerias/{gallery.id}/',
            {'action': 'confirm_sensitive_content'},
        )

        self.assertRedirects(response, f'/galerias/{gallery.id}/')
        response = self.client.get(f'/galerias/{gallery.id}/')
        self.assertContains(response, 'Galeria exclusiva')
        self.assertContains(response, 'covers/capa.jpg')

    def test_artist_manager_can_view_sensitive_gallery_without_age_gate(self):
        gallery = self.create_gallery(is_sensitive=True)
        self.client.force_login(self.artist_user)

        response = self.client.get(f'/galerias/{gallery.id}/')

        self.assertContains(response, 'Galeria exclusiva')
        self.assertNotContains(response, 'Confirma antes de continuar')

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
        self.assertContains(response, 'data-gallery-lightbox-trigger')
        self.assertContains(response, 'gallery-lightbox')


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
