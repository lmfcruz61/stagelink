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
    cloudflare_stream_id = forms.CharField(
        label='ID do stream Cloudflare',
        max_length=120,
        required=False,
        help_text='Para eventos ao vivo. Cola o Live Input ID de Cloudflare Stream > Live Inputs.',
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
            'cloudflare_playback_url',
            'youtube_video_id',
            'event_type',
            'access_price',
            'scheduled_at',
            'duration_minutes',
        )
        labels = {
            'title': 'Titulo',
            'description': 'Descricao publica',
            'video_provider': 'Plataforma de video',
            'event_type': 'Tipo de conteudo',
            'access_price': 'Preco do bilhete',
            'duration_minutes': 'Duração estimada',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            event_type = self.instance.event_type
            if event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                self.fields['cloudflare_stream_id'].initial = self.instance.cloudflare_live_input_uid
            else:
                self.fields['cloudflare_stream_id'].initial = self.instance.cloudflare_video_uid

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('video_provider')
        event_type = cleaned_data.get('event_type')
        cloudflare_stream_id = (cleaned_data.get('cloudflare_stream_id') or '').strip()
        cloudflare_playback_url = (cleaned_data.get('cloudflare_playback_url') or '').strip()
        youtube_video_id = (cleaned_data.get('youtube_video_id') or '').strip()

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE:
            if not cloudflare_stream_id and not cloudflare_playback_url:
                self.add_error(
                    'cloudflare_stream_id',
                    'Indica o ID do stream Cloudflare ou uma URL de embed Cloudflare.',
                )

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE_WEBRTC and not cloudflare_playback_url:
            self.add_error(
                'cloudflare_playback_url',
                'Para WebRTC, cola a URL de playback WHEP/Embed da Cloudflare. Este modo sera afinado no proximo passo.',
            )

        if provider == LiveStream.VIDEO_PROVIDER_YOUTUBE and not youtube_video_id:
            self.add_error('youtube_video_id', 'Indica o ID/link do YouTube para usar o modo legado.')

        return cleaned_data

    def save(self, commit=True):
        live_stream = super().save(commit=False)
        cloudflare_stream_id = (self.cleaned_data.get('cloudflare_stream_id') or '').strip()
        if live_stream.event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
            live_stream.cloudflare_live_input_uid = cloudflare_stream_id
            live_stream.cloudflare_video_uid = ''
        else:
            live_stream.cloudflare_video_uid = cloudflare_stream_id
            live_stream.cloudflare_live_input_uid = ''
        if commit:
            live_stream.save()
            self.save_m2m()
        return live_stream

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
