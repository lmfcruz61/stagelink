from django import forms
from urllib.parse import parse_qs, urlparse

from .models import LiveStream


class LiveStreamForm(forms.ModelForm):
    cover_image = forms.ImageField(
        label='Foto de capa do espetaculo',
        required=False,
        help_text='Recomendado: imagem horizontal 16:9, pelo menos 1280x720 px, em JPG ou PNG.',
    )
    scheduled_at = forms.DateTimeField(
        label='Data e hora',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    cloudflare_video_uid = forms.CharField(
        label='Cloudflare Video UID',
        max_length=120,
        required=False,
        help_text='Para video gravado, estreia ou replay. Cola o UID de Cloudflare Stream > Videos.',
    )
    cloudflare_live_input_uid = forms.CharField(
        label='Cloudflare Live Input UID',
        max_length=120,
        required=False,
        help_text='Para evento ao vivo. Cola o Live Input ID de Cloudflare Stream > Live inputs.',
    )
    cloudflare_playback_url = forms.URLField(
        label='URL de embed/playback Cloudflare',
        required=False,
        help_text='Opcional. Usa se quiseres colar diretamente a URL do separador Embed da Cloudflare.',
    )
    youtube_video_id = forms.CharField(
        label='ID ou link do video YouTube legado',
        max_length=200,
        required=False,
        help_text='Apenas para eventos antigos/testes. Nao usar para eventos pagos.',
    )

    class Meta:
        model = LiveStream
        fields = (
            'title',
            'description',
            'cover_image',
            'video_provider',
            'cloudflare_video_uid',
            'cloudflare_live_input_uid',
            'cloudflare_playback_url',
            'youtube_video_id',
            'event_type',
            'access_price',
            'scheduled_at',
            'is_active',
        )
        labels = {
            'title': 'Titulo',
            'description': 'Descricao publica',
            'video_provider': 'Plataforma de video',
            'event_type': 'Tipo de conteudo',
            'access_price': 'Preco do bilhete',
            'is_active': 'Espetaculo ativo',
        }

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('video_provider')
        event_type = cleaned_data.get('event_type')
        cloudflare_video_uid = (cleaned_data.get('cloudflare_video_uid') or '').strip()
        cloudflare_live_input_uid = (cleaned_data.get('cloudflare_live_input_uid') or '').strip()
        cloudflare_playback_url = (cleaned_data.get('cloudflare_playback_url') or '').strip()
        youtube_video_id = (cleaned_data.get('youtube_video_id') or '').strip()

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE:
            if event_type == LiveStream.LIVE and not cloudflare_live_input_uid and not cloudflare_playback_url:
                self.add_error(
                    'cloudflare_live_input_uid',
                    'Para evento ao vivo, indica o Live Input UID ou uma URL de embed Cloudflare.',
                )
            if event_type != LiveStream.LIVE and not cloudflare_video_uid and not cloudflare_playback_url:
                self.add_error(
                    'cloudflare_video_uid',
                    'Para video gravado, estreia ou replay, indica o Video UID ou uma URL de embed Cloudflare.',
                )

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE_WEBRTC and not cloudflare_playback_url:
            self.add_error(
                'cloudflare_playback_url',
                'Para WebRTC, cola a URL de playback WHEP/Embed da Cloudflare. Este modo sera afinado no proximo passo.',
            )

        if provider == LiveStream.VIDEO_PROVIDER_YOUTUBE and not youtube_video_id:
            self.add_error('youtube_video_id', 'Indica o ID/link do YouTube para usar o modo legado.')

        return cleaned_data

    def clean_youtube_video_id(self):
        value = (self.cleaned_data.get('youtube_video_id') or '').strip()
        if not value:
            return ''
        parsed = urlparse(value)
        video_id = value
        if parsed.netloc:
            if parsed.hostname and 'youtu.be' in parsed.hostname:
                video_id = parsed.path.strip('/').split('/')[0]
            else:
                query_id = parse_qs(parsed.query).get('v')
                if query_id:
                    video_id = query_id[0]
                else:
                    parts = [part for part in parsed.path.split('/') if part]
                    for marker in ('embed', 'live', 'shorts'):
                        if marker in parts:
                            index = parts.index(marker)
                            if len(parts) > index + 1:
                                video_id = parts[index + 1]
                                break

        if len(video_id) < 10:
            raise forms.ValidationError('Confirma o ID/link do YouTube. Um ID normal tem cerca de 11 caracteres.')
        return video_id
