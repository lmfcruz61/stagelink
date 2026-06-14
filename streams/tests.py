from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Artist

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
