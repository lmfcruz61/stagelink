from django import forms
from urllib.parse import parse_qs, urlparse

from .models import LiveStream


class LiveStreamForm(forms.ModelForm):
    cover_image = forms.ImageField(
        label='Foto de capa do evento',
        required=False,
        help_text='Recomendado: imagem horizontal 16:9, pelo menos 1280x720 px, em JPG ou PNG.',
    )
    scheduled_at = forms.DateTimeField(
        label='Data e hora',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
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
    create_upload_url = forms.BooleanField(
        label='Preparar upload de video para Cloudflare',
        required=False,
        help_text='Para video gravado/replay: cria um link seguro para enviar o ficheiro direto para Cloudflare.',
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
        self.artist = kwargs.pop('artist', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['create_upload_url'].initial = self.instance.has_pending_direct_upload
        elif self.initial.get('event_type') in {LiveStream.RECORDED, LiveStream.REPLAY}:
            self.fields['create_upload_url'].initial = True
        if self.instance and self.instance.pk:
            event_type = self.instance.event_type
            if event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                self.fields['cloudflare_stream_id'].initial = self.instance.cloudflare_live_input_uid
            else:
                self.fields['cloudflare_stream_id'].initial = self.instance.cloudflare_video_uid
        elif self.artist and self.artist.cloudflare_live_input_uid:
            self.fields['cloudflare_stream_id'].initial = self.artist.cloudflare_live_input_uid

    def should_validate_video_rules(self):
        if not self.instance or not self.instance.pk:
            return True
        video_fields = {
            'access_price',
            'cloudflare_playback_url',
            'cloudflare_stream_id',
            'create_upload_url',
            'event_type',
            'video_provider',
            'youtube_video_id',
        }
        return bool(video_fields.intersection(self.changed_data))

    def clean(self):
        cleaned_data = super().clean()
        provider = cleaned_data.get('video_provider')
        event_type = cleaned_data.get('event_type')
        cloudflare_stream_id = (cleaned_data.get('cloudflare_stream_id') or '').strip()
        cloudflare_playback_url = (cleaned_data.get('cloudflare_playback_url') or '').strip()
        youtube_video_id = (cleaned_data.get('youtube_video_id') or '').strip()
        create_upload_url = cleaned_data.get('create_upload_url')
        duration_minutes = cleaned_data.get('duration_minutes')
        if cloudflare_stream_id.lower().startswith(('rtmp://', 'rtmps://')):
            self.add_error(
                'cloudflare_stream_id',
                'Este campo deve ter o Live Input ID/Video UID, nao o RTMPS URL. O RTMPS URL vai apenas no OBS.',
            )
        else:
            normalized_cloudflare_stream_id = LiveStream.extract_cloudflare_identifier(cloudflare_stream_id)
            if normalized_cloudflare_stream_id:
                cloudflare_stream_id = normalized_cloudflare_stream_id
                cleaned_data['cloudflare_stream_id'] = cloudflare_stream_id
        if (
            not cloudflare_stream_id
            and self.artist
            and event_type in {LiveStream.LIVE, LiveStream.PREMIERE}
            and self.artist.cloudflare_live_input_uid
        ):
            cloudflare_stream_id = self.artist.cloudflare_live_input_uid
            cleaned_data['cloudflare_stream_id'] = cloudflare_stream_id

        if not self.should_validate_video_rules():
            return cleaned_data

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE:
            accepts_direct_upload = event_type in {LiveStream.RECORDED, LiveStream.REPLAY} and create_upload_url
            if not cloudflare_stream_id and not cloudflare_playback_url and not accepts_direct_upload:
                self.add_error(
                    'cloudflare_stream_id',
                    'Indica o ID do stream Cloudflare, uma URL de embed Cloudflare ou prepara um upload direto.',
                )

        access_price = cleaned_data.get('access_price')
        if access_price is not None:
            if access_price <= 0:
                if provider != LiveStream.VIDEO_PROVIDER_YOUTUBE:
                    self.add_error(
                        'video_provider',
                        'Eventos gratuitos devem usar YouTube legado. Cloudflare fica reservado para eventos pagos.',
                    )
                if event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                    self.add_error(
                        'event_type',
                        'Eventos gratuitos devem ser video gravado ou replay no YouTube.',
                    )
            elif provider == LiveStream.VIDEO_PROVIDER_YOUTUBE:
                self.add_error(
                    'video_provider',
                    'Eventos pagos devem usar Cloudflare Stream.',
                )

        if provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE_WEBRTC and not cloudflare_playback_url:
            self.add_error(
                'cloudflare_playback_url',
                'Para WebRTC, cola a URL de playback WHEP/Embed da Cloudflare. Este modo sera afinado no proximo passo.',
            )

        if (
            provider == LiveStream.VIDEO_PROVIDER_CLOUDFLARE
            and event_type in {LiveStream.RECORDED, LiveStream.REPLAY}
            and duration_minutes
            and duration_minutes > 60
        ):
            self.add_error(
                'duration_minutes',
                'Videos gravados/replays na StageHub nao podem ultrapassar 60 minutos.',
            )

        if provider == LiveStream.VIDEO_PROVIDER_YOUTUBE and not youtube_video_id:
            self.add_error('youtube_video_id', 'Indica o ID/link do YouTube para usar o modo legado.')

        return cleaned_data

    def save(self, commit=True):
        live_stream = super().save(commit=False)
        cloudflare_stream_id = LiveStream.extract_cloudflare_identifier(self.cleaned_data.get('cloudflare_stream_id'))
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
