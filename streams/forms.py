from django import forms
from urllib.parse import parse_qs, urlparse

from .models import LiveStream


class LiveStreamForm(forms.ModelForm):
    cover_image = forms.ImageField(
        label='Foto de capa do stream',
        required=False,
        help_text='Recomendado: imagem horizontal 16:9, pelo menos 1280x720 px, em JPG ou PNG.',
    )
    scheduled_at = forms.DateTimeField(
        label='Data e hora',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )
    youtube_video_id = forms.CharField(
        label='ID ou link do video YouTube',
        max_length=200,
        help_text='Usa uma live/video publico ou nao listado, com incorporacao permitida no YouTube Studio. Videos privados, com restricao de idade, copyright ou incorporacao bloqueada mostram "ver no YouTube".',
    )

    class Meta:
        model = LiveStream
        fields = ('title', 'cover_image', 'youtube_video_id', 'access_price', 'scheduled_at', 'is_active')
        labels = {
            'title': 'Titulo',
            'access_price': 'Preco do bilhete',
            'is_active': 'Stream ativo',
        }

    def clean_youtube_video_id(self):
        value = self.cleaned_data['youtube_video_id'].strip()
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
