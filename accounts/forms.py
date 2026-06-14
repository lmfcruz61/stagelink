from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import Artist, ArtistPhoto, Fan, NewsletterSubscriber, Organization, OrganizationMember, Profile


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES, label='Tipo de conta')
    display_name = forms.CharField(max_length=120, label='Nome público')
    organization_name = forms.CharField(
        max_length=140,
        required=False,
        label='Nome da equipa/empresa',
        help_text='Obrigatorio apenas para managers, agencias, produtoras ou empresas.',
    )
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'display_name', 'role', 'organization_name', 'password1', 'password2')

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        organization_name = cleaned_data.get('organization_name', '').strip()
        if role == Profile.MANAGER and not organization_name:
            self.add_error('organization_name', 'Indica o nome da equipa ou empresa.')
        return cleaned_data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            role = self.cleaned_data['role']
            display_name = self.cleaned_data['display_name']
            Profile.objects.create(user=user, role=role)
            if role == Profile.MUSICIAN:
                Artist.objects.create(user=user, name=display_name)
            elif role == Profile.MANAGER:
                organization = Organization.objects.create(
                    name=self.cleaned_data['organization_name'],
                    created_by=user,
                )
                OrganizationMember.objects.create(
                    organization=organization,
                    user=user,
                    role=OrganizationMember.OWNER,
                )
            else:
                Fan.objects.create(user=user, display_name=display_name)
        return user


class ArtistProfileForm(forms.ModelForm):
    photo = forms.ImageField(
        label='Foto principal',
        required=False,
        help_text='Recomendado: imagem quadrada, pelo menos 800x800 px, em JPG ou PNG.',
    )
    hero_image = forms.ImageField(
        label='Imagem de capa da pagina',
        required=False,
        help_text='Recomendado: imagem horizontal 16:9, pelo menos 1600x900 px.',
    )

    class Meta:
        model = Artist
        fields = (
            'name',
            'headline',
            'location',
            'bio',
            'photo',
            'hero_image',
            'youtube_link',
            'instagram_link',
            'spotify_link',
            'website_link',
            'cloudflare_live_input_uid',
        )
        labels = {
            'name': 'Nome artistico',
            'headline': 'Frase de destaque',
            'location': 'Cidade / pais',
            'bio': 'Bio',
            'photo': 'Foto principal',
            'hero_image': 'Imagem de capa da pagina',
            'youtube_link': 'Link YouTube',
            'instagram_link': 'Link Instagram',
            'spotify_link': 'Link Spotify',
            'website_link': 'Site oficial',
            'cloudflare_live_input_uid': 'Live Input UID Cloudflare',
        }
        help_texts = {
            'cloudflare_live_input_uid': 'Opcional. A StageHub cria um Live Input por artista na conta Cloudflare da plataforma e reutiliza-o nos eventos pagos ao vivo.',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 6}),
        }


class ManagedArtistForm(ArtistProfileForm):
    class Meta(ArtistProfileForm.Meta):
        fields = ArtistProfileForm.Meta.fields


class OrganizationForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ('name', 'description', 'website', 'logo')
        labels = {
            'name': 'Nome da equipa/empresa',
            'description': 'Descricao',
            'website': 'Site',
            'logo': 'Logotipo',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class OrganizationMemberForm(forms.ModelForm):
    username = forms.CharField(label='Username do utilizador')

    class Meta:
        model = OrganizationMember
        fields = ('username', 'role')
        labels = {
            'role': 'Permissao',
        }


class FanProfileForm(forms.ModelForm):
    photo = forms.ImageField(
        label='Foto de perfil',
        required=False,
        help_text='Recomendado: imagem quadrada, pelo menos 400x400 px, em JPG ou PNG.',
    )

    class Meta:
        model = Fan
        fields = ('display_name', 'photo')
        labels = {
            'display_name': 'Nome publico',
            'photo': 'Foto de perfil',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 5}),
        }


class ArtistPhotoForm(forms.ModelForm):
    image = forms.ImageField(
        label='Foto da galeria',
        help_text='Recomendado: pelo menos 1200 px de largura, em JPG ou PNG.',
    )

    class Meta:
        model = ArtistPhoto
        fields = ('image', 'caption')
        labels = {
            'image': 'Foto da galeria',
            'caption': 'Legenda',
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(file, initial) for file in data]
        return single_file_clean(data, initial)


class ArtistGalleryUploadForm(forms.Form):
    images = MultipleFileField(
        label='Fotos para a galeria',
        help_text='Podes escolher uma ou varias fotos. Recomendado: pelo menos 1200 px de largura, em JPG ou PNG.',
    )
    caption = forms.CharField(
        label='Legenda comum',
        max_length=140,
        required=False,
        help_text='Opcional. Sera aplicada a todas as fotos deste envio.',
    )


class NewsletterSubscriberForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscriber
        fields = ('name', 'email', 'interest_type')
        labels = {
            'name': 'Nome',
            'email': 'Email',
            'interest_type': 'Tipo de interesse',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'O teu nome'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if NewsletterSubscriber.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Este email ja esta subscrito na newsletter.')
        return email
